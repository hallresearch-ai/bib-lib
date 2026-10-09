"""Assign citation keys once, then preserve them using a versioned registry.

Used by the cleaned-workbook updater. The registry must travel with the library.
"""
import hashlib
import json
import re
import unicodedata
from collections import Counter

from bibtexparser.middlewares.names import (
    parse_single_name_into_parts, split_multiple_persons_names,
)
from pylatexenc.latex2text import LatexNodes2Text

STOPWORDS = frozenset('a an the and or of in on for to with by from at as is are '
                      'be this that these those'.split())
IDENTITY_FIELDS = ('author', 'editor', 'year', 'title', 'entry_type', 'doi',
                   'eprint', 'edition', 'journal', 'booktitle', 'number', 'url')
POLICY = (
    'Stable citation-key rule v1 (2026-10-08): Assign once as '
    'LeadNameYearShortTitle, for example Hall2020MachineLearning. LeadName is '
    'the first personal author surname including particles, or the first three '
    'significant words of a braced corporate author; use the first editor if '
    'author is absent, then institution/organization, then Anon. Year is the '
    'four-digit publication year, or nd when undated. ShortTitle is the first '
    'three significant title words, or Untitled. Decode LaTeX, transliterate '
    'Latin accents, remove punctuation, and capitalize each ASCII alphanumeric '
    'word. Stop words: ' + ', '.join(sorted(STOPWORDS)) + '. '
    'If a key begins with a digit, prefix Ref. Keys are unique ignoring case. '
    'For simultaneous collisions, suffix every colliding new key with x plus '
    'the first eight hexadecimal digits of the SHA-256 of canonical identity '
    'metadata; extend by four digits if needed. Identity metadata consists of '
    'author, editor, year, title, entry_type, doi, eprint, edition, journal, '
    'booktitle, number, url, in that order, trimmed and whitespace-collapsed, '
    'serialized as a UTF-8 JSON array with compact separators. Identical '
    'unregistered identities require manual differentiation; never merge them '
    'automatically. Existing keys and historical aliases take precedence over '
    'metadata-derived candidates. Once assigned, never regenerate a key for '
    'sorting, insertion, deletion, metadata correction, or a new collision. '
    'New collisions receive a suffix without changing existing keys. Persist '
    'citation-key-registry.json with the library, preserve literal citation_key '
    'values on all imports/exports, and reserve deleted keys permanently. '
    'The migration map resolves legacy keys; historical evidence retains its '
    'original references. This supersedes the previous row-number formula and '
    'alphabetical-suffix advice. The workbook Change audit records every rename '
    'and this rule; Citation key map and citation-key-migration.csv provide aliases.'
)


def words(value):
    text = LatexNodes2Text().latex_to_text(str(value or ''))
    text = text.translate(str.maketrans({'ß': 'ss', 'ø': 'o', 'Ø': 'O',
                                       'ł': 'l', 'Ł': 'L', 'æ': 'ae', 'œ': 'oe'}))
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode()
    return re.findall(r'[A-Za-z0-9]+', text)


def significant(value):
    tokens = words(value)
    return [t for t in tokens if t.lower() not in STOPWORDS] or tokens


def camel(tokens):
    return ''.join(t[:1].upper() + t[1:].lower() for t in tokens)


def candidate(record):
    creators = record.get('author') or record.get('editor')
    if creators:
        first = split_multiple_persons_names(str(creators))[0].strip()
        if first.startswith('{') and first.endswith('}'):
            lead = camel(significant(first)[:3])
        else:
            parts = parse_single_name_into_parts(first)
            lead = camel(words(' '.join(parts.von + parts.last)))
    else:
        lead = camel(significant(record.get('institution') or
                                 record.get('organization') or 'Anon')[:3])
    year = str(record.get('year') or '')
    year = year if re.fullmatch(r'\d{4}', year) else 'nd'
    key = (lead or 'Anon') + year + (camel(significant(record.get('title'))[:3]) or 'Untitled')
    return ('Ref' if key[0].isdigit() else '') + key


def identity(record):
    values = [' '.join(str(record.get(f) or '').split()) for f in IDENTITY_FIELDS]
    return hashlib.sha256(json.dumps(values, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


def assign(records, registry, migrate=False):
    """Return assignments and a new registry; never mutate caller inputs.

    Only migrate=True renames unregistered existing keys. Registered keys and
    legacy aliases always resolve to their permanent assignment.
    """
    registry = json.loads(json.dumps(registry))
    registry.setdefault('schema_version', 1)
    registry.setdefault('rule', POLICY)
    entries = registry.setdefault('entries', [])
    retired = registry.setdefault('reserved_keys', [])
    aliases = {}
    for entry in entries:
        for alias in [entry['key']] + entry['aliases']:
            if alias in aliases and aliases[alias] != entry['key']:
                raise ValueError('Ambiguous registry alias: ' + alias)
            aliases[alias] = entry['key']
    used = {k.casefold() for k in retired}
    used.update(e['key'].casefold() for e in entries)
    used.update(k.casefold() for k in aliases)
    output = [None] * len(records)
    pending = []
    for i, record in enumerate(records):
        old = str(record.get('citation_key') or '')
        if old in aliases:
            output[i] = aliases[old]
        elif old and not migrate:
            if old.casefold() in used or not re.fullmatch(r'[A-Za-z][A-Za-z0-9]*', old):
                raise ValueError('Unregistered key conflicts or is invalid: ' + old)
            output[i] = old
            used.add(old.casefold())
            entries.append({'key': old, 'aliases': [], 'identity_sha256': identity(record)})
        else:
            pending.append((i, old, candidate(record), identity(record)))
    counts = Counter(base.casefold() for _, _, base, _ in pending)
    # Hash sorting makes first-time allocation independent of worksheet order.
    for i, old, base, digest in sorted(pending, key=lambda x: (x[2].casefold(), x[3])):
        key = base
        if counts[base.casefold()] > 1 or key.casefold() in used:
            length = 8
            key = base + 'x' + digest[:length]
            while key.casefold() in used and length < 64:
                length += 4
                key = base + 'x' + digest[:length]
            if key.casefold() in used:
                raise ValueError('Identical citation identities need manual differentiation')
        if any(e['identity_sha256'] == digest for e in entries):
            raise ValueError('Identical citation identities need manual differentiation')
        output[i] = key
        used.add(key.casefold())
        entries.append({'key': key, 'aliases': [old] if old else [],
                        'identity_sha256': digest})
    if len({k.casefold() for k in output}) != len(output):
        raise ValueError('Multiple records resolve to the same citation key')
    return output, registry
