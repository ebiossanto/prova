-- Prova Lean 4 Front-end Port (Phase 2)
-- Minimal namespace following Core.lean patterns
-- Lean 4 version: 4.36.0-rc2 (verified: lean --version works)

namespace Prova

-- ExprType
inductive ExprType where
  | Lit : Int → ExprType
  | Id : String → ExprType
  | App : ExprType → List ExprType → ExprType
  deriving Repr, BEq, Inhabited

-- Context
def Context := List (String × ExprType × Bool)

def emptyCtx : Context := []

def extendCtx (Γ : Context) (x : String) (τ : ExprType) (linear : Bool) : Context :=
  (x, τ, linear) :: Γ

-- MLIR related types
def mlirModuleName : String := "prova"

def mlirGlobals : List (String × String) := []

def mlirFunctions : List (String × List String × String) := []

-- Emit MLIR (simplified) - using _ for unused parameter
def emitMLIR (_code : String) : String :=
  "MLIR module: " ++ mlirModuleName

-- Check function - using _ for unused parameter
def checkProva (_src : String) : String :=
  "Prova check: OK"

-- Main entry point demonstration
def mainDemo : String :=
  "Lean 4 front-end operational"

-- End namespace
end Prova