-- ATENÇÃO: ESBOÇO. Nada aqui verifica programas Prova: `checkProvaStub` devolve sempre o mesmo texto.
-- O verificador real hoje é o Python em provac/. Fase 2 (porte para Lean 4) NÃO está concluída.
-- Pendente: este arquivo está em lean/Prova/Prova.lean, mas o lakefile espera o módulo raiz `Prova`.

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
def emitMLIRStub (_code : String) : String :=
  "MLIR module: " ++ mlirModuleName

-- Check function - using _ for unused parameter
def checkProvaStub (_src : String) : String :=
  "STUB: nada foi verificado"

-- Main entry point demonstration
def mainDemo : String :=
  "esboço do front-end Lean 4 (nada é verificado aqui)"

-- End namespace
end Prova