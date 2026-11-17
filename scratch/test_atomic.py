import os
import sys
sys.path.insert(0, r'D:\PROVA lenguaje')
from tests.gbnf import parse_grammar, accepts
from provac.sexp import parse

root = r'D:\PROVA lenguaje'
gbnf_path = os.path.join(root, 'spec', 'prova.gbnf')
text = open(gbnf_path, encoding='utf-8').read()
rules = parse_grammar(text)

# Test atomic type syntax
test_cases = [
    '(fn test (params (x (atomic u32))) (returns i64) (pre) (post) (body (return x)))',
]

for tc in test_cases:
    lines = tc.splitlines()
    cleaned = ' '.join(line.strip() for line in lines if not line.strip().startswith(';;'))
    result = accepts(rules, cleaned)
    print(f'GBNF accepts: {result}')
    if result:
        try:
            parsed = parse(cleaned)
            print(f'  S-expression: OK, got {parsed}')
        except Exception as e:
            print(f'  S-expression: ERROR - {e}')