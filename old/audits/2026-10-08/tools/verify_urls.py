"""Check live URL resolution and publication identity; mutability is not an issue."""
import concurrent.futures,difflib,hashlib,json,re,subprocess,unicodedata
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from urllib.parse import urlsplit
from research_title_followup import Page,plain,harmless_match
from verify_titles import comparison_title
from bibtexparser.middlewares.names import split_multiple_persons_names,parse_single_name_into_parts
BASE=Path('bib_files/normalized-2026-10-08');CACHE=Path('/tmp/bib-url-cache');CACHE.mkdir(exist_ok=True)
TITLES={r['citation_key']:r for r in map(json.loads,(BASE/'title-verification.jsonl').read_text().splitlines())}
AUTHOR=json.loads((BASE/'author-verification-decisions.json').read_text())
FOLLOW=json.loads((BASE/'title-followup-decisions.json').read_text())
def norm(x):return ''.join(c for c in unicodedata.normalize('NFKD',plain(x)).casefold() if c.isalnum() and not unicodedata.combining(c))
def research(row):
 key=row['citation_key'];url=row['url'];out={'citation_key':key,'requested_url':url,'status':'unverified','resolved':False,'record_matches':{},'notes':[]}
 if not url:out['status']='missing';return out
 address=url.replace('\\_','_').replace('\\&','&').replace('\\#','#')
 if '.pdf/web/viewer.html' in address:address=address.split('.pdf/web/viewer.html')[0]+'.pdf'
 try:
  req=Request(address,headers={'User-Agent':'Mozilla/5.0 (compatible; bibliography-link-verification/1.0)','Accept':'text/html,application/pdf;q=0.9,*/*;q=0.8'})
  with urlopen(req,timeout=15) as f:data=f.read(25_000_000);out.update(final_url=f.url,http_status=f.status,content_type=f.headers.get('Content-Type',''),sha256=hashlib.sha256(data).hexdigest(),resolved=True)
 except HTTPError as ex:out.update(status='access_blocked' if ex.code in {401,403,429} else 'http_error',http_status=ex.code,final_url=ex.url);out['notes'].append(str(ex));return out
 except Exception as ex:out.update(status='request_failed');out['notes'].append(str(ex)[:200]);return out
 titles=[];body='';pdf=data.startswith(b'%PDF')
 if pdf:
  stem=hashlib.sha256(address.encode()).hexdigest()[:20];file=CACHE/(stem+'.pdf');file.write_bytes(data)
  body=subprocess.run(['pdftotext','-layout','-f','1','-l','2',str(file),'-'],capture_output=True,text=True,timeout=20).stdout
  title_area=re.split(r'\n\s*(?:abstract|1\.?\s+introduction|references)\b',body.split('\f')[0],flags=re.I)[0]
  titles=[title_area[:6000]];out['pdf_title_area']=title_area[:10000]
 else:
  page=Page();page.feed(data.decode('utf-8',errors='replace'));titles=[t for k,t in page.meta+page.headings if 'title' in k or k in {'title','h1','h2'} or k.startswith('JSON-LD')];body=' '.join(page.alltext)
  if any(re.search(r'(?:verifying your browser|just a moment|access denied|checking your browser|are you a robot|captcha|enable javascript and cookies to continue)',t,re.I) for t in titles[:4]):out.update(status='access_blocked',resolved=False);out['notes'].append('Challenge/error page; record content was not retrieved.');return out
 out['page_titles']=titles[:30];out['content_excerpt']=body[:12000]
 expected=comparison_title(row['title']);titlematch=any(harmless_match(row['title'],t) for t in titles)
 if pdf:titlematch=bool(len(expected)>12 and expected in comparison_title(titles[0]))
 # A substantial main title plus matching author/date can corroborate subtitles omitted from page headings.
 main=re.split(r'[:–—]',plain(row['title']),1)[0].strip();mainnorm=norm(main)
 partial= len(main.split())>=3 and any(mainnorm in norm(t) for t in titles)
 textnorm=norm(body);verified_names=[]
 for name in split_multiple_persons_names(row['author'] or ''):
  if name=='others':continue
  if name.startswith('{'):
   n=norm(name);present=n in textnorm
  else:
   p=parse_single_name_into_parts(plain(name));family=norm(' '.join(p.von+p.last));given=norm(' '.join(p.first));first=norm(p.first[0]) if p.first else ''
   present=bool(given and family and (given+family in textnorm or family+given in textnorm or len(first)>1 and re.search(re.escape(first)+r'[a-z]{0,3}'+re.escape(family),textnorm)))
  if present:verified_names.append(name)
 author_match=bool(verified_names);year_match=bool(row.get('year') and re.search(r'\b'+re.escape(row['year'])+r'\b',body))
 doi_match=bool(row.get('doi') and norm(row['doi']) in textnorm);isbn_match=bool(row.get('isbn') and norm(row['isbn']) in textnorm)
 host=urlsplit(out['final_url']).netloc.lower();org_names=[n.strip('{}') for n in split_multiple_persons_names(row['author'] or '') if n.startswith('{')]
 org_match=any((norm(n) in norm(host) or len(norm(n))>=4 and norm(n) in textnorm) for n in org_names)
 out['record_matches']={'title':titlematch,'main_title':partial,'author':author_match,'year':year_match,'doi':doi_match,'isbn':isbn_match,'organization':org_match};out['matched_author_names']=verified_names
 # Reuse reviewed visual covers only after this request retrieves the same actual resource.
 trusted=False
 for ev in TITLES.get(key,{}).get('evidence',[]):
  if not ev.get('matches'):continue
  source=ev.get('final_url') or ev.get('source_url','')
  if source in {address,out['final_url']} and not ('api.crossref.org' in source and 'api.crossref.org' not in address):trusted=True
 dec=FOLLOW.get(key,{})
 if dec.get('source_url') in {address,out['final_url']} and dec.get('evidence_kind')=='reviewed':trusted=True
 # DOI locators should resolve to the actual publication, not an authentication/error page.
 distinctive=len(plain(row['title']).split())>=4
 if titlematch and (author_match or year_match or doi_match or isbn_match or org_match or distinctive) or partial and (author_match or org_match) and (year_match or doi_match or isbn_match) or trusted and (pdf or titlematch):
  out['status']='matched';out['notes'].append('URL resolves to content matching the cited work; mutability is accepted.')
 else:out['status']='content_unconfirmed';out['notes'].append('URL resolves, but retrieved content does not establish a substantial record match.')
 return out

def main():
 rows=json.loads(Path('/tmp/bib-url-input.json').read_text());file=BASE/'url-verification-evidence.jsonl';done=set()
 if file.exists():done={json.loads(l)['citation_key'] for l in file.read_text().splitlines()}
 with file.open('a') as f,concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
  n=len(done)
  for fut in concurrent.futures.as_completed([pool.submit(research,r) for r in rows if r['citation_key'] not in done]):
   try:r=fut.result()
   except Exception as ex:raise RuntimeError('URL research error') from ex
   f.write(json.dumps(r,ensure_ascii=False)+'\n');f.flush();n+=1
   if n%50==0:print('URL checks',n,'/637',flush=True)
 print('URL verification complete',flush=True)
if __name__=='__main__':main()
