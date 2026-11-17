# Estado real por fase (13/nov/2026)

Substitui `docs/archive/PROVA_STATUS.md`, `PROJECT_SUMMARY.md`, `CONCLUSION.md` e `NEXT_STEPS.md`, que se contradiziam
(p.ex. a Fase 2 aparecia como ✅ e como "bloqueada") e contavam exemplos de formas diferentes.
Legenda: ✅ funciona e tem teste · ⚠️ parcial ou não validado no ambiente-alvo · ❌ não funciona / não existe.

| Fase | Estado | O que existe | O que falta para fechar |
|---|---|---|---|
| 1. Gramática + testes | ✅ | `spec/prova.gbnf` aceita todos os exemplos e rejeita 9 programas inválidos (`tests/test_grammar.py`). Uma versão anterior teve a regra de `call` quebrada e o teste enfraquecido; ambos foram restaurados. | Manter a gramática alinhada ao verificador a cada novo recurso. |
| 2. Porte para Lean 4 | ❌ | `lean/Prova/Sexp.lean` (leitor) e `Core.lean` (teorema do `nsw`/`nuw`), **nunca compilados**. `Prova.lean` é um stub. | Instalar com `elan`, ajustar o módulo raiz do `lakefile`, rodar `lake build`, portar tipos e VCs. |
| 3. Conteúdo de fatias (arrays no SMT) | ❌ | Nada. A versão anterior declarava `(UInt 8)` (sort inválido em SMT-LIB) e nunca o usava. | Teoria de arrays em contratos (`load` hoje é proibido em contratos); precisa de Z3 para testar. |
| 4. Boot | ⚠️ | `prova.py boot` gera stub + linker script por arquitetura; x86-64 **montado, ligado e executado**. `_start` corrigidos (fd 1, `exit(0)`, `(len b)`). | Montar/rodar AArch64 e RISC-V (clang + QEMU); passar a `kmain` compilada pelo LLVM; testar `scripts/build.sh`. |
| 5. `ptr`/MMIO com regiões | ❌ | Nada utilizável: o código em `check.py` (`is_ptr`) nunca é verdadeiro e nenhum programa usa `ptr`. | Tipo `ptr` com região, leitura/escrita volátil emitida como op real do dialeto `llvm`. |
| 6. Relatório por região | ⚠️ | `audit` mostra contratos e efeitos (lê/escreve/syscall/chama/consome). | Regiões ainda não existem (depende da Fase 5). |
| 7. Laço de correção com IA | ⚠️ | `check --json` devolve obrigações com `label`, `goal`, `status`, contraexemplo. | O laço (`ai_correction_loop.py`) é simulado: chamar um modelo de verdade e travar assinatura e contratos entre iterações. |
| 8. Atômicos | ❌ | Nada utilizável: `(atomic u32)` é rejeitado, `u32` não existe, não há operações atômicas. Experimentos em `examples/wip/`. | Tipo `u32`, `atomic_load/store/fetch_add/cas` com ordem checada, emissão como `load atomic`/`atomicrmw`/`cmpxchg`. |

## Código inativo que sobrou
`check.py` ainda tem `is_ptr`, `is_atomic` e `PTR_REGIONS`/`ATOMIC_ORDERS` (e `audit.py` uma checagem de região): nunca
executam. Remova ou conclua junto com as Fases 5 e 8.
