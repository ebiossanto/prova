# Resumo da linguagem

```
topo     := (data nome "texto" [região]) | (region nome) | (deny-flow ORIGEM DESTINO)
          | (static nome (atomic i64|usize) inicial) | (mmio nome endereco i64|usize|u8 região) | fn
fn       := (fn nome (params (x T)...) (returns T|unit) [(effects syscall|atomic|mmio ...)] [(stack-budget N)]
               (pre e...) (post e...) (body stmt...))               ; ordem canônica; pre e post são obrigatórios
tipos    := i64 | usize | u8 | (slice u8 n [região]) | (own (slice u8 n [região]))   ; n = parâmetro declarado antes
stmt     := (let x T e) | (var x T e) | (set x e) | (let_slice b (data-ref d)) | (store b i v) | (drop b)
          | (if c (then s...) (else s...)) | (while c (invariant e...) (decreases e) s...)
          | (assert e) | (do e) | (return [e]) | (sys_exit e) | (atomic_store cel v ordem) | (mmio_write reg v)
expr     := inteiro | x | (+ - * add_wrap sub_wrap bit_and bit_or bit_xor shl shr a b)
          | (< <= > >= = != a b) | (and/or/not ...) | (cast T e) | (len b) | (load b i) | (occ b v)
          | (old e) | (forall var inicio fim cond)
          | (sys_write fd b n) | (call f arg...)
          | (atomic_load cel ordem) | (atomic_fetch_add cel v ordem) | (atomic_cas cel esperado novo sucesso falha)
          | (mmio_read reg)
ordem    := relaxed | acquire | release | acq_rel | seq_cst
```

## Regras
- **Contratos** usam inteiros matemáticos; o código executável tem todo overflow e deslocamento (`shl`/`shr`) provado dentro dos limites. `result` nomeia o retorno em `post`. `(load b i)`, `(occ b v)`, `(old e)` e `(forall k inicio fim cond)` (inclusive aninhado) permitem expressar e provar propriedades completas sobre fatias, incluindo ordenação e preservação de multiconjunto/permutação (`sort_perm.prova`). Uma `pre` contraditória é erro (tornaria toda prova vazia).
- **Laços**: todo `while` exige `invariant` e `decreases` (terminação). Sem recursão.
- **Tipos estritos**: sem conversão implícita (`cast` explícito), sem sombreamento, índices são `usize`.
- **Posse e aliasing**: `(own ...)` é consumido exatamente uma vez (`drop` ou movimento para um `own` de outra função). Passar a mesma fatia em dois parâmetros de uma chamada quando ao menos um é escrito é erro de aliasing mutável.
- **Efeitos**: sem `(effects ...)` a função é pura. `syscall` (`sys_write`, `sys_exit`), `atomic` e `mmio` (`mmio_read`, `mmio_write`) precisam ser declarados e propagam de chamado para chamador.
- **Regiões**: fatias e registradores `(mmio ...)` têm região; passar para um parâmetro com outra região é erro de tipo;
  `deny-flow A B` proíbe que dado de A chegue a B (também de forma transitiva, por variáveis, chamadas, memória, células
  atômicas e MMIO). Destinos especiais: `@write` (saída por syscall), `@static:NOME` (célula atômica) e `@mmio:NOME` (registrador de hardware).
- **Memória compartilhada e MMIO**: memória compartilhada entre threads é `(static ... (atomic T))`; acesso volátil de hardware é `(mmio nome endereco T região)`. Cada operação atômica escolhe a ordem; `load` não pode ser `release`/`acq_rel`, `store` não pode ser `acquire`/`acq_rel`, a ordem de falha do `cas` não pode ser mais forte que a de sucesso. O valor lido de um atômico ou MMIO nunca é assumido estável. `atomic_fetch_add`, `add_wrap` e `sub_wrap` dão a volta (wrap) por definição.
- **Pilha**: `(stack-budget N)` é provado pelo grafo de chamadas com quadros de um modelo de custo (ou `--frames`).

Fora da linguagem (por enquanto): `u32`/`i8`, alocação dinâmica, recursão, threads. Ver `docs/STATUS.md`. Gramática testada: `spec/prova.gbnf` (GBNF = notação BNF do GGML/llama.cpp).
