import os
os.chdir(r'D:\PROVA linguagem')
from tests.gbnf import parse_grammar, accepts

root = os.getcwd()
gbnf_path = os.path.join(root, 'spec', 'prova.gbnf')
text = open(gbnf_path, encoding='utf-8').read()
rules = parse_grammar(text)

# Print all rules 
for name, rhs in rules.items():
    print(f'{name}: {rhs}')