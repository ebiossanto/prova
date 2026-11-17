from provac.sexp import parse

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
    print(f"\n=== {path} ===")
    try:
        forms = parse(open(path, encoding="utf-8").read())
        print(f"  OK: {len(forms)} forms")
        for f in forms[:3]:
            print(f"    {f}")
    except Exception as e:
        print(f"  ERROR: {e}")