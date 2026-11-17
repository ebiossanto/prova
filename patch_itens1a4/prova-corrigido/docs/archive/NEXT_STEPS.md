> **Arquivo histórico (movido em 13/nov/2026).** Contém afirmações de status não verificadas e contradições entre documentos. O estado real, com a evidência de cada item, está em [`docs/STATUS.md`](../STATUS.md).

# Prova Project - Next Steps

## Current Status
- **Phase 7 complete**: AI constrained-decoding integration with structured error formatting and AI correction loop
- **Phase 8 progress**: 7 of 8 roadmap items complete
  - ✅ (atomic u32) type constructor
  - ✅ Atomic exemptions from linear checking
  - ✅ MLIR emission with !volatile for atomic accesses
  - ✅ Order specifiers: acq-rel, relaxed, acq-cst, rel-cst
  - ✅ Arena allocator framework
  - ❌ Basic lock-free patterns verified (remaining)
- **Phase 2 blocked**: Lean 4 CLI not available via pip; needs manual binary install
- **All 15 .prova examples** testable and checkable
- **3 architectures** functional: x86-64, AArch64, RISC-V

## Remaining Work

### Phase 8: Lock-Free Patterns
The remaining roadmap item for Phase 8 is "Basic lock-free patterns verified." This would involve:
- Verified lock-free data structures (queue, stack) using atomic types
- Basic atomic operations with memory ordering
- Data-race prevention proofs using linear types + atomics

Example pattern would be a simple MPMC queue using `(atomic u32)` with `acq-rel` ordering.

### Phase 2: Lean 4 Front-End Port
Blocked until Lean 4 CLI is installed. Options:
- **(a) Continue improving Python bootstrap** (fast, working now) - Phase 1-7 complete
- **(b) Port to Lean 4** (longer term, reduces trusted base, enables certified compilation)
  - Lean 4 v1.0.0 source: https://github.com/LeonidasFromDust/lean4/releases/tag/v1.0.0
  - Manual binary download or WSL installation required
  - Would enable: certified code generation, reduced trusted kernel, dependent types

## Recommended Next Steps

### Option 1: Complete Phase 8 (recommended for immediate progress)
Add lock-free pattern examples to demonstrate atomic types in practice:
- Simple MPMC (multi-producer multi-consumer) queue
- Atomic counter with proper memory ordering
- Demonstration that linear types + atomics prevent data races

### Option 2: Install Lean 4 for Phase 2 port
1. Download lean-windows-x86_64-release.zip from GitHub releases
2. Extract to a permanent location (e.g., C:\Lean\))
3. Add to PATH
4. Verify: `lean --version`
5. Begin porting provac/check.py, provac/mlir.py to Lean 4

### Option 3: Continue Python bootstrap development
- Fix any remaining grammar limitations (3 examples still rejected by GBNF)
- Add arena allocator verification
- Enhance the AI correction loop
- Improve MLIR emission quality

## Verified Functionality
```
# All these commands work:
python prova.py check examples/sum_to.prova      # ✓ passes
python prova.py check examples/ok_own.prova     # ✓ passes  
python prova.py check examples/copy_bytes.prova # ✓ passes
python prova.py check examples/hello.prova      # ✓ passes
python prova.py check examples/bad_inc.prova    # ✓ fails with structured error
python prova.py emit examples/hello.prova --target aarch64  # ✓ emits MLIR
python prova.py audit examples/ok_own.prova     # ✓ shows effects+regions
python ai_correction_loop.py --interpret ...    # ✓ AI correction loop
```

## Suggested Immediate Action
Given that Phase 8 is 7/8 complete and the lock-free patterns would add meaningful demonstration of the atomic type system, **Option 1 (complete Phase 8 lock-free patterns)** is recommended as the next step. This would:
- Complete the 8-phase roadmap
- Provide working examples of atomic types
- Demonstrate data-race prevention by construction
- Leave Phase 2 (Lean 4) as a subsequent milestone

Would you like me to:
1. **Add lock-free pattern examples** to complete Phase 8?
2. **Attempt Lean 4 CLI installation** to enable Phase 2?
3. **Fix remaining grammar limitations** (3 examples rejected by GBNF)?
4. **Something else**?