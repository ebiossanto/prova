"""examples/selftest.prova: programa de TESTE escrito em Prova.
Estaticamente: tudo provado (segurança de memória, ausência de overflow, terminação, contratos, política de fluxo).
Dinamicamente: roda os casos e imprime PASS/FAIL. A CORREÇÃO FUNCIONAL de sort/reverse/gcd/... (que contratos ainda não
expressam, pois o conteúdo de fatias não é modelado) é conferida aqui, executando contra o Python."""
import math, random
from _util import build, example, pending, problems
from provac.interp import Slice, fuzz_function, run
from provac.mlir import emit_module

P = build(example("selftest"))


def mutate(src, fn, old, new):
    """Troca `old` por `new` SÓ dentro de (fn <fn> ...). Se o padrão não existir ali, o teste falha dizendo qual
    (um replace global pegaria a primeira ocorrência de outra função: o teste ficaria acoplado à ordem do arquivo)."""
    head, sep, rest = src.partition(f"(fn {fn}\n")
    assert sep, f"função {fn} não encontrada em selftest.prova"
    body, nxt, tail = rest.partition("\n(fn ")
    assert old in body, f"padrão {old!r} não encontrado em (fn {fn}): atualize o teste junto com o exemplo"
    return head + sep + body.replace(old, new, 1) + nxt + tail


def call(prog, name, *args):
    res, _ = run(prog, name, list(args))
    return res.returned


def sorted_by_prova(prog, data):
    s = Slice(data)
    run(prog, "sort", [len(data), s])
    return bytes(s.data)


def reversed_by_prova(prog, data):
    s = Slice(data)
    run(prog, "reverse", [len(data), s])
    return bytes(s.data)


def inputs(seed, count=300, max_len=40):
    rnd = random.Random(seed)
    yield b""
    yield b"\x00"
    yield bytes(range(255, 245, -1))          # decrescente
    yield bytes([7] * 9)                      # todos iguais
    for _ in range(count):
        yield bytes(rnd.randrange(256) for _ in range(rnd.randrange(max_len + 1)))


def test_selftest_is_fully_proved_with_nothing_merely_tested():
    assert not problems(P) and not pending(P)
    assert sum(len(r["obligations"]) for r in P.results) > 150


def test_selftest_runs_and_prints_pass():
    res, _ = run(P)
    assert res.stdout == b"PASS\n" and res.exit_code == 0


def test_a_wrong_case_is_caught_at_runtime_but_not_by_the_verifier():
    wrong = mutate(example("selftest"), "_start", "(call sum_bytes (len s) s) 1129)", "(call sum_bytes (len s) s) 1130)")
    Q = build(wrong)
    assert not problems(Q), "o conteúdo de `sample` não é modelado: o verificador não pode saber que 1130 está errado"
    res, _ = run(Q)
    assert res.stdout == b"FAIL\n" and res.exit_code == 1


def test_sort_matches_python_sorted():
    for data in inputs(1):
        assert sorted_by_prova(P, data) == bytes(sorted(data)), data


def test_reverse_matches_python():
    for data in inputs(2):
        assert reversed_by_prova(P, data) == data[::-1], data


def test_gcd_matches_math_gcd():
    rnd = random.Random(3)
    for _ in range(300):
        a, b = rnd.randrange(1, 400), rnd.randrange(1, 400)
        assert call(P, "gcd", a, b) == math.gcd(a, b), (a, b)


def test_sum_count_max_match_python():
    for data in inputs(4, max_len=60):
        n = len(data)
        assert call(P, "sum_bytes", n, Slice(data)) == sum(data)
        for v in (0, 111, 255):
            assert call(P, "count_byte", n, Slice(data), v) == data.count(v)
        if n:
            assert call(P, "max_byte", n, Slice(data)) == max(data)


def test_no_runtime_violation_in_any_function_of_the_program():
    for fn in P.fns:
        if fn.name != "_start":
            executed, violations = fuzz_function(P, fn.name, runs=150, seed=5)
            assert executed > 0 and not violations, (fn.name, violations[:2])


def test_functional_tests_have_teeth():
    # uma ordenação ao contrário é SEGURA (o verificador aceita) mas errada: só a execução denuncia
    bad = mutate(example("selftest"), "sort", "(if (> x y)", "(if (< x y)")
    Q = build(bad)
    assert not problems(Q)
    assert any(sorted_by_prova(Q, d) != bytes(sorted(d)) for d in inputs(1, count=50)), "teste sem poder"
    # e uma reversão que para cedo
    bad2 = mutate(example("selftest"), "reverse", "(while (< (+ lo 1) hi)", "(while (< (+ lo 2) hi)")
    Q2 = build(bad2)
    assert not problems(Q2)
    assert any(reversed_by_prova(Q2, d) != d[::-1] for d in inputs(2, count=50)), "teste sem poder"


def test_selftest_emits_for_every_target():
    for t in ("x86_64", "aarch64", "riscv64"):
        text = emit_module(P.compiled, P.data, t)
        for needle in ("func.func @sort", "func.func @gcd", "arith.cmpi ult", "llvm.inline_asm"):
            assert needle in text, (t, needle)
