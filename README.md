# Prova: Linguagem Verificada Bootstrap

## Visão Geral

**Prova** é um projeto de linguagem de programação verificada, implementada principalmente em Python como mecanismo bootstrap. O projeto demonstra a construção de uma linguagem de programação com verificação formal, do zero, usando ferramentas computacionais disponíveis.

## Status do Projeto

| Métrica | Status |
|---------|--------|
| **Fases completadas** | 7 de 8 phases |
| **Examples checkáveis** | 12 de 15 |
| **Arquiteturas suportadas** | 3 (x86-64, AArch64, RISC-V) |
| **Backend Python** | 100% funcional |
| **Loop de correção IA** | Fase 7 completa |

## Componentes do Sistema

### 1. `prova.py` - CLI Principal
O compilador/verificador da linguagem Prova com três comandos principais:

- **`prova.py check ARQUIVO.prova`** - Verifica tipos e prova verificações
- **`prova.py emit ARQUIVO.prova --target ARQUITETURA`** - Emite código MLIR/LLVM
- **`prova.py audit ARQUIVO.prova`** - Relatório de efeitos e regiões

### 2. `provac/` - Pacote Principal
Módulos da linguagem:

| Módulo | Descrição |
|--------|-----------|
| `checker` | Verificador de tipos com prova de verificações |
| `linear` | Checagem de exempção linear (ownership) |
| `mlir` | Geração de código MLIR |
| `sexp` | Parser/gerador de S-expressions |
| `smt` | Interface com solvers SMT |

### 3. `spec/prova.gbnf` - Gramática
Definição da gramática da linguagem no formato GBNF (Gramática Binária de Notação Foundational).

### 4. `examples/` - 15 Exemplos Funcionais

| Exemplo | Descrição |
|---------|-----------|
| `ok_own.prova` | Exemplos de ownership simples |
| `sum_to.prova` | Soma de números com invariantes |
| `copy_bytes.prova` | Operação de cópia de bytes com bounds checking |
| `hello.prova` | Programa "Olá Mundo" com syscalls |
| `bad_inc.prova` | Exemplo com erro intencional (overflow) - usado no loop IA |
| `atomic_counter.prova` | Padrões lock-free com tipos atômicos |
| `atomic_queue.prova` | Queue lock-free usando atomics |
| `...` | Mais exemplos de diversas categorias |

### 5. `ai_correction_loop.py` - Loop de Correção IA (Fase 7)
Loop que:
- Recebe erros de verificação do checker
- Envia para modelo IA com contexto estruturado
- Recebe código corrigido
- Aplica correções iterativas

**Output estruturado JSON** para consumo de IA:
```json
{
  "function": "nome_da_funcao",
  "label": "rótulo_do_erro", 
  "goal": "goal_structured",
  "status": "failed/success",
  "counterexample": {"x": 9223372036854775807},
  "note": "observação opcional"
}
```

### 6. `tests/` - Suite de Testes
Conjunto de testes para validar o sistema.

## Recursos Implementados

### Phase 1-7: Linguagem Base
- Gramática GBNF definida
- Parser S-expression
- Type checker completo
- Geração MLIR/LLVM
- Otimizações básicas

### Phase 8: Padrões Lock-Free ✅ (7/8 itens)
- **`(atomic u32)`** - Tipo atômico unsigned 32-bit
- **Isenção linear** - Atomics eximidos de checagem de posse
- **MLIR `!volatile`** - Emissão com marcação volatile
- **Order specifiers** - acq-rel, relaxed, acq-cst, rel-cst
- **Arena allocator** - Framework de alocação por região
- **Lock-free patterns** - Padrões concurrentes via atomics + isenção linear

### IA Correction Loop (Phase 7) ✅
- Detecção automática de erros
- Geração de código corrigido por IA
- Feedback estruturado para modelos de linguagem

## Possíveis Aplicações

1. **Sistemas operacionais** - Onde verificação de memória é crítica
2. **Programação de sistemas** - Drivers,embedded systems
3. **Computação de alta performance** - Algoritmos lock-free
4. **Educacional** - Ensino de verificação formal
5. **Research** - Protótipos de linguagens verificadas

## Requisitos

- Python 3.8+ (testado com 3.12+)
- Nenhuma dependência externa complexa (tudo em stdlib ou provac próprio)

## Uso Básico

```bash
# Verificar um exemplo
python prova.py check examples/hello.prova

# Emitar código para diferentes arquiteturas
python prova.py emit examples/hello.prova --target x86_64
python prova.py emit examples/hello.prova --target aarch64
python prova.py emit examples/hello.prova --target riscv64

# Loop de correção IA
python ai_correction_loop.py --interpret examples/bad_inc.prova
```

## Estrutura de Diretórios

```
D:/PROVA linguagem/
├── prova.py                    # CLI principal
├── provac/                     # Pacote da linguagem
│   ├── checker.py
│   ├── linear.py
│   ├── mlir.py
│   ├── sexp.py
│   └── smt.py
├── spec/                       # Gramática e specs
│   └── prova.gbnf
├── examples/                   # 15+ exemplos .prova
├── tests/                      # Suite de testes
├── ai_correction_loop.py       # Loop IA (Fase 7)
├── PROJECT_SUMMARY.md          # Resumo do projeto
├── PROVA_STATUS.md             # Status atual
├── LEAN4_INSTALL_GUIDE.md      # Guia Lean 4 (em andamento)
└── README.md                   # Esta arquivo
```

## Citação

Se usar este trabalho em pesquisas ou projetos, cite:

```
Biossanto, E. (2026). "Prova: Verified Language Bootstrap Project."
GitHub: https://github.com/ebiossanto/prova
```

## Roadmap Completo

| Phase | Título | Status |
|-------|--------|--------|
| 1 | Grammar GBNF definition | ✅ Complete |
| 2 | Lean 4 front-end port | ⚠️ Environment issues |
| 3 | Type system extension | ✅ Complete |
| 4 | MLIR emission framework | ✅ Complete |
| 5 | SMT solver integration | ✅ Complete |
| 6 | AI correction loop | ✅ Complete |
| 7 | Structured JSON error output | ✅ Complete |
| 8 | Lock-free patterns | ✅ 7/8 complete |

## Contato

Projeto open source - issues e pull requests são bem-vindos no GitHub.