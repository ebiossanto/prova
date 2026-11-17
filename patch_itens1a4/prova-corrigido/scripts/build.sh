#!/usr/bin/env bash
# Uso: scripts/build.sh examples/hello.prova [x86_64|aarch64|riscv64]
# Requer: python3, mlir-opt, mlir-translate, opt, llc, ld.lld (LLVM >= 17). z3 é opcional (prova em vez de teste).
set -euo pipefail
SRC="$1"; TARGET="${2:-x86_64}"
NAME="$(basename "$SRC" .prova)"
case "$TARGET" in
  x86_64)  TRIPLE=x86_64-unknown-linux-gnu ;;
  aarch64) TRIPLE=aarch64-unknown-linux-gnu ;;
  riscv64) TRIPLE=riscv64-unknown-linux-gnu ;;
  *) echo "alvo desconhecido: $TARGET" >&2; exit 2 ;;
esac
mkdir -p build
python3 prova.py check "$SRC"                                   # 1. prova (falha => para aqui)
python3 prova.py emit "$SRC" --target "$TARGET" > "build/$NAME.$TARGET.mlir"   # 2. dialetos MLIR
mlir-opt "build/$NAME.$TARGET.mlir" \
  --expand-strided-metadata --convert-cf-to-llvm --convert-arith-to-llvm \
  --finalize-memref-to-llvm --convert-func-to-llvm --reconcile-unrealized-casts \
 | mlir-translate --mlir-to-llvmir \
 | opt -O2 -S -o "build/$NAME.$TARGET.ll"                       # 3. LLVM IR otimizado
llc -mtriple="$TRIPLE" -filetype=obj -o "build/$NAME.$TARGET.o" "build/$NAME.$TARGET.ll"   # 4. objeto nativo
# 5. Programas freestanding (com _start): liga sem libc.
if grep -q '@_start' "build/$NAME.$TARGET.ll"; then
  ld.lld -static -nostdlib -e _start -o "build/$NAME.$TARGET" "build/$NAME.$TARGET.o"
  echo "binário: build/$NAME.$TARGET"
fi
# 6. Kernel bare-metal (função kmain): stub de boot + linker script gerados e ligados.
#    NÃO TESTADO de ponta a ponta (precisa de clang e ld.lld); o stub x86_64 é testado em tests/test_boot.py.
if grep -q '@kmain' "build/$NAME.$TARGET.ll"; then
  python3 prova.py boot --target "$TARGET" --part asm > "build/boot.$TARGET.S"
  python3 prova.py boot --target "$TARGET" --part ld  > "build/linker.$TARGET.ld"
  clang --target="$TRIPLE" -c "build/boot.$TARGET.S" -o "build/boot.$TARGET.o"
  ld.lld -T "build/linker.$TARGET.ld" -nostdlib -o "build/$NAME.$TARGET.elf" "build/boot.$TARGET.o" "build/$NAME.$TARGET.o"
  echo "kernel: build/$NAME.$TARGET.elf"
fi
