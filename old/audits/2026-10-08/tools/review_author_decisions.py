"""Record manually reviewed author evidence and conservative version decisions."""
import json,re
from pathlib import Path
from bibtexparser.middlewares.names import split_multiple_persons_names
from resolve_authors import parts,person,display,compatible,improvement,norm
B=Path('bib_files/normalized-2026-10-08');d=json.loads((B/'author-verification-decisions.json').read_text());e={r['citation_key']:r for r in map(json.loads,(B/'author-verification-evidence.jsonl').read_text().splitlines())};rows={r['citation_key']:r for r in json.load(open('/tmp/bib-author-input.json'))};manual=[]
def whole(k,names,url,reason):
 before=split_multiple_persons_names(rows[k]['author'] or '');out=[]
 for name in names:
  prior=next((n for n in before if compatible(parts(n),parts(name))),None)
  after=improvement(prior,parts(name)) if prior else name
  out.append({'before':prior or '', 'after':after,'status':'corrected' if not prior or after!=prior else 'confirmed','source_url':url,'method':'Reviewed full publication author list','reason':reason,'external_name':name})
 d[k]['names']=out;d[k]['after']=' and '.join(n['after'] for n in out);d[k]['complete_author_list_restored']='others' in before
 manual.append({'citation_key':k,'source_url':url,'author_list':names,'reason':reason})
def one(k,before,after,url,reason):
 n=next((n for n in d[k]['names'] if n['before']==before),None)
 if n is None:return
 n.update(after=after,status='corrected' if after!=before else 'confirmed',source_url=url,method='Reviewed publication-specific name evidence',reason=reason,external_name=after)
 d[k]['after']=' and '.join(x['after'] for x in d[k]['names']);manual.append({'citation_key':k,'source_url':url,'name':after,'reason':reason})
def pdfurl(k):return next(p['source_url'] for p in e[k]['pdf_headers'] if p['publication_matched'])
whole('EthicsOwnersANewMode199',['Moss, Emanuel','Metcalf, Jacob'],pdfurl('EthicsOwnersANewMode199'),'Cover explicitly lists Emanuel Moss and Jacob Metcalf; repair inverted first-name/surname fields.')
whole('DraftforPublicCommen185',['Grother, Patrick','Hom, Austin','Ngan, Mei','Hanaoka, Kayee'],pdfurl('DraftforPublicCommen185'),'Draft cover provides four individual authors; split incorrectly merged Patrick Grother/Austin Hom names.')
whole('TaxonomyofFailureMod548',['Bryan, Pete','Severi, Giorgio','de Gruyter, Joris','Jones, Daniel','Bullwinkel, Blake','Minnich, Amanda','Chawla, Shiven','Lopez, Gary','Pouliot, Martin','Fourney, Adam','Maxwell, Whitney','Pratt, Katherine','Qi, Saphir','Chikanov, Nina','Lutz, Roman','Dheekonda, Raja Sekhar Rao','Jagdagdorj, Bolor-Erdene','Kim, Eugenia','Song, Justin','Hines, Keegan','Jones, Daniel','Lundeen, Richard','Vaughan, Sam','Westerhoff, Victoria','Zunger, Yonatan','Kawaguchi, Chang','Russinovich, Mark','Kumar, Ram Shankar Siva'],pdfurl('TaxonomyofFailureMod548'),'Publication cover author list reviewed in full; split four merged author pairs and preserve the repeated Daniel Jones exactly as printed.')
whole('PatternRecognitionan430',['Bishop, Christopher M.'],'https://link.springer.com/book/9780387310732','Publisher identifies Christopher M. Bishop as the sole book author; Nasser M. Nasrabadi is not an author of this book.')
source=next(s for s in e['Thereplicationcrisis586']['author_lists'] if s['publication_matched'])
whole('Thereplicationcrisis586',[display(person(a)) for a in source['authors']],source['source_url'],'Exact DOI publication author list replaces malformed et al., Max Korbmacher entry and restores the full list.')
whole('LanguageModelsareUns354',['Radford, Alec','Wu, Jeffrey','Child, Rewon','Luan, David','Amodei, Dario','Sutskever, Ilya'],'https://cdn.openai.com/better-language-models/language_models_are_unsupervised_multitask_learners.pdf','Original OpenAI paper title page explicitly provides all six authors.')
whole('ArtificialIntelligen078',['Autio, Chloe','Schwartz, Reva','Dunietz, Jesse','Jain, Shomik','Stanley, Martin','Tabassi, Elham','Hall, Patrick','Roberts, Kamie'],'https://www.nist.gov/people/chloe-autio','NIST author profile lists this exact 2024 publication and all eight individual authors, supplementing corporate-only DOI metadata.')
whole('TheNISTAssessingRisk582',['Schwartz, Reva','Fiscus, Jonathan','Greene, Kristen','Waters, Gabriella','Chowdhury, Rumman','Jensen, Theodore','Greenberg, Craig','Godil, Afzal','Amironesei, Razvan','Hall, Patrick','Jain, Shomik'],'https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.700-2.pdf','Reference [2] in the NIST ARIA pilot report explicitly lists the 2024 pilot evaluation plan and these eleven authors.')
whole('FairnessandMachineLe230',['Barocas, Solon','Hardt, Moritz','Narayanan, Arvind'],'https://fairmlbook.org/','Book authors own website supplies an explicit BibTeX citation and the same three authors; no edition metadata is changed.')
one('AddingStructuretoAIH034','Hoffmann, M.','Hoffmann, Mia',pdfurl('AddingStructuretoAIH034'),'CSET report cover explicitly prints Mia Hoffmann.')
one('AIUseTaxonomyAHumanC049','Theofanos, M.','Theofanos, Mary',pdfurl('AIUseTaxonomyAHumanC049'),'NIST report cover explicitly prints Mary Theofanos; DOI list omits her.')
one('DistributedOptimizat175','Eckstein, Jonahtan','Eckstein, Jonathan',pdfurl('DistributedOptimizat175'),'Publication title page prints Jonathan Eckstein; correct transposed letters in the given name.')
one('Ascalableframeworkfo017','Kim, Young, Bum','Kim, Young-Bum','https://arxiv.org/abs/2010.12251','Exact publication metadata prints Young-Bum Kim; repair misplaced comma and hyphen.')
one('InterpretingtheRepea333','and Yossi Gandelsman','Gandelsman, Yossi','https://arxiv.org/abs/2503.08908','Publication metadata identifies Yossi Gandelsman; remove duplicated and prefix and parse surname first.')
one('Evaluatingthereplica204','Ho, Teck','Ho, Teck-Hua','https://api.crossref.org/works/10.1038%2Fs41562-018-0399-z','Exact publication author list prints Teck-Hua Ho; complete truncated given name.')
one('DeepfakesandChildSaf162','Atherton, D.','Atherton, Daniel','https://incidentdatabase.ai/about/?lang=en','Official AI Incident Database collaborator profile explicitly attributes this named 2024 report to Daniel Atherton.')
for k in ['DAIRAIPromptEngineer140','PromptEngineeringGui458']:
 whole(k,['Saravia, Elvis'],'https://github.com/dair-ai/Prompt-Engineering-Guide/blob/main/README.md?plain=1','Project README supplies the recommended citation with Elvis Saravia as author.')
# Expansion must not substitute a later arXiv revision for the original citation.
for k in ['RealityCheckANewEval480','Evaluatinglargelangu202']:
 original=split_multiple_persons_names(rows[k]['author']);old={n['before']:n for n in d[k]['names'] if n['before']};out=[]
 for name in original:
  n=old.get(name)
  if name=='others':n={'before':name,'after':name,'status':'unverified','source_url':rows[k]['url'],'method':'Original-version comparison','reason':'Original PDF and current metadata have different author lists; full expansion is withheld to preserve the cited version.'}
  if n is None:n={'before':name,'after':name,'status':'unverified','source_url':rows[k]['url'],'method':'','reason':'No sufficient publication-specific author evidence.'}
  out.append(n)
 d[k]['names']=out;d[k]['after']=' and '.join(n['after'] for n in out);d[k]['complete_author_list_restored']=False
# The 2022 v3 PDF supports the expanded Chain-of-Thought authors, including Brian Ichter and Fei Xia.
for n in d['ChainofthoughtPrompt113']['names']:
 n['source_url']='https://arxiv.org/pdf/2201.11903v3';n['method']='Reviewed cited-year PDF author list';n['reason']='2022 v3 PDF author block confirms the complete nine-person author list.'
manual.append({'citation_key':'ChainofthoughtPrompt113','source_url':'https://arxiv.org/pdf/2201.11903v3','reason':'v3 is dated 1 June 2022 and includes Brian Ichter and Fei Xia; v1 has a different list.'})
# Later H2O covers provide full spellings, but editor Jessica Lanford remains a role/edition uncertainty.
for k,names in {
'GeneralizedLinearMod260':{'Hussami, N.':'Hussami, Nadine','Kraljevic, T.':'Kraljevic, Tom','Nykodym, T.':'Nykodym, Tomas','Rao, A.':'Rao, Ariel','Wang, A.':'Wang, Amy'},
'DeepLearningwithH2O158':{'Arora, A.':'Arora, Anisha','Candel, A.':'Candel, Arno','LeDell, E.':'LeDell, Erin','and Parmar, V.':'Parmar, Viraj'},
'GradientBoostedModel277':{'Click, C.':'Click, Cliff','Malohlava, M.':'Malohlava, Michal','Parmar, V.':'Parmar, Viraj','Roark, H.':'Roark, Hank'},
}.items():
 url=e[k]['pdf_headers'][-1]['source_url']
 for before,after in names.items():one(k,before,after,url,'Official manual cover provides this full personal name; no authors from a later edition are added.')
 for n in d[k]['names']:
  if n['before']=='Lanford, J.':n['status']='unverified';n['reason']='Later official cover lists Jessica Lanford as editor, not author; cited-edition author/editor role remains unconfirmed.';n['source_url']=url
# Prior visual review of the original interpretability booklet cover confirmed its two authors.
whole('AnIntroductiontoMach060',['Hall, Patrick','Gill, Navdeep'],'https://h2o.ai/content/dam/h2o/en/marketing/documents/2019/08/An-Introduction-to-Machine-Learning-Interpretability-Second-Edition.pdf','Original second-edition cover was visually reviewed during title verification and explicitly prints Patrick Hall and Navdeep Gill.')
(B/'author-verification-decisions.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');(B/'author-reviewed-evidence.json').write_text(json.dumps(manual,ensure_ascii=False,indent=2)+'\n')
from collections import Counter
print('Final name decisions',Counter(n['status'] for r in d.values() for n in r['names']));print('Changed fields',sum(r['before']!=r['after'] for r in d.values()),'Full lists restored',sum(r['complete_author_list_restored'] for r in d.values()))
