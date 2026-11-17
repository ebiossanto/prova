import os
os.chdir('D:/PROVA lenguaje')
from tests.gbnf import parse_grammar, accepts

root = os.getcwd()
gbnf_path = os.path.join(root, 'spec', 'prova.gbnf')
text = open(gbnf_path, encoding='utf-8').read()
rules = parse_grammar(text)

# Test all examples
print("=== GBNF acceptance test ===")
examples_dir = os.path.join(root, 'examples')
success = 0
failed = 0
for f in sorted(os.listdir(examples_dir)):
    if not f.endswith('.prova'):
        continue
    filepath = os.path.join(examples_dir, f)
    text = open(filepath, encoding='utf-8').read()
    lines = text.splitlines()
    cleaned = ' '.join(line.strip() for line in lines if not line.strip().startswith(';;'))
    result = accepts(rules, cleaned)
    name = f
    status = 'OK' if result else 'REJECTED'
    if result:
        success += 1
    else:
        failed += 1
    print(f'{status}: {name}')

print(f'\n=== Results: {success} accepted, {failed} rejected ===')