import sys
sys.path.insert(0, "tests")
from gbnf import parse_grammar, accepts

rules = parse_grammar(open("spec/prova.gbnf", encoding="utf-8").read())

test_cases = [
    ("examples/bad_call_len.prova", False),
    ("examples/bad_call_pre.prova", False),
    ("examples/bad_move.prova", False),
    ("examples/calls.prova", True),  # should be accepted after fix
    ("examples/sum_to.prova", True),
    ("examples/copy_bytes.prova", True),
    ("examples/hello.prova", True),
    ("examples/ok_own.prova", True),
    # Invalid patterns that should be rejected
    ("(fn f (params) (returns unit) (pre) (body))", False, "while sem decreases"),
    ("(fn f (params (x i64)) (returns i64) (pre) (post) (body (return (^ x 1))))", False, "operador inexistente"),
]

for case in test_cases:
    if len(case) == 3:
        text, expected, name = case
    else:
        text, expected = case
        name = text[:40]
    
    result = accepts(rules, open(text, encoding="utf-8").read() if not text.startswith("(fn") else text)
    status = "OK" if result == expected else "FAIL"
    print(f"[{status}] {name}: {'aceita' if result else 'rejeita'} (esperado: {'aceita' if expected else 'rejeita'})")