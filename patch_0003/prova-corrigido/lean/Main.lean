import Prova.Sexp
open Prova

def main (args : List String) : IO UInt32 := do
  match args with
  | [path] =>
    let src ← IO.FS.readFile path
    match parseAll src with
    | .ok forms =>
      for f in forms do
        IO.println (toString f)
      return 0
    | .error e =>
      IO.eprintln s!"erro: {e}"
      return 1
  | _ =>
    IO.eprintln "uso: prova <arquivo.prova>"
    return 2
