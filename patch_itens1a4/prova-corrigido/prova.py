#!/usr/bin/env python3
"""Prova (bootstrap): check | emit | audit.

  prova.py check ARQ.prova [--json] [--strict]
  prova.py emit  ARQ.prova --target x86_64|aarch64|riscv64 [--strict]
  prova.py audit ARQ.prova          # só contratos e efeitos (o que o humano audita)
  prova.py boot --target T [--part asm|ld] [--entry kmain] [--base 0x...]
                                    # stub de boot bare-metal + linker script (pilha, .bss, chamada a kmain)

--strict: só aceita se TODAS as obrigações forem provadas (sem "testado"/"incerto").
"""
import argparse
import json
import sys

from provac.audit import audit
from provac.boot import TARGETS as BOOT_TARGETS, boot_asm, linker_script
from provac.check import Fn, ProvaError, check_call_graph, verify_fn
from provac.linear import check_linear
from provac.mlir import ABI, emit_module
from provac.sexp import ParseError, parse
from provac.smt import discharge


def load(path):
    forms = parse(open(path, encoding="utf-8").read())
    data, fns = {}, []
    for f in forms:
        if not isinstance(f, list) or not f or not isinstance(f[0], str):
            raise ProvaError(f"forma de topo inválida: {f!r} (esperado (fn ...) ou (data ...))")
        if f[0] == "data":
            if len(f) != 3 or not isinstance(f[1], str):
                raise ProvaError("data espera (data nome \"texto\")")
            data[f[1]] = f[2].encode("utf-8")
        elif f[0] == "fn":
            fns.append(Fn(f))
        else:
            raise ProvaError(f"forma de topo desconhecida: {f[0]}")
    return data, fns


def _analyse(path):
    data, fns = load(path)
    dlen = {k: len(v) for k, v in data.items()}
    results, compiled, sigs = [], [], {}
    for fn in fns:
        if fn.name in sigs:
            raise ProvaError(f"função duplicada: {fn.name}")
        sigs[fn.name] = fn
    check_call_graph(fns)
    for fn in fns:
        lin = check_linear(fn, sigs)
        cx = verify_fn(fn, dlen, sigs)
        compiled.append((fn, cx))
        # "goal" (termo da obrigação) vai no JSON para o laço de correção da IA.
        obs = [{"label": ob["label"], "goal": str(ob["goal"]), **discharge(ob)} for ob in cx.obs]
        results.append({"fn": fn.name, "linear_errors": lin, "obligations": obs})
    return data, compiled, results


def analyse(path):
    try:
        return _analyse(path)
    except (IndexError, KeyError, TypeError, ValueError, AttributeError) as e:
        raise ProvaError("forma malformada (aridade ou estrutura inválida; confira spec/prova.gbnf): "
                         f"{type(e).__name__}: {e}")


def verdict(results, strict):
    """Retorna (falhas, pendentes)."""
    failed = sum(len(r["linear_errors"]) for r in results)
    pending = 0
    for r in results:
        for o in r["obligations"]:
            if o["status"] == "failed":
                failed += 1
            elif o["status"] != "proved":
                pending += 1
    return failed, pending


def report(results):
    tags = {"proved": "✔ provado ", "tested": "~ testado ", "failed": "✘ FALHOU  ", "unknown": "? incerto "}
    for r in results:
        print(f"fn {r['fn']}")
        for e in r["linear_errors"]:
            print(f"  ✘ posse    {e}")
        for o in r["obligations"]:
            how = f" [{o['how']}]" if o["status"] == "proved" and o.get("how") != "linarith" else ""
            print(f"  {tags[o['status']]} {o['label']}{how}")
            if o["status"] == "failed":
                print(f"      contraexemplo: {o['model']}")
            if o.get("note"):
                print(f"      nota: {o['note']}")
    obs = [o for r in results for o in r["obligations"]]
    proved = sum(o["status"] == "proved" for o in obs)
    pending = sum(o["status"] in ("tested", "unknown") for o in obs)
    failed = sum(o["status"] == "failed" for o in obs)
    posse = sum(len(r["linear_errors"]) for r in results)
    print(f"\nresumo: {proved} provadas, {pending} não provadas (testadas/incertas), "
          f"{failed} falhas de obrigação, {posse} erros de posse")


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "emit", "audit", "boot"])
    ap.add_argument("file", nargs="?")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--target", default="x86_64", choices=sorted(ABI))
    ap.add_argument("--part", default="asm", choices=["asm", "ld"])
    ap.add_argument("--entry", default="kmain")
    ap.add_argument("--base", default=None)
    a = ap.parse_args()
    if a.cmd == "boot":
        base = int(a.base, 0) if a.base else None
        sys.stdout.write(boot_asm(a.target, a.entry) if a.part == "asm"
                         else linker_script(a.target, base=base, entry=a.entry))
        return 0
    if not a.file:
        ap.error("informe o arquivo .prova")
    try:
        if a.cmd == "audit":
            _, fns = load(a.file)
            print(audit(fns))
            return 0
        data, compiled, results = analyse(a.file)
    except (ParseError, ProvaError) as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False) if a.json else f"erro: {e}",
              file=sys.stdout if a.json else sys.stderr)
        return 2
    failed, pending = verdict(results, a.strict)
    bad = failed > 0 or (a.strict and pending > 0)
    if a.cmd == "check":
        if a.json:
            print(json.dumps(results, ensure_ascii=False, indent=1))
        else:
            report(results)
        return 1 if bad else 0
    if bad:
        report(results)
        print("emissão recusada: " + ("há obrigações falhando" if failed else "--strict exige tudo provado"),
              file=sys.stderr)
        return 1
    sys.stdout.write(emit_module(compiled, data, a.target))
    return 0


if __name__ == "__main__":
    sys.exit(main())
