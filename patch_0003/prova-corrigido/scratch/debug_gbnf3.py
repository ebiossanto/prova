import sys
sys.path.insert(0, "tests")
from gbnf import parse_grammar, accepts

rules = parse_grammar(open("spec/prova.gbnf", encoding="utf-8").read())

# Test each example
examples = [
    "examples/bad_call_len.prova",
    "examples/bad_call_pre.prova", 
    "examples/bad_move.prova",
    "examples/calls.prova",
    "examples/sum_to.prova",
    "examples/copy_bytes.prova",
    "examples/hello.prova",
    "examples/ok_own.prova",
]

for path in examples:
    with open(path, encoding="utf-8") as f:
        text = f.read()
    # Strip comment lines
    cleaned = "\n".join(line for line in text.splitlines() if not line.strip().startswith(";;"))
    result = accepts(rules, cleaned)
    basename = path.split("/")[-1]
    print(f"{basename}: {'ACCEPTED' if result else 'REJECTED'} (chars={len(cleaned)})")