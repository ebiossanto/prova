#!/usr/bin/env bash
# Uso: scripts/build.sh examples/hello.prova [x86_64|aarch64|riscv64]
# Requer: python3, mlir-opt, mlir-translate, opt, llc, ld.lld (LLVM >= 17). z3 é opcional (prova em vez de teste).
# Validado de ponta a ponta em 19/nov/2026 (LLVM/MLIR 23.1.5): 16 exemplos x 3 alvos = 48/48 ELF gerados.
set -euo pipefail
SRC="$1"; TARGET="${2:-x86_64}"
NAME="$(basename "$SRC" .prova)"
case "$TARGET" in
  x86_64)  TRIPLE=x86_64-unknown-linux-gnu;  LLC_ATTR=() ;;
  aarch64) TRIPLE=aarch64-unknown-linux-gnu; LLC_ATTR=() ;;
  riscv64) TRIPLE=riscv64-unknown-linux-gnu; LLC_ATTR=(-mattr=+m,+a,+f,+d,+c) ;;  # rv64gc: áticos nativos (A) e mesma ABI lp64d do clang no boot
  *) echo "alvo desconhecido: $TARGET" >&2; exit 2 ;;
esac
PY="$(command -v python3 || command -v python)"
mkdir -p build
"$PY" prova.py check "$SRC"                                   # 1. prova (falha => para aqui)
"$PY" prova.py emit "$SRC" --target "$TARGET" > "build/$NAME.$TARGET.mlir"   # 2. dialetos MLIR
mlir-opt "build/$NAME.$TARGET.mlir" \
  --expand-strided-metadata --convert-cf-to-llvm --convert-arith-to-llvm \
  --finalize-memref-to-llvm --convert-func-to-llvm --reconcile-unrealized-casts \
 | mlir-translate --mlir-to-llvmir \
 | opt -O2 -S -o "build/$NAME.$TARGET.ll"                       # 3. LLVM IR otimizado
llc -mtriple="$TRIPLE" "${LLC_ATTR[@]}" -filetype=obj -o "build/$NAME.$TARGET.o" "build/$NAME.$TARGET.ll"   # 4. objeto nativo
# 5. Programas freestanding (com _start): liga sem libc.
#    NOTA: ld.lld não aceita -nostdlib (é flag do driver clang); -static já não pega libc.
if grep -q '@_start' "build/$NAME.$TARGET.ll"; then
  ld.lld -static -e _start -o "build/$NAME.$TARGET" "build/$NAME.$TARGET.o"
  echo "binário: build/$NAME.$TARGET"
fi
# 6. Kernel bare-metal (função kmain): stub de boot + linker script gerados e ligados.
#    Validado de ponta a ponta em 19/nov/2026 (clang + ld.lld); o stub x86_64 também é testado em tests/test_boot.py.
if grep -q '@kmain' "build/$NAME.$TARGET.ll"; then
  "$PY" prova.py boot --target "$TARGET" --part asm > "build/boot.$TARGET.S"
  "$PY" prova.py boot --target "$TARGET" --part ld  > "build/linker.$TARGET.ld"
  clang --target="$TRIPLE" -c "build/boot.$TARGET.S" -o "build/boot.$TARGET.o"
  ld.lld -T "build/linker.$TARGET.ld" -o "build/$NAME.$TARGET.elf" "build/boot.$TARGET.o" "build/$NAME.$TARGET.o"
  echo "kernel: build/$NAME.$TARGET.elf"
fi
