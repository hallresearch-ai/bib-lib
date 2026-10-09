"""Material-equivalence helpers for July ground truth comparisons."""
import sys,re,unicodedata,json,datetime,difflib
sys.path.insert(0,'.')
from normalize_library import clean_url,doi_id,ORGANIZATIONS
from research_title_followup import plain
from resolve_authors import parts,compatible
from bibtexparser.middlewares.names import split_multiple_persons_names
from urllib.parse import urlsplit,unquote
from pylatexenc.latex2text import LatexNodes2Text

def canon(v):
 t=plain(str(v or ''));return ''.join(c for c in unicodedata.normalize('NFKD',t).casefold() if c.isalnum() and not unicodedata.combining(c))
def urlcanon(v):
 v=clean_url(v);p=urlsplit(v);host=(p.hostname or '').lower().removeprefix('www.');path=unquote(p.path).rstrip('/')
 if host in {'arxiv.org','export.arxiv.org'}:path=re.sub(r'^/(abs|pdf)/','/',path).removesuffix('.pdf');host='arxiv.org'
 if host in {'doi.org','dx.doi.org'}:host='doi.org';path=path.lower()
 return host+path+('?' + p.query if p.query else '')+('#'+p.fragment if p.fragment else '')
def datecanon(v):
 v=str(v)
 for fmt in ['%Y-%m-%d','%m/%d/%Y','%B %Y','%b %Y']:
  try:return datetime.datetime.strptime(v,fmt).strftime('%Y-%m-%d')
  except ValueError:pass
 return v

def namematch(a,b):
 if canon(a)==canon(b):return True
 try:return compatible(parts(a),parts(b))
 except Exception:return False

def match(field,a,b,truth):
 if not a:return False,'No populated value to confirm'
 if field=='url':
  candidates=[(k,truth.get(k,'')) for k in ['url','note','howpublished','bdsk-url-1']]
  for k,v in candidates:
   for u in re.findall(r'https?://[^\s{}<>]+',v):
    if urlcanon(a)==urlcanon(u):return True,'Equivalent locator from ground truth '+k
  return False,'No equivalent locator in ground truth'
 if not b and field=='eprint':
  for k in ['url','note','howpublished','bdsk-url-1']:
   m=re.search(r'arxiv\.org/(?:abs|pdf)/([^\s{}?#]+)',truth.get(k,''))
   if m:b=m[1].removesuffix('.pdf');break
 if not b and field=='eprint':
  m=re.search(r'10\.48550/arxiv\.([0-9.]+(?:v[0-9]+)?)',truth.get('doi',''),re.I)
  if m:b=m[1]
 if not b:return False,'Ground truth has no usable value'
 if canon(a)==canon(b):return True,'Same substantive value after capitalization, accents, TeX and punctuation normalization'
 if field in {'author','editor'}:
  def names(v):
   v=re.sub(r'\s+et\s+al\.?\s*$', ' and others',v,flags=re.I)
   v=re.sub(r'\band\s+and\b','and',v)
   raw=v.strip().strip('{}').casefold()
   if raw in ORGANIZATIONS:return ['{'+ORGANIZATIONS[raw]+'}']
   return split_multiple_persons_names(v)
  aa=names(a);bb=names(b)
  if len(aa)==len(bb) and all(namematch(x,y) for x,y in zip(aa,bb)):return True,'Author list matches with name formatting/compatible initials'
  return False,'Author list differs; compare individual names'
 if field=='url':return (urlcanon(a)==urlcanon(b),'Equivalent normalized locator' if urlcanon(a)==urlcanon(b) else 'Different locator')
 if field in {'date','issue_date'} and datecanon(a)==datecanon(b):return True,'Equivalent normalized date'
 if canon(a)==canon(b):return True,'Same substantive value after capitalization, accents, TeX and punctuation normalization'
 if field=='title':
  ca,cb=canon(a),canon(b);ops=[(x,ca[i:j],cb[k:l]) for x,i,j,k,l in difflib.SequenceMatcher(None,ca,cb,autojunk=False).get_opcodes() if x!='equal']
  # Accept only small spelling corrections, with all numbers unchanged.
  if min(len(ca),len(cb))>=30 and sum(max(len(x),len(y)) for _,x,y in ops)<=2 and re.findall(r'\d+',ca)==re.findall(r'\d+',cb):return True,'Minor spelling correction; title otherwise agrees'
 return False,'Substantive values differ'
