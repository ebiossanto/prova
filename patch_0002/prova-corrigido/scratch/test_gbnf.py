import os
from tests.gbnf import parse_grammar, accepts
from provac.sexp import parse

root = os.getcwd()
gbnf_path = os.path.join(root, 'spec', 'prova.gbnf')
rules = parse_grammar(open(gbnf_path, encoding='utf-8').read())

# Check all examples
print("=== GBNF acceptance test ===")
examples_dir = os.path.join(root, 'examples')
for f in sorted(os.listdir(examples_dir)):
    if not f.endswith('.prova'):
        continue
    filepath = os.path.join(examples_dir, f)
    text = open(filepath, encoding='utf-8').read()
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(';;'):
            continue
        cleaned.append(stripped)
    cleaned_text = ' '.join(cleaned)
    result = accepts(rules, cleaned_text)
    status = 'OK' if result else 'REJECTED'
    print(f'{status}: {f}')
    if not result:
        # Try S-expression parser
        try:
            parsed = parse(text)
            print(f'  S-expression: OK')
        except Exception as e:
            print(f'  S-expression: ERROR - {e}')

print("\n=== Testing calls.prova specifically ===")
f = os.path.join(root, 'examples', 'calls.prova')
text = open(f, encoding='utf-8').read()
lines = text.splitlines()
cleaned = []
for line in lines:
    stripped = line.strip()
    if stripped.startswith(';;'):
        continue
    cleaned.append(stripped)
cleaned_text = ' '.join(cleaned)
result = accepts(rules, cleaned_text)
print(f'GBNF accepts calls.prova: {result}')
try:
    parsed = parse(text)
    print(f'S-expression parser: OK, got {parsed}')
except Exception as e:
    print(f'S-expression parser error: {e}')