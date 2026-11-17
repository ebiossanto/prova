/-! Semântica do núcleo: por que as flags `nsw`/`nuw` do MLIR são seguras.
    Se a VC "cabe em i64" é válida, a soma com wrap coincide com a soma matemática.
    NÃO TESTADO (sem Lean no ambiente de geração); `omega` deve fechar estas provas. -/
namespace Prova

/-- Soma com wrap em complemento de dois de 64 bits (valor com sinal). -/
def wrapI64 (v : Int) : Int :=
  (v + 9223372036854775808) % 18446744073709551616 - 9223372036854775808

/-- Soma com wrap em 64 bits sem sinal (usize). -/
def wrapU64 (v : Int) : Int := v % 18446744073709551616

/-- Obrigação gerada pelo compilador para `(+ a b)` em i64. -/
def fitsI64 (v : Int) : Prop := -9223372036854775808 ≤ v ∧ v ≤ 9223372036854775807

def fitsU64 (v : Int) : Prop := 0 ≤ v ∧ v ≤ 18446744073709551615

/-- Se a VC vale, wrap é identidade: `arith.addi ... overflow<nsw>` não muda o valor. -/
theorem wrapI64_of_fits (v : Int) (h : fitsI64 v) : wrapI64 v = v := by
  unfold wrapI64 fitsI64 at *
  omega

theorem wrapU64_of_fits (v : Int) (h : fitsU64 v) : wrapU64 v = v := by
  unfold wrapU64 fitsU64 at *
  omega

end Prova
