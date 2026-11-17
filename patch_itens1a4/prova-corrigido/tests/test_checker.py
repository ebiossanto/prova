"""Verificador: exemplos bons são TOTALMENTE provados; exemplos ruins são recusados pelo motivo certo;
regressões de solidez/robustez (achadas na revisão de 13/nov/2026) ficam travadas."""
import os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import prova  # noqa: E402
from provac.check import ProvaError  # noqa: E402
from provac.sexp import ParseError  # noqa: E402

EX = os.path.join(ROOT, "examples")
GOOD = ["sum_to", "copy_bytes", "hello", "ok_own", "calls",
        "x86_64_start", "aarch64_start", "riscv64_start", "kmain_min"]


def results(name):
    return prova.analyse(os.path.join(EX, name + ".prova"))[2]


def failed(res):
    return [o["label"] for r in res for o in r["obligations"] if o["status"] == "failed"]


def linear(res):
    return [e for r in res for e in r["linear_errors"]]


def src_error(src):
    """Devolve a mensagem de erro (ProvaError/ParseError) ou None se aceitou."""
    with tempfile.NamedTemporaryFile("w", suffix=".prova", delete=False, encoding="utf-8") as f:
        f.write(src)
    try:
        _, _, res = prova.analyse(f.name)
    except (ProvaError, ParseError) as e:
        return str(e)
    bad = failed(res) or linear(res)
    return "\n".join(map(str, bad)) if bad else None


def test_good_examples_are_fully_proved():
    for name in GOOD:
        res = results(name)
        assert not failed(res) and not linear(res), name
        pending = [o["label"] for r in res for o in r["obligations"] if o["status"] != "proved"]
        assert not pending, f"{name}: obrigações só testadas/incertas: {pending}"


def test_bad_examples_are_rejected_for_the_right_reason():
    assert any("overflow" in l for l in failed(results("bad_inc")))
    assert any("limites" in l for l in failed(results("bad_bounds")))
    assert any("vazamento" in e for e in linear(results("bad_leak")))
    assert any("chamada clamp: pre" in l for l in failed(results("bad_call_pre")))
    assert any("len(buf) = n" in l for l in failed(results("bad_call_len")))
    assert any("após drop ou movimento" in e for e in linear(results("bad_move")))
    try:
        results("bad_recursion")
    except ProvaError as e:
        assert "recursão" in str(e)
    else:
        raise AssertionError("recursão deveria ser recusada")


def test_strict_types_and_contracts():
    assert "incompatíveis" in src_error("(fn f (params (a i64) (b usize)) (returns i64) (pre) (post) (body (return (+ a b))))")
    assert "terminação" in src_error("(fn f (params (n usize)) (returns unit) (pre) (post) (body (while (< 0 n) (invariant))))")
    assert "(pre" in src_error("(fn f (params) (returns unit) (body))")
    assert "mutável" in src_error("(fn f (params (n usize)) (returns unit) (pre) (post) (body (set n 1)))")


def test_soundness_regressions():
    callee = "(fn g (params (x usize)) (returns usize) (pre) (post (<= 0 result)) (body (return x)))\n"
    assert "argumento cabe em usize" in src_error(callee + "(fn f (params) (returns usize) (pre) (post) (body (return (call g -1))))")
    assert "argumento cabe em u8" in src_error(
        "(fn g (params (x u8)) (returns unit) (pre) (post) (body (return)))\n(fn f (params) (returns unit) (pre) (post) (body (do (call g 300))))")
    assert "fd de sys_write deve ser i64" in src_error(
        '(data m "a")\n(fn f (params (fd usize)) (returns unit) (pre) (post) (body (let_slice b (data-ref m)) (do (sys_write fd b 1))))')
    assert "argumento cabe em i64" in src_error(
        "(fn f (params) (returns unit) (pre) (post) (body (sys_exit 99999999999999999999)))")
    assert "and exige operandos booleanos" in src_error("(fn f (params (x i64) (y i64)) (returns unit) (pre (and x y)) (post) (body))")


def test_robustness_errors_are_structured():
    # antes: KeyError/IndexError/TypeError vazavam como traceback
    assert "não está definida em todos os caminhos" in src_error(
        '(data m "abc")\n(fn f (params (c i64)) (returns unit) (pre) (post) (body (if (< c 0) (then (let_slice b (data-ref m)))) (store b 0 1)))')
    assert "malformada" in src_error("(fn f (params (x)) (returns unit) (pre) (post) (body))")
    assert "tipo inválido" in src_error("(fn f (params) (returns unit) (pre) (post) (body (let x i8 0)))")  # i8 não existe
    assert "forma de topo inválida" in src_error("foo")


def test_report_summary_is_never_negative():
    out = subprocess.run([sys.executable, os.path.join(ROOT, "prova.py"), "check", os.path.join(EX, "bad_leak.prova")],
                         capture_output=True, text=True, encoding="utf-8").stdout
    assert "resumo:" in out and "-1" not in out, out
    assert "1 erros de posse" in out
