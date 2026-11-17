"""Efeitos na assinatura: sem (effects ...) a função é pura; o efeito de um chamado propaga ao chamador."""
from _util import ROOT, build, example, pending, problems, src_error  # noqa: F401
from provac.audit import audit
from provac.program import load_text

SYS = '(data m "x")\n'
NOISY = SYS + '''(fn noisy (params) (returns unit) (effects syscall) (pre) (post)
  (body (let_slice b (data-ref m)) (do (sys_write 1 b (len b)))))\n'''


def test_declared_effects_are_accepted_and_proved():
    P = build(example("effects"))
    assert not problems(P) and not pending(P)


def test_pure_function_cannot_call_an_effectful_one():
    e = src_error(example("bad_effect").replace(";; DEVE", ";; deve"))
    assert "efeito 'syscall' não declarado" in e and "a chamada a noisy" in e


def test_missing_clause_means_pure_and_body_syscall_is_rejected():
    e = src_error(SYS + '(fn f (params) (returns unit) (pre) (post) (body (let_slice b (data-ref m)) (do (sys_write 1 b (len b)))))')
    assert "efeito 'syscall' não declarado" in e and "o corpo" in e


def test_effect_propagates_through_two_levels():
    src = NOISY + '''(fn mid (params) (returns unit) (effects syscall) (pre) (post) (body (do (call noisy))))
(fn top (params) (returns unit) (effects) (pre) (post) (body (do (call mid))))'''
    e = src_error(src)
    assert "top: efeito 'syscall' não declarado" in e and "a chamada a mid" in e
    assert "mid: efeito" not in e  # mid declarou corretamente


def test_unknown_effect_and_overdeclaration():
    assert "efeito desconhecido" in src_error("(fn f (params) (returns unit) (effects magic) (pre) (post) (body))")
    # declarar a mais é permitido (o contrato pode ser mais largo que o corpo)
    assert src_error("(fn f (params) (returns unit) (effects syscall atomic) (pre) (post) (body))") is None


def test_audit_shows_effects():
    _, fns, meta = load_text(example("effects"))
    text = audit(fns, meta)
    assert "efeitos  nenhum (pura)" in text and "efeitos  syscall" in text
