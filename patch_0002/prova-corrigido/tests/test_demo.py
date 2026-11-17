"""Demonstração de ponta a ponta (examples/driver_demo.prova): contratos, posse/tamanhos, efeitos, regiões com
política, pilha, atômicos e syscalls juntos; e as três visões que o humano usa (audit, flow, stack)."""
from _util import build, example, pending, problems
from provac import flow as flowmod
from provac.audit import audit
from provac.mlir import emit_module
from provac.program import load_text


def test_demo_is_fully_proved_with_no_policy_errors():
    P = build(example("driver_demo"))
    assert not problems(P) and not pending(P)


def test_audit_view_has_only_what_a_human_needs_to_read():
    _, fns, meta = load_text(example("driver_demo"))
    text = audit(fns, meta)
    for needle in ("política  deny-flow net-rx @write", "static    received: (atomic usize) = 0",
                   "exige    (<= n m)", "efeitos  atomic", "efeitos  syscall", "efeitos  nenhum (pura)",
                   "pilha    ≤ 256 bytes", "corpo    chama copy_in"):
        assert needle in text, needle
    assert "invariant" not in text and "while" not in text   # o corpo não precisa ser lido


def test_flow_and_stack_views():
    P = build(example("driver_demo"))
    assert flowmod.concrete_edges(P.fns, P.summaries) == {
        ("net-rx", "kmem"): "copy_in", ("rodata", "@write"): "announce"}
    assert P.worst["on_packet"] == (144, ["on_packet", "copy_in"])   # modelo: 64 + 80


def test_demo_emits_on_every_target():
    P = build(example("driver_demo"))
    for t in ("x86_64", "aarch64", "riscv64"):
        text = emit_module(P.compiled, P.data, t)
        assert "llvm.atomicrmw add" in text and "func.call @copy_in" in text and "llvm.inline_asm" in text
