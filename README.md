# Prova — linguagem verificada para IA e kernel (esqueleto bootstrap)

Contratos `pre`/`post` obrigatórios · tipos estritos sem conversões implícitas · posse linear `(own ...)` ·
sintaxe de S-expressions (decodificação restrita pela gramática) · emissão MLIR → LLVM → x86-64 / AArch64 / RISC-V.

## O que funciona hoje (testado)
Compilador bootstrap em Python (`prova.py`, pacote `provac/`):

| Recurso | Estado |
|---|---|
| Leitor S-expr, gramática fechada (`spec/prova.gbnf`) | ✔ |
| Tipos estritos `i64`/`usize`/`u8`, `cast` explícito, sem sombreamento | ✔ |
| Contratos `pre`/`post` obrigatórios; laços exigem `invariant` + `decreases` | ✔ |
| VCs: overflow aritmético, limites de `load`/`store`, invariantes, terminação, `post` | ✔ |
| Posse linear: uso após `drop`, `drop` duplo, vazamento, ramos discordantes | ✔ |
| Chamadas com contratos (verificação modular): `pre` do chamado vira obrigação, `post` vira hipótese; `(slice u8 n)` exige `len = n` na chamada (tipo dependente); `own` é movido para o chamado; recursão recusada | ✔ |
| Emissão MLIR (func/arith/memref/cf/llvm) com `nsw`/`nuw` vindos das provas | ✔ (texto gerado; não rodei `mlir-opt`) |
| Syscalls `write`/`exit` por arquitetura via `llvm.inline_asm` | ✔ (texto gerado; não rodei `llc`) |
| Descarga das VCs | Z3 se estiver no PATH (prova); senão **teste limitado em valores de borda (não é prova)** |

## Uso
```
python3 prova.py check examples/sum_to.prova          # relatório (use --json para a IA corrigir sozinha)
python3 prova.py emit  examples/hello.prova --target aarch64
scripts/build.sh examples/hello.prova riscv64          # pipeline completo (precisa de LLVM/MLIR e ld.lld)
python3 tests/run_tests.py
```
Instale `z3` (`apt install z3`) para que "~ testado" vire "✔ provado".

## Exemplos
`sum_to` (laço com invariante, provado) · `copy_bytes` (limites) · `hello` (freestanding, sem libc) ·
`ok_own` (posse linear) · `calls` (contratos entre funções) · `bad_inc`, `bad_bounds`, `bad_leak`, `bad_call_pre`, `bad_call_len`, `bad_move`, `bad_recursion` (devem ser recusados).

## Limites conhecidos (honestidade)
- Fatias só de `u8`; o **conteúdo** das fatias não é modelado (pós-condições sobre bytes ainda não).
- Sem alocação dinâmica, sem concorrência/atômicos, sem recursão (chamadas existem, só não recursivas).
- Boot freestanding: `_start` é função comum; falta o stub nu por arquitetura (pilha alinhada, `.bss`, `linker.ld`).
- "Nunca estoura memória" só vale contra orçamentos declarados; o contrato pode estar errado.
- `lean/` é um esqueleto **não testado** (sem Lean no ambiente de geração): leitor S-expr + teorema de que
  `nsw`/`nuw` são seguros quando a VC vale.

## Próximos passos
1. Rodar `scripts/build.sh` com LLVM/MLIR e corrigir a sintaxe MLIR onde `mlir-opt` reclamar.
2. Modelar conteúdo de fatias (teoria de arrays no SMT).
3. Portar front-end para Lean 4 e emitir certificados para VCs que o Z3 não fecha.
4. Stub de boot nu + `linker.ld` por arquitetura; MMIO com capacidades; relatório de fluxo por região.
