"""Conservative per-name author decisions from saved publication evidence."""
import json,re,unicodedata
from functools import lru_cache
from pathlib import Path
from bibtexparser.middlewares.names import parse_single_name_into_parts,split_multiple_persons_names
from research_title_followup import plain
BASE=Path('bib_files/normalized-2026-10-08')
ORCIDS={r['orcid']:r for r in map(json.loads,(BASE/'author-orcid-evidence.jsonl').read_text().splitlines())}
@lru_cache(maxsize=30000)
def norm(x):return ''.join(c for c in unicodedata.normalize('NFKD',plain(x)).casefold() if c.isalpha() and not unicodedata.combining(c))
@lru_cache(maxsize=10000)
def parts(name):
 if name.strip().startswith('{') and name.strip().endswith('}'):return {'family':plain(name).strip('{}'),'given':'','suffix':'','corporate':True}
 p=parse_single_name_into_parts(plain(name));return {'family':' '.join(p.von+p.last),'given':' '.join(p.first),'suffix':' '.join(p.jr)}
def display(p):
 if p.get('corporate'):return '{'+p['family'].strip('{}')+'}'
 given=' '.join(v+'.' if len(v)==1 and v.isalpha() else v for v in p['given'].split())
 return p['family']+(', '+p['suffix'] if p.get('suffix') else '')+(', '+given if given else '')
def person(raw):
 if raw.get('family'):return {'family':raw['family'],'given':raw.get('given',''),'suffix':raw.get('suffix',''),'orcid':raw.get('ORCID','')}
 if raw.get('name'):return {'family':raw['name'],'given':'','suffix':'','corporate':True}
 n=raw.get('display_name','');p=parts(n)
 if ',' not in n and not p['given'] and ' ' in n:p['corporate']=True
 return p

def compatible(a,b):
 af=norm(a['family']);bf=norm(b['family'])
 if not a['given'] and not b['given']:
  af=re.sub(r'us$','',af);bf=re.sub(r'us$','',bf)
 if af!=bf:return False
 ag=[norm(x) for x in a['given'].split() if norm(x)];bg=[norm(x) for x in b['given'].split() if norm(x)]
 if not ag or not bg:return not ag and not bg
 for x,y in zip(ag,bg):
  if x==y:continue
  if (x,y) in {('rob','robert'),('robert','rob'),('jeff','jeffrey'),('jeffrey','jeff'),('rich','richard'),('richard','rich'),('ted','theodore'),('theodore','ted')}:continue
  if len(x)==1 and y.startswith(x) or len(y)==1 and x.startswith(y):continue
  return False
 return True

def improvement(old,external):
 # Fill supported full given names/middle names; never replace a full name by initials.
 a=parts(old);b=external
 if not compatible(a,b):return old
 ag=[norm(x) for x in a['given'].split()];bg=[norm(x) for x in b['given'].split()]
 if len(bg)>=len(ag) and sum(map(len,bg))>sum(map(len,ag)) and all(len(x)>=len(y) for x,y in zip(bg,ag)):return display(b)
 return old

def in_pdf(name,text):
 p=parts(name);f=norm(p['family']);g=[norm(x) for x in p['given'].split() if norm(x)]
 if not f or not g:return False
 t=norm(text)
 # Require first given name and surname in one contiguous author-name sequence.
 choices={''.join(g)+f,g[0]+f,g[0]+''.join(v[:1] for v in g[1:])+f}
 if len(g[0])<2:return False
 return any(c in t for c in choices if len(c)>=5) or bool(re.search(re.escape(g[0])+r'[a-z]{0,3}'+re.escape(f),t))

def main():
 rows=json.loads(Path('/tmp/bib-author-input.json').read_text());e={v['citation_key']:v for v in map(json.loads,(BASE/'author-verification-evidence.jsonl').read_text().splitlines())}
 pool={}
 for row in rows:
  for n in split_multiple_persons_names(row['author'] or ''):
   if n=='others' or n.startswith('{'):continue
   try:p=parts(n)
   except Exception:continue
   if p['given'] and len(norm(p['given'].split()[0]))>1:pool.setdefault(norm(p['family']),set()).add(n)
 out={}
 for row in rows:
  key=row['citation_key'];r=e.get(key,{});sources=[s for s in r.get('author_lists',[]) if s['publication_matched']];pdfs=[p for p in r.get('pdf_headers',[]) if p['publication_matched']]
  current=split_multiple_persons_names(row['author'] or '');dec=[]
  for n in current:
   item={'before':n,'after':n,'status':'unverified','source_url':'','method':'','reason':'No sufficient publication-specific author evidence found.'}
   if n=='others':dec.append(item);continue
   a=parts(n)
   candidates=[]
   for source in sources:
    for raw in source['authors']:
     b=person(raw)
     if compatible(a,b):candidates.append((source,b))
   if candidates:
    source,b=max(candidates,key=lambda v:len(norm(v[1]['given'])));b=dict(b)
    oid=b.get('orcid','').split('/')[-1];public=ORCIDS.get(oid,{}).get('public_name',{})
    if public.get('given') and public.get('family') and compatible(b,public) and compatible(a,public) and len(norm(public['given']))>len(norm(b['given'])):b['given']=public['given']
    item.update(after=improvement(n,b),status='confirmed',source_url=source['source_url'],method=source['kind'],reason='Name matches an author of the externally matched publication; initial differences are compatible.',external_name=display(b),orcid=b.get('orcid',''))
   else:
    direct=next((p for p in pdfs if in_pdf(n,p.get('layout_author_area') or p['title_and_author_area'])),None)
    if direct:item.update(status='confirmed',source_url=direct['source_url'],method=direct['kind'],reason='Full given name and surname occur together in the matched publication author block.')
    elif not n.startswith('{'):
     options=[(name,pdf) for name in pool.get(norm(a['family']),set()) if compatible(a,parts(name)) for pdf in pdfs if in_pdf(name,pdf.get('layout_author_area') or pdf['title_and_author_area'])]
     unique={name for name,pdf in options}
     if len(unique)==1:
      name,pdf=options[0];item.update(after=improvement(n,parts(name)),status='confirmed',source_url=pdf['source_url'],method='Full author name in matched publication PDF',reason='Initials expand to the unique compatible full name printed in this publication.',external_name=name)
   if n=='Hall, Patrick' and item['status']=='unverified':item.update(status='normalized_by_user',source_url='Explicit user normalization of Patrick Hall',method='User-approved canonical name',reason='Retain the user-approved Hall, Patrick normalization and black marking.')
   if item['after']!=n:item['status']='corrected'
   dec.append(item)
  # Expand truncation only when an authoritative full list accounts for all named authors.
  if 'others' in current:
   for source in sources:
    if source.get('doi') and source['doi']!=row.get('doi') and source.get('year') and row.get('year') and str(source['year'][0][0])!=row['year']:continue
    ext=[person(a) for a in source['authors'] if not a.get('name','').lower().startswith('on behalf of')];ext=list({(norm(a['family']),norm(a['given'])):a for a in ext}.values());known=[parts(n) for n in current if n!='others']
    if len(ext)>len(known) and all(any(compatible(a,b) for b in ext) for a in known) and all(x['given'] or x.get('corporate') for x in ext):
     complete=[]
     for b in ext:
      existing=next((n for n in current if n!='others' and compatible(parts(n),b)),None)
      name=improvement(existing,b) if existing else display(b)
      complete.append({'before':existing or '', 'after':name,'status':'corrected' if not existing or name!=existing else 'confirmed','source_url':source['source_url'],'method':source['kind'],'reason':'Complete authoritative author list matches all previously listed authors; restore omitted authors in source order.','external_name':display(b),'orcid':b.get('orcid','')})
     dec=complete;break
  out[key]={'citation_key':key,'before':row['author'],'after':' and '.join(d['after'] for d in dec) or None,'names':dec,'complete_author_list_restored': 'others' in current and all(d['after']!='others' for d in dec)}
 (BASE/'author-verification-decisions.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 from collections import Counter
 print('Name decisions',Counter(d['status'] for r in out.values() for d in r['names']))
 print('Changed fields',sum(r['before']!=r['after'] for r in out.values()),'Expanded lists',sum(r['complete_author_list_restored'] for r in out.values()))
if __name__=='__main__':main()
