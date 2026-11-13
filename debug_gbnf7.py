import sys
sys.path.insert(0, "tests")
from gbnf import parse_grammar, accepts

rules = parse_grammar(open("spec/prova.gbnf", encoding="utf-8").read())

# Test bad_call_len.prova
with open("examples/bad_call_len.prova", encoding="utf-8") as f:
    text = f.read()
lines = text.splitlines()
cleaned = []
for line in lines:
    stripped = line.strip()
    if stripped.startswith(";;"):
        continue
    cleaned.append(line)
cleaned_text = "\n".join(cleaned)
print("=== bad_call_len.prova cleaned ===")
print(cleaned_text[:200])
print()

# Parse with S-expr from provac
from provac.sexp import parse
try:
    forms = parse(cleaned_text)
    print("S-expr parse OK:", len(forms), "forms")
except Exception as e:
    print("S-expr parse ERROR:", e)

# Now let's try to understand the GBNF matching issue
# The expr rule has: | "(" ws "call" ws ident ws expr* ws ")"
# But the tokenizer might not handle 'call' properly in all contexts