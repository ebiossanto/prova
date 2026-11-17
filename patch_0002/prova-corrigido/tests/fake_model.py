#!/usr/bin/env python3
"""'Modelo' determinístico para testar o laço de correção (nenhuma IA real aqui).
Uso: fake_model.py MODO   (lê o JSON do laço no stdin, imprime o fonte .prova completo)
  honest   : corrige o laço de bad_bounds.
  cheater  : na 1ª iteração tenta 'corrigir' tornando a pre contraditória (prova tudo!); depois fica honesto.
  garbage  : na 1ª iteração devolve lixo; depois fica honesto.
  stubborn : nunca corrige."""
import json, sys

mode = sys.argv[1] if len(sys.argv) > 1 else "honest"
req = json.load(sys.stdin)
src, first = req["source"], req["feedback"] is None and req["iteration"] == 0
if mode == "stubborn":
    out = src
elif mode == "cheater" and first:
    out = src.replace("(pre (<= len n))", "(pre (<= len n) (< len 0))")
elif mode == "garbage" and first:
    out = "((("
else:
    out = src.replace("(while (<= i len)", "(while (< i len)")
sys.stdout.write(out)
