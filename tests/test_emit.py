"""Emissão MLIR: cobre `emit` (que não tinha nenhum teste e quebrou em `KeyError: '<'`) em todos os
alvos, e trava a tradução de syscalls por arquitetura (fd=1, exit(0), números e registradores certos)."""
import os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import prova  # noqa: E402
from provac.mlir import emit_module  # noqa: E402

EX = os.path.join(ROOT, "examples")
GOOD = ["sum_to", "copy_bytes", "hello", "ok_own", "calls",
        "x86_64_start", "aarch64_start", "riscv64_start", "kmain_min",
        "effects", "regions_flow", "stack_budget", "atomic_counter", "driver_demo",
        "packet_inspector", "selftest", "ring_buffer"]
TARGETS = ("x86_64", "aarch64", "riscv64")
WRITE_NR = {"x86_64": 1, "aarch64": 64, "riscv64": 64}
EXIT_NR = {"x86_64": 60, "aarch64": 93, "riscv64": 93}


def emit(name, target):
    data, compiled, _ = prova.analyse(os.path.join(EX, name + ".prova"))
    return emit_module(compiled, data, target)


def test_every_good_example_emits_on_every_target():
    for name in GOOD:
        for t in TARGETS:
            text = emit(name, t)
            assert text.startswith("module {") and text.rstrip().endswith("}"), (name, t)
            assert "func.func @" in text, (name, t)
            assert "!volatile" not in text, "sintaxe inválida de MLIR não pode voltar"


def test_comparisons_and_overflow_flags_are_emitted():
    # regressão: `op in ARITH or op in CMP` deixava o ramo de comparações inalcançável
    text = emit("sum_to", "x86_64")
    assert "arith.cmpi ult" in text and "overflow<nuw>" in text
    assert "func.call @clamp" in emit("calls", "x86_64")
    assert "memref.store" in emit("copy_bytes", "x86_64")


def _asm_calls(text):
    consts = dict(re.findall(r"(%t\d+) = arith\.constant (-?\d+) : i64", text))
    out = []
    for m in re.finditer(r'llvm\.inline_asm [^"]*"([^"]*)", "([^"]*)" ([^:]*) :', text):
        ops = [x.strip() for x in m.group(3).split(",")]
        out.append((m.group(1), m.group(2), [int(consts[o]) if o in consts else None for o in ops]))
    return out


def test_syscall_translation_per_architecture():
    insn = {"x86_64": "syscall", "aarch64": "svc #0", "riscv64": "ecall"}
    for t in TARGETS:
        calls = _asm_calls(emit(f"{t}_start", t))
        assert len(calls) == 2, (t, calls)
        (i1, _, ops1), (i2, _, ops2) = calls
        assert i1 == i2 == insn[t]
        assert ops1[0] == WRITE_NR[t] and ops1[1] == 1, f"{t}: write precisa de nr={WRITE_NR[t]} e fd=1, veio {ops1}"
        assert ops2[0] == EXIT_NR[t] and ops2[1] == 0, f"{t}: exit precisa de nr={EXIT_NR[t]} e código 0, veio {ops2}"


def test_start_examples_use_len_and_stdout():
    for t in TARGETS:
        src = open(os.path.join(EX, f"{t}_start.prova"), encoding="utf-8").read()
        assert "(sys_write 1 b (len b))" in src and "(sys_exit 0)" in src, t


def test_cli_refuses_to_emit_a_failing_program():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "prova.py"), "emit", os.path.join(EX, "bad_inc.prova")],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 1 and "emissão recusada" in r.stderr
    assert "func.func" not in r.stdout
