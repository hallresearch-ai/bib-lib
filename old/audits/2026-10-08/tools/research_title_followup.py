"""Read-only PDF/page/registry research for pending bibliography titles.

Writes candidate evidence, never modifies the workbook. Corrections require a
separate evidence review. Uses pdftotext for the publication's opening pages.
"""
import concurrent.futures
import difflib
import hashlib
import html
from html.parser import HTMLParser
import json
import re
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import quote, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from verify_titles import comparison_title
from pylatexenc.latex2text import LatexNodes2Text

BASE = Path('bib_files/normalized-2026-10-08')
CACHE = Path('/tmp/bib-title-followup-cache')
CACHE.mkdir(exist_ok=True)
REGISTRY = threading.Semaphore(2)
FETCH = threading.Semaphore(6)
REGISTRY_PACING = threading.Lock()
LAST_REGISTRY_REQUEST = 0.0


def plain(value):
    return ' '.join(LatexNodes2Text().latex_to_text(html.unescape(value or '')).split())


def family(row):
    author = plain(row.get('author'))
    if author.startswith('{') or not author: return ''
    return author.split(' and ')[0].split(',')[0].strip()


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.headings = []
        self.meta = []
        self.links = []
        self.alltext = []
        self.capture = None
        self.data = []
        self.jsonld = False
        self.jsontext = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta':
            name = (attrs.get('name') or attrs.get('property') or '').lower()
            if name in {'citation_title','dc.title','dcterms.title','og:title','twitter:title','citation_author','citation_date','citation_publication_date','citation_pdf_url'}:
                self.meta.append((name,attrs.get('content','')))
        if tag in {'h1','h2','h3','title'}:
            self.capture = tag
            self.data = []
        if tag == 'script' and attrs.get('type') == 'application/ld+json':
            self.jsonld = True
            self.jsontext = []
        if tag == 'a' and attrs.get('href'):
            self.links.append(attrs['href'])

    def handle_data(self, data):
        if self.capture: self.data.append(data)
        if self.jsonld: self.jsontext.append(data)
        elif data.strip(): self.alltext.append(data.strip())

    def handle_endtag(self, tag):
        if self.capture == tag:
            text = ' '.join(''.join(self.data).split())
            if text: self.headings.append((tag,text))
            self.capture = None
        if tag == 'script' and self.jsonld:
            try:
                obj=json.loads(''.join(self.jsontext))
                def walk(v):
                    if isinstance(v,dict):
                        for k,x in v.items():
                            if k in {'headline','name'} and isinstance(x,str): self.headings.append(('JSON-LD '+k,x))
                            if isinstance(x,(list,dict)):walk(x)
                    elif isinstance(v,list):
                        for x in v:walk(x)
                walk(obj)
            except (ValueError,TypeError): pass
            self.jsonld = False


def fetch(url):
    with FETCH:
        request=Request(url,headers={'User-Agent':'bib-lib-title-audit/1.0'})
        with urlopen(request,timeout=15) as response:
            data=response.read(25_000_000)
            return response.url,response.headers.get('Content-Type',''),data


def title_variants(title):
    # Descriptive/category prefixes and separately supplied standard identifiers.
    values=[title]
    values.append(re.sub(r'^(?:survey article|research article|white paper)\s*:\s*','',title,flags=re.I))
    values.append(re.sub(r'^\{?ASTM\}?\s+\{?E\d+-\d+\}?\s*[-—:]\s*','',title,flags=re.I))
    return list(dict.fromkeys(values))


def harmless_match(current, external):
    variants=title_variants(current)
    choices=title_variants(external)
    # Accept site branding only at an explicit heading/page-title separator.
    for separator in (' | ',' · ',' - '):
        if separator in external: choices.append(external.split(separator,1)[0])
    return any(comparison_title(v)==comparison_title(c) for v in variants for c in choices)


def record_page(url,row,result,follow_pdf=True):
    final,content_type,data=fetch(url)
    result['resources'].append({'requested_url':url,'source_url':final,'content_type':content_type,'sha256':hashlib.sha256(data).hexdigest()})
    if data.startswith(b'%PDF') or 'application/pdf' in content_type:
        stem=hashlib.sha256(final.encode()).hexdigest()[:20]
        pdf=CACHE/(stem+'.pdf');pdf.write_bytes(data)
        out=subprocess.run(['pdftotext','-f','1','-l','2',str(pdf),'-'],capture_output=True,text=True,timeout=25)
        text=out.stdout
        (CACHE/(stem+'.txt')).write_text(text)
        first=text.split('\f')[0]
        # Exclude abstract/body/references from title matching.
        header=re.split(r'\n\s*(?:abstract|introduction|1\.?\s+introduction|references)\b',first,flags=re.I)[0]
        header='\n'.join(header.splitlines()[:100])[:8000]
        expected=comparison_title(row['title'])
        match=any(comparison_title(v) in comparison_title(header) for v in title_variants(row['title']) if len(comparison_title(v))>=16)
        author=family(row)
        author_match=bool(author and comparison_title(author) in comparison_title(first))
        result['pdf_evidence'].append({'source_url':final,'title_area':header,'normalized_title_found':match,'first_author_found':author_match,'first_author':author,'cache_text':str(CACHE/(stem+'.txt'))})
        return
    if 'html' not in content_type: return
    page=Page();page.feed(data.decode('utf-8',errors='replace'))
    author=family(row)
    author_match=bool(author and comparison_title(author) in comparison_title(' '.join(page.alltext)))
    for kind,title in page.meta+page.headings:
        if 'title' in kind or kind in {'h1','h2','h3'} or kind.startswith('JSON-LD'):
            result['page_titles'].append({'source_url':final,'kind':kind,'title':title,'harmless_match':harmless_match(row['title'],title),'first_author_found':author_match})
    if follow_pdf:
        candidates=[urljoin(final,v) for k,v in page.meta if k=='citation_pdf_url']
        candidates.extend(urljoin(final,l) for l in page.links if re.search(r'\.pdf(?:$|[?#])',l,re.I))
        for candidate in list(dict.fromkeys(candidates))[:2]:
            try:record_page(candidate,row,result,follow_pdf=False)
            except Exception as e:result['errors'].append({'source_url':candidate,'error':str(e)[:200]})


def crossref(row,result):
    global LAST_REGISTRY_REQUEST
    query=plain(row['title'])+' '+family(row)+' '+(row.get('year') or '')
    address='https://api.crossref.org/works?'+urlencode({'query.bibliographic':query,'rows':5})
    with REGISTRY:
        with REGISTRY_PACING:
            time.sleep(max(0.0, 0.8-(time.monotonic()-LAST_REGISTRY_REQUEST)))
            LAST_REGISTRY_REQUEST=time.monotonic()
        with urlopen(Request(address,headers={'User-Agent':'bib-lib-title-audit/1.0'}),timeout=18) as response:
            items=json.loads(response.read())['message']['items']
    expected=comparison_title(row['title']);first=family(row)
    for item in items:
        authors=[plain(a.get('family','')) for a in item.get('author',[])]
        author_match=any(comparison_title(first)==comparison_title(a) for a in authors) if first else False
        dates={}
        for f in ('published','published-print','published-online','issued'):
            value=item.get(f,{}).get('date-parts',[])
            if value and value[0]:dates[f]=value[0][0]
        year=row.get('year') or ''
        year_match=any(str(y)==year for y in dates.values())
        for title in item.get('title',[]):
            title=html.unescape(re.sub('<[^>]+>','',title))
            score=difflib.SequenceMatcher(None,expected,comparison_title(title)).ratio()
            if score<0.55:continue
            result['registry_candidates'].append({'source_url':'https://api.crossref.org/works/'+quote(item['DOI'],safe=''),'record_url':item.get('URL'),'doi':item['DOI'],'title':title,'authors':authors,'dates':dates,'venue':item.get('container-title',[]),'score':round(score,3),'first_author_found':author_match,'year_matches':year_match,'harmless_match':harmless_match(row['title'],title)})


def research(row,existing):
    key=row['citation_key']
    result={'citation_key':key,'workbook_title':row['title'],'resources':[],'page_titles':[],'pdf_evidence':[],'registry_candidates':[],'errors':[]}
    # Existing primary-page titles remain usable, with current policy comparison.
    for ev in existing.get(key,{}).get('evidence',[]):
        result['page_titles'].append({'source_url':ev['source_url'],'kind':ev['kind'],'title':ev['title'],'harmless_match':harmless_match(row['title'],ev['title']),'prior_evidence':True})
    url=row.get('url') or ''
    if url:
        # Remove LaTeX URL escaping and PDF-viewer suffixes before fetching.
        url=url.replace('\\_','_').replace('\\#','#').replace('\\&','&')
        if '.pdf/web/viewer.html' in url:url=url.split('.pdf/web/viewer.html')[0]+'.pdf'
        urls=[url]
        parts=urlsplit(url)
        if parts.scheme=='http':urls.insert(0,urlunsplit(('https',parts.netloc,parts.path,parts.query,parts.fragment)))
        if 'aclanthology.org' in parts.netloc and parts.path.endswith('.pdf'):
            urls.insert(0,url.replace('.pdf','/'))
        if 'neurips.cc' in parts.netloc or 'nips.cc' in parts.netloc:
            urls=[u.replace('http://','https://') for u in urls]
        for address in list(dict.fromkeys(urls)):
            try:
                record_page(address,row,result)
                if result['pdf_evidence'] or any(t['harmless_match'] for t in result['page_titles']):break
            except Exception as e:result['errors'].append({'source_url':address,'error':str(e)[:200]})
    try:crossref(row,result)
    except Exception as e:result['errors'].append({'source_url':'Crossref bibliographic title/author/year search','error':str(e)[:200]})
    return result


def main():
    rows=json.loads(Path('/tmp/bib-title-followup-input.json').read_text())
    old={r['citation_key']:r for r in map(json.loads,(BASE/'title-verification.jsonl').read_text().splitlines())}
    output=BASE/'title-followup-evidence.jsonl'
    completed=set()
    if output.exists():completed={json.loads(line)['citation_key'] for line in output.read_text().splitlines()}
    rows=[r for r in rows if r['citation_key'] not in completed]
    n=len(completed)
    with output.open('a',encoding='utf-8') as f,concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for future in concurrent.futures.as_completed([pool.submit(research,r,old) for r in rows]):
            result=future.result();f.write(json.dumps(result,ensure_ascii=False)+'\n');f.flush();n+=1
            if n%20==0:print(f'Researched {n}/254 pending titles',flush=True)
    print(f'Finished {n} title research records',flush=True)


if __name__=='__main__':main()
