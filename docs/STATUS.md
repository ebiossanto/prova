# Estado real (16/nov/2026): a ideia original, item por item

Substitui os documentos de status antigos (`docs/archive/`), que se contradiziam.
Legenda: ✅ funciona e tem teste · ⚠️ parcial ou não validado no ambiente-alvo · ❌ não existe.

## Camada 1: semântica (contratos, tipos, provas)
| Item | Estado | Notas |
|---|---|---|
| `pre`/`post` obrigatórios; erros matemáticos para a IA (`--json`: rótulo, objetivo, contraexemplo) | ✅ | |
| `pre` contraditória (tornaria toda prova vazia) é erro | ✅ | detectada pelo provador interno, fuzzing sem falso alarme |
| Overflow, limites, shifts (`shl`/`shr`), invariantes, terminação, `post` provados | ✅ | provador interno + Z3 opcional |
| Tipos dependentes leves: comprimento da fatia no tipo, exigido nas chamadas | ✅ | |
| Posse linear de fatias (`own`, `drop`, movimento) e proibição de aliasing mutável em chamadas | ✅ | `test_checker.py`, `test_next_steps.py` |
| Conteúdo de fatias, permutação/multiconjunto (`occ`) e ordenação em contratos (`load`, `occ`, `old`, `forall` aninhado; ex.: `copy_bytes`, `fill`, `swap`, `sort_perm`) | ✅ | provador interno (McCarthy + Ackermann + cancelamento de `ite`) + Z3 (`z3-solver` 5.4.1 em processo) (`test_next_steps.py`, `sort_perm.prova`) |
| Certificados Lean 4 (`lean/Prova/`) | ✅ | `Core.lean`, `Sexp.lean`, `Prova.lean` e `SortPerm.lean` (teoremas de McCarthy, preservação de multiconjunto em `swap` e passo indutivo de `sort`) compilados com Lean 4 (`v4.36.0-rc2`) em `test_next_steps.py` |

## Camada 2: sintaxe para IA
| Item | Estado | Notas |
|---|---|---|
| S-expressions sem açúcar, sem conversão implícita | ✅ | |
| Gramática GBNF para constrained decoding | ✅ | testada com mini-interpretador (aceita todos os exemplos, rejeita 16 inválidos) |
| Laço fechado com a IA, contratos travados | ✅ mecânica | trava assinatura, `pre`, `post`, `effects`, `stack-budget`, regiões, `deny-flow`, `static` e `mmio` (`test_fix_loop.py`, `test_next_steps.py`) |

## Camada 3: recursos de hardware
| Item | Estado | Notas |
|---|---|---|
| Efeitos na assinatura (`syscall`, `atomic`, `mmio`) com propagação | ✅ | `test_effects.py`, `test_next_steps.py` |
| Regiões nos tipos, relatório de fluxo (`flow`, `--dot`), `deny-flow` transitivo | ✅ | inclui `@write`, `@static:NOME` e `@mmio:NOME` (só fluxo explícito de valores) |
| Orçamento de pilha pelo grafo de chamadas | ⚠️ | quadros de um modelo de custo; `--frames` aceita medidas do backend (não testado contra LLVM real) |
| Memória concorrente: `static` atômico, ordens tipadas, emissão `llvm.load/store atomic`, `atomicrmw`, `cmpxchg`, Ring Buffer SPSC (`ring_buffer.prova`) | ✅/⚠️ | tipos, ordens, `add_wrap`/`sub_wrap`/`bit_and` e execução testados (`test_atomics.py`, `test_next_steps.py`); sintaxe MLIR **não validada** com `mlir-opt` |
| MMIO tipado com regiões (`(mmio nome addr T regiao)`, `mmio_read`, `mmio_write`, efeito `mmio`, emissão `llvm.load/store volatile`) | ✅/⚠️ | verificação de tipos/efeitos/fluxo e execução no interpretador testadas (`test_next_steps.py`); MLIR não validado com `mlir-opt` |
| Execução: interpretador de referência (`run`) com checagem de contratos e teste diferencial | ✅ | confere `load`, `old` e `forall` em contratos; não é código nativo |
| Programas de teste executáveis (`selftest`, `packet_inspector`, `ring_buffer`) | ✅ | provados estaticamente e executados |
| Compilação até binário nativo (MLIR → LLVM → ELF) | ❌ não validado | exige LLVM/MLIR, ausente no desenvolvimento |
| Syscalls por arquitetura (números e registradores) | ✅ texto | `write` e `exit`; MLIR nunca passou por `mlir-opt`/`llc` |
| Registradores da CPU como recursos lineares | ❌ | |
| Gerenciamento manual de memória (alocador dinâmico verificado) | ❌ | só posse linear de fatias recebidas |
| Boot freestanding x86-64 (pilha, `.bss`, linker script) | ✅ | montado, ligado e executado (em Linux x86-64) |
| Boot AArch64 e RISC-V | ⚠️ | gerados; só estrutura verificada |
