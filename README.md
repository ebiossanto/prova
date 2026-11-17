# Prova: linguagem verificada para IA e kernel (bootstrap em Python)

Contratos `pre`/`post` obrigatórios, tipos estritos sem conversão implícita, posse linear `(own ...)`,
sintaxe de S-expressions (apta a *constrained decoding*) e emissão MLIR para x86-64, AArch64 e RISC-V.
O compilador atual (`provac/`) é um **bootstrap em Python**: verifica o programa, tenta provar cada
obrigação e só então emite MLIR.

> **Leia a tabela de estado abaixo antes de confiar em qualquer afirmação.** Cada linha aponta o teste que a sustenta.

## A ideia original e onde cada parte está
A Prova combina três abordagens como camadas de um mesmo sistema:
**sintaxe** (S-expressions + gramática, para a IA nunca errar pontuação), **semântica** (contratos matemáticos, tipos
lineares e dependentes, provas) e **recursos de hardware** (efeitos, regiões, pilha, atômicos, syscalls, boot).
O humano audita só os contratos (`prova.py audit`); a IA corrige o corpo e **não pode alterar os contratos** (`prova.py fix`).

## Estado real

| Parte da ideia | Estado | Evidência |
|---|---|---|
| Contratos `pre`/`post`, erros matemáticos detalhados (`--json`), `pre` contraditória é erro | ✅ | `test_checker.py`, `test_fix_loop.py` |
| Tipos estritos, tamanhos no tipo (`(slice u8 n)`), overflow e limites provados | ✅ | `test_checker.py` |
| Posse linear (`own`, `drop`, movimento em chamadas), chamadas com contratos, sem recursão | ✅ | `test_checker.py` |
| **Efeitos nas assinaturas** (`syscall`, `atomic`), propagação por chamadas | ✅ | `test_effects.py` |
| **Regiões e fluxo de dados** (`flow`, `--dot`, `deny-flow` transitivo) | ✅ só fluxo explícito de valores | `test_flow.py` |
| **Orçamento de pilha** pelo grafo de chamadas | ⚠️ quadros de um *modelo de custo*; valores reais via `--frames` | `test_stack.py` |
| **Memória concorrente**: `static` atômico, ordens de memória tipadas, emissão `llvm` | ⚠️ checagem de tipos testada; MLIR atômico não validado | `test_atomics.py` |
| **Laço fechado com a IA** com contratos travados (`prova.py fix`) | ✅ mecânica, com modelo de teste determinístico; plugue seu modelo via `--model-cmd` | `test_fix_loop.py` |
| Provador linear interno (Fourier–Motzkin + McCormick), sem Z3 | ✅ sólido por fuzzing; incompleto | `test_linarith_fuzz.py` |
| Gramática GBNF para constrained decoding | ✅ testada com mini-interpretador | `test_grammar.py` |
| **Execução** (`prova.py run`): interpretador de referência que confere pre/post/invariantes/variante/limites/overflow em tempo de execução; teste diferencial contra o verificador | ✅ (não é código nativo) | `test_run.py`, `test_packet_inspector.py` |
| Emissão MLIR para 3 alvos, syscalls por arquitetura | ⚠️ texto gerado e estrutura testada; **nunca passou por `mlir-opt`/`llc`** | `test_emit.py` |
| Boot bare-metal x86-64 (pilha, `.bss`, linker script) | ✅ montado, ligado e **executado** | `test_boot.py` |
| Boot AArch64 e RISC-V | ⚠️ só estrutura (sem toolchain/QEMU) | `test_boot.py` |
| Z3 opcional | ⚠️ caminho existe, **não testado** | n/d |
| Registradores como recursos lineares, MMIO/ponteiros, alocador, conteúdo de fatias (arrays), certificados Lean, threads/lock-free | ❌ não implementado | `docs/STATUS.md` |

Mapa completo da ideia original: [`docs/STATUS.md`](docs/STATUS.md).

## Uso
```
python prova.py check  examples/sum_to.prova            # relatório (--json p/ máquinas, --strict: exige tudo provado)
python prova.py audit  examples/regions_flow.prova      # SÓ contratos, efeitos, regiões, políticas: o que o humano audita
python prova.py flow   examples/bad_flow.prova [--dot]  # por onde os dados passam entre regiões (e violações de política)
python prova.py stack  examples/stack_budget.prova [--frames frames.json]
python prova.py run    examples/packet_inspector.prova  # executa (interpretador de referência) e devolve o código de saída do programa
python prova.py emit   examples/hello.prova --target aarch64
python prova.py fix    prog.prova --model-cmd "SEU_COMANDO" [--max-iter 5] [--out novo.prova]
python prova.py boot   --target riscv64 --part asm      # stub de boot (--part ld: linker script; --entry NOME)
scripts/build.sh examples/x86_64_start.prova x86_64     # pipeline completo; exige LLVM/MLIR e ld.lld
```
**`fix`**: `SEU_COMANDO` lê um JSON no stdin (`source`, `errors` com rótulo/objetivo/contraexemplo, `locked`, `feedback`) e
imprime o fonte `.prova` completo. O laço só aceita candidatos que preservam assinatura, `pre`, `post`, `effects`,
`stack-budget`, regiões, `deny-flow` e `static` de cada função original; tentar "consertar" enfraquecendo o contrato é
rejeitado e o modelo recebe esse feedback. Veja `tests/fake_model.py`.

## Programa de teste: `examples/packet_inspector.prova`
Um inspetor de pacotes que usa tudo junto: região `net-rx` com política `deny-flow net-rx @write`, validação (tamanho mínimo e byte
mágico), checksum com cota provada (`result ≤ 255·n`), contadores em células atômicas, veredito por syscall e código de saída = pacotes
aceitos. É totalmente provado (60 obrigações). Executando:
```
$ python prova.py run examples/packet_inspector.prova
ACCEPT
DROP
DROP                                   # código de saída do processo: 1
```
`tests/test_packet_inspector.py` introduz 6 bugs realistas (laço `<=`, falta de checagem de tamanho, vazamento para a saída, efeito
esquecido, pilha curta, checksum errado): o verificador recusa cada um pelo motivo certo e o bug do laço também falha ao executar.
O `run` só executa programas que passaram na verificação (`--force` ignora isso).

## Programa de teste que se autotesta: `examples/selftest.prova`
Seis funções (`gcd`, `sum_bytes`, `count_byte`, `max_byte`, `sort`, `reverse`) e um `_start` que confere resultados esperados e escreve
`PASS` ou `FAIL` (código de saída 0 ou 1). Estaticamente, tudo é provado (sem overflow, sem acesso fora dos limites, todo laço termina,
nenhum dado da região `input` chega à saída). `python prova.py run examples/selftest.prova` imprime `PASS`.

Ele mostra, de propósito, **o limite atual**: a Prova ainda não expressa "o vetor ficou ordenado" em contrato (conteúdo de fatias não é
modelado). Um `sort` com a comparação invertida é aceito pelo verificador (é seguro, só está errado); quem o pega é a execução em
`tests/test_selftest.py`, que compara `sort`, `reverse`, `gcd`, `sum_bytes`, `count_byte` e `max_byte` com o Python em centenas de
entradas aleatórias. Um achado real do verificador: sem `(pre (<= n 1000000))`, `reverse` falha com o contraexemplo `lo = hi = n = 2^64-1`
(a condição `(+ lo 1)` do laço estouraria).

## Testes
```
python tests/run_tests.py        # sem dependências; sai com código != 0 se algo falhar
python tests/run_tests.py -k emit
```
`pytest tests/` também funciona. O CI (`.github/workflows/ci.yml`) roda em Linux e Windows.
Testado localmente em Python 3.12 (97 testes).

## Estrutura
```
provac/    sexp.py (leitor) · check.py (tipos + VCs) · linear.py (posse) · linarith.py (provador interno)
           effects.py · flow.py (regiões/fluxo) · stack.py · program.py (programa completo) · loop.py (laço com a IA)
           smt.py (provador interno → Z3 → teste limitado) · mlir.py (emissão) · audit.py · boot.py
spec/      prova.gbnf (gramática) · LANGUAGE.md      boot/   stubs e linker scripts gerados
examples/  programas que DEVEM verificar (+ bad_*.prova, que DEVEM ser recusados) · wip/ (experimentos que ainda não funcionam)
tests/     test_*.py + run_tests.py + fake_model.py · wip/ (casos a reescrever)      lean/  esboço (ver docs/STATUS.md)
docs/      STATUS.md · archive/ (documentos antigos; contêm afirmações não verificadas)
```

## O que "provado" e "testado" significam
- **provado**: o provador interno (ou o Z3, se instalado) mostrou que a obrigação vale para todos os valores.
- **testado**: só valores de borda foram enumerados; um contraexemplo achado é real, mas a ausência **não** prova nada.
  Use `--strict` para recusar qualquer obrigação que não esteja provada.
- Contratos podem estar errados: a prova garante o programa contra o contrato, não o contrato contra a intenção.
- "Nunca estoura memória" vale só contra os limites declarados; alocação dinâmica ainda não existe, e a pilha usa um modelo de custo
  até que se informe `--frames` medidos no backend.
- `run` é um interpretador de referência, não um backend: sem entrada (stdin/argumentos), só `write`/`exit`, e a velocidade é a do Python.
- Fluxo de dados: só fluxo explícito de valores; fluxo implícito (por `if`/`while`) e vazamento por comprimento não são rastreados.
- Atômicos: a Prova garante tipos e ordens legais e que só células atômicas são compartilhadas; **não** verifica que a ordem escolhida
  baste para a correção de um algoritmo lock-free.

## Observação
GBNF é a notação BNF do GGML/llama.cpp (a gramática serve a decodificadores que a aceitam, p.ex. llama.cpp).
