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
    "atomic não é tipo de parâmetro": "(fn f (params (x (atomic usize))) (returns unit) (pre) (post) (body))\n",
    "efeito inexistente": "(fn f (params) (returns unit) (effects magic) (pre) (post) (body))\n",
    "ordem inexistente": "(static c (atomic usize) 0)\n(fn f (params) (returns usize) (pre) (post) (body (return (atomic_load c acq))))\n",
    "static não atômico": "(static c (plain usize) 0)\n",
    "static com tipo pequeno": "(static c (atomic u8) 0)\n",
    "orçamento sem inteiro": "(fn f (params) (returns unit) (stack-budget big) (pre) (post) (body))\n",
    "região com maiúscula": "(region NetRx)\n",
    "cláusulas fora de ordem": "(fn f (params) (returns unit) (pre) (effects syscall) (post) (body))\n",
}


def test_grammar_accepts_every_example():
    files = sorted(glob.glob(os.path.join(ROOT, "examples", "*.prova")))
    assert len(files) >= 9
    rejected = [os.path.basename(f) for f in files if not accepts(RULES, open(f, encoding="utf-8").read())]
    assert not rejected, f"a gramática rejeita exemplos válidos: {rejected}"


def test_grammar_accepts_the_new_constructs():
    ok = [
        "(region net-rx)\n(region kmem)\n(deny-flow net-rx @write)\n(deny-flow kmem @static:box)\n",
        "(static box (atomic usize) 0)\n(static neg (atomic i64) -5)\n",
        '(data msg "x" rodata)\n',
        "(fn f (params (n usize) (b (slice u8 n net-rx)) (c (own (slice u8 n kmem)))) (returns unit) (effects syscall atomic) "
        "(stack-budget 256) (pre) (post) (body (atomic_store box 1 release) (do (atomic_fetch_add box 1 acq_rel)) "
        "(return)))\n",
        "(fn f (params) (returns usize) (pre) (post) (body (return (atomic_cas box 0 1 acq_rel acquire))))\n",
        "(region hw)\n(mmio reg0 268435456 usize hw)\n(deny-flow hw @mmio:reg0)\n"
        "(fn f (params (n usize) (b (slice u8 n))) (returns usize) (effects mmio) (pre (< 0 n)) "
        "(post (forall k 0 n (= (load b k) (old (load b k))))) "
        "(body (mmio_write reg0 (shl (bit_and (add_wrap (mmio_read reg0) 1) 63) 2)) (return 0)))\n",
    ]
    for src in ok:
        assert accepts(RULES, src), src


def test_grammar_accepts_both_comment_styles_like_the_reader():
    assert accepts(RULES, "; um\n;; dois\n" + OK + "(region a) ; fim de linha\n")


def test_grammar_accepts_call_with_several_arguments():
    assert accepts(RULES, "(fn f (params) (returns i64) (pre) (post) (body (return (call g 1 2 3))))\n")


def test_grammar_rejects_invalid_programs():
    assert accepts(RULES, OK)
    wrongly_accepted = [n for n, s in REJECT.items() if accepts(RULES, s)]
    assert not wrongly_accepted, f"a gramática aceitou programas inválidos: {wrongly_accepted}"
