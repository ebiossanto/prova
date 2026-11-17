import sys
sys.path.insert(0, "tests")
from gbnf import parse_grammar

rules = parse_grammar(open("spec/prova.gbnf", encoding="utf-8").read())

# Tokenize the calls.prova text
import re
TOK = re.compile(r'\s*(?:("(?:[^"\\]|\\.)*")|(\[(?:[^\]\\]|\\.)*\])|([A-Za-z_][\w-]*)|([()|*+?]))')

src = open("examples/calls.prova", encoding="utf-8").read()
print("Tokenizing calls.prova...")
pos = 0
while pos < len(src):
    m = TOK.match(src, pos)
    if not m:
        print(f"NO MATCH at pos {pos}: {src[pos:pos+30]!r}")
        break
    groups = m.groups()
    # Find which group matched
    for i, g in enumerate(groups):
        if g is not None:
            print(f"  pos {pos}: group {i} = {g!r} (type: {TOK.pattern})")
            break
    pos = m.end()