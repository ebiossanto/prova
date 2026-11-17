# examples/wip: experimentos que AINDA NÃO funcionam

Estes arquivos usam sintaxe que a linguagem não implementa (`(atomic u32)`, `u32`, `region`, `let ((..))`,
`+wrap`, `bit-and`, `atomic-load`...). Não são aceitos pelo verificador nem pela gramática e ficam fora
dos testes. Voltam para `examples/` quando os atômicos existirem de verdade (tipos `u32`, operações
`atomic_load/store/fetch_add/cas` com ordem checada, emitidas como ops reais do dialeto `llvm`).
`atomic_counter.prova` ainda tem um `)` sobrando na linha 86.
