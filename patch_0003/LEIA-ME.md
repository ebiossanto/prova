# Patch 0003: programa de teste executável (base: o zip do patch 0002)

## Como aplicar (na raiz do repositório, com git)
- **Você aplicou 0001 e 0002**: `git apply --whitespace=nowarn 0003-programa-de-teste.patch`
- **Você não aplicou nada**: `git apply --whitespace=nowarn "cumulativo-0001+0002+0003.patch"`
- **Sem git**: copie `prova-corrigido/` por cima do repositório (apague antes `.zip`, `__pycache__` e `pytest_out.txt`).

Depois: `python tests/run_tests.py` (97 testes, ~12 s). Não use `patch -p1` (há remoções de binários).

## O programa de teste
`examples/selftest.prova`: seis funções (`gcd`, `sum_bytes`, `count_byte`, `max_byte`, `sort`, `reverse`) e um `_start` que confere
resultados esperados e escreve `PASS` ou `FAIL` (código de saída 0 ou 1). Há também `examples/packet_inspector.prova` (regiões, política
de fluxo, átomos, syscalls, pilha).
```
python prova.py check examples/selftest.prova     # 179 obrigações provadas, nenhuma só "testada"
python prova.py run   examples/selftest.prova     # PASS (código 0), conferindo contratos/invariantes/variantes a cada passo
```
**Execução** é por um interpretador de referência (`provac/interp.py`): LLVM/MLIR não existe no meu ambiente, então **nada foi executado
como código nativo**. O interpretador também faz teste diferencial: programa verificado que viole algo em execução é defeito do verificador.

## O que este patch traz (14 arquivos)
- `selftest`, `packet_inspector`, interpretador, comando `prova.py run`, testes (`test_selftest`, `test_run`, `test_packet_inspector`).
- **Correções no verificador** achadas ao escrever o programa: (1) escrever numa fatia vinda de `data` (memória somente-leitura) era
  aceito, direta ou via chamada; (2) um `let` depois de um `if` que bifurca estados dava "redeclaração" falsa.
- **Correções nos testes/fuzzer** que encontrei ao retomar: o fuzzer contava "combustível esgotado" como *violação* (falso positivo) e
  travava em `gcd` com entradas grandes (>5 min); dois testes de `selftest` falhavam por mutações aplicadas na função errada
  (`replace` na primeira ocorrência). Agora: inconclusivo ≠ violação, e as mutações são limitadas à função alvo e falham com mensagem clara.
  Cada correção foi conferida injetando o defeito de volta (os testes o derrubam).

## O que o teste mostra e o que NÃO mostra
- A Prova ainda não expressa "o vetor ficou ordenado" em contrato (conteúdo de fatias não é modelado). Um `sort` com a comparação
  invertida é **aceito** pelo verificador (é seguro, só está errado); quem o pega é a execução em `test_selftest.py`, comparando com o
  Python. Segurança de memória, ausência de overflow, terminação e política de fluxo são provadas; a correção funcional é testada.
- Achado real: sem `(pre (<= n 1000000))`, `reverse` falha com `lo = hi = n = 2^64-1` (a condição `(+ lo 1)` estouraria).

## Não verificado
MLIR/LLVM, AArch64/RISC-V, CI no GitHub, Windows, Z3 e Lean seguem como antes (veja `docs/STATUS.md`).
