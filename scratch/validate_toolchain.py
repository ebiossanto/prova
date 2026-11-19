"""Varredura: emite MLIR de bons exemplos para os 3 alvos e roda o pipeline real
mlir-opt -> mlir-translate -> opt -> llc -> ld.lld. Relaciona falhas por exemplo/alvo."""
import glob
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

MSYS_BIN = r"D:\msys64\clang64\bin"
OFFICIAL = sorted(glob.glob(r"D:\clang+llvm-*\bin"))
CANDIDATES = [MSYS_BIN] + OFFICIAL


def find_tool(name):
    for d in CANDIDATES:
        for p in (os.path.join(d, name + ".exe"), os.path.join(d, name)):
            if os.path.exists(p):
                return p
    return shutil.which(name)


TOOLS = {n: find_tool(n) for n in
         ("mlir-opt", "mlir-translate", "opt", "llc", "ld.lld", "clang")}
print("ferramentas:", {k: (v or "AUSENTE") for k, v in TOOLS.items()})
if not all(TOOLS.values()):
    print("faltam ferramentas"); sys.exit(2)

PASSES = ["--expand-strided-metadata", "--convert-cf-to-llvm", "--convert-arith-to-llvm",
          "--finalize-memref-to-llvm", "--convert-func-to-llvm", "--reconcile-unrealized-casts"]
TRIPLES = {"x86_64": "x86_64-unknown-linux-gnu",
           "aarch64": "aarch64-unknown-linux-gnu",
           "riscv64": "riscv64-unknown-linux-gnu"}

EXAMPLES = ["hello", "sum_to", "copy_bytes", "x86_64_start", "aarch64_start", "riscv64_start",
            "kmain_min", "effects", "regions_flow", "stack_budget", "atomic_counter",
            "driver_demo", "packet_inspector", "selftest", "ring_buffer", "sort_perm"]


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=ROOT, **kw)


def pipeline(example, target):
    src = os.path.join(ROOT, "examples", example + ".prova")
    mlir = os.path.join(tempfile.gettempdir(), f"{example}.{target}.mlir")
    llvm = mlir + ".llvm.mlir"
    ll = mlir + ".ll"
    obj = mlir + ".o"

    r = run([sys.executable, "prova.py", "emit", src, "--target", target])
    if r.returncode != 0:
        return "emit", r.stderr.strip().splitlines()[-1] if r.stderr else "?"
    open(mlir, "w", encoding="utf-8").write(r.stdout)

    r = run([TOOLS["mlir-opt"], mlir] + PASSES)
    if r.returncode != 0:
        return "mlir-opt", (r.stderr or r.stdout).strip().splitlines()[0]
    open(llvm, "w", encoding="utf-8").write(r.stdout)

    r = run([TOOLS["mlir-translate"], "--mlir-to-llvmir", llvm])
    if r.returncode != 0:
        return "mlir-translate", (r.stderr or r.stdout).strip().splitlines()[0]
    open(ll, "w", encoding="utf-8").write(r.stdout)

    r = run([TOOLS["opt"], "-O2", "-S", "-o", obj + ".ll", ll])
    if r.returncode != 0:
        return "opt", (r.stderr or r.stdout).strip().splitlines()[0]

    r = run([TOOLS["llc"], "-mtriple=" + TRIPLES[target]]
            + (["-mattr=+a"] if target == "riscv64" else [])  # extensão A: áticos nativos, não libatomic
            + ["-filetype=obj", "-o", obj, obj + ".ll"])
    if r.returncode != 0:
        return "llc", (r.stderr or r.stdout).strip().splitlines()[0]
    if open(obj, "rb").read(4) != b"\x7fELF":
        return "llc", "objeto não é ELF"

    text = open(obj + ".ll", encoding="utf-8").read()
    if "@_start" in text:
        # ld.lld oficial; o do MSYS2 rejeita ELF (bug do pacote)
        lld = find_tool("ld.lld")
        for d in OFFICIAL:
            cand = os.path.join(d, "ld.lld.exe")
            if os.path.exists(cand):
                lld = cand
        r = run([lld, "-static", "-e", "_start", "-o", obj + ".elf", obj])
        if r.returncode != 0:
            return "ld.lld", (r.stderr or r.stdout).strip().splitlines()[0]
        if open(obj + ".elf", "rb").read(4) != b"\x7fELF":
            return "ld.lld", "binário não é ELF"
    return None, None


fails = 0
for ex in EXAMPLES:
    for tgt in TRIPLES:
        stage, err = pipeline(ex, tgt)
        if stage:
            fails += 1
            print(f"FALHA {ex:20s} {tgt:8s} @{stage}: {err}")
        else:
            print(f"ok    {ex:20s} {tgt}")
print(f"\n{fails} falhas")
sys.exit(1 if fails else 0)
