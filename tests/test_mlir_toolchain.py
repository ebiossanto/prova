"""Validação real da toolchain MLIR/LLVM (Fase 10 do roadmap): a emissão da Prova precisa
sobreviver ao pipeline `mlir-opt -> mlir-translate -> opt -> llc -> ld.lld` e virar ELF nos
3 alvos, incluindo o kernel (stub de boot + linker script). Sem as ferramentas no ambiente os
testes pulam, no mesmo padrão de `test_boot.py`; no CI elas são instaladas em
`.github/workflows/ci.yml` (ubuntu). A varredura completa (16 exemplos x 3 alvos = 48 pipelines)
está em `scratch/validate_toolchain.py`."""
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import prova  # noqa: E402
from provac.mlir import emit_module  # noqa: E402

EX = os.path.join(ROOT, "examples")
TARGETS = {"x86_64": "x86_64-unknown-linux-gnu",
           "aarch64": "aarch64-unknown-linux-gnu",
           "riscv64": "riscv64-unknown-linux-gnu"}
PASSES = ["--expand-strided-metadata", "--convert-cf-to-llvm", "--convert-arith-to-llvm",
          "--finalize-memref-to-llvm", "--convert-func-to-llvm", "--reconcile-unrealized-casts"]
# um representante por caminho do backend: memref, syscall/_start, kernel, atômicos,
# arrays/occ/forall e mmio (volatile) — todos já varridos 48/48 em scratch/validate_toolchain.py
EXAMPLES = ["copy_bytes", "x86_64_start", "kmain_min", "ring_buffer", "sort_perm", "driver_demo"]
# rv64gc: áticos nativos (extensão A, senão vira chamada __atomic_*/libatomic) e a mesma ABI
# lp64d do clang usado no stub de boot (senão o ld.lld recusa por ABI de ponto flutuante diferente)
LLC_ATTR = {"riscv64": ["-mattr=+m,+a,+f,+d,+c"]}


def _tool_dirs():
    dirs = []
    if os.name == "nt":
        # LLVM oficial primeiro: o ld.lld do MSYS2 (23.1.5) rejeita até ELF válido
        # ("unknown file type"); o oficial 23.1.6 linka. O MSYS2 é o único lugar com
        # mlir-opt/mlir-translate no Windows (23.1.5) — combinação já validada de ponta a ponta.
        dirs += sorted(glob.glob(r"D:\clang+llvm-*\bin"))
        dirs.append(r"D:\msys64\clang64\bin")
    dirs += [d for d in os.environ.get("PATH", "").split(os.pathsep) if d]
    out, seen = [], set()
    for d in dirs:
        if os.path.isdir(d) and d not in seen:
            seen.add(d)
            out.append(d)
    return out


def find_tool(name):
    """sem versão primeiro; depois `nome-NN` (Debian/Ubuntu instalam `mlir-opt-18` etc.)."""
    ext = ".exe" if os.name == "nt" else ""
    names = [name + ext] + [f"{name}-{v}{ext}" for v in range(30, 12, -1)]
    for d in _tool_dirs():
        for cand in names:
            p = os.path.join(d, cand)
            if os.path.isfile(p):
                return p
    return shutil.which(name)


def _tools():
    found = {n: find_tool(n) for n in ("mlir-opt", "mlir-translate", "opt", "llc", "ld.lld")}
    missing = [n for n, p in found.items() if not p]
    if missing:
        raise unittest.SkipTest("toolchain MLIR/LLVM ausente: " + ", ".join(missing))
    return found


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=ROOT)


def _pipeline(tools, name, target, d):
    """emissão real + pipeline real; devolve o caminho do objeto ELF."""
    data, compiled, _ = prova.analyse(os.path.join(EX, name + ".prova"))
    mlir = os.path.join(d, f"{name}.{target}.mlir")
    with open(mlir, "w", encoding="utf-8") as f:
        f.write(emit_module(compiled, data, target))

    llvm = os.path.join(d, f"{name}.{target}.llvm.mlir")
    r = _run([tools["mlir-opt"], mlir] + PASSES)
    assert r.returncode == 0, f"mlir-opt {name}/{target}: {(r.stderr or r.stdout).strip()[:500]}"
    with open(llvm, "w", encoding="utf-8") as f:
        f.write(r.stdout)

    ll = os.path.join(d, f"{name}.{target}.ll")
    r = _run([tools["mlir-translate"], "--mlir-to-llvmir", llvm])
    assert r.returncode == 0, f"mlir-translate {name}/{target}: {(r.stderr or r.stdout).strip()[:500]}"
    with open(ll, "w", encoding="utf-8") as f:
        f.write(r.stdout)

    ll_opt = os.path.join(d, f"{name}.{target}.opt.ll")
    r = _run([tools["opt"], "-O2", "-S", "-o", ll_opt, ll])
    assert r.returncode == 0, f"opt {name}/{target}: {(r.stderr or r.stdout).strip()[:500]}"

    obj = os.path.join(d, f"{name}.{target}.o")
    r = _run([tools["llc"], "-mtriple=" + TARGETS[target]] + LLC_ATTR.get(target, [])
             + ["-filetype=obj", "-o", obj, ll_opt])
    assert r.returncode == 0, f"llc {name}/{target}: {(r.stderr or r.stdout).strip()[:500]}"
    with open(obj, "rb") as f:
        assert f.read(4) == b"\x7fELF", f"objeto não-ELF {name}/{target}"

    with open(ll_opt, encoding="utf-8") as f:
        if "@_start" in f.read():  # programa freestanding: liga sem libc
            elf = os.path.join(d, f"{name}.{target}.elf")
            r = _run([tools["ld.lld"], "-static", "-e", "_start", "-o", elf, obj])
            assert r.returncode == 0, f"ld.lld {name}/{target}: {(r.stderr or r.stdout).strip()[:500]}"
            with open(elf, "rb") as g:
                assert g.read(4) == b"\x7fELF", f"binário não-ELF {name}/{target}"
    return obj


def test_pipeline_mlir_to_elf_for_every_example_and_target():
    tools = _tools()
    with tempfile.TemporaryDirectory() as d:
        for name in EXAMPLES:
            for target in TARGETS:
                _pipeline(tools, name, target, d)


def test_kmain_links_as_kernel_for_every_target():
    tools = _tools()
    clang = find_tool("clang")
    if not clang:
        raise unittest.SkipTest("toolchain ausente: clang (monta o stub de boot)")
    with tempfile.TemporaryDirectory() as d:
        for target in TARGETS:
            obj = _pipeline(tools, "kmain_min", target, d)
            boot_s = os.path.join(d, f"boot.{target}.S")
            linker = os.path.join(d, f"linker.{target}.ld")
            for part, out in (("asm", boot_s), ("ld", linker)):
                r = _run([sys.executable, os.path.join(ROOT, "prova.py"), "boot",
                          "--target", target, "--part", part])
                assert r.returncode == 0, f"boot {target}: {(r.stderr or r.stdout).strip()[:500]}"
                with open(out, "w", encoding="utf-8") as f:
                    f.write(r.stdout)
            boot_o = os.path.join(d, f"boot.{target}.o")
            r = _run([clang, f"--target={TARGETS[target]}", "-c", boot_s, "-o", boot_o])
            assert r.returncode == 0, f"clang {target}: {(r.stderr or r.stdout).strip()[:500]}"
            elf = os.path.join(d, f"kmain_min.{target}.elf")
            r = _run([tools["ld.lld"], "-T", linker, "-o", elf, boot_o, obj])
            assert r.returncode == 0, f"ld.lld kernel {target}: {(r.stderr or r.stdout).strip()[:500]}"
            with open(elf, "rb") as f:
                assert f.read(4) == b"\x7fELF", f"kernel não-ELF {target}"
