"""Review harmless heading differences and logical publication identifiers."""
import json,re,html,hashlib,concurrent.futures
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urljoin
from research_title_followup import Page,plain
from verify_urls import norm,research,TITLES
B=Path('bib_files/normalized-2026-10-08');e={r['citation_key']:r for r in map(json.loads,(B/'url-verification-evidence.jsonl').read_text().splitlines())};rows={r['citation_key']:r for r in json.load(open('/tmp/bib-url-input.json'))}
def words(t):
 t=plain(t).lower().replace('&',' and ')
 t=re.sub(r'\bai\b','artificial intelligence',t);t=re.sub(r'\bml\b','machine learning',t)
 for a,b in {'one':'1','two':'2','three':'3','four':'4','five':'5','six':'6','seven':'7','eight':'8','nine':'9','ten':'10'}.items():t=re.sub(r'\b'+a+r'\b',b,t)
 return [w for w in re.findall(r'[a-z0-9]+',t) if w not in {'the','a','an'}]
def approve(k,reason):
 z=e[k];assert z['resolved'];z['status']='matched';z['notes'].append(reason);z['reviewed']=True
for k,z in e.items():
 if z['status']!='content_unconfirmed':continue
 ts=z.get('page_titles',[]);r=rows[k];m=z['record_matches'];body=z.get('content_excerpt','');expected=words(r['title']);et=set(expected)
 # Exact main/core titles, harmless digits, branding wrappers, and trailing date/edition labels.
 for t in ts:
  candidate=words(t);ct=set(candidate);overlap=len(et&ct)/max(1,len(et));core=re.split(r':',plain(r['title']),1)[0];wc=words(core)
  core_match=len(wc)>=3 and ' '.join(wc) in ' '.join(candidate)
  full_match=bool(expected) and ' '.join(expected) in ' '.join(candidate)
  if full_match and len(expected)>=3 or (overlap>=.80 or core_match) and (m['author'] or m['organization'] or m['year'] or m['doi'] or m['isbn']):approve(k,'Reviewed heading agrees substantially with title; available author, organization, year or identifier corroborates identity.');break
 # DOI and author/year support identity despite a title change.
 if z['status']=='content_unconfirmed' and m['doi'] and (m['author'] or m['year']):approve(k,'The resolved page contains the exact DOI and matching author or year; title wording differences do not invalidate this locator.')
 # arXiv retains its logical identifier when the displayed title changes in a revision.
 if z['status']=='content_unconfirmed' and 'arxiv.org/abs/' in z.get('final_url','') and (m['author'] and m['year']):
  rid=re.search(r'arxiv.org/abs/([^?#]+)',z['final_url']);existing=(r.get('eprint') or '').removesuffix('.pdf')
  known=[v.get('source_url','') for v in TITLES.get(k,{}).get('evidence',[]) if v.get('matches')]
  linked=rid and any(rid[1].split('v')[0] in v and 'arxiv.org' in v for v in known)
  if rid and (existing and rid[1].split('v')[0]==existing.split('v')[0] or linked):approve(k,'Same arXiv record resolves with matching authors and year; the repository may display a later title.')
 # Full PDFs can put their report title on a graphical cover; confirm report identifier plus contributors/date.
 if z['status']=='content_unconfirmed' and z.get('pdf_title_area') and m['author'] and m['year']:
  doi=r.get('doi') or '';number=r.get('number') or '';report=re.sub(r'^10\.\d+/','',doi)
  if report and norm(report) in norm(body) or number and len(norm(number))>4 and norm(number) in norm(body):approve(k,'Resolved PDF matches the report identifier, author block and year; cover-title extraction is incomplete.')
# Explicit project/document identity review of the actual retrieved pages.
manual={
'AFrameworkforFewShot008':'The original EleutherAI repository resolves; its heading and recommended citation identify the language-model evaluation harness and listed author.',
'AHolisticFrameworkfo009':'The Stanford CRFM HELM classic leaderboard resolves with the Holistic Evaluation of Language Models heading and the requested leaderboard route.',
'AIIncidentDatabase045':'The database homepage resolves and explicitly identifies the Artificial Intelligence Incident Database; this homepage is the cited resource.',
'DataCardsPlaybook141':'The Google Research page explicitly identifies The Data Cards Playbook; the leading article is harmless.',
'ArtificialIntelligen073':'Official EUR-Lex Regulation EU 2024/1689 matches the AI Act, year and institution; its full text contains the annexes.',
'LLMSecurityandPrivac369':'The cited GitHub repository resolves and its README heading is LLM Security & Privacy; ampersand versus and is harmless.',
'PEFTStateoftheartPar432':'The official Hugging Face PEFT repository resolves and describes state-of-the-art parameter-efficient fine-tuning, matching the cited software resource.',
'H2Owebsite289':'The H2O.ai homepage resolves to the H2O product website, which is the resource cited by this record.',
'RALanguageandEnviron473':'The R Project homepage resolves and identifies R as the statistical-computing language/environment; this is the standard software locator.',
'TheHAXToolkitProject570':'The Microsoft Research page resolves to The HAX Toolkit Project; title core and corporate author match.',
'TrustedAIBlogSeries610':'The Adversa AI site resolves to its Trusted AI Security Blog; series name and organization match.',
'TrustworthinessVocab611':'The ISO product page resolves for ISO/IEC TS 5723:2022, the cited Trustworthiness vocabulary standard; identifier, year and organization match.',
}
for k,reason in manual.items():
 if e[k]['status']=='content_unconfirmed':approve(k,reason)
# Classify successful responses that return error/challenge screens accurately.
for z in e.values():
 if z['status']!='content_unconfirmed':continue
 ts=' '.join(z.get('page_titles',[])[:4])
 if re.search(r'(not a bot|client challenge|javascript is disabled|cookies must be enabled|pardon our interruption|log in to psycnet)',ts,re.I):z['status']='access_blocked';z['resolved']=False;z['notes'].append('Retrieved an access/challenge screen, not citation content.')
 elif re.search(r'page not found|404 not found',ts,re.I):z['status']='http_error';z['notes'].append('Soft 404: server returned HTTP 200 with a page-not-found message.')
# An explicit relocation notice can link to the actual canonical documentation.
k='PresidioDataProtecti448';z=e[k]
if z['status']=='content_unconfirmed':
 try:
  with urlopen(Request(z['requested_url'],headers={'User-Agent':'bib-lib-url-audit/1.0'}),timeout=15) as f:raw=f.read().decode()
  page=Page();page.feed(raw);targets=[u for u in page.links if 'presidio' in u and u.startswith('https://')]
  if targets:
   temp=dict(rows[k]);temp['url']=targets[0];new=research(temp);z['relocation_destination']=new
   if new['status']=='matched':approve(k,'Original URL resolves to an explicit relocation notice; linked canonical Presidio documentation resolves and matches the cited SDK.')
 except Exception as ex:z['notes'].append('Relocation follow-up: '+str(ex)[:120])
(B/'url-verification-evidence.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in e.values()))
from collections import Counter
print(Counter(r['status'] for r in e.values()))
