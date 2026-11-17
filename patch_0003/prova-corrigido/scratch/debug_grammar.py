import os
from gbnf import accepts, parse_grammar

rules = parse_grammar(open(os.path.join('spec', 'prova.gbnf', encoding='utf-8')).read())

for name in ['bad_call_len.prova', 'bad_call_pre.prova', 'bad_move.prova', 'calls.prova']:
    with open(os.path.join('examples', name), encoding='utf-8') as f:
        text = f.read()
    result = accepts(rules, text)
    print(f'{name}: {"ACCEPTED" if result else "REJECTED"}')

# Also test the good examples
for name in ['sum_to.prova', 'copy_bytes.prova', 'hello.prova', 'ok_own.prova', 'calls.prova']:
    with open(os.path.join('examples', name), encoding='utf-8') as f:
        text = f.read()
    result = accepts(rules, text)
    print(f'good_{name}: {"ACCEPTED" if result else "REJECTED"}')