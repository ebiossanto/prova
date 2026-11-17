# Patch 0002: alinhando a Prova à ideia original (base: `prova-main.zip`)

## Como aplicar (na raiz do repositório, com git)
- **Você já aplicou o 0001** (zip anterior): `git apply --whitespace=nowarn 0002-ideia-original.patch`
- **Você não aplicou nada**: `git apply --whitespace=nowarn "cumulativo-0001+0002.patch"`
- **Sem git**: copie `prova-corrigido/` por cima do repositório (apague antes os `.zip`, `__pycache__` e `pytest_out.txt`).

Depois: `python tests/run_tests.py` (68 testes). Não use `patch -p1` (há remoções de binários).

## O que entrou (a ideia original, que estava só parcialmente implementada)
| Ideia | Agora |
|---|---|
| Efeitos e capacidades na assinatura | `(effects syscall atomic)`; sem a cláusula a função é **pura**; o efeito propaga por chamadas |
| Regiões e relatório de fluxo de dados | `(slice u8 n net-rx)`, `(region ..)`, `(deny-flow A B)` (transitivo, por variáveis, chamadas, memória e células atômicas); `prova.py flow [--dot]` |
| Orçamento de pilha | `(stack-budget N)` provado pelo grafo de chamadas; `prova.py stack [--frames medidas.json]` |
| Memória concorrente | `(static x (atomic usize) 0)`, `atomic_load/store/fetch_add/cas` com ordem de memória tipada (ordens ilegais são erro), emissão `llvm.load/store atomic`, `atomicrmw`, `cmpxchg` |
| IA em laço fechado, humano audita só contratos | `prova.py fix --model-cmd ...`: o modelo corrige o corpo e **não pode alterar** contratos, efeitos, orçamento, regiões, políticas nem `static` |
| Auditoria enxuta | `prova.py audit` mostra só contratos, efeitos, regiões, políticas, pilha |
| (achado no caminho) | pré-condição **contraditória** agora é erro: antes ela "provava" qualquer programa no vazio |

Exemplos novos: `effects`, `regions_flow`, `stack_budget`, `atomic_counter`, `driver_demo` (combina tudo) e os `bad_*` correspondentes.
O `ai_correction_loop.py` (simulado) foi para `scratch/`, substituído por `prova.py fix`.

## Mudanças que podem quebrar programas existentes
- Quem faz `sys_write`/`sys_exit` precisa de `(effects syscall)` (os `_start` e o `hello` já foram atualizados).
- Gramática: ordem canônica das cláusulas (`params`, `returns`, `effects`, `stack-budget`, `pre`, `post`, `body`); comentários `;` e `;;`.
- O verificador (não a gramática) continua aceitando as cláusulas em qualquer ordem.

## O que foi verificado
- Patches aplicados em originais intocados (sequencial e cumulativo): árvore idêntica à corrigida, 68/68 testes.
- **14 defeitos injetados de propósito** (efeito não propaga, fluxo sem transitividade, ordem de cas sem checagem, atômico assumido estável, contrato não travado, pré contraditória não detectada, gramática sem `atomic_cas`...): **todos derrubados** pela suíte.
- Fuzzing do detector de contradição: ~380 marcações, 0 falso alarme. Fuzzing do provador: 0 falso positivo.
- `fix`: modelos de teste determinísticos (honesto, trapaceiro, lixo, teimoso) cobrem a mecânica e a trava de contratos.

## O que NÃO foi verificado
- O MLIR (inclusive a sintaxe dos atômicos `llvm.*`) nunca passou por `mlir-opt`/`llc`. AArch64/RISC-V sem montar. CI e Windows não rodados.
- `fix` nunca foi testado com um LLM real (nada de rede aqui): você fornece o comando.
- Z3 e Lean seguem sem teste.

## Limites que ficaram (veja `docs/STATUS.md`)
Pilha usa modelo de custo até haver `--frames` reais; fluxo só rastreia valores (não `if`/`while`); atômicos garantem tipos e ordens legais,
**não** a correção de algoritmos lock-free; sem ponteiros/MMIO, arrays em contratos, alocador, registradores lineares, threads.
