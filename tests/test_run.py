"""Interpretador de referência: executa programas Prova e confere em tempo de execução o que o verificador
prometeu. Teste diferencial: programas verificados não podem violar nada; programas recusados são pegos."""
import os, subprocess, sys
from _util import ROOT, build, example
from provac.interp import RunError, fuzz_function, run

VERIFIED = ["sum_to", "copy_bytes", "calls", "effects", "regions_flow", "stack_budget", "atomic_counter",
            "packet_inspector", "driver_demo", "ok_own", "selftest", "ring_buffer", "sort_perm"]


def prog(body, statics="", params="", ret="unit", pre="", post=""):
    return f"{statics}\n(fn f (params {params}) (returns {ret}) (effects syscall atomic) (pre {pre}) (post {post}) (body {body}))"


def test_packet_inspector_runs_with_the_expected_result():
    res, _ = run(build(example("packet_inspector")))
    assert res.stdout == b"ACCEPT\nDROP\nDROP\n"
    assert res.exit_code == 1                       # um pacote aceito
    assert res.statics == {"accepted": 1, "dropped": 2, "last_sum": sum(b"PING hello")}


def test_cli_run_prints_output_and_returns_the_program_exit_code():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "prova.py"), "run",
                        os.path.join(ROOT, "examples", "packet_inspector.prova")],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.stdout == "ACCEPT\nDROP\nDROP\n" and r.returncode == 1
    assert "interpretador de referência" in r.stderr


def test_run_refuses_unverified_programs_unless_forced():
    path = os.path.join(ROOT, "examples", "bad_inc.prova")
    cli = lambda *a: subprocess.run([sys.executable, os.path.join(ROOT, "prova.py"), "run", path, "--entry-fn", "inc", *a],
                                    capture_output=True, text=True, encoding="utf-8")
    assert cli().returncode == 2 and "não passou na verificação" in cli().stderr


def test_runtime_reproduces_the_verifier_counterexamples():
    inc = build(example("bad_inc"))       # o verificador diz: x = 2**63-1 estoura
    try:
        run(inc, "inc", [2**63 - 1])
    except RunError as e:
        assert "overflow" in str(e)
    else:
        raise AssertionError("o contraexemplo do verificador não reproduziu em tempo de execução")
    from provac.interp import Slice
    fill = build(example("bad_bounds"))   # o verificador diz: len = n escreve fora do buffer
    try:
        run(fill, "fill", [3, Slice(b"abc"), 3])
    except RunError as e:
        assert "fora dos limites" in str(e)
    else:
        raise AssertionError("escrita fora dos limites não foi detectada")


def test_differential_fuzz_verified_programs_never_violate_anything():
    total = 0
    for name in VERIFIED:
        P = build(example(name))
        for fn in P.fns:
            if fn.name == "_start":
                continue
            executed, violations = fuzz_function(P, fn.name, runs=120, seed=11)
            assert executed > 0, f"{name}.{fn.name}: nenhuma entrada satisfez a pre (teste sem poder)"
            assert not violations, f"{name}.{fn.name}: o verificador aceitou, mas em execução: {violations[:2]}"
            total += executed
    assert total > 1000


def test_fuzz_finds_the_bugs_in_programs_the_verifier_rejects():
    for name, fn in (("bad_inc", "inc"), ("bad_bounds", "fill")):
        executed, violations = fuzz_function(build(example(name)), fn, runs=600, seed=3)
        assert violations, f"{name}: o fuzzing não achou o bug que o verificador apontou"


def test_runtime_checks_contracts_invariants_and_variants():
    wrong_post = build("(fn f (params (x usize)) (returns usize) (pre (<= x 5)) (post (= result (+ x 1))) (body (return x)))")
    try:
        run(wrong_post, "f", [2])
    except RunError as e:
        assert "pós-condição de f violada" in str(e)
    else:
        raise AssertionError
    bad_inv = build("(fn f (params) (returns unit) (pre) (post) (body (var i usize 0) "
                    "(while (< i 5) (invariant (< i 3)) (decreases (- 5 i)) (set i (+ i 1)))))")
    try:
        run(bad_inv, "f")
    except RunError as e:
        assert "invariante violada" in str(e)
    else:
        raise AssertionError
    bad_var = build("(fn f (params) (returns unit) (pre) (post) (body (var i usize 0) "
                    "(while (< i 5) (invariant) (decreases 9) (set i (+ i 1)))))")
    try:
        run(bad_var, "f")
    except RunError as e:
        assert "variante não decresceu" in str(e)
    else:
        raise AssertionError
    pre = build("(fn f (params (x usize)) (returns unit) (pre (<= x 5)) (post) (body))")
    try:
        run(pre, "f", [9])
    except RunError as e:
        assert "pré-condição de f violada" in str(e)
    else:
        raise AssertionError


def test_atomic_semantics_at_runtime():
    cas = build(prog("(return (atomic_cas c 5 9 seq_cst seq_cst))", "(static c (atomic usize) 5)", ret="usize"))
    r, _ = run(cas, "f")
    assert r.returned == 5 and r.statics["c"] == 9                  # casou: troca e devolve o antigo
    cas2 = build(prog("(return (atomic_cas c 5 9 seq_cst seq_cst))", "(static c (atomic usize) 7)", ret="usize"))
    r, _ = run(cas2, "f")
    assert r.returned == 7 and r.statics["c"] == 7                  # não casou: não troca
    wrap = build(prog("(return (atomic_fetch_add c 1 relaxed))", "(static c (atomic usize) 18446744073709551615)", ret="usize"))
    r, _ = run(wrap, "f")
    assert r.returned == 2**64 - 1 and r.statics["c"] == 0          # dá a volta (wrap) por definição


def test_syscall_semantics_at_runtime():
    P = build('(data m "hi")\n' + "(fn f (params) (returns i64) (effects syscall) (pre) (post) "
              "(body (let_slice b (data-ref m)) (do (sys_write 2 b (len b))) (return (sys_write 7 b (len b)))))")
    r, _ = run(P, "f")
    assert r.stderr == b"hi" and r.stdout == b"" and r.returned == -9   # fd 2 -> stderr; fd inválido -> EBADF


def test_out_of_fuel_is_inconclusive_not_a_violation():
    # regressão: o limite era contado como VIOLAÇÃO (falso positivo) e o fuzzing de gcd com entradas grandes travava.
    # Dois caminhos de combustível: limite de ITERAÇÕES do laço (gcd: poucas instruções por volta) e limite de
    # PASSOS (sort: muitas instruções por volta). Os dois precisam ser inconclusivos.
    from provac.interp import Inconclusive, Machine, RunError, Slice
    P = build(example("selftest"))
    data = bytes((i * 7) % 256 for i in range(300))
    for name, args in (("gcd", [1000, 1]), ("sort", [len(data), Slice(data)])):
        try:
            Machine(P, check=True, fuel=50).call(name, args)
        except Inconclusive:
            pass
        else:
            raise AssertionError(f"{name} deveria esgotar o combustível")
    assert issubclass(Inconclusive, RunError)
    executed, violations = fuzz_function(P, "gcd", runs=120, seed=3)
    assert executed > 0 and not violations, violations[:2]
