/-! Certificado Lean 4 para a Teoria de Arrays (McCarthy), Preservação de Multiconjunto (`occ`) em Trocas
    e Passo Indutivo de Ordenação (`sort_perm.prova`).
    Verificado com Lean 4 (v4.36.0-rc2). -/
namespace Prova

/-- Modelo funcional de fatia/array inteiro usado nas VCs. -/
def Arr := Int → Int

def select (A : Arr) (i : Int) : Int := A i

def store (A : Arr) (i : Int) (v : Int) : Arr :=
  fun k => if k = i then v else A k

/-- Axioma 1 de McCarthy: leitura no mesmo índice devolve o valor escrito. -/
theorem select_store_eq (A : Arr) (i v : Int) :
    select (store A i v) i = v := by
  unfold select store
  simp

/-- Axioma 2 de McCarthy: leitura em índice distinto preserva o valor anterior. -/
theorem select_store_ne (A : Arr) (i j v : Int) (h : j ≠ i) :
    select (store A i v) j = select A j := by
  unfold select store
  simp [h]

/-- Indicador 0/1 de igualdade usado na recorrência exata de `occ` em `provac/smt.py` e `provac/linarith.py`. -/
def iteEq (a b : Int) : Int :=
  if a = b then 1 else 0

/-- Recorrência de ocorrências sob uma escrita `(store A p val)`. -/
def occStore (occA : Int → Int) (A : Arr) (p val : Int) : Int → Int :=
  fun v => occA v + iteEq v val - iteEq v (select A p)

/-- Escrever o próprio elemento `select A p` na posição `p` preserva a contagem de qualquer valor `v`. -/
theorem occStore_id (occA : Int → Int) (A : Arr) (p v : Int) :
    occStore occA A p (select A p) v = occA v := by
  unfold occStore
  omega

/-- Teorema da Troca (Swap) em Índices Distintos:
    trocar `x = select A p` e `y = select A q` (com `q ≠ p`) preserva exatamente o multiconjunto `occA v`
    para todo valor `v`. Justifica a redução algébrica de `(occ buf v)` em `sort_perm.prova`. -/
theorem occ_swap_preserved (occA : Int → Int) (A : Arr) (p q v : Int) (hne : q ≠ p) :
    let x := select A p
    let y := select A q
    let A1 := store A p y
    let occ1 := occStore occA A p y
    occStore occ1 A1 q x v = occA v := by
  dsimp
  unfold occStore select store iteEq
  split <;> omega

/-- Teorema do Passo Indutivo de Ordenação (Bubble Sort):
    se o sufixo `[m, n)` já está ordenado, todo elemento de `[0, m)` é `≤` todo elemento de `[m, n)`,
    e o laço interno garantiu que `A[m - 1]` domina `[0, m - 1)`, então em `m - 1` o sufixo `[m - 1, n)`
    inteiro está ordenado. -/
theorem bubble_suffix_step (A : Arr) (m n a b : Int)
    (h_suf : ∀ x y, m ≤ x → x < y → y < n → select A x ≤ select A y)
    (h_part : ∀ x y, 0 ≤ x → x < m → m ≤ y → y < n → select A x ≤ select A y)
    (hm : 0 < m)
    (ha : m - 1 ≤ a) (hab : a < b) (hb : b < n) :
    select A a ≤ select A b := by
  by_cases h : a = m - 1
  · subst h
    have h1 : 0 ≤ m - 1 := by omega
    have h2 : m - 1 < m := by omega
    have h3 : m ≤ b := by omega
    exact h_part (m - 1) b h1 h2 h3 hb
  · have h_ma : m ≤ a := by omega
    exact h_suf a b h_ma hab hb

/-- Teorema da Partição no Passo Indutivo de Ordenação:
    sob as mesmas hipóteses, todo elemento de `[0, m - 1)` é `≤` todo elemento de `[m - 1, n)`. -/
theorem bubble_partition_step (A : Arr) (m n a b : Int)
    (h_part : ∀ x y, 0 ≤ x → x < m → m ≤ y → y < n → select A x ≤ select A y)
    (h_max : ∀ x, 0 ≤ x → x < m - 1 → select A x ≤ select A (m - 1))
    (ha0 : 0 ≤ a) (ham : a < m - 1) (hbm : m - 1 ≤ b) (hbn : b < n) :
    select A a ≤ select A b := by
  by_cases h : b = m - 1
  · subst h
    exact h_max a ha0 ham
  · have h_am : a < m := by omega
    have h_mb : m ≤ b := by omega
    exact h_part a b ha0 h_am h_mb hbn

end Prova
