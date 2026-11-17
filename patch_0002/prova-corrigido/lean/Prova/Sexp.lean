/-! Leitor de S-expressions da Prova (porta do `provac/sexp.py`).
    NÃO TESTADO: escrito sem Lean disponível no ambiente de geração. -/
namespace Prova

inductive Sexp where
  | atom : String → Sexp
  | str  : String → Sexp
  | int  : Int → Sexp
  | list : List Sexp → Sexp
  deriving Repr, BEq, Inhabited

partial def Sexp.render : Sexp → String
  | .atom s => s
  | .str s => "\"" ++ s ++ "\""
  | .int i => ToString.toString i
  | .list xs => "(" ++ " ".intercalate (xs.map Sexp.render) ++ ")"

instance : ToString Sexp := ⟨Sexp.render⟩

inductive Tok where
  | lp | rp
  | atom (s : String)
  | str (s : String)

def isDelim (c : Char) : Bool :=
  c.isWhitespace || c == '(' || c == ')' || c == ';' || c == '"'

partial def tokenize (cs : List Char) (acc : Array Tok) : Except String (Array Tok) :=
  match cs with
  | [] => .ok acc
  | c :: rest =>
    if c == '(' then tokenize rest (acc.push .lp)
    else if c == ')' then tokenize rest (acc.push .rp)
    else if c == ';' then tokenize (rest.dropWhile (· != '\n')) acc
    else if c.isWhitespace then tokenize rest acc
    else if c == '"' then
      let body := rest.takeWhile (· != '"')
      match rest.dropWhile (· != '"') with
      | [] => .error "string não terminada"
      | _ :: after => tokenize after (acc.push (.str (String.mk body)))
    else
      let body := cs.takeWhile (fun d => !isDelim d)
      tokenize (cs.dropWhile (fun d => !isDelim d)) (acc.push (.atom (String.mk body)))

mutual
partial def parseSexp (ts : Array Tok) (i : Nat) : Except String (Sexp × Nat) :=
  if h : i < ts.size then
    match ts[i] with
    | .lp => parseList ts (i + 1) #[]
    | .rp => .error "')' inesperado"
    | .str s => .ok (.str s, i + 1)
    | .atom s =>
      match s.toInt? with
      | some n => .ok (.int n, i + 1)
      | none => .ok (.atom s, i + 1)
  else .error "fim inesperado"

partial def parseList (ts : Array Tok) (i : Nat) (acc : Array Sexp) : Except String (Sexp × Nat) :=
  if h : i < ts.size then
    match ts[i] with
    | .rp => .ok (.list acc.toList, i + 1)
    | _ => do
      let (x, j) ← parseSexp ts i
      parseList ts j (acc.push x)
  else .error "'(' sem ')' correspondente"
end

partial def parseAllFrom (ts : Array Tok) (i : Nat) (acc : Array Sexp) : Except String (List Sexp) :=
  if i < ts.size then do
    let (x, j) ← parseSexp ts i
    parseAllFrom ts j (acc.push x)
  else .ok acc.toList

def parseAll (src : String) : Except String (List Sexp) := do
  let ts ← tokenize src.toList #[]
  parseAllFrom ts 0 #[]

end Prova
