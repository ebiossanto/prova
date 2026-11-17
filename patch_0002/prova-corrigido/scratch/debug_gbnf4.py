import sys
sys.path.insert(0, "tests")
from gbnf import parse_grammar, accepts, Matcher

rules = parse_grammar(open("spec/prova.gbnf", encoding="utf-8").read())

# Test bad_call_len.prova
with open("examples/bad_call_len.prova", encoding="utf-8") as f:
    text = f.read()
cleaned = "\n".join(line for line in text.splitlines() if not line.strip().startswith(";;"))
print("=== bad_call_len.prova cleaned ===")
print(repr(cleaned[:100]))
print()

m = Matcher(rules, cleaned)
# Try matching from root
result = m.m(("ref", "root"), 0)
print(f"Match result from root: {result}")
print(f"Text length: {len(cleaned)}")
print(f"Full match: {len(cleaned) in result}")

# Let's also try matching the fn rule
fn_result = m.m(("ref", "fn"), 0)
if fn_result:
    print(f"Match result from fn: {list(fn_result)[:5]}")
else:
    print("Match result from fn: empty")

# Try matching a simple fn pattern
simple = "(fn f (params (x i64)) (returns i64) (pre) (post) (body (return x)))"
simple_cleaned = "\n".join(line for line in simple.splitlines() if not line.strip().startswith(";;"))
print(f"\nSimple fn accepted: {accepts(rules, simple_cleaned)}")