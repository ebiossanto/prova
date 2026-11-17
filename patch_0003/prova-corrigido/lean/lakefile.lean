import Lake
open Lake DSL

package prova

lean_lib Prova

@[default_target]
lean_exe prova where
  root := `Main
