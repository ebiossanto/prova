import sys
sys.path.insert(0, "tests")
from gbnf import parse_grammar, accepts

rules = parse_grammar(open("spec/prova.gbnf", encoding="utf-8").read())

# Test simple call expression
test1 = "(call zero_fill 5 buf)"
print(f"Test 1 (call zero_fill 5 buf): {accepts(rules, test1)}")

# Test call within do
test2 = "(do (call zero_fill 5 buf))"
print(f"Test 2 (do (call zero_fill 5 buf)): {accepts(rules, test2)}")

# Test the full caller example from bad_call_len
test3 = "(fn caller (params (m usize) (buf (slice u8 m))) (returns unit) (pre) (post) (body (do (call zero_fill 5 buf))))"
print(f"Test 3 (fn caller ...): {accepts(rules, test3)}")

# Test just the call part
test4 = "(call zero_fill 5 buf)"
print(f"Test 4 (call zero_fill 5 buf): {accepts(rules, test4)}")

# Test bad_call_len.prova cleaned
with open("examples/bad_call_len.prova", encoding="utf-8") as f:
    text = f.read()
cleaned = "\n".join(line for line in text.splitlines() if not line.strip().startswith(";;"))
print(f"\nbad_call_len.prova cleaned accepted: {accepts(rules, cleaned)}")