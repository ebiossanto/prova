# Estado real (14/nov/2026): a ideia original, item por item

Substitui os documentos de status antigos (`docs/archive/`), que se contradiziam.
Legenda: ✅ funciona e tem teste · ⚠️ parcial ou não validado no ambiente-alvo · ❌ não existe.

## Camada 1: semântica (contratos, tipos, provas)
| Item | Estado | Notas |
|---|---|---|
| `pre`/`post` obrigatórios; erros matemáticos para a IA (`--json`: rótulo, objetivo, contraexemplo) | ✅ | |
| `pre` contraditória (tornaria toda prova vazia) é erro | ✅ | detectada pelo provador interno, fuzzing sem falso alarme |
| Overflow, limites, invariantes, terminação, `post` provados | ✅ | provador interno + Z3 opcional |
| Tipos dependentes leves: comprimento da fatia no tipo, exigido nas chamadas | ✅ | |
| Posse linear de fatias (`own`, `drop`, movimento) | ✅ | |
| Conteúdo de fatias em contratos (ex.: "dst é cópia de src") | ❌ | precisa de teoria de arrays/quantificadores (Z3) |
| Certificados Lean 4 para o que o SMT não fecha | ❌ | `lean/` é esboço nunca compilado |

## Camada 2: sintaxe para IA
| Item | Estado | Notas |
|---|---|---|
| S-expressions sem açúcar, sem conversão implícita | ✅ | |
| Gramática GBNF para constrained decoding | ✅ | testada com mini-interpretador (aceita todos os exemplos, rejeita 16 inválidos) |
| Laço fechado com a IA, contratos travados | ✅ mecânica | modelo de teste determinístico; a integração com um LLM real é externa (`--model-cmd`) |

## Camada 3: recursos de hardware
| Item | Estado | Notas |
|---|---|---|
| Efeitos na assinatura (`syscall`, `atomic`) com propagação | ✅ | `mmio` ainda não (não há ponteiros) |
| Regiões nos tipos, relatório de fluxo (`flow`, `--dot`), `deny-flow` transitivo | ✅ | só fluxo explícito de valores |
| Orçamento de pilha pelo grafo de chamadas | ⚠️ | quadros de um modelo de custo; `--frames` aceita medidas do backend (não testado contra LLVM real) |
| Memória concorrente: `static` atômico, ordens tipadas, emissão `llvm.load/store atomic`, `atomicrmw`, `cmpxchg` | ⚠️ | tipos e ordens testados; sintaxe MLIR atômica **não validada**; sem threads nem verificação de protocolos lock-free |
| Syscalls por arquitetura (números e registradores) | ✅ texto | `write` e `exit`; MLIR nunca passou por `mlir-opt`/`llc` |
| Registradores da CPU como recursos lineares | ❌ | |
| MMIO / ponteiros com regiões | ❌ | |
| Gerenciamento manual de memória (alocador verificado) | ❌ | só posse linear de fatias recebidas |
| Boot freestanding x86-64 (pilha, `.bss`, linker script) | ✅ | montado, ligado e executado |
| Boot AArch64 e RISC-V | ⚠️ | gerados; só estrutura verificada |

## O que bloqueia o próximo salto
1. **Ferramentas ausentes no ambiente de desenvolvimento**: LLVM/MLIR, QEMU, Z3 e Lean. Tudo marcado ⚠️ depende delas.
2. **Arrays/quantificadores**: sem eles não dá para provar corretude *funcional* de cópia, ordenação, buffers circulares.
3. **Ponteiros e MMIO** (e, com eles, `u32`): destravam drivers, `ring_buffer` e os experimentos de `examples/wip/`.

## Histórico
As Fases 1 a 8 do roadmap antigo (`docs/archive/PROJECT_ROADMAP.md`) estão cobertas assim: gramática ✅, Lean ❌, arrays ❌,
boot ⚠️/✅, ptr/MMIO ❌, relatório por região ✅, laço de IA ✅ (mecânica), atômicos ⚠️.
