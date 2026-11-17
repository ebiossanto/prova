# Prova: linguagem verificada para IA e kernel (bootstrap em Python)

Contratos `pre`/`post` obrigatórios, tipos estritos sem conversão implícita, posse linear `(own ...)`,
sintaxe de S-expressions (apta a *constrained decoding*) e emissão MLIR para x86-64, AArch64 e RISC-V.
O compilador atual (`provac/`) é um **bootstrap em Python**: verifica o programa, tenta provar cada
obrigação e só então emite MLIR.

> **Leia a tabela de estado abaixo antes de confiar em qualquer afirmação.** Cada linha aponta o teste que a sustenta.

## Estado real

| Componente | Estado | Evidência |
|---|---|---|
| Leitor S-expr, tipos estritos (`i64`, `usize`, `u8`, fatias), `cast` explícito | ✅ implementado | `tests/test_checker.py` |
| Contratos, laços (`invariant` + `decreases`), VCs de overflow/limites/invariantes/terminação | ✅ | `test_good_examples_are_fully_proved` |
| Posse linear (`own`, `drop`, movimento em chamadas), chamadas com contratos, sem recursão | ✅ | `test_bad_examples_are_rejected_...` |
| Provador linear interno (Fourier–Motzkin + McCormick), sem Z3 | ✅ sólido por fuzzing; incompleto | `tests/test_linarith_fuzz.py` |
| Z3 opcional para o que o provador interno não fecha | ⚠️ caminho existe, **não testado** (sem Z3 no desenvolvimento) | n/d |
| Gramática GBNF (`spec/prova.gbnf`) para constrained decoding | ✅ testada com mini-interpretador | `tests/test_grammar.py` |
| Emissão MLIR (texto) para 3 alvos, syscalls traduzidas por arquitetura | ⚠️ texto gerado e estrutura testada; **nunca passou por `mlir-opt`/`llc`** | `tests/test_emit.py` |
| `audit` (contratos + efeitos), `--strict`, `--json` | ✅ | `tests/test_checker.py` |
| Boot bare-metal x86-64 (pilha, `.bss`, linker script) | ✅ montado, ligado e **executado** | `test_x86_64_stub_assembles_links_and_runs` |
| Boot bare-metal AArch64 e RISC-V | ⚠️ gerados e verificados só estruturalmente; **não montados nem rodados** | `tests/test_boot.py` |
| Laço de correção com IA (`ai_correction_loop.py`) | ❌ simulado; não chama modelo | n/d |
| Porte para Lean 4 (`lean/`) | ❌ esboço; `Prova.lean` é um stub; `lake build` não foi validado | n/d |
| Atômicos, `ptr`/MMIO com regiões, conteúdo de fatias, alocação, concorrência | ❌ não implementado | `examples/wip/` |

Detalhe por fase do roadmap: [`docs/STATUS.md`](docs/STATUS.md).

## Uso
```
python prova.py check  examples/sum_to.prova            # relatório (--json p/ máquinas, --strict: exige tudo provado)
python prova.py emit   examples/hello.prova --target aarch64
python prova.py audit  examples/calls.prova             # só contratos e efeitos: o que o humano audita
python prova.py boot   --target riscv64 --part asm      # stub de boot (--part ld: linker script; --entry NOME)
scripts/build.sh examples/x86_64_start.prova x86_64     # pipeline completo; exige LLVM/MLIR e ld.lld
```
`boot/` guarda os arquivos gerados para `kmain` (`python prova.py boot ...` os regenera; um teste impede divergência).

## Testes
```
python tests/run_tests.py        # sem dependências; sai com código != 0 se algo falhar
python tests/run_tests.py -k emit
```
`pytest tests/` também funciona. O CI (`.github/workflows/ci.yml`) roda em Linux e Windows.
Testado localmente em Python 3.12.

## Estrutura
```
provac/    sexp.py (leitor) · check.py (tipos + VCs) · linear.py (posse) · linarith.py (provador interno)
           smt.py (provador interno → Z3 → teste limitado) · mlir.py (emissão) · audit.py · boot.py
spec/      prova.gbnf (gramática) · LANGUAGE.md      boot/   stubs e linker scripts gerados
examples/  programas que DEVEM verificar (+ bad_*.prova, que DEVEM ser recusados) · wip/ (experimentos que ainda não funcionam)
tests/     test_*.py + run_tests.py · wip/ (casos a reescrever)      lean/  esboço (ver tabela)
docs/      STATUS.md · archive/ (documentos antigos; contêm afirmações não verificadas)
```

## O que "provado" e "testado" significam
- **provado**: o provador interno (ou o Z3, se instalado) mostrou que a obrigação vale para todos os valores.
- **testado**: só valores de borda foram enumerados; um contraexemplo achado é real, mas a ausência **não** prova nada.
  Use `--strict` para recusar qualquer obrigação que não esteja provada.
- Contratos podem estar errados: a prova garante o programa contra o contrato, não o contrato contra a intenção.
- "Nunca estoura memória" vale só contra os limites declarados; alocação dinâmica ainda não existe.

## Observação
GBNF é a notação BNF do GGML/llama.cpp (a gramática serve a decodificadores que a aceitam, p.ex. llama.cpp).
