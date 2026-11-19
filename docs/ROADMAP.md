# Roadmap: fases de desenvolvimento

Legenda: ✅ concluído (detalhes em [`STATUS.md`](STATUS.md)) · 🚧 fase ativa · ⏸ bloqueada pelo ambiente.
Estado em 17/nov/2026.

## Fase 9 (próxima): certificados Lean 4 de ponta a ponta — base de confiança mínima

**Objetivo.** Toda obrigação que o provador em Python declara "provada" pode ser **exportada como
certificado `.lean` e checada pelo kernel do Lean 4**. A base de confiança (TCB) deixa de ser
"provador Python + Z3" e passa a ser o kernel do Lean (cerca de 10 mil linhas de C, reescrito e
auditado pela comunidade). É o elo que falta da ideia original: o compilador emite o programa,
a prova **e** o certificado verificável por um núcleo pequeno e independente.

**Por que esta fase, agora.**

- Lean 4 (`v4.36.0-rc2`) e `z3-solver` (`5.4.1`) já estão disponíveis no ambiente e testados na
  suíte (`test_next_steps.py`).
- `lean/Prova/` já contém os lemas que os certificados vão reutilizar: axiomas de McCarthy
  (`select_store_eq`/`select_store_ne`), recorrência de multiconjunto (`occStore_id`,
  `occ_swap_preserved`) e o passo indutivo do `sort` (`bubble_suffix_step`,
  `bubble_partition_step`) — todos compilando sem erros.
- O que **não** existe é o elo automático: hoje as VCs provadas por `linarith`/Z3 ficam só em
  Python. A exportação para Lean é o passo que converte "o provador diz que provou" em
  "o kernel do Lean confirma".

**Marcos.**

| # | Marco | Descrição |
|---|---|---|
| M9.1 | `prova.py cert <prog> [--out DIR]` | Gera um `.lean` por função com `theorem vc_<fn>_<n> : <hipóteses> → <objetivo>` para cada obrigação, convertindo a VC interna (S-expression) em termo Lean. |
| M9.2 | Fragmento QF_LIA → `omega` | Aritmética linear inteira sem quantificadores (a maioria das VCs: limites, overflow, invariantes numéricos) fecha com `omega`; o Lean elabora o script e o **kernel checa o termo resultante**. |
| M9.3 | Arrays, `occ` e `forall` → lemas | `select`/`store_arr` viram `Prova.select`/`Prova.store` com os lemas de McCarthy; `(occ ...)` usa `occ_swap_preserved`/`occStore_id`; `forall` limitado vira `∀ v, lo ≤ v → v < hi → ...`. Funções de ocorrência não interpretadas são **generalizadas** (quantificadas) na hipótese — generalize é sempre som. |
| M9.4 | `tests/test_certificates.py` | Roda `lean` em cada certificado gerado; exige **0 erros, 0 `sorry`, 0 `axiom`** (teste automatizado que varre o texto). Sem Lean no PATH: skip (mesmo padrão do boot Linux). |
| M9.5 | Métricas e docs | % de VCs com certificado por exemplo, tabela em `STATUS.md`/`README.md`. |

**Critérios de aceite.**

1. `python prova.py cert examples/sort_perm.prova` gera certificados que compilam com `lean`
   sem erros e sem `sorry`.
2. Cobertura: **100% das VCs de aritmética linear** de `sum_to`, `copy_bytes`, `ring_buffer`,
   `sort_perm` e `packet_inspector`; arrays/`occ` cobertos pelos lemas de `SortPerm.lean`.
3. Suíte completa mantém os 103 testes passando + os novos de certificado; 0 falhas.
4. Nenhum certificado contém `sorry`/`axiom` (verificado por teste, não só por declaração).

**Honestidade sobre a TCB.** Os scripts de tática (`omega`, `simp`) rodam na elaboração do Lean
e produzem um termo de prova; quem confia é o **kernel** ao checar esse termo. Evitamos
`native_decide` (dependeria do compilador). `sorry` e `axiom` são proibidos por teste.

**Fora do escopo desta fase:** MLIR/LLVM (Fase 10), alocador dinâmico, registradores lineares,
protocolos multi-thread.

---

## Fase 10 (⏸ bloqueada): validação da toolchain MLIR/LLVM

Validar a emissão real: `mlir-opt` → `mlir-translate` → `llc` → `ld.lld` → ELF, para os 3 alvos,
e medir os quadros de pilha reais contra o modelo de custo (`--frames`).
**Bloqueio:** nenhum de `clang`, `llc`, `mlir-opt`, `ld.lld`, `qemu` está instalado neste
ambiente Windows e não há `winget`/gestor de pacotes para instalá-los. Requer o usuário instalar
LLVM (ex.: `https://llvm.org/builds/` ou MSYS2 `pacman -S mingw-w64-x86_64-llvm`) ou rodar em
Linux. Quando disponível: `scripts/build.sh examples/x86_64_start.prova x86_64`.

## Fase 11 (❌ não iniciada): registradores como recursos lineares

Cada registrador da CPU com dono único nas chamadas (asm inline/epílogos), rejeitando leituras
antes da escrita e uso após o clobber — fechando a última lacuna de "hardware" da ideia original.

## Fase 12 (❌ não iniciada): alocador dinâmico verificado + protocolos multi-thread

`alloc`/`free` com posse linear e invariante de heap; verificação de invariantes de protocolo
(ex.: produtor-consumidor) para além das ordens de memória já tipadas.

---

## Histórico de fases concluídas

| Fase | Conteúdo | Evidência |
|---|---|---|
| 1–5 | Contratos, tipos, posse linear, efeitos, regiões/fluxo, pilha | `docs/STATUS.md` |
| 6 | Emissão MLIR + boot bare-metal x86-64 (executado em Linux) | `test_emit.py`, `test_boot.py` |
| 7 | Loop com IA e contratos travados (`prova.py fix`) | `test_fix_loop.py` |
| 8 | Interpretador de referência, testes executáveis, atômicos, MMIO, ring buffer, testes negativos | `test_run.py`, `test_next_steps.py` |
| 8b | Conteúdo de fatias, `occ`/permutação, `forall` aninhado (prova completa de `sort`), Z3 integrado | `sort_perm.prova`, `test_next_steps.py` |
