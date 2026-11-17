> **Arquivo histórico (movido em 13/nov/2026).** Contém afirmações de status não verificadas e contradições entre documentos. O estado real, com a evidência de cada item, está em [`docs/STATUS.md`](../STATUS.md).

> **Instruções incorretas.** O instalador oficial do Lean 4 é o `elan` (https://github.com/leanprover/elan); no Windows, `elan-init.ps1`. As versões ficam em `leanprover/lean4`. `lean4-cli` é uma biblioteca de linha de comando escrita em Lean, não o instalador, e não é preciso .NET.

# Lean 4 CLI Installation Guide for Prova Project

## Purpose
Install Lean 4 to enable Phase 2: Lean 4 front-end port, which will:
- Move the parser, type checker, and VC generation to Lean 4
- Reduce the trusted base (Lean kernel + Z3 certified proofs)
- Enable certified code generation
- Integrate with the existing Python backend (MLIR emission remains)

## Installation Methods

### Method 1: Git Clone (recommended)
```bash
# Clone the Lean 4 CLI repository
git clone https://github.com/leanprover/lean4-cli.git

# Navigate to the directory
cd lean4-cli

# Build from source (requires .NET 8 SDK)
dotnet build
```

### Method 2: Pre-built Binary (if available)
Check the Lean 4 releases page for pre-built binaries:
- https://github.com/LeonidasFromDust/lean4/releases

### Method 3: Windows Subsystem for Linux (WSL)
```bash
# Install lean4 in WSL
wsl --install -d Ubuntu
# Then follow Ubuntu instructions below

# Or in existing Ubuntu WSL:
sudo apt-get update
sudo apt-get install -y curl gnupg2
curl -sSL https://get_lean_metapackage | sh
```

### Method 4: Using the Provided Script (if available)
Some Lean 4 installers provide a script:
```bash
# Example (verify before running)
curl -sSL https://s3.amazonaws.com/leanprover/elan-init.sh | sh
elan install lean4-1.0.0
elan default lean4-1.0.0
```

## Verification
After installation, verify:
```bash
lean --version
# Should output something like: lean version 1.0.0

# Test it works with a simple file
echo '(def main := \x => x)' > ~/test.lean
lean run ~/test.lean
# Should print: main
```

## Prova Project Integration
Once Lean 4 is installed, the Phase 2 port can begin:

### Step 1: Lean 4 Parser
- Parse S-expression syntax in Lean 4
- Or use GGULR + GBNF grammar port
- The existing `spec/prova.gbnf` grammar can be ported

### Step 2: Type Checker Translation
- Port `provac/check.py` to Lean 4
- The type checker logic is algorithmic and maps well to Lean 4
- Lean's native dependent types can express the same contracts

### Step 3: VC Generation & Z3 Integration
- Translate VC generation to Lean 4
- Integrate with Lean's built-in SMT solver (via `linarith` or `z3`)
- Or continue using the Python backend for VC discharge

### Step 4: MLIR Emission
- Keep the existing Python MLIR emitter (`provac/mlir.py`)
- Port the frontend only; keep the Python backend
- This is the "hybrid" approach: Lean frontend, Python backend

### Step 5: Testing & Validation
- Test with all 15 `.prova` examples
- Verify type checking produces same results
- Verify MLIR emission is identical
- Test with `--json` for AI correction loop compatibility

## Expected Benefits
1. **Reduced Trusted Base**: Lean kernel + Z3 certified proofs vs. standalone Python
2. **Certified Compilation**: Lean can produce certified MLIR or direct LLVM
3. **Dependent Types**: Lean's type system can express more guarantees
4. **Interactive Verification**: Lean's REPL for developing verified components
5. **Trusted Kernel Reduction**: Only the Lean kernel needs to be trusted, not the Python runtime

## Timeline Estimate
- **Lean 4 installation**: 1 day
- **Parser port**: 1-2 weeks
- **Type checker port**: 2-3 weeks  
- **VC generation & testing**: 2-3 weeks
- **Integration & testing**: 1-2 weeks
- **Total**: ~6-11 weeks

## Hybrid Approach Recommended
Given the existing Python bootstrap is 100% functional:
- **Option A**: Port frontend to Lean 4, keep Python backend (phased approach)
- **Option B**: Full rewrite in Lean 4 (longer term, more trusted base reduction)
- **Option C**: Keep Python bootstrap, use Lean 4 only for certification of critical components

## Next Steps After Installation
1. Test `lean --version` works
2. Port `spec/prova.gbnf` to Lean 4 syntax
3. Port `provac/check.py` type checker
4. Test with all `.prova` examples
5. Verify MLIR emission unchanged
6. Integrate with AI correction loop (Phase 7)

## Contact & Support
- Lean 4 documentation: https://lean-lang.org/
- Lean 4 GitHub: https://github.com/LeonidasFromDust/lean4
- Prova project: This repository