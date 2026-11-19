# scratch/: scripts de depuração antigos (NÃO fazem parte do projeto)

Restos do desenvolvimento das Fases 1 e 8. Vários têm caminhos fixos (`D:/PROVA linguagem/...`) e não
rodam em outra máquina. Os testes de verdade estão em `tests/`. Pode apagar esta pasta quando quiser.

`ai_correction_loop.py` (simulado, não chamava modelo nenhum) foi substituído por `python prova.py fix` (`provac/loop.py`), que tem laço de verdade e contratos travados.

`validate_toolchain.py` (19/nov) é a varredura da Fase 10: 16 exemplos × 3 alvos pelo pipeline real
`mlir-opt → mlir-translate → opt → llc → ld.lld` → ELF (48/48 na última execução). O equivalente
permanente — que roda na suíte e no CI, com skip sem as ferramentas — é `tests/test_mlir_toolchain.py`.
