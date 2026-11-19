# Relatório de Mudanças - Revisão dos Patches

**Data:** 16 de novembro de 2026  
**Fonte:** 3 patches zipados fornecidos pelo usuário

---

## 📦 Patches Analisados

| Patch | Data | Conteúdo Principal |
|-------|------|-------------------|
| `prova-patch-itens-1-a-4 revisado.zip` | 14/11 | Itens 1-4 revisados + estrutura organizada |
| `prova-patch-0002-ideia-original.zip` | 14/11 | Alinhamento com a ideia original + mais features |
| `prova-patch-0003-programa-de-teste.zip` | 16/11 | Programas de teste executáveis + correções |

---

## 🔄 Progressão dos Patches

### **Patch 1 (Itens 1-4 revisado)** — Base
- **Estrutura organizada**: `docs/`, `boot/`, `scratch/`, `examples/wip/`, `tests/wip/`
- **Novos módulos provac/**: `boot.py`, `audit.py`
- **Documentação movida para `docs/archive/`**: todos os .md antigos reorganizados
- **CI GitHub**: `.github/workflows/ci.yml` para Linux e Windows

### **Patch 2 (Ideia Original)** — Features Críticas Adicionadas

| Feature | Implementação |
|---------|---------------|
| **Efeitos na assinatura** | `(effects syscall atomic)` — funções puras sem cláusula |
| **Regiões e fluxo de dados** | `(slice u8 n net-rx)`, `(region ...)`, `(deny-flow A B)` transitivo |
| **Orçamento de pilha** | `(stack-budget N)` provado pelo grafo de chamadas |
| **Memória concorrente** | `(static x (atomic usize) 0)`, `atomic_load/store/fetch_add/cas` com ordens tipadas |
| **IA loop fechada** | `prova.py fix` com contratos travados (IA não pode alterar) |
| **Precontradição detectada** | Condição contraditória agora é erro (antes "provava" tudo) |

### **Patch 3 (Programa de Teste)** — Execução e Validação

| Feature | Implementação |
|---------|---------------|
| **Interpretador de referência** | `provac/interp.py` + `prova.py run` |
| **Programas de teste executáveis** | `selftest.prova` (179 obrigações), `packet_inspector.prova` (60 obrigações) |
| **Teste diferencial** | Programa verificado que viole em execução = defeito do verificador |
| **Correções no verificador** | Escrita em fatia `data` (read-only) bloqueada; `let` após `if` bifurcado corrigido |
| **Correções no fuzzer** | "Combustível esgotado" é inconclusivo (não violação); `gcd` com entradas grandes não trava |

---

## 📁 Estrutura Final (Patch 3 — Mais Completa)

```
prova-corrigido/
├── provac/           # 14 módulos Python
│   ├── sexp.py       # Leitor S-expressions
│   ├── check.py      # Tipos + VCs
│   ├── linear.py     # Posse linear
│   ├── linarith.py   # Provador interno (Fourier-Motzkin + McCormick)
│   ├── effects.py    # Efeitos na assinatura
│   ├── flow.py       # Regiões/fluxo de dados
│   ├── stack.py      # Orçamento de pilha
│   ├── program.py    # Programa completo
│   ├── loop.py       # Loop com IA
│   ├── smt.py        # Provador interno → Z3 opcional
│   ├── mlir.py       # Emissão MLIR
│   ├── audit.py      # Auditoria
│   ├── boot.py       # Boot bare-metal
│   └── interp.py     # Interpretador de referência
├── spec/
│   ├── prova.gbnf    # Gramática GBNF (para constrained decoding IA)
│   └── LANGUAGE.md   # Especificação
├── examples/         # Programas que DEVEM verificar
│   ├── selftest.prova         # 6 funções + _start auto-testável (179 provas)
│   ├── packet_inspector.prova # Inspetor de pacotes (60 provas)
│   ├── driver_demo.prova      # Combina todas as features
│   ├── bad_*.prova            # 12+ que DEVEM ser recusados
│   └── wip/                   # Experimentos (ring_buffer, atomic_*)
├── tests/            # 97 testes, ~12s
│   ├── run_tests.py
│   ├── test_checker.py, test_flow.py, test_stack.py
│   ├── test_effects.py, test_atomics.py
│   ├── test_selftest.py, test_packet_inspector.py
│   ├── test_emit.py, test_boot.py
│   └── wip/          # Testes a reescrever
├── boot/             # Stubs + linker scripts (x86_64, aarch64, riscv64)
├── lean/             # Esboço Lean 4 (Core.lean, Sexp.lean)
├── docs/
│   ├── STATUS.md     # Mapa completo da ideia original
│   └── archive/      # Docs antigos
├── scripts/build.sh  # Pipeline completo (requer LLVM/MLIR)
├── .github/workflows/ci.yml  # CI Linux + Windows
└── prova.py          # CLI principal
```

---

## 📊 Estado da Ideia Original (docs/STATUS.md)

| Camada | Item | Estado |
|--------|------|--------|
| **Semântica** | Contratos pre/post, erros matemáticos | ✅ Sim |
| | Overflow, limites, invariantes, terminação | ✅ Sim |
| | Tipos dependentes (comprimento no tipo) | ✅ Sim |
| | Posse linear de fatias | ✅ Sim |
| | Conteúdo de fatias em contratos | ✅ Sim (McCarthy + Z3; `sort_perm.prova`) |
| | Certificados Lean 4 | ⚠️ Lemas compilam (`SortPerm.lean`); exportação automática é a Fase 9 |
| **Sintaxe** | S-expressions sem açúcar | ✅ Sim |
| | Gramática GBNF (constrained decoding) | ✅ Sim |
| | IA loop fechada, contratos travados | ✅ Sim (mecânica) |
| **Hardware** | Efeitos na assinatura | ✅ Sim |
| | Regiões + fluxo de dados | ✅ Sim (só fluxo explícito) |
| | Orçamento de pilha | ⚠️ Parcial (modelo de custo) |
| | Memória concorrente (atomics) | ✅ Sim (tipos, ordens e MLIR validados) |
| | Execução (interpretador) | ✅ Sim |
| | Programas de teste executáveis | ✅ Sim |
| | Compilação nativa (MLIR→LLVM→ELF) | ✅ Sim (validada em 19/nov, `test_mlir_toolchain.py`) |
| | Boot x86-64 freestanding | ✅ Sim (montado, ligado, executado) |
| | Boot AArch64/RISC-V | ⚠️ Parcial (ligado em ELF; não executado — sem qemu-user) |
| | Z3 opcional | ✅ Sim (`z3-solver` 5.4.1 integrado e testado) |

---

## 🎯 O que os Patches Acrescentam vs Estado Anterior

### ✅ **Novidades Principais (não existiam antes)**

1. **Programas de teste executáveis reais** — `selftest.prova` com 6 funções (gcd, sum_bytes, count_byte, max_byte, sort, reverse) que se autotestam
2. **Interpretador de referência** — `prova.py run` executa e valida contratos em runtime
3. **Teste diferencial** — encontra defeitos no verificador automaticamente
4. **Packet inspector** — programa completo usando regiões, efeitos, atomics, syscalls
5. **Efeitos na assinatura** — `(effects syscall atomic)` com propagação
6. **Regiões + fluxo de dados** — `(deny-flow A B)` transitivo, `prova.py flow`
7. **Orçamento de pilha** — `(stack-budget N)` provado pelo call graph
8. **AIClosed loop** — `prova.py fix` com contratos travados
9. **97 testes automatizados** — incluindo teste diferencial
10. **CI GitHub** — Linux + Windows

### 🔧 **Correções Encontradas pelo Próprio Autor**

1. Escrita em fatia vinda de `data` (read-only) era aceita — AGORA bloqueada
2. `let` após `if` bifurcado dava "redeclaração" falsa — corrigido
3. Fuzzer contava "combustível esgotado" como violação — agora é inconclusivo
4. `gcd` com entradas grandes travava o fuzzer — limitado
5. Precondição contraditória "provava" tudo — agora é erro

### 📈 **Testes e Validação**

- **97 testes automatizados** (~12 segundos)
- **14 defeitos injetados propositalmente** — todos derrubados pela suíte
- **Fuzzing**: ~380 marcações de contradição, 0 falso alarme
- **Teste diferencial**: programas verificados executados e comparados
- **Modelli di test deterministici**: honesto, trapaceiro, lixo, teimoso

---

## 🚧 O que NÃO está implementado (limitações explícitas)

| Item | Motivo |
|------|--------|
| Certificados Lean 4 automáticos (`prova.py cert`) | Fase 9 do roadmap; hoje só há lemas escritos à mão em `lean/Prova/` (compilam) |
| Ponteiros crus / aritmética de ponteiros | MMIO tipado existe (`mmio_read`/`mmio_write`), mas não há ponteiros na linguagem |
| Alocador dinâmico verificado | Só posse linear de fatias recebidas |
| Registradores como recursos lineares | Não implementado (Fase 11) |
| Threads / lock-free verification | Atomics garantem tipos/ordens, não correção de algoritmos |
| Medição de quadros de pilha reais (`--frames`) | Só existe o modelo de custo; a toolchain já está instalada (resto da Fase 10) |
| Execução dos ELFs gerados neste Windows | Alvo é Linux; sem `qemu-user`/WSL neste ambiente (validação para no ELF checado) |

---

## 🔄 Próximos Passos Implementados (17/nov/2026)

1. **Teoria de Arrays e Quantificadores em Contratos (`load`, `old`, `forall`, `occ`):**
   - Implementada redução de McCarthy (*read-over-write*), congruência de Ackermann, Skolemização e cancelamento algébrico de ocorrências (`occ`) em `provac/linarith.py` + integração em processo com **Z3 5.4.1** (`provac/smt.py`).
2. **Prova Estática Completa de Ordenação e Permutação (`examples/sort_perm.prova` + `lean/Prova/SortPerm.lean`):**
   - `sort_perm.prova`: 67/67 obrigações provadas estaticamente (ordenação par-a-par com `forall` aninhado + preservação de multiconjunto com `occ`).
   - `lean/Prova/SortPerm.lean`: certificado formal compilado sem erros no **Lean 4 (v4.36.0-rc2)** provando os axiomas de McCarthy, a preservação de `occ` em trocas (`occ_swap_preserved`) e o passo indutivo do Bubble Sort (`bubble_suffix_step`, `bubble_partition_step`).
3. **MMIO Tipado com Regiões, Operadores Bitwise/Shift/Wrap e Ring Buffer SPSC (`examples/ring_buffer.prova`):**
   - `(mmio nome endereco T regiao)`, `mmio_read`, `mmio_write`, efeito `mmio` e destino `@mmio:NOME` em `deny-flow`.
   - `bit_and`, `bit_or`, `bit_xor`, `shl`, `shr` (com VC `0 <= y < width`) e `add_wrap`/`sub_wrap`.
   - `examples/ring_buffer.prova`: 55/55 obrigações provadas estaticamente e execução validada.
4. **Suíte de Testes Expandida:**
   - **103 testes passando, 0 falhas** em `python tests/run_tests.py` (incluindo os 4 casos negativos de segurança em `tests/` e compilação dos certificados Lean 4).

---

## 🔄 Fase 10 — Toolchain MLIR/LLVM instalada e validada (19/nov/2026)

O bloqueio da Fase 10 ("nenhuma ferramenta LLVM neste ambiente") foi removido **sem privilégios de
administrador**:

1. **Instalação portátil**
   - LLVM oficial 23.1.6 (`clang+llvm-…tar.zst`, 276 MB) extraído em `D:\clang+llvm-23.1.6-x86_64-pc-windows-msvc`: `opt`, `llc`, `clang`, `ld.lld` — **sem** `mlir-opt` (o instalador/MSI oficial não traz as ferramentas MLIR).
   - MSYS2 portátil extraído em `D:\msys64` + `pacman`: `mingw-w64-clang-x86_64-mlir` 23.1.5 (`mlir-opt`, `mlir-translate`), `llvm`, `lld`, `clang` (o pacote `qemu` só traz modo system, sem user-mode).
2. **Validação real: 48/48** — `scratch/validate_toolchain.py` varre 16 exemplos × 3 alvos (x86_64, aarch64, riscv64) por `emit → mlir-opt → mlir-translate → opt → llc → ld.lld`, conferindo a mágica ELF no objeto e no binário.
3. **3 bugs reais encontrados e corrigidos em `scripts/build.sh`**
   - `-nostdlib` é flag do driver `clang`, não do `ld.lld` — o link falhava;
   - riscv64 sem `-mattr` baixava átomicos para `__atomic_*`/libatomic e o kernel não ligava por ABI de ponto flutuante diferente da do stub de boot → `-mattr=+m,+a,+f,+d,+c` (rv64gc, a mesma ABI lp64d do clang);
   - `python3` não existe no Windows → fallback `python3 || python`.
   - (o `ld.lld` do MSYS2 23.1.5 rejeita até ELF válido — bug do pacote; o link usa o oficial 23.1.6.)
4. **Teste permanente** `tests/test_mlir_toolchain.py`: 6 exemplos × 3 alvos + kernel (stub de boot + linker script) dos 3 alvos, com **skip** se as ferramentas faltarem. Suíte local: **105 testes passando, 0 falhas, 1 skip**.
5. **CI**: `.github/workflows/ci.yml` instala `mlir-*-tools`, `llvm-*`, `lld-*` e `clang-*` no job Linux (versão detectada automaticamente), então a validação roda também no GitHub.

**Pendências honestas:** os ELFs gerados não são *executados* neste Windows (sem `qemu-user`/WSL);
os quadros de pilha reais ainda não foram medidos para alimentar `--frames` (resto da Fase 10).

---

## 📌 Conclusão

Os patches representam um **salto significativo** em relação ao estado anterior:

- **De:** Verificador básico + exemplos simples
- **Para:** Sistema completo com semântica (contratos, tipos, provas), sintaxe para IA (GBNF), recursos de hardware (efeitos, regiões, pilha, atomics, syscalls, boot), execução validada, compilação MLIR→LLVM→ELF validada nos 3 alvos e 105 testes automatizados

A **ideia original** está **majoritariamente implementada** (21/25 itens mapeados), com limitações documentadas e honestas. O patch 0003 é a versão mais completa e pronta para desenvolvimento contínuo.