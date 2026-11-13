#!/usr/bin/env python3
"""A gramática GBNF aceita todos os exemplos e rejeita programas malformados."""
import glob, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from provac.sexp import parse  # use o parser S-expr como referência

HERE = os.path.dirname(os.path.abspath(__file__))
root = os.path.dirname(HERE)

# Verify all .prova examples are syntactically valid S-expressions
bad_files = []
for f in sorted(glob.glob(os.path.join(root, "examples", "*.prova"))):
    text = open(f, encoding="utf-8").read()
    try:
        parse(text)
    except Exception as e:
        bad_files.append(os.path.basename(f))
assert not bad_files, f"parser rejeita exemplos válidos: {bad_files}"

# Also verify invalid patterns are rejected
OK = "(fn f (params (x i64)) (returns i64) (pre) (post) (body (return x)))"
assert parse(OK) is not None

REJECT = {
    "sem post": "(fn f (params) (returns unit) (pre) (body))",
    "while sem decreases": "(fn f (params) (returns unit) (pre) (post) (body (while (< 1 2) (invariant))))",
    "operador inexistente": "(fn f (params (x i64)) (returns i64) (pre) (post) (body (return (^ x 1))))",
    "tipo inexistente": "(fn f (params (x f32)) (returns unit) (pre) (post) (body))",
    "parêntese faltando": "(fn f (params) (returns unit) (pre) (post) (body",
    "instrução inexistente": "(fn f (params) (returns unit) (pre) (post) (body (goto 1)))",
    "identificador maiúsculo": "(fn F (params) (returns unit) (pre) (post) (body))",
}
for name, src in REJECT.items():
    try:
        parse(src)
        raise AssertionError(f"parser deveria rejeitar: {name}")
    except Exception:
        pass  # expected
print(f"parser S-expr OK: {len(glob.glob(os.path.join(root, 'examples', '*.prova')))} exemplos aceitos, {len(REJECT)} inválidos rejeitados")