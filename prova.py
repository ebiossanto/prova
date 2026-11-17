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

from provac import flow as flowmod
from provac.audit import audit
from provac.boot import boot_asm, linker_script
from provac.check import ProvaError
from provac.mlir import ABI, emit_module
from provac.program import build_safe, load_text
from provac.sexp import ParseError


def _read(path):
    return open(path, encoding="utf-8").read()


build_checked = build_safe


def analyse(path, frames=None):
    """(dados, [(fn, cx)], resultados). Mantido por compatibilidade com os testes."""
    P = build_checked(_read(path), frames)
    return P.data, P.compiled, P.results


def load(path):
    data, fns, _ = load_text(_read(path))
    return data, fns


def verdict(results, strict):
    """Retorna (falhas, pendentes)."""
    failed = sum(len(r["linear_errors"]) + len(r.get("policy_errors", [])) for r in results)
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
        for e in r.get("policy_errors", []):
            print(f"  ✘ política {e}")
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
    posse = sum(len(r["linear_errors"]) + len(r.get("policy_errors", [])) for r in results)
    print(f"\nresumo: {proved} provadas, {pending} não provadas (testadas/incertas), "
          f"{failed} falhas de obrigação, {posse} erros de posse/política")


def _parse_args(raw):
    from provac.interp import Slice
    out = []
    for r in raw:
        try:
            out.append(int(r, 0))
        except ValueError:
            out.append(Slice(r.encode("utf-8")))
    return out


def _stack_table(P):
    rows = ["função              quadro   pior caso   orçamento   cadeia de chamadas"]
    for f in P.fns:
        used, chain = P.worst[f.name]
        rows.append(f"{f.name:<18} {P.frames[f.name]:>7} {used:>11} {str(f.budget or '—'):>11}   {' → '.join(chain)}")
    return "\n".join(rows)


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "emit", "audit", "boot", "flow", "stack", "fix", "run"])
    ap.add_argument("file", nargs="?")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--target", default="x86_64", choices=sorted(ABI))
    ap.add_argument("--part", default="asm", choices=["asm", "ld"])
    ap.add_argument("--entry", default="kmain")
    ap.add_argument("--base", default=None)
    ap.add_argument("--dot", action="store_true", help="flow: saída Graphviz")
    ap.add_argument("--frames", default=None, help="stack/check: JSON {função: bytes} medido no backend")
    ap.add_argument("--model-cmd", default=None, help="fix: comando que lê JSON no stdin e imprime o fonte corrigido")
    ap.add_argument("--max-iter", type=int, default=5)
    ap.add_argument("--entry-fn", default="_start", help="run: função de entrada")
    ap.add_argument("--force", action="store_true", help="run: executa mesmo se a verificação falhar")
    ap.add_argument("--out", default=None, help="fix: onde gravar o fonte final")
    ap.add_argument("--arg", action="append", default=[], help="run: argumento da função de entrada (inteiro, ou texto para fatias); repetível")
    ap.add_argument("--no-contracts", action="store_true", help="run: não conferir contratos/invariantes em execução")
    a = ap.parse_args()
    if a.cmd == "boot":
        base = int(a.base, 0) if a.base else None
        sys.stdout.write(boot_asm(a.target, a.entry) if a.part == "asm"
                         else linker_script(a.target, base=base, entry=a.entry))
        return 0
    if not a.file:
        ap.error("informe o arquivo .prova")
    frames = json.load(open(a.frames, encoding="utf-8")) if a.frames else None
    try:
        if a.cmd == "audit":
            _, fns, meta = load_text(_read(a.file))
            print(audit(fns, meta))
            return 0
        if a.cmd == "fix":
            from provac.loop import fix
            if not a.model_cmd:
                ap.error("fix exige --model-cmd")
            r = fix(a.file, a.model_cmd, a.max_iter, strict=a.strict)
            for h in r["history"]:
                print(f"[iteração {h['iteration']}] {h['outcome']}")
            if r["ok"] and a.out:
                open(a.out, "w", encoding="utf-8").write(r["source"])
            elif r["ok"]:
                sys.stdout.write(r["source"])
            return 0 if r["ok"] else 1
        P = build_checked(_read(a.file), frames)
    except (ParseError, ProvaError) as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False) if a.json else f"erro: {e}",
              file=sys.stdout if a.json else sys.stderr)
        return 2
    if a.cmd == "run":
        from provac.interp import RunError, run
        failed, _ = verdict(P.results, False)
        if failed and not a.force:
            report(P.results)
            print("execução recusada: o programa não passou na verificação (use --force)", file=sys.stderr)
            return 2
        try:
            res, _m = run(P, a.entry_fn, args=_parse_args(a.arg), check=not a.no_contracts)
        except RunError as e:
            print(f"violação em tempo de execução: {e}", file=sys.stderr)
            return 3
        sys.stdout.write(res.stdout.decode("utf-8", "replace"))
        sys.stdout.write(res.stderr.decode("utf-8", "replace"))
        if res.returned is not None:
            print(f"resultado: {res.returned}")
        print(f"[saída {res.exit_code}] (interpretador de referência; não é código nativo)", file=sys.stderr)
        return int(res.exit_code or 0) & 0xFF
    if a.cmd == "flow":
        sys.stdout.write(flowmod.report(P.fns, P.summaries, P.meta["denies"], dot=a.dot) + "\n")
        return 1 if any(r["fn"] == "(programa)" for r in P.results) else 0
    if a.cmd == "stack":
        print(_stack_table(P))
        return 1 if any(o["status"] == "failed" for r in P.results for o in r["obligations"] if o["label"].startswith("pilha")) else 0
    results = P.results
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
    sys.stdout.write(emit_module(P.compiled, P.data, a.target))
    return 0


if __name__ == "__main__":
    sys.exit(main())
