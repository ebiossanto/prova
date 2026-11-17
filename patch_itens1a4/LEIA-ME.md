# Patch itens 1 a 4 para `ebiossanto/prova` (base: `prova-main.zip`)

## Como aplicar
**A) Com git (recomendado)**, na raiz do repositório:
```
git apply --whitespace=nowarn 0001-prova-itens-1-a-4.patch
git add -A && git commit -m "Itens 1-4: emit, gramática, testes reais, README honesto, boot"
python tests/run_tests.py
```
Não use `patch -p1`: o patch remove arquivos binários (`.pyc`, `.zip`) e só o `git apply` entende isso.
**B) Sem git:** copie o conteúdo de `prova-corrigido/` por cima do repositório (apague antes os `.zip`, `__pycache__` e `pytest_out.txt`).

## O que muda
1. **Consertos.** `emit` voltou a funcionar em programas com comparação (o ramo `op in ARITH or op in CMP` o quebrava); gramática com `call` de vários argumentos; `i8` não derruba mais o compilador; `smt.py` sem o sort inválido `(UInt 8)` (quebraria o Z3); resumo do `check` nunca fica negativo; saída em UTF-8 no Windows.
2. **Testes que podem falhar.** `tests/run_tests.py` (sem dependências, sai com código != 0), gramática testada de verdade, cobertura de `emit` por alvo, travas de solidez, fuzzing do provador com teste de que o fuzzer detecta um defeito injetado. `.github/workflows/ci.yml` (Linux e Windows), `.gitignore`, `.gitattributes`.
3. **Documentação honesta.** `README.md` com tabela de estado e evidência; `docs/STATUS.md` por fase; documentos antigos em `docs/archive/` com aviso; `Prova.lean` e `ai_correction_loop.py` marcados como esboço/simulado.
4. **Boot.** `_start` corrigidos (fd 1, `exit(0)`, `(len b)`); `python prova.py boot` gera stub (pilha, `.bss`, chamada a `kmain`) e linker script por arquitetura; arquivos em `boot/`; `scripts/build.sh` com modo kernel.

## O que foi verificado
- Patch aplicado num original intocado (extraído do seu zip): árvore idêntica à corrigida e 21/21 testes passando, sem avisos.
- Os testes novos, rodados contra o **código original**, derrubam 10 casos: eles pegam os defeitos de verdade.
- Stub x86-64: montado com `as`, ligado com `ld` e **executado**; saiu com código 0 (pilha alinhada e na região, `.bss` zerado e gravável).

## O que NÃO foi verificado (sem ferramenta no meu ambiente)
- O MLIR gerado nunca passou por `mlir-opt`/`llc`; `scripts/build.sh` não foi executado.
- Stubs AArch64 e RISC-V: só estrutura (sem toolchain nem QEMU).
- O CI do GitHub e o Windows: a configuração existe, mas eu não pude rodá-la.
- Z3 (o caminho existe, não testado) e Lean (nada compilado).

## Decisões que você pode querer reverter
- `atomic_*.prova`, `ring_buffer.prova` e os 4 `tests/*.prova` "proibidos" foram para `examples/wip/` e `tests/wip/` (não aceitos pelo verificador); nada foi apagado.
- A gramática voltou ao subconjunto que o verificador aceita (sem `ptr`/`atomic`/`region`).
- Scripts soltos da raiz foram para `scratch/`. Zips, `.pyc` e `pytest_out.txt` saíram do versionamento, mas **continuam no histórico do git**; `pytest_out.txt` contém `C:\Users\Euzebio...`. Para limpar o histórico use `git filter-repo`.

## Ainda pendente (itens 5 a 7 da análise)
Atômicos de verdade, laço de IA real, Lean com `elan` (e o módulo raiz do `lakefile`).
