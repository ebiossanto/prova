# examples/wip: experimentos que AINDA NÃO funcionam

Estes arquivos usam sintaxe que a linguagem não implementa (`(atomic u32)`, `u32`, `region`, `let ((..))`,
`+wrap`, `bit-and`, `atomic-load`...). Não são aceitos pelo verificador nem pela gramática e ficam fora
dos testes. Atualização: os atômicos tipados agora existem (`(static x (atomic usize) 0)`, `atomic_load/store/fetch_add/cas` com ordem
checada); veja `examples/atomic_counter.prova`. Estes arquivos continuam em `wip/` porque dependem de `u32`, ponteiros e
algoritmos lock-free, que ainda não existem.
`atomic_counter.prova` ainda tem um `)` sobrando na linha 86.
