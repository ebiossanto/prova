# tests/wip: casos movidos para tests/

Os quatro casos negativos (`test_atomic_uaf.prova`, `test_aliasing_mut.prova`, `test_shift_ub.prova` e
`test_loop_contract_lock.prova`) foram reescritos na sintaxe oficial da Prova, movidos para `tests/` e são
verificados automaticamente em `tests/test_next_steps.py`.
