> **Arquivo histórico (movido em 13/nov/2026).** Contém afirmações de status não verificadas e contradições entre documentos. O estado real, com a evidência de cada item, está em [`docs/STATUS.md`](../STATUS.md).

## **Prova: base de uma linguagem verificada para IA e kernel**

Chamei a linguagem de **Prova** (nome provisório). Minha conclusão sobre as três abordagens é que elas não competem, e sim formam camadas de um mesmo sistema.

### **1\. Análise das três abordagens**

|  | Contrato Matemático | AST / S-Expressions | Híbrida p/ Hardware |
| ----- | ----- | ----- | ----- |
| **Resolve** | *O que* é correto | *Como* escrever sem erro de sintaxe | *Onde* cada dado vive e flui |
| **Ponto forte** | Auditoria humana curta; erro formal que a IA usa para se corrigir | Constrained decoding, com sintaxe inválida impossível | Familiaridade para a IA; relatórios de fluxo de dados |
| **Risco** | O contrato pode estar errado (a prova só garante o que foi especificado); o SMT pode dar timeout | Verbosidade; pouca leitura humana direta | Sozinha não prova nada; etiquetas sem checagem viram comentários |
| **Papel na Prova** | Camada de **semântica** | Camada de **sintaxe** | Camada de **recursos e hardware** |

**Decisão:** a sintaxe é de S-expressions (abordagem 2). O sistema de tipos e contratos é o da abordagem 1\. As etiquetas de origem e destino da abordagem 3 viram **regiões e capacidades no sistema de tipos**, e não metadados soltos. Assim, o relatório de fluxo de dados é um subproduto do verificador.

### **2\. Arquitetura do compilador**

```
fonte .prova (S-expr)
   │  parser com gramática fechada ──► (mesma gramática alimenta o constrained decoding da IA)
   ▼
AST tipada ── checagem linear/afim + regiões + capacidades
   │
   ├─► gerador de VCs (condições de verificação) ─► Z3 (automático)
   │                                               └► Lean 4 (prova manual/da IA, certificado)
   ▼
dialeto MLIR `prova`  ──►  memref / arith / cf / scf  ──►  dialeto `llvm`
   ▼
LLVM IR ──► llc ──► x86-64 | AArch64 | RISC-V (sem escrever Assembly por arquitetura)
```

**Por que MLIR e não só LLVM IR:** o dialeto `prova` preserva ownership, regiões e contratos até o fim. Isso permite otimizações e relatórios de fluxo *antes* de perder a informação no LLVM IR. O LLVM cuida do backend para cada CPU.

**Escolha de implementação para o MVP:** o front-end (parser, tipos, VCs) em **Lean 4**, emitindo **MLIR textual**. Depois, `mlir-opt`, `mlir-translate` e `llc` fazem o resto. Isso dispensa bindings C++ no início e deixa o verificador no mesmo ambiente das provas.

### **3\. Sistema de tipos**

* **Tipos lineares/afins** para posse de memória: `(own T)` é movido e usado exatamente uma vez, e `(ref T)` e `(mut T)` são empréstimos com região.  
* **Tipos de refinamento** (um subconjunto de tipos dependentes) para tamanhos: `(slice u8 n)` carrega `n` no tipo, e `n` é decidível por Z3.  
* **Aritmética explícita:** nada de overflow implícito. `+` exige prova de não-estouro, ou você escreve `+wrap`, `+sat` ou `+checked`.  
* **Efeitos e capacidades:** `(effects syscall mmio)` aparece na assinatura, e uma função sem a capacidade não pode tocar o recurso.

#### **Exemplo**

lisp

```
(fn copy-bytes
  (params (dst (mut (slice u8 n)))
          (src (ref (slice u8 m)))
          (len usize))
  (returns unit)
  (pre  (<= len n) (<= len m))                       ; contrato lido pelo humano
  (post (forall (i usize) (< i len)
          (= (get dst i) (get src i))))
  (effects)                                          ; pura: sem syscall nem MMIO
  (body
    (loop (i usize 0) (< i len)
      (invariant (<= i len)
                 (forall (j usize) (< j i) (= (get dst j) (get src j))))
      (decreases (- len i))
      (set (index dst i) (index src i))
      (continue (+ i 1)))))
```

O compilador gera obrigações como `i < len ∧ len ≤ n ⟹ i < n` para o acesso `(index dst i)`. Se Z3 não prova, o erro é do tipo: *“não consigo provar `i < n`; contraexemplo: `len=5, n=4`”*. Esse é o laço fechado que a IA usa para se corrigir.

### **3.1. Hardware**

#### **Syscalls e registradores como recursos lineares**

Um registrador é um recurso que se consome e se produz. A syscall é um intrínseco com *clobbers* declarados, e o `llvm.inline_asm` é gerado pelo compilador, não pelo programador:

| Arquitetura | Instrução | Nº da syscall | Argumentos | Clobbers |
| ----- | ----- | ----- | ----- | ----- |
| x86-64 | `syscall` | `rax` | `rdi rsi rdx r10 r8 r9` | `rcx`, `r11` |
| AArch64 | `svc #0` | `x8` | `x0`–`x5` | memória |
| RISC-V | `ecall` | `a7` | `a0`–`a5` | memória |

lisp

```
(intrinsic syscall3
  (params (nr usize) (a (own Fd)) (b (ref (slice u8 n))) (c usize))
  (pre (<= c n))
  (effects syscall)
  (target-lowering (x86_64 ...) (aarch64 ...) (riscv64 ...)))
```

O `pre` impede passar `c` maior que o buffer. O `own Fd` impede usar o descritor depois de `close`.

#### **Modelo de memória concorrente**

* Base: modelo de memória do LLVM/C11, com ordenações explícitas no tipo: `(atomic u32 :order acq-rel)`.  
* A posse linear impede *data races* por construção: para compartilhar dados, é preciso transferir a posse ou usar um tipo atômico.  
* Fronteira honesta: provar corretude sob *weak memory* (ARM e RISC-V) é muito mais difícil que em x86. Na v1, os contratos cobrem o código sequencial e o uso correto de atômicos. A verificação de algoritmos lock-free fica para depois.

#### **Boot freestanding**

Sem libc, o programa precisa de:

1. Ponto de entrada `_start` (ou o reset vector), escrito na própria Prova com um atributo `(section ".text.boot")`.  
2. Script de ligação (`linker.ld`) definindo `.text`, `.data`, `.bss` e a pilha.  
3. Zerar `.bss`, configurar a pilha e chamar `kmain`.  
4. Por arquitetura: x86-64 recebe o controle de um bootloader (Limine ou Multiboot2) já em *long mode*. AArch64 entra em EL2 ou EL1 e recebe o ponteiro do *device tree* em `x0`. RISC-V entra em modo S pelo OpenSBI, com `hartid` em `a0` e o *device tree* em `a1`.  
5. Runtime mínimo: `memcpy`, `memset` e `panic`, escritos em Prova e verificados.

#### **Etiquetas de origem e destino (abordagem 3\)**

Cada ponteiro carrega uma região: `(ptr T :region net-rx)`. O verificador rastreia por onde o dado passa e gera o relatório de fluxo: *“pacote entra em `net-rx`, é copiado para `skb`, toca `kmem` em tal função”*.

### **4\. O que a prova garante e o que não garante**

**Garante:**

* Nenhum acesso fora dos limites e nenhum *use-after-free* ou *double free*.  
* Nenhum overflow aritmético não declarado.  
* Limite de pilha e de memória estática, se você declarar um orçamento (`(stack-budget 4096)`), com a prova baseada em grafo de chamadas sem recursão ilimitada.

**Não garante:**

* “Nunca estoura memória” em geral é **indecidível**. A prova só vale contra o orçamento que você declara. Alocação dinâmica exige que o contrato diga quanto cada função aloca, no máximo.  
* Que o contrato esteja certo. A auditoria humana vira auditoria de especificação, e esse é o trabalho mais importante.  
* A base confiável: Z3, o kernel do Lean e o LLVM continuam no *trusted computing base*. Para reduzir isso, use certificados Lean para as VCs críticas e validação de tradução no que for viável.

### **5\. Roadmap**

1. **Núcleo mínimo:** gramática S-expr, inteiros, `let`, `if`, `loop`, funções com `pre`/`post`, VCs via Z3, emissão de MLIR (`arith`/`cf`) e execução em x86-64 Linux.  
2. **Memória:** `own`/`ref`/`mut`, `slice` com tamanho no tipo, alocador de arena verificado.  
3. **Hardware:** intrínsecos de syscall e registradores, `_start` freestanding, saída serial em QEMU para x86-64, AArch64 e RISC-V.  
4. **Provas pesadas:** integração com Lean 4 para o que o Z3 não fecha, com certificados verificáveis.  
5. **IA no laço:** exportar a gramática para constrained decoding (por exemplo, GBNF ou llguidance) e formatar os erros como JSON estruturado para correção automática.  
6. **Fluxo de dados:** relatórios por região e uma tela de auditoria.

\======================================================================

Pontos de Atenção e Armadilhas Técnicas

Ao tirar a **Prova** do papel, você esbarrará em atritos clássicos entre verificação formal, geração por IA e desenvolvimento de kernel.

**1\. O gargalo dos quantificadores (forall) no Z3**

No seu exemplo de copy-bytes, tanto o post quanto o invariant usam forall sobre arrays/slices.

* **O problema.** Quantificadores universais combinados com aritmética linear e teoria de arrays frequentemente tiram o Z3 da zona decidível, causando *timeouts* imprevisíveis ou respostas unknown. Quando o Z3 dá *timeout*, o contraexemplo gerado pode ser inútil para a IA se corrigir.  
* **A solução.** Restrinja os padrões de gatilho (*triggers* / *e-matching*) gerados pelo seu tradutor de VCs para o Z3, ou adote um fragmento decidível específico (como *Array Property Fragment*). Deixe o Lean 4 como fallback automático sempre que o Z3 ultrapassar um limite rígido de tempo (por exemplo, 500 milissegundos).

**2\. A explosão de invariantes de loop para a IA**

Loops em código de kernel exigem invariantes precisos para provar segurança de memória e pós-condições.

* **O problema.** Embora S-expressions eliminem erros de sintaxe via *Constrained Decoding*, a IA ainda terá dificuldade em sintetizar invariantes complexos de primeira em funções de kernel que manipulam múltiplas estruturas e ponteiros simultaneamente.  
* **A solução.** Implemente um passe de **inferência básica de invariantes** no front-end (como propagação de limites de variáveis de indução e preservação de regiões não modificadas no loop) antes de enviar a VC ao Z3. Isso reduz o fardo lógico da IA, exigindo que ela escreva apenas a lógica central do algoritmo.

**3\. Aritmética explícita e ergonomia do código gerado**

Exigir provas de não-estouro para todo operador \+ é excelente para segurança, mas pode gerar código excessivamente verboso.

* **O problema.** Em código de baixo nível, cálculos de offsets e alinhamento de páginas geram dezenas de somas simples. Se a IA precisar provar manualmente cada uma delas, o consumo de tokens e o tempo de verificação vão disparar.  
* **A solução.** Utilize os tipos de refinamento já existentes para automatizar isso. Se i tem tipo {v: usize \| v \< len} e len \<= 1024, o compilador deve aceitar (+ i 1\) silenciosamente porque o Z3 resolve a prova de não-estouro em microssegundos sem exigir anotação extra no código-fonte.

**4\. Aliases e mutabilidade em baixo nível (MMIO e DMA)**

O sistema de posse linear (own, ref, mut) funciona perfeitamente para memória RAM comum, mas o hardware viola essas regras.

* **O problema.** Em drivers de kernel, registradores mapeados em memória (MMIO) e buffers de DMA são modificados pelo hardware de forma assíncrona, fora do controle do modelo linear da CPU. Se o compilador achar que tem posse exclusiva (mut), ele pode otimizar e remover leituras repetidas de um registrador de status.  
* **A solução.** Crie uma categoria de região específica para hardware, como (ptr u32 :region mmio :volatile true), que proíba o MLIR de reordenar ou eliminar acessos de leitura/escrita, desativando deduções de imutabilidade sobre aquela região.

---

Sugestão de Ajuste Imediato no MVP (Fase 1\)

Para validar o ciclo completo o mais rápido possível, mantenha o **Passo 1 do seu Roadmap** rigorosamente enxuto:

1. **Gramática mínima.** Implemente apenas funções, inteiros de largura fixa (u64, usize), let, if, loop e contratos (pre, post, invariant). Deixe regiões e empréstimos para a Fase 2\.  
2. **Backend direto para teste.** Em vez de configurar toda a árvore do MLIR na semana 1, você pode fazer o front-end em Lean 4 emitir **LLVM IR textual** simples para funções puras e validar o pipeline Lean 4 \-\> Z3 \-\> LLVM \-\> Binário x86-64. Assim que o ciclo de feedback de erro do Z3 para a IA estiver funcionando, introduza o dialeto MLIR prova para suportar regiões e *ownership*.

Anotei as especificações da linguagem **Prova**, incluindo sua sintaxe em S-expressions, o sistema de tipos lineares com regiões e o pipeline em Lean 4 \+ Z3 \+ MLIR para mantermos esse contexto nos próximos passos.

Se você quiser partir para o código agora, posso ajudar a estruturar o **Passo 1 do Roadmap** escrevendo:

* A **gramática formal (EBNF / GBNF)** inicial do núcleo mínimo da Prova  
* A estrutura dos **tipos de dados da AST** em Lean 4  
* O tradutor inicial de **condições de verificação (VCs)** para o formato SMT-LIB2 do Z3

