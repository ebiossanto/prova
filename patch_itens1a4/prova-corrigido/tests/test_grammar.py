"""A gramática GBNF (spec/prova.gbnf) é testada DE VERDADE com um mini-interpretador de GBNF:
aceita todos os exemplos de examples/ e rejeita programas inválidos. (Nunca use o leitor de
S-expressions como substituto: ele aceitaria quase tudo.)"""
import glob, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gbnf import accepts, parse_grammar  # noqa: E402

ROOT = os.path.dirname(HERE)
RULES = parse_grammar(open(os.path.join(ROOT, "spec", "prova.gbnf"), encoding="utf-8").read())
OK = "(fn f (params (x i64)) (returns i64) (pre) (post) (body (return x)))\n"

REJECT = {
    "sem post": "(fn f (params) (returns unit) (pre) (body))\n",
    "while sem decreases": "(fn f (params) (returns unit) (pre) (post) (body (while (< 1 2) (invariant))))\n",
    "operador inexistente": "(fn f (params (x i64)) (returns i64) (pre) (post) (body (return (^ x 1))))\n",
    "tipo inexistente": "(fn f (params (x f32)) (returns unit) (pre) (post) (body))\n",
    "parêntese faltando": "(fn f (params) (returns unit) (pre) (post) (body)\n",
    "instrução inexistente": "(fn f (params) (returns unit) (pre) (post) (body (goto 1)))\n",
    "identificador maiúsculo": "(fn F (params) (returns unit) (pre) (post) (body))\n",
    "u32 não existe": "(fn f (params (x u32)) (returns unit) (pre) (post) (body))\n",
    "atomic não existe": "(fn f (params (x (atomic u32))) (returns unit) (pre) (post) (body))\n",
}


def test_grammar_accepts_every_example():
    files = sorted(glob.glob(os.path.join(ROOT, "examples", "*.prova")))
    assert len(files) >= 9
    rejected = [os.path.basename(f) for f in files if not accepts(RULES, open(f, encoding="utf-8").read())]
    assert not rejected, f"a gramática rejeita exemplos válidos: {rejected}"


def test_grammar_accepts_call_with_several_arguments():
    assert accepts(RULES, "(fn f (params) (returns i64) (pre) (post) (body (return (call g 1 2 3))))\n")


def test_grammar_rejects_invalid_programs():
    assert accepts(RULES, OK)
    wrongly_accepted = [n for n, s in REJECT.items() if accepts(RULES, s)]
    assert not wrongly_accepted, f"a gramática aceitou programas inválidos: {wrongly_accepted}"
