"""Testes dos Próximos Passos:
1. Conteúdo de fatias em contratos (load, old, forall — teoria de arrays McCarthy + Ackermann).
2. Operadores bitwise, shift com prova de ausência de UB e aritmética modular (add_wrap, sub_wrap).
3. Registradores MMIO com regiões, efeito mmio, política deny-flow e emissão volátil.
4. Ring Buffer SPSC lock-free (examples/ring_buffer.prova) e os 4 casos negativos de segurança em tests/."""
import os
from _util import ROOT, build, example, pending, problems, src_error
from provac.audit import audit
from provac.interp import RunError, Slice, run
from provac.loop import diff_lock, lock_of
from provac.mlir import emit_module

TESTS_DIR = os.path.join(ROOT, "tests")


def read_test_prova(name):
    return open(os.path.join(TESTS_DIR, name), encoding="utf-8").read()


def test_four_security_negative_tests_in_tests_dir():
    # 1. test_atomic_uaf.prova: uso após drop (UAF linear) é bloqueado
    uaf_err = src_error(read_test_prova("test_atomic_uaf.prova"))
    assert uaf_err and "uso de 'buf' após drop" in uaf_err
    # e tentar declarar (atomic usize) localmente como variável também é bloqueado
    local_atm = "(fn f (params) (returns usize) (pre) (post) (body (let a (atomic usize) 0) (return 0)))"
    assert "tipo inválido para variável" in src_error(local_atm)

    # 2. test_aliasing_mut.prova: passar a mesma fatia em dois parâmetros quando ao menos um é escrito
    alias_err = src_error(read_test_prova("test_aliasing_mut.prova"))
    assert alias_err and "aliasing mutável de 'buf'" in alias_err

    # 3. test_shift_ub.prova: shift sem prova de limite 0 <= y < bitwidth falha com contraexemplo
    shift_err = src_error(read_test_prova("test_shift_ub.prova"))
    assert shift_err and "shift: (shl x y) exige 0 <= deslocamento < 64" in shift_err

    # 4. test_loop_contract_lock.prova: laço de IA bloqueia qualquer adulteração de contrato/efeito/mmio/static
    orig_src = read_test_prova("test_loop_contract_lock.prova")
    assert "post: (= result (+ x 1))" in src_error(orig_src)
    locked = lock_of(orig_src)
    tampered_cases = [
        orig_src.replace("(post (= result (+ x 1)))", "(post (= result (+ x 2)))"),
        orig_src.replace("(pre (< x 100))", "(pre (< x 10))"),
        orig_src.replace("(effects atomic mmio)", "(effects atomic)"),
        orig_src.replace("(stack-budget 128)", "(stack-budget 256)"),
        orig_src.replace("(deny-flow hw-reg @write)", "(deny-flow hw-reg @static:ticks)"),
        orig_src.replace("(mmio ctrl_reg 268435456 usize hw-reg)", "(mmio ctrl_reg 268435464 usize hw-reg)"),
    ]
    for cand in tampered_cases:
        assert diff_lock(locked, lock_of(cand)), f"deveria bloquear adulteração: {cand}"


def test_array_contracts_swap_fill_and_in_place_map():
    # Swap de dois elementos provado com (load ...) e (old (load ...)), mesmo quando i pode ser igual a j
    swap_src = """
    (fn swap_bytes
      (params (n usize) (buf (slice u8 n)) (i usize) (j usize))
      (returns unit)
      (pre (< i n) (< j n))
      (post (= (load buf i) (old (load buf j)))
            (= (load buf j) (old (load buf i))))
      (body
        (let xi u8 (load buf i))
        (let xj u8 (load buf j))
        (store buf i xj)
        (store buf j xi)))
    """
    P_swap = build(swap_src)
    assert not problems(P_swap) and not pending(P_swap)
    s = Slice(b"\x0a\x14\x1e")
    run(P_swap, "swap_bytes", [3, s, 0, 2])
    assert bytes(s.data) == b"\x1e\x14\x0a"

    # Fill com quantificador universal (forall k 0 n (= (load buf k) val))
    fill_src = """
    (fn fill_bytes
      (params (n usize) (buf (slice u8 n)) (val u8))
      (returns unit)
      (pre)
      (post (forall k 0 n (= (load buf k) val)))
      (body
        (var i usize 0)
        (while (< i n)
          (invariant (<= i n) (forall k 0 i (= (load buf k) val)))
          (decreases (- n i))
          (store buf i val)
          (set i (+ i 1)))))
    """
    P_fill = build(fill_src)
    assert not problems(P_fill) and not pending(P_fill)
    s2 = Slice(b"\x00\x00\x00\x00")
    run(P_fill, "fill_bytes", [4, s2, 77])
    assert bytes(s2.data) == b"MMMM"

    # Pós-condição falsa sobre conteúdo de fatia é rejeitada estaticamente e em execução
    bad_arr = """
    (fn bad_write
      (params (n usize) (buf (slice u8 n)))
      (returns unit)
      (pre (< 0 n))
      (post (= (load buf 0) 99))
      (body
        (store buf 0 42)))
    """
    assert "post: (= (load buf 0) 99)" in src_error(bad_arr)


def test_bitwise_shift_and_wrap_verification_and_runtime():
    src = """
    (fn bit_ops
      (params (x usize) (sh usize))
      (returns usize)
      (pre (< sh 16) (<= x 1024))
      (post (< (bit_and result 63) 64))
      (body
        (let m usize (bit_and x 63))
        (let s usize (shl m sh))
        (let r usize (shr s sh))
        (let w usize (add_wrap (sub_wrap r 1) 1))
        (return (bit_xor (bit_or w 0) 0))))
    """
    P = build(src)
    assert not problems(P) and not pending(P)
    res, _ = run(P, "bit_ops", [123, 4])
    assert res.returned == (123 & 63)
    mlir = emit_module(P.compiled, P.data, "x86_64")
    for op in ("arith.andi", "arith.ori", "arith.xori", "arith.shli", "arith.shrui"):
        assert op in mlir, op


def test_mmio_registers_effects_flow_and_mlir():
    src = """
    (region mmio-sec)
    (deny-flow mmio-sec @write)
    (mmio secret_reg 268435456 u8 mmio-sec)
    (mmio out_reg 268435464 usize mmio-sec)
    (fn read_hw
      (params)
      (returns u8)
      (effects mmio)
      (pre)
      (post)
      (body
        (mmio_write out_reg 123)
        (return (mmio_read secret_reg))))
    """
    P = build(src)
    assert not problems(P) and not pending(P)
    res, _ = run(P, "read_hw")
    assert res.mmios["out_reg"] == 123 and res.returned == 0
    mlir = emit_module(P.compiled, P.data, "aarch64")
    assert "llvm.inttoptr" in mlir and "llvm.load volatile" in mlir and "llvm.store volatile" in mlir
    assert "mmio      secret_reg: u8 @ 0x10000000 (mmio-sec)" in audit(P.fns, P.meta)

    # Esquecer (effects mmio) é recusado
    assert "efeito 'mmio' não declarado" in src_error(src.replace("(effects mmio)", "(effects)"))

    # Vazar dado de registrador MMIO protegido para @write viola deny-flow
    leak = src + """
    (fn leak_mmio
      (params (n usize) (buf (slice u8 n mmio-sec)))
      (returns unit)
      (effects mmio syscall)
      (pre (< 0 n))
      (post)
      (body
        (store buf 0 (mmio_read secret_reg))
        (do (sys_write 1 buf 1))))
    """
    assert "fluxo proibido mmio-sec → @write" in src_error(leak)


def test_ring_buffer_example_is_proved_and_executes_spsc_cycle():
    P = build(example("ring_buffer"))
    assert not problems(P) and not pending(P)
    res, _ = run(P)
    assert res.stdout == b"PASS\n" and res.exit_code == 0 and res.mmios["nic_doorbell"] == 1

    # Testa o ciclo completo push -> pop via interpretador
    buf = Slice(bytes(64))
    status = Slice(b"\x00")
    r1, _ = run(P, "test_ring_cycle", [64, buf, 1, status])
    assert r1.returned == 42 and status.data[0] == 1

    # Fila vazia devolve status=0 e item=0
    r_empty, _ = run(P, "ring_pop", [64, buf, 1, status])
    assert r_empty.returned == 0 and status.data[0] == 0
