# Resumo da linguagem (MVP)

```
topo     := (data nome "texto") | (fn nome (params (x T)...) (returns T|unit) (pre e...) (post e...) (body stmt...))
tipos    := i64 | usize | u8 | (slice u8 n) | (own (slice u8 n))      ; n = parâmetro declarado antes
stmt     := (let x T e) | (var x T e) | (set x e) | (let_slice b (data-ref d)) | (store b i v)
          | (if c (then s...) (else s...)) | (while c (invariant e...) (decreases e) s...)
          | (assert e) | (do e) | (drop x) | (return [e]) | (sys_exit e)
expr     := inteiro | x | (+ - * a b) | (< <= > >= = != a b) | (and/or/not ...) | (cast T e)
          | (len b) | (load b i) | (sys_write fd b n) | (call f arg...)
```
Regras: contratos usam inteiros matemáticos; código executável tem overflow provado ausente;
`result` nomeia o retorno em `post`; todo `while` precisa de `decreases`; sem sombreamento; sem conversão implícita.

Fora da linguagem (por enquanto): `u32`/`i8`, `atomic`, `ptr`/MMIO com regiões, conteúdo de fatias em contratos,
alocação dinâmica, recursão. Ver `docs/STATUS.md`. Gramática testada: `spec/prova.gbnf` (GBNF = notação BNF do GGML/llama.cpp).
