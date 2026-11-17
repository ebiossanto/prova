import sys
sys.path.insert(0, "tests")
from gbnf import parse_grammar, accepts

rules = parse_grammar(open("spec/prova.gbnf", encoding="utf-8").read())

# Test calls.prova
text = open("examples/calls.prova", encoding="utf-8").read()
print("=== calls.prova text ===")
print(repr(text))
print()
print("GBNF accepts:", accepts(rules, text))

# Parse with S-expression
from provac.sexp import parse
forms = parse(text)
print("S-expr forms:", forms)