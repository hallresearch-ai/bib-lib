"""Collect external title evidence without changing the bibliography.

Usage: python verify_titles.py library-cleaned.xlsx title-verification.jsonl
Requires openpyxl and pylatexenc. Resolves only normalized exact title matches.
"""
import concurrent.futures
import html
from html.parser import HTMLParser
import json
import re
import sys
import threading
import unicodedata
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

import openpyxl
from pylatexenc.latex2text import LatexNodes2Text


def comparison_title(value):
    value = html.unescape(value or '')
    value = re.sub(r'<[^>]+>', '', value)
    value = LatexNodes2Text().latex_to_text(value)
    value = unicodedata.normalize('NFKC', value).casefold()
    return ''.join(c for c in value if c.isalnum())


class PageTitles(HTMLParser):
    def __init__(self):
        super().__init__()
        self.candidates = []
        self.tag = None
        self.text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta':
            kind = (attrs.get('name') or attrs.get('property') or '').lower()
            if kind in {'citation_title', 'dc.title', 'dc.title.alternative', 'dcterms.title', 'og:title', 'twitter:title'}:
                if attrs.get('content'): self.candidates.append((kind, attrs['content']))
        if tag in {'title', 'h1'}:
            self.tag = tag
            self.text = []

    def handle_data(self, data):
        if self.tag: self.text.append(data)

    def handle_endtag(self, tag):
        if self.tag == tag:
            value = ' '.join(''.join(self.text).split())
            if tag == 'title': value = re.sub(r'^\[\d{4}\.\d{4,5}(?:v\d+)?\]\s*', '', value)
            if value: self.candidates.append((tag, value))
            self.tag = None


DOI_LIMIT = threading.Semaphore(2)
ARXIV_LIMIT = threading.Semaphore(2)
WEB_LIMIT = threading.Semaphore(4)


def request_titles(url, method, limiter):
    with limiter:
        request = Request(url, headers={'User-Agent': 'bib-lib-title-audit/1.0', 'Accept': 'application/json' if method == 'crossref' else 'text/html'})
        with urlopen(request, timeout=12) as response:
            data = response.read(2_000_000)
            final_url = response.url
            content_type = response.headers.get('Content-Type', '')
        if method == 'crossref':
            record = json.loads(data)['message']
            # Title and subtitle are separately represented by Crossref.
            titles = record.get('title', [])
            candidates = [('Crossref title', t) for t in titles]
            for t in titles:
                for sub in record.get('subtitle', []):
                    candidates.append(('Crossref title and subtitle', t + ': ' + sub))
            return final_url, candidates
        if 'html' not in content_type:
            return final_url, []
        parser = PageTitles()
        parser.feed(data.decode('utf-8', errors='replace'))
        return final_url, parser.candidates


def verify(row):
    current = row['title'] or ''
    key = row['citation_key']
    result = {'citation_key': key, 'workbook_title': current, 'status': 'unverified', 'evidence': [], 'errors': []}
    requests = []
    doi = row.get('doi') or ''
    if doi and not doi.lower().startswith('10.48550/arxiv.'):
        requests.append(('https://api.crossref.org/works/' + quote(doi, safe=''), 'crossref', DOI_LIMIT))
    eprint = row.get('eprint') or ''
    url = row.get('url') or ''
    if eprint and row.get('archiveprefix') == 'arXiv':
        requests.append(('https://arxiv.org/abs/' + eprint, 'arxiv', ARXIV_LIMIT))
    if url and not any(url == u for u,m,l in requests):
        requests.append((url, 'web', WEB_LIMIT))
    expected = comparison_title(current)
    for address, method, limiter in requests:
        try:
            final_url, candidates = request_titles(address, method, limiter)
            for kind, title in candidates:
                match = comparison_title(title) == expected
                result['evidence'].append({'source_url': address, 'final_url': final_url, 'kind': kind, 'title': title, 'matches': match})
            if any(e['matches'] for e in result['evidence']):
                result['status'] = 'matched'
                break
        except Exception as exc:
            result['errors'].append({'source_url': address, 'error': str(exc)[:200]})
    if result['status'] != 'matched' and result['evidence']:
        result['status'] = 'needs_review'
    return result


def main():
    path, dest = map(Path, sys.argv[1:])
    workbook = openpyxl.load_workbook(path, data_only=True)
    values = list(workbook['Bibliography'].values)
    records = [dict(zip(values[0], r)) for r in values[1:]]
    issues = list(workbook['Review'].values)
    fields = {h:i for i,h in enumerate(issues[0])}
    keys = {r[fields['citation_key']] for r in issues[1:] if r[fields['check']] == 'title_capitalization_review'}
    records = [r for r in records if r['citation_key'] in keys]
    existing = {}
    if dest.exists():
        for line in dest.read_text().splitlines():
            r = json.loads(line)
            existing[r['citation_key']] = r
    records = [r for r in records if r['citation_key'] not in existing or existing[r['citation_key']]['workbook_title'] != r['title']]
    matched = sum(r['status']=='matched' for r in existing.values())
    total = len(existing)
    with dest.open('a', encoding='utf-8') as output, concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        for future in concurrent.futures.as_completed([executor.submit(verify,r) for r in records]):
            result = future.result()
            output.write(json.dumps(result, ensure_ascii=False)+'\n')
            output.flush()
            total += 1
            matched += result['status']=='matched'
            if total % 25 == 0:
                print(f'Checked {total} titles; {matched} matched external metadata', flush=True)
    print(f'Finished: {total} titles checked; {matched} externally matched', flush=True)


if __name__ == '__main__':
    main()
