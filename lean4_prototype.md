# Lean 4 Front-end Prototype for Prova Language
# Based on the Python bootstrap at provac/

# The Prova language front-end in Lean 4 should:
# 1. Parse S-expressions (or GBNF-compatible format)
# 2. Type-check with strict types (i64, usize, u8)
# 3. Check linear possession (own/ref/mut)
# 4. Generate VCs (overflow, bounds, invariants, termination)
# 5. Emit MLIR textual output

# Key components to port from provac/:
# - sexp.py: S-expression parser
# - check.py: Type checker + VC generation
# - linear.py: Linear possession checking
# - smt.py: Z3/aided discharge
# - mlir.py: MLIR emission

# Lean 4 advantages:
# - Native dependently-typed verification
# - Certified code generation via Lean theorems
# - Reduced trusted base (Lean kernel + Z3 certified proofs)
# - Better integration with proof assistants
# - Quantifier handling via e-matching triggers

# Next step: Implement core data types and parser in Lean 4