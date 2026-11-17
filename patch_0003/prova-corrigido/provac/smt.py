"""Descarrega obrigações. Com z3 no PATH: prova (unsat) ou contraexemplo (sat).
Sem z3: verificador limitado (TESTE em valores de borda, não é prova)."""
import itertools
import re
import shutil
import subprocess

from . import linarith


def smt(t):
    if isinstance(t, int):
        return str(t) if t >= 0 else f"(- {-t})"
    if isinstance(t, str):
        return t
    op = t[0]
    if op == "!=":
        return f"(not (= {smt(t[1])} {smt(t[2])}))"
    return "(" + op + " " + " ".join(smt(x) for x in t[1:]) + ")"


def free(t, acc):
    if isinstance(t, str):
        acc.add(t)
    elif isinstance(t, tuple):
        for x in t[1:]:
            free(x, acc)


def to_smt2(ob):
    vs = set()
    for h in ob["hyps"]:
        free(h, vs)
    free(ob["goal"], vs)
    lines = ["(set-logic ALL)"]
    lines += [f"(declare-const {v} Int)" for v in sorted(vs)]
    lines += [f"(assert {smt(h)})" for h in ob["hyps"]]
    lines += [f"(assert (not {smt(ob['goal'])}))", "(check-sat)", "(get-model)"]
    return "\n".join(lines), sorted(vs)


def evalt(t, a):
    if isinstance(t, int):
        return t
    if isinstance(t, str):
        return a[t]
    op = t[0]
    xs = [evalt(x, a) for x in t[1:]]
    if op == "+": return xs[0] + xs[1]
    if op == "-": return xs[0] - xs[1]
    if op == "*": return xs[0] * xs[1]
    if op == "<": return xs[0] < xs[1]
    if op == "<=": return xs[0] <= xs[1]
    if op == ">": return xs[0] > xs[1]
    if op == ">=": return xs[0] >= xs[1]
    if op == "=": return xs[0] == xs[1]
    if op == "!=": return xs[0] != xs[1]
    if op == "and": return xs[0] and xs[1]
    if op == "or": return xs[0] or xs[1]
    if op == "not": return not xs[0]
    raise ValueError(op)


# Ordem de prioridade: bordas de overflow cedo, para que domínios reduzidos ainda as incluam.
ORDER = [0, 1, 2, -1, 2**63 - 1, 2**64 - 1, 3, 5, 8, 255, -2**63, 256, 2**63]


def bounded(ob, budget=300_000):
    """TESTE (não é prova): enumera valores de borda. Contraexemplo achado é real; ausência não prova."""
    _, vs = to_smt2(ob)
    n = len(ORDER)
    while n > 3 and n ** len(vs) > budget:
        n -= 1
    sat_hyps = 0
    for vals in itertools.product(ORDER[:n], repeat=len(vs)):
        a = dict(zip(vs, vals))
        if all(evalt(h, a) for h in ob["hyps"]):
            sat_hyps += 1
            if not evalt(ob["goal"], a):
                return {"status": "failed", "model": a, "how": "bounded"}
    if sat_hyps == 0:
        return {"status": "unknown", "how": "bounded", "note": "hipóteses insatisfeitas no domínio testado"}
    return {"status": "tested", "models": sat_hyps, "how": "bounded"}


def z3(ob):
    text, vs = to_smt2(ob)
    try:
        p = subprocess.run(["z3", "-in", "-T:20"], input=text, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return {"status": "unknown", "how": "z3"}
    out = p.stdout.strip().splitlines()
    if out and out[0] == "unsat":
        return {"status": "proved", "how": "z3"}
    if out and out[0] == "sat":
        model = {}
        for m in re.finditer(r"\(define-fun (\S+) \(\) Int\s+(\(- \d+\)|\d+)\)", p.stdout):
            v = m.group(2)
            model[m.group(1)] = -int(v[3:-1]) if v.startswith("(-") else int(v)
        return {"status": "failed", "model": model, "how": "z3"}
    return {"status": "unknown", "how": "z3"}


def discharge(ob):
    """1) provador linear interno (sólido); 2) Z3 se instalado; 3) teste limitado."""
    if linarith.prove(list(ob["hyps"]), ob["goal"]):
        return {"status": "proved", "how": "linarith"}
    if shutil.which("z3"):
        return z3(ob)
    return bounded(ob)
