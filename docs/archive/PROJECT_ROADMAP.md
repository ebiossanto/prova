> **Arquivo histórico (movido em 13/nov/2026).** Contém afirmações de status não verificadas e contradições entre documentos. O estado real, com a evidência de cada item, está em [`docs/STATUS.md`](../STATUS.md).

# Prova: Verified Language Project - Roadmap

## Objective
Build a verified systems programming language called **Prova** that combines:
- S-expression syntax with constrained decoding for AI code generation
- Linear/affine types for memory ownership
- Refinement types for dependent-like guarantees
- Contracts (pre/post/invariant) with automated discharge
- MLIR → LLVM → machine code compilation pipeline
- Freestanding kernel support for multiple architectures

The **minimum viable product (MVP)** targets: x86-64, AArch64, RISC-V

---

## Current Status (November 2026)
✅ **Working bootstrap**: Python-based compiler (`prova.py` + `provac/` package)
✅ S-expression parser with closed GBNF grammar
✅ Strict types (i64, usize, u8) with explicit casts
✅ Contracts: `pre`, `post`, `invariant` with `decreases`
✅ VC generation for: overflow, bounds, invariants, termination, possession
✅ Linear possession checking (`own` type)
✅ MLIR emission (func/arith/memref/cf/llvm dialects) with nsw/nuw flags
✅ Syscall emission via `llvm.inline_asm` per architecture
✅ Z3 discharge when available; bounded SMT fallback otherwise
✅ Test suite: `sum_to`, `copy_bytes`, `hello`, `ok_own`, `calls` pass
✅ Known failures documented for grammar restrictions

❌ **Pending**: Grammar rejects some valid examples (test_grammar.py error)
❌ **Pending**: Lean 4 front-end port (currently Python bootstrap)
❌ **Pending**: Content modeling for slices (array theory in SMT)
❌ **Pending**: Boot stub per architecture + linker scripts
❌ **Pending**: MMIO/DMA capability regions
❌ **Pending**: Data flow/region tracking reports
❌ **Persistent**: No dynamic allocation, no concurrency/atomics, no recursion

---

## Phased Roadmap

### Phase 1 — Grammar & Test Fix (1-2 weeks)
**Objective:** Make the grammar accept all valid examples and reject invalid ones.

- [ ] Fix `spec/prova.gbnf` to accept: `calls.prova`, `ok_own.prova`, `bad_move.prova`, `bad_recursion.prova`, `bad_call_len.prova`, `bad_call_pre.prova`
- [ ] Review why these are rejected and adjust grammar constraints
- [ ] Update `tests/test_grammar.py` to reflect corrected behavior
- [ ] Verify all existing examples pass `prova.py check`

**Deliverable:** `python -m pytest tests/ -v` runs without collection errors; all good examples pass.

---

### Phase 2 — Front-end: Lean 4 Port (2-3 weeks)
**Objective:** Move the front-end (parser + type checking + VC generation) to Lean 4, keeping MLIR emission as backend.

- [ ] Study Lean 4 syntax and metaprogramming model
- [ ] Implement S-expression parser in Lean 4 (or use GGULR + GBNF)
- [ ] Translate the type checker (`provac/check.py`) to Lean 4
- [ ] Implement VC generation and Z3/linarith integration in Lean
- [ ] Emit Lean-native SMT2 or quantifier-free lemmas for Z3
- [ ] Produce MLIR textual output from Lean (same format as Python backend)

**Why Lean 4:** The design doc states: "o front-end (parser, tipos, VCs) em Lean 4, emitindo MLIR textual". Lean provides:
- Native dependently-typed verification
- Certified code generation
- The trusted base can be reduced (Lean kernel + Z3 certified proofs)
- Better integration with proof assistants than standalone Z3

**Deliverable:** Lean 4 prototype that parses `.prova` files, checks types, generates VCs, and emits MLIR textual.

---

### Phase 3 — Memory Model: Slice Content & Arrays (2 weeks)
**Objective:** Model slice contents in SMT theories so post-conditions about bytes work.

- [ ] Add theory of arrays / mutable slices to VC generation
- [ ] Implement `load`/`store` content assertions in `provac/check.py`
- [ ] Update `discharge()` in `smt.py` to handle array reasoning
- [ ] Verify `copy_bytes` post-condition with array quantifiers (with Z3 triggers fix)

**Known blocker:** "Só de u8; o conteúdo das fatias não é modelado" (README). This requires SMT array logic.

**Deliverable:** `copy_bytes.prova` post-condition fully proved by Z3, not just tested.

---

### Phase 4 — Hardware: Boot Stubs & Architecture Support (2-3 weeks)
**Objective:** Complete freestanding kernel support for all target architectures.

- [ ] Write `_start` assembly-free stub in Prova for each architecture
- [ ] Create `linker.ld` templates for: x86-64, AArch64, RISC-V
- [ ] Implement `.bss` zeroing, stack configuration, `kmain` call
- [ ] Test pipeline `scripts/build.sh` with QEMU for each arch
- [ ] Add serial output verification in QEMU

**Architecture details** (from LANGUAGE.md):
- x86-64: bootloader (Limine/Multiboot2) in long mode
- AArch64: EL2/EL1, device tree in x0
- RISC-V: OpenSBI, hartid in a0, device tree in a1

**Deliverable:** `prova.py emit examples/hello.prova --target aarch64` produces valid MLIR → LLVM → runnable binary via QEMU.

---

### Phase 5 — Hardware Capabilities: MMIO & DMA (1 week)
**Objective:** Add `mmio`/`volatile` region types that bypass linear possession rules.

- [ ] Add `(ptr T :region mmio :volatile true)` type constructor
- [ ] Modify MLIR emission to NOT reorder/eliminate volatile accesses
- [ ] Add capability category separate from `own`/`ref`/`mut`
- [ ] Update linear checker to allow temporary "borrow" of mmio regions

**Deliverable:** Driver-like functions with MMIO access are accepted without linear errors.

---

### Phase 6 — Data Flow & Region Reports (1 week)
**Objective:** Track data provenance through regions and generate audit reports.

- [ ] Implement region tracking in the type checker (each pointer carries `:region X`)
- [ ] Generate flow reports: "pacote entra em net-rx, é copiado para skb, toca kmem"
- [ ] Add `--audit` flag to `prova.py` that shows effects + regions (already has `audit.py` basic version)
- [ ] Design UI/screen for auditoria in IDE/agent loop

**Deliverable:** `prova.py audit ARQ.prova` shows region flow, not just effects.

---

### Phase 7 — IA Laço: Constrained Decoding (1-2 weeks)
**Objective:** Export grammar for AI-constrained decoding and structured error formatting.

- [ ] Verify GBNF grammar is compatible with `llguidance` / `constrained decoding`
- [ ] Format VC errors as JSON: `{ "label": "...", "goal": "...", "model": {...}, "note": "..." }`
- [ ] Enable AI to auto-correct: emit function + JSON error → AI rewrites the function
- [ ] Test end-to-end: IA generates `.prova`, tool checks + returns structured errors, IA fixes

**Deliverable:** Full loop: IA writes Prova code → tool checks → returns JSON errors → IA corrects → repeat until proven.

---

### Phase 8 — Persistent Memory & Concurrency (2+ weeks, optional)
**Objective:** Dynamic allocation, garbage-collected or arena-based; basic atomics.

- [ ] Arena allocator verified (Prova code allocates from verified region)
- [ ] `(atomic u32 :order acq-rel)` type and primitive operations
- [ ] Data-race prevention by construction (linear types + atomics)
- [ ] Basic lock-free patterns verified

**Deliverable:** Basic allocator + atomic types work in kernel context.

---

## Immediate Next Steps (Start Here)

Given the project state, the recommended immediate path is:

### Step 1: Fix Grammar (highest priority — blocks test suite)
Run and fix `tests/test_grammar.py` so the 6 "bad_" examples are correctly rejected and the 5 "good_" examples pass.

### Step 2: Validate the full check pipeline
Run `prova.py check` on all examples and fix any regressions.

### Step 3: Choose the Lean 4 port path
Decide whether to:
- (a) Continue improving the Python bootstrap (fast, working now)
- (b) Port to Lean 4 (longer term, reduces trusted base, enables certified compilation)

### Step 4: Choose the next feature domain
Based on interest:
- Slice content + array theory (Z3 provability)
- Boot stubs + multi-arch QEMU testing
- MMIO capabilities
- AI constrained-decoding integration

---

## Commands Reference

```
# Check a file
python3 prova.py check ARQ.prova        # text report
python3 prova.py check ARQ.prova --json # structured for IA

# Emit MLIR + LLVM
python3 prova.py emit ARQ.prova --target aarch64

# Audit (effects + regions)
python3 prova.py audit ARQ.prova

# Run test suite (after grammar fix)
python3 -m pytest tests/ -v
```

---
*This roadmap tracks the "Prova" language project. Last updated: 2026-11-13.*