"""Collect publication-specific author evidence without modifying the workbook."""
import concurrent.futures,hashlib,html,json,re,subprocess,threading,time,unicodedata
from pathlib import Path
from urllib.parse import quote,urljoin
from urllib.request import Request,urlopen
from html.parser import HTMLParser
from verify_titles import comparison_title
from research_title_followup import harmless_match,plain
BASE=Path('bib_files/normalized-2026-10-08');CACHE=Path('/tmp/bib-author-cache');CACHE.mkdir(exist_ok=True)
PACE=threading.Lock();LAST=0
class Authors(HTMLParser):
 def __init__(self):super().__init__();self.authors=[];self.titles=[];self.pdf=[];self.jsonld=False;self.jd=[]
 def handle_starttag(self,t,attrs):
  a=dict(attrs)
  if t=='meta':
   k=(a.get('name') or a.get('property') or '').lower();v=a.get('content','')
   if k in {'citation_author','dc.creator','dcterms.creator'} and v:self.authors.append(v)
   if k in {'citation_title','dc.title','dcterms.title','og:title'} and v:self.titles.append(v)
   if k=='citation_pdf_url' and v:self.pdf.append(v)
  if t=='script' and a.get('type')=='application/ld+json':self.jsonld=True;self.jd=[]
 def handle_data(self,v):
  if self.jsonld:self.jd.append(v)
 def handle_endtag(self,t):
  if t=='script' and self.jsonld:
   try:
    obj=json.loads(''.join(self.jd))
    def walk(o):
     if isinstance(o,dict):
      if o.get('@type') in {'ScholarlyArticle','Article','NewsArticle','BlogPosting','Book','Report'}:
       for k in ['headline','name']:
        if isinstance(o.get(k),str):self.titles.append(o[k])
       v=o.get('author',[]);v=v if isinstance(v,list) else [v]
       for a in v:
        if isinstance(a,str):self.authors.append(a)
        elif isinstance(a,dict) and a.get('name'):self.authors.append(a['name'])
      for v in o.values():
       if isinstance(v,(dict,list)):walk(v)
     elif isinstance(o,list):
      for v in o:walk(v)
    walk(obj)
   except (ValueError,TypeError):pass
   self.jsonld=False

def download(u):
 global LAST
 stem=hashlib.sha256(u.encode()).hexdigest();raw=CACHE/(stem+'.data');info=CACHE/(stem+'.json')
 if raw.exists() and info.exists():return json.loads(info.read_text()),raw.read_bytes()
 if 'api.crossref.org' in u:
  with PACE:
   time.sleep(max(0,.55-(time.monotonic()-LAST)));LAST=time.monotonic()
 req=Request(u,headers={'User-Agent':'bib-lib-author-audit/1.0','Accept':'application/json' if 'api.crossref.org' in u else '*/*'})
 with urlopen(req,timeout=13) as f:
  data=f.read(25_000_000);meta={'source_url':f.url,'content_type':f.headers.get('Content-Type',''),'sha256':hashlib.sha256(data).hexdigest()}
 raw.write_bytes(data);info.write_text(json.dumps(meta));return meta,data

def match_title(row,t):return harmless_match(row['title'],t)
def collect(u,row,out,follow=True):
 meta,data=download(u);out['resources'].append({'requested_url':u,**meta});url=meta['source_url']
 if 'api.crossref.org' in u:
  rec=json.loads(data)['message'];titles=rec.get('title',[]);titles+= [t+': '+s for t in rec.get('title',[]) for s in rec.get('subtitle',[])]
  identity=any(match_title(row,t) for t in titles)
  if not identity:
   known=[z.get('title','') for z in TITLE.get(row['citation_key'],{}).get('evidence',[]) if z.get('matches') and 'api.crossref.org' in z.get('source_url','') and z['source_url']==u]
   identity=any(comparison_title(t)==comparison_title(k) for t in titles for k in known)
  out['author_lists'].append({'source_url':url,'kind':'Publisher-deposited DOI author list','titles':titles,'publication_matched':identity,'authors':rec.get('author',[]),'year':rec.get('published',{}).get('date-parts',[]),'doi':rec.get('DOI')})
  return
 if data.startswith(b'%PDF'):
  file=CACHE/(hashlib.sha256(url.encode()).hexdigest()+'.pdf');file.write_bytes(data)
  text=subprocess.run(['pdftotext','-f','1','-l','2',str(file),'-'],capture_output=True,text=True,timeout=20).stdout
  add_pdf(url,text,row,out);return
 if 'html' in meta['content_type']:
  parser=Authors();parser.feed(data.decode('utf-8',errors='replace'))
  authors=list(dict.fromkeys(parser.authors))
  if authors:out['author_lists'].append({'source_url':url,'kind':'Publication page author metadata','titles':parser.titles,'publication_matched':any(match_title(row,t) for t in parser.titles),'authors':[{'display_name':a} for a in authors]})
  if follow and not authors:
   for link in parser.pdf[:1]:
    try:collect(urljoin(url,link),row,out,False)
    except Exception as ex:out['errors'].append({'source_url':link,'error':str(ex)[:160]})

def add_pdf(url,text,row,out):
 first=text.split('\f')[0];area=re.split(r'\n\s*(?:abstract|introduction|1\.?\s+introduction|references)\b',first,flags=re.I)[0];area='\n'.join(area.splitlines()[:120])[:10000]
 expected=comparison_title(row['title']);identity=len(expected)>10 and expected in comparison_title(area)
 prior=FOLLOW.get(row['citation_key'],{}).get('pdf_evidence',[])
 identity=identity or any(p['source_url']==url and p.get('normalized_title_found') for p in prior)
 # A manually reviewed title identity is usable, but only for that reviewed source.
 dec=DECISIONS.get(row['citation_key'],{})
 if dec.get('source_url')==url and dec.get('evidence_kind')=='reviewed':identity=True
 out['pdf_headers'].append({'source_url':url,'kind':'Publication opening-page author block','publication_matched':identity,'title_and_author_area':area})

TITLE={r['citation_key']:r for r in map(json.loads,(BASE/'title-verification.jsonl').read_text().splitlines())}
FOLLOW={r['citation_key']:r for r in map(json.loads,(BASE/'title-followup-evidence.jsonl').read_text().splitlines())}
DECISIONS=json.loads((BASE/'title-followup-decisions.json').read_text())
def research(row):
 k=row['citation_key'];out={'citation_key':k,'workbook_title':row['title'],'workbook_author':row['author'],'resources':[],'author_lists':[],'pdf_headers':[],'errors':[]}
 if not row['author']:return out
 # Reuse previously retrieved actual publication pages rather than fetch the same PDFs again.
 for p in FOLLOW.get(k,{}).get('pdf_evidence',[]):
  f=Path(p['cache_text'])
  if f.exists():add_pdf(p['source_url'],f.read_text(),row,out)
 urls=[]
 if row.get('doi') and not row['doi'].lower().startswith('10.48550'):urls.append('https://api.crossref.org/works/'+quote(row['doi'],safe=''))
 for e in TITLE.get(k,{}).get('evidence',[]):
  u=e.get('source_url','')
  if e.get('matches') and 'api.crossref.org/works/' in u:urls.append(u)
 urls=list(dict.fromkeys(urls))[:2]
 # DOI lists, official paper-page authors, and already verified alternative sources.
 url=row.get('url') or ''
 if url:urls.append(url.replace('\\_','_').replace('\\&','&').replace('\\#','#'))
 for e in reversed(TITLE.get(k,{}).get('evidence',[])):
  u=e.get('source_url','')
  if e.get('matches') and u and u not in urls and 'api.crossref.org' not in u:
   urls.append(u);break
 for u in list(dict.fromkeys(urls))[:4]:
  if any(p['source_url']==u for p in out['pdf_headers']):continue
  try:collect(u,row,out)
  except Exception as ex:out['errors'].append({'source_url':u,'error':str(ex)[:180]})
 return out

def main():
 rows=json.loads(Path('/tmp/bib-author-input.json').read_text());file=BASE/'author-verification-evidence.jsonl';done=set()
 if file.exists():done={json.loads(l)['citation_key'] for l in file.read_text().splitlines()}
 with file.open('a') as f,concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
  futures=[pool.submit(research,r) for r in rows if r['citation_key'] not in done]
  n=len(done)
  for result in concurrent.futures.as_completed(futures):
   value=result.result();f.write(json.dumps(value,ensure_ascii=False)+'\n');f.flush();n+=1
   if n%40==0:print('Author research:',n,'/637',flush=True)
 print('Author evidence collection complete',flush=True)
if __name__=='__main__':main()
