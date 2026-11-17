"""Regiões nos tipos e fluxo de dados: o relatório mostra por onde o dado passa e (deny-flow A B) o impede,
inclusive de forma transitiva e através de chamadas."""
import os, subprocess, sys
from _util import ROOT, build, example, problems, src_error
from provac import flow as flowmod

REG = "(region net-rx)\n(region kmem)\n"
COPY = '''(fn copy (params (n usize) (src (slice u8 n net-rx)) (m usize) (dst (slice u8 m kmem)))
  (returns unit) (effects) (pre (<= n m)) (post)
  (body (var i usize 0)
    (while (< i n) (invariant (<= i n)) (decreases (- n i))
      (store dst i (load src i)) (set i (+ i 1)))))\n'''


def edges(src):
    P = build(src)
    return {k: v for k, v in flowmod.concrete_edges(P.fns, P.summaries).items()}


def test_allowed_flow_is_reported_and_policy_holds():
    P = build(example("regions_flow"))
    assert not problems(P)
    assert edges(example("regions_flow")) == {("net-rx", "kmem"): "copy_packet"}
    text = flowmod.report(P.fns, P.summaries, P.meta["denies"])
    assert "net-rx → kmem" in text and "deny-flow net-rx @write" in text


def test_transitive_violation_through_memory_is_caught():
    e = src_error(example("bad_flow"))
    assert "fluxo proibido net-rx → @write" in e
    assert "net-rx → kmem em copy_packet" in e and "kmem → @write em leak" in e


def test_direct_violation():
    src = REG + '(deny-flow net-rx @write)\n' + '''(fn f (params (n usize) (b (slice u8 n net-rx))) (returns unit) (effects syscall)
  (pre) (post) (body (do (sys_write 1 b n))))'''
    assert "fluxo proibido net-rx → @write" in src_error(src)


def test_region_mismatch_in_call_and_undeclared_region():
    src = REG + COPY + '''(fn g (params (n usize) (a (slice u8 n kmem)) (m usize) (b (slice u8 m kmem))) (returns unit)
  (effects) (pre (<= n m)) (post) (body (do (call copy n a m b))))'''
    assert "região incompatível" in src_error(src)
    assert "não declarada" in src_error("(fn f (params (n usize) (b (slice u8 n ghost))) (returns unit) (pre) (post) (body))")


def test_flow_through_a_scalar_variable():
    src = REG + '''(fn f (params (n usize) (src (slice u8 n net-rx)) (dst (slice u8 n kmem))) (returns unit)
  (effects) (pre (< 0 n)) (post)
  (body (let x u8 (load src 0)) (var y u8 0) (set y x) (store dst 0 y)))'''
    assert ("net-rx", "kmem") in edges(src)


def test_generic_region_parameters_are_instantiated_at_each_call():
    # mv não declara regiões: o fluxo é "região do param 0 → região do param 1" e só vira concreto na chamada
    src = REG + '''(fn mv (params (n usize) (a (slice u8 n)) (b (slice u8 n))) (returns unit) (effects) (pre (< 0 n)) (post)
  (body (store b 0 (load a 0))))
(fn use (params (n usize) (p (slice u8 n net-rx)) (q (slice u8 n kmem))) (returns unit) (effects) (pre (< 0 n)) (post)
  (body (do (call mv n p q))))'''
    assert edges(src) == {("net-rx", "kmem"): "use"}
    assert "fluxo proibido net-rx → kmem" in src_error(src.replace(REG, REG + "(deny-flow net-rx kmem)\n"))


def test_flow_through_atomic_cells():
    src = REG + "(static box (atomic usize) 0)\n" + '''(fn f (params (n usize) (src (slice u8 n net-rx))) (returns unit) (effects atomic)
  (pre (< 0 n)) (post) (body (atomic_store box (cast usize (load src 0)) relaxed)))'''
    assert ("net-rx", "@static:box") in edges(src)
    assert "fluxo proibido net-rx → @static:box" in src_error(src.replace(REG, REG + "(deny-flow net-rx @static:box)\n"))


def test_deny_flow_endpoints_are_validated():
    assert "não é região declarada" in src_error("(deny-flow ghost @write)\n(fn f (params) (returns unit) (pre) (post) (body))")


def test_dot_output_and_cli_exit_codes():
    run = lambda *a: subprocess.run([sys.executable, os.path.join(ROOT, "prova.py"), *a], capture_output=True,
                                    text=True, encoding="utf-8")
    ok = run("flow", os.path.join(ROOT, "examples", "regions_flow.prova"), "--dot")
    assert ok.returncode == 0 and "digraph flow" in ok.stdout and '"net-rx" -> "kmem"' in ok.stdout
    assert run("flow", os.path.join(ROOT, "examples", "bad_flow.prova")).returncode == 1
