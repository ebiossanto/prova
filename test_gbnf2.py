import os
import re
from tests.gbnf import parse_grammar, Matcher

root = r'.'
gbnf_path = os.path.join(root, 'spec', 'prova.gbnf')
rules = parse_grammar(open(gbnf_path, encoding='utf-8').read())

f = os.path.join(root, 'examples', 'calls.prova')
text = open(f, encoding='utf-8').read()
lines = text.splitlines()
cleaned = ' '.join(line.strip() for line in lines if not line.strip().startswith(';;'))

matcher = Matcher(rules, cleaned)

# Tokenize
TOK = re.compile(r'\s*(?:"(?:[^"\\]|\\.)*"|\[(?:[^\]\\]|\\.)*\]|;;[^\n]*\n|([A-Za-z_][\w-]*)|([()|*+?]))')
toks = []
pos = 0
while pos < len(cleaned):
    m = TOK.match(cleaned, pos)
    if not m:
        print(f'Token error at {pos}: {cleaned[pos:pos+30]!r}')
        break
    tok = m.group(1) or m.group(2)
    toks.append(tok)
    pos = m.end()

print(f'Total tokens: {len(toks)}')
print(f'First 30 tokens: {toks[:30]}')

# Try matching root
node = ('ref', 'root')
result = matcher.m(node, 0)
print(f'Root match positions: {result}')

# Check what the full text looks like
print(f'\nCleaned text ({len(cleaned)} chars):')
print(cleaned)