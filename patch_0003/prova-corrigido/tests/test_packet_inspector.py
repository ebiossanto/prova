"""O programa de teste (examples/packet_inspector.prova) e erros realistas nele: cada bug plausível é recusado
pelo verificador pelo motivo certo, e o mesmo bug falha também em tempo de execução."""
from _util import build, example, pending, problems
from provac.interp import RunError, run

BASE = example("packet_inspector")


def mutated(old, new):
    assert old in BASE, old
    return BASE.replace(old, new, 1)


def test_the_unmodified_program_is_fully_proved_and_clean():
    P = build(BASE)
    assert not problems(P) and not pending(P)
    assert len([o for r in P.results for o in r["obligations"]]) >= 55


def test_off_by_one_in_the_loop_is_caught_statically_and_at_runtime():
    src = mutated("(while (< i n)\n      (invariant (<= i n) (<= s (* 255 i)))", "(while (<= i n)\n      (invariant (<= i n) (<= s (* 255 i)))")
    assert any("limites" in p for p in problems(build(src)))
    try:
        run(build(src))
    except RunError as e:
        assert "fora dos limites" in str(e)
    else:
        raise AssertionError("o mesmo bug deveria falhar na execução")


def test_missing_length_check_is_caught():
    src = mutated("    (if (< n 2) (then (return 0)))\n", "")
    assert any("limites" in p and "load buf 0" in p for p in problems(build(src)))   # n pode ser 0


def test_leaking_packet_data_to_output_violates_the_policy():
    src = mutated("(effects atomic)\n  (stack-budget 256)\n  (pre (<= n 4096))\n  (post (<= result 1))\n  (body\n    (let ok usize",
                  "(effects atomic syscall)\n  (stack-budget 256)\n  (pre (<= n 4096))\n  (post (<= result 1))\n  (body\n    (do (sys_write 1 pkt n))\n    (let ok usize")
    ps = problems(build(src))
    assert any("fluxo proibido net-rx → @write" in p for p in ps), ps


def test_forgotten_effect_declaration_is_caught():
    src = mutated("(effects atomic)\n  (stack-budget 256)", "(effects)\n  (stack-budget 256)")
    assert any("efeito 'atomic' não declarado" in p for p in problems(build(src)))


def test_stack_budget_too_small_is_caught():
    src = mutated("(stack-budget 256)", "(stack-budget 100)")
    assert any(p.startswith("pilha: inspect") for p in problems(build(src)))


def test_wrong_checksum_breaks_the_loop_invariant():
    src = mutated("(set s (+ s (cast usize (load buf i))))", "(set s (+ s (* 2 (cast usize (load buf i)))))")
    assert any("invariante preservada" in p for p in problems(build(src)))
