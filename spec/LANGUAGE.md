# Resumo da linguagem

```
topo     := (data nome "texto" [região]) | (region nome) | (deny-flow ORIGEM DESTINO)
          | (static nome (atomic i64|usize) inicial) | fn
fn       := (fn nome (params (x T)...) (returns T|unit) [(effects syscall|atomic ...)] [(stack-budget N)]
               (pre e...) (post e...) (body stmt...))               ; ordem canônica; pre e post são obrigatórios
tipos    := i64 | usize | u8 | (slice u8 n [região]) | (own (slice u8 n [região]))   ; n = parâmetro declarado antes
stmt     := (let x T e) | (var x T e) | (set x e) | (let_slice b (data-ref d)) | (store b i v) | (drop b)
          | (if c (then s...) (else s...)) | (while c (invariant e...) (decreases e) s...)
          | (assert e) | (do e) | (return [e]) | (sys_exit e) | (atomic_store cel v ordem)
expr     := inteiro | x | (+ - * a b) | (< <= > >= = != a b) | (and/or/not ...) | (cast T e) | (len b) | (load b i)
          | (sys_write fd b n) | (call f arg...)
          | (atomic_load cel ordem) | (atomic_fetch_add cel v ordem) | (atomic_cas cel esperado novo sucesso falha)
ordem    := relaxed | acquire | release | acq_rel | seq_cst
```

## Regras
- **Contratos** usam inteiros matemáticos; o código executável tem todo overflow provado ausente. `result` nomeia o retorno em `post`.
  Uma `pre` contraditória é erro (tornaria toda prova vazia).
- **Laços**: todo `while` exige `invariant` e `decreases` (terminação). Sem recursão.
- **Tipos estritos**: sem conversão implícita (`cast` explícito), sem sombreamento, índices são `usize`.
- **Posse**: `(own ...)` é consumido exatamente uma vez (`drop` ou movimento para um `own` de outra função).
- **Efeitos**: sem `(effects ...)` a função é pura. `syscall` (`sys_write`, `sys_exit`) e `atomic` precisam ser declarados e
  propagam de chamado para chamador.
- **Regiões**: fatias podem ter região (`(slice u8 n net-rx)`); passar para um parâmetro com outra região é erro de tipo;
  `deny-flow A B` proíbe que dado de A chegue a B (também de forma transitiva, por variáveis, chamadas, memória e células
  atômicas). Destinos especiais: `@write` (saída por syscall) e `@static:NOME` (célula atômica).
- **Memória compartilhada**: só `static` atômico. Cada operação escolhe a ordem; `load` não pode ser `release`/`acq_rel`,
  `store` não pode ser `acquire`/`acq_rel`, a ordem de falha do `cas` não pode ser mais forte que a de sucesso.
  O valor lido de um atômico nunca é assumido estável. `atomic_fetch_add` dá a volta (wrap) por definição.
- **Pilha**: `(stack-budget N)` é provado pelo grafo de chamadas com quadros de um modelo de custo (ou `--frames`).

Fora da linguagem (por enquanto): `u32`/`i8`, ponteiros/MMIO, conteúdo de fatias em contratos, alocação dinâmica, recursão,
threads. Ver `docs/STATUS.md`. Gramática testada: `spec/prova.gbnf` (GBNF = notação BNF do GGML/llama.cpp).
