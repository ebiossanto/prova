"""Descarrega obrigações. Com z3 no PATH: prova (unsat) ou contraexemplo (sat).
Sem z3: verificador limitado (TESTE em valores de borda, não é prova).

Suporta: inteiros, booleanos, arrays (McCarthy select/store_arr), quantificadores limitados (forall) e bitwise/shift/wrap.
"""
import itertools
import re
import shutil
import subprocess

from . import linarith


def smt(t):
    """Converte termo interno para sintaxe SMT-LIB."""
    if isinstance(t, int):
        return str(t) if t >= 0 else f"(- {-t})"
    if isinstance(t, str):
        return t
    op = t[0]
    if op == "!=":
        return f"(not (= {smt(t[1])} {smt(t[2])}))"
    if op == "select":
        return f"(select {smt(t[1])} {smt(t[2])})"
    if op in ("store", "store_arr"):
        return f"(store {smt(t[1])} {smt(t[2])} {smt(t[3])})"
    if op == "forall":
        if len(t) == 5:
            _, var, lo, hi, body = t
            return f"(forall (({var} Int)) (=> (and (<= {smt(lo)} {var}) (< {var} {smt(hi)})) {smt(body)}))"
        var, body = t[1], t[2]
        return f"(forall (({var} Int)) {smt(body)})"
    if op == "exists":
        var, body = t[1], t[2]
        return f"(exists (({var} Int)) {smt(body)})"
    return "(" + op + " " + " ".join(smt(x) for x in t[1:]) + ")"


def free(t, acc, bound=frozenset()):
    """Coleta variáveis escalares livres em um termo."""
    if isinstance(t, str):
        if t not in bound:
            acc.add(t)
    elif isinstance(t, tuple):
        if t[0] in ("select", "store", "store_arr"):
            if isinstance(t[1], tuple):
                free(t[1], acc, bound)
            for x in t[2:]:
                free(x, acc, bound)
            return
        if t[0] == "forall" and len(t) == 5:
            _, var, lo, hi, body = t
            free(lo, acc, bound)
            free(hi, acc, bound)
            free(body, acc, bound | {var})
            return
        for x in t[1:]:
            free(x, acc, bound)


def array_vars(t, acc):
    """Coleta variáveis de array base (nomes que são arrays, não escalares)."""
    if isinstance(t, tuple):
        if t[0] in ("select", "store", "store_arr"):
            if isinstance(t[1], str):
                acc.add(t[1])
            elif isinstance(t[1], tuple):
                array_vars(t[1], acc)
            for x in t[2:]:
                array_vars(x, acc)
            return
        for x in t[1:]:
            array_vars(x, acc)


def to_smt2(ob):
    """Converte obrigação para SMT-LIB2."""
    vs = set()
    arrs = set()
    for h in ob["hyps"]:
        free(h, vs)
        array_vars(h, arrs)
    free(ob["goal"], vs)
    array_vars(ob["goal"], arrs)

    lines = ["(set-logic ALL)"]
    for a in sorted(arrs):
        lines.append(f"(declare-const {a} (Array Int Int))")
    for v in sorted(vs - arrs):
        lines.append(f"(declare-const {v} Int)")
    lines += [f"(assert {smt(h)})" for h in ob["hyps"]]
    lines += [f"(assert (not {smt(ob['goal'])}))", "(check-sat)", "(get-model)"]
    return "\n".join(lines), sorted(vs - arrs), sorted(arrs)


def _eval_arr(arr, idx, a):
    while isinstance(arr, tuple) and arr[0] in ("store", "store_arr"):
        _, base_a, s_idx, s_val = arr
        if evalt(s_idx, a) == idx:
            return evalt(s_val, a)
        arr = base_a
    d = a.get(arr, {})
    return d.get(idx, 0) if isinstance(d, dict) else 0


def evalt(t, a):
    """Avalia termo em uma interpretação (para bounded testing)."""
    if isinstance(t, int):
        return t
    if isinstance(t, str):
        return a[t]
    op = t[0]
    if op == "select":
        return _eval_arr(t[1], evalt(t[2], a), a)
    if op == "forall" and len(t) == 5:
        _, var, lo_e, hi_e, body = t
        lo, hi = evalt(lo_e, a), evalt(hi_e, a)
        if hi - lo > 64:
            raise ValueError("forall grande demais para bounded")
        a2 = dict(a)
        for k in range(lo, hi):
            a2[var] = k
            if not evalt(body, a2):
                return False
        return True
    xs = [evalt(x, a) for x in t[1:]]
    if op == "+": return xs[0] + xs[1]
    if op == "-": return xs[0] - xs[1]
    if op == "*": return xs[0] * xs[1]
    if op == "add_wrap": return (xs[0] + xs[1]) % (2**64)
    if op == "sub_wrap": return (xs[0] - xs[1]) % (2**64)
    if op == "bit_and": return xs[0] & xs[1]
    if op == "bit_or": return xs[0] | xs[1]
    if op == "bit_xor": return xs[0] ^ xs[1]
    if op == "shl":
        if not 0 <= xs[1] < 64:
            raise ValueError("shl fora da faixa")
        return xs[0] << xs[1]
    if op == "shr":
        if not 0 <= xs[1] < 64:
            raise ValueError("shr fora da faixa")
        return xs[0] >> xs[1]
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


# Ordem de prioridade: bordas de overflow e shifts cedo, para que domínios reduzidos ainda as incluam.
ORDER = [0, 1, 2, -1, 8, 64, 2**63 - 1, 2**64 - 1, 3, 5, 255, -2**63, 256, 2**63]


def bounded(ob, budget=300_000):
    """TESTE (não é prova): enumera valores de borda. Contraexemplo achado é real; ausência não prova."""
    hyps, goal = list(ob["hyps"]), ob["goal"]
    if not linarith.has_ext(goal):
        hyps = [h for h in hyps if not (isinstance(h, tuple) and len(h) == 3 and h[0] == "="
                                        and isinstance(h[2], tuple) and h[2][0] == "select")]
    if any(linarith.has_ext(h) for h in hyps) or linarith.has_ext(goal):
        try:
            hyps, goal = linarith._reduce_ext(hyps, goal)
        except linarith.Giveup:
            return {"status": "unknown", "how": "bounded"}
    red_ob = {"fn": ob.get("fn", ""), "label": ob.get("label", ""), "hyps": tuple(hyps), "goal": goal}
    _, vs, arrs = to_smt2(red_ob)
    if arrs:
        return {"status": "unknown", "how": "bounded", "note": "arrays requerem provador interno ou Z3"}
    n = len(ORDER)
    while n > 3 and n ** len(vs) > budget:
        n -= 1
    sat_hyps = 0
    try:
        for vals in itertools.product(ORDER[:n], repeat=len(vs)):
            a = dict(zip(vs, vals))
            if all(evalt(h, a) for h in hyps):
                sat_hyps += 1
                if not evalt(goal, a):
                    return {"status": "failed", "model": a, "how": "bounded"}
    except ValueError:
        return {"status": "unknown", "how": "bounded"}
    if sat_hyps == 0:
        return {"status": "unknown", "how": "bounded", "note": "hipóteses insatisfeitas no domínio testado"}
    return {"status": "tested", "models": sat_hyps, "how": "bounded"}


def z3(ob):
    """Usa Z3 para provar (unsat) ou encontrar contraexemplo (sat)."""
    text, vs, arrs = to_smt2(ob)
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
    """1) provador linear/arrays interno (sólido); 2) Z3 se instalado; 3) teste limitado."""
    if linarith.prove(list(ob["hyps"]), ob["goal"]):
        return {"status": "proved", "how": "linarith"}
    if shutil.which("z3"):
        return z3(ob)
    return bounded(ob)
