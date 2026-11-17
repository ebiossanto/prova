"""Memória concorrente: a única memória compartilhada são (static ... (atomic T)); cada operação escolhe a
ordem de memória e ordens ilegais são erro de tipo. O valor lido de um atômico nunca é tratado como estável."""
import re
from _util import build, example, pending, problems, src_error
from provac.mlir import emit_module

CELL = "(static c (atomic usize) 0)\n"


def fn(body, ret="unit", eff="atomic"):
    return CELL + f"(fn f (params) (returns {ret}) (effects {eff}) (pre) (post) (body {body}))"


def test_atomic_counter_example_is_fully_proved():
    P = build(example("atomic_counter"))
    assert not problems(P) and not pending(P)


def test_memory_orders_reach_the_mlir_unchanged():
    P = build(example("atomic_counter"))
    text = emit_module(P.compiled, P.data, "x86_64")
    assert "llvm.mlir.global internal @counter(0 : i64) : i64" in text
    assert re.search(r"llvm\.atomicrmw add .* monotonic", text)
    assert re.search(r"llvm\.store .* atomic release", text)
    assert re.search(r"llvm\.load .* atomic acquire", text)
    assert re.search(r"llvm\.cmpxchg .* acq_rel acquire", text)


def test_illegal_orders_are_type_errors():
    assert "ilegal em atomic_load" in src_error(fn("(return (atomic_load c release))", "usize"))
    assert "ilegal em atomic_load" in src_error(fn("(return (atomic_load c acq_rel))", "usize"))
    assert "ilegal em atomic_store" in src_error(fn("(atomic_store c 1 acquire)"))
    assert "ilegal em atomic_store" in src_error(fn("(atomic_store c 1 acq_rel)"))
    assert "ilegal em atomic_cas (falha)" in src_error(fn("(return (atomic_cas c 0 1 seq_cst release))", "usize"))
    assert "ordem de memória desconhecida" in src_error(fn("(return (atomic_load c acq))", "usize"))


def test_cas_failure_order_cannot_be_stronger_than_success():
    assert "mais forte que a de sucesso" in src_error(fn("(return (atomic_cas c 0 1 relaxed acquire))", "usize"))
    assert "mais forte que a de sucesso" in src_error(fn("(return (atomic_cas c 0 1 acquire seq_cst))", "usize"))
    for ok in ("relaxed relaxed", "acquire acquire", "acq_rel acquire", "seq_cst seq_cst", "release relaxed"):
        assert src_error(fn(f"(return (atomic_cas c 0 1 {ok}))", "usize")) is None, ok


def test_legal_orders_are_accepted():
    for o in ("relaxed", "acquire", "seq_cst"):
        assert src_error(fn(f"(return (atomic_load c {o}))", "usize")) is None
    for o in ("relaxed", "release", "seq_cst"):
        assert src_error(fn(f"(atomic_store c 1 {o})")) is None
    for o in ("relaxed", "acquire", "release", "acq_rel", "seq_cst"):
        assert src_error(fn(f"(do (atomic_fetch_add c 1 {o}))")) is None


def test_atomic_requires_declared_effect_and_declared_cell():
    assert "efeito 'atomic' não declarado" in src_error(fn("(atomic_store c 1 relaxed)", eff=""))
    assert "não é um (static ...) atômico declarado" in src_error(
        "(fn f (params) (returns unit) (effects atomic) (pre) (post) (body (atomic_store nope 1 relaxed)))")


def test_static_declarations_are_validated():
    assert "static espera" in src_error("(static c (atomic u8) 0)\n(fn f (params) (returns unit) (pre) (post) (body))")
    assert "fora da faixa" in src_error("(static c (atomic usize) -1)\n(fn f (params) (returns unit) (pre) (post) (body))")


def test_atomic_values_are_never_assumed_stable():
    # outra thread pode ter escrito: afirmar que o valor lido é 0 NÃO pode ser provado
    P = build(fn("(let r usize (atomic_load c acquire)) (assert (= r 0))"))
    assert any("assert" in p for p in problems(P)), "o verificador assumiu um valor fixo para um atômico"
    # mas a faixa do tipo vale sempre
    assert src_error(fn("(let r usize (atomic_load c acquire)) (assert (<= 0 r))")) is None


def test_atomic_operations_are_not_allowed_in_contracts():
    src = CELL + "(fn f (params) (returns unit) (effects atomic) (pre) (post (= (atomic_load c relaxed) 0)) (body))"
    assert "contrato não suportada" in src_error(src)


def test_operand_types_are_strict():
    assert "recebeu u8" in src_error(CELL + "(fn f (params (x u8)) (returns unit) (effects atomic) (pre) (post) "
                                     "(body (atomic_store c x relaxed)))")
