"""Verificação linear de posse: parâmetros (own T) devem ser consumidos (drop) exatamente uma vez
em todos os caminhos. Uso depois de drop, drop duplo, drop em laço e vazamento são erros."""
from .check import show


def _names(e, acc):
    if isinstance(e, list):
        items = e[2:] if e and e[0] == "call" else e  # o nome do chamado não é variável
        for x in items:
            _names(x, acc)
    elif isinstance(e, str):
        acc.add(e)


def _exprs(s):
    h = s[0]
    if h in ("let", "var"):
        return [s[3]]
    if h == "set":
        return [s[2]]
    if h == "store":
        return list(s[1:])
    if h in ("return", "assert", "do", "sys_exit", "atomic_store", "mmio_write"):
        return list(s[1:])
    if h in ("if", "while"):
        return [s[1]]
    return []


def _calls(e, out):
    if isinstance(e, list):
        if e and e[0] == "call" and len(e) > 1 and isinstance(e[1], str):
            out.append(e)
        for x in e:
            _calls(x, out)


def _block(stmts, dropped, owned, errs, fn, sigs):
    dropped = set(dropped)
    for s in stmts:
        used = set()
        for e in _exprs(s):
            _names(e, used)
        for u in sorted(used & dropped):
            errs.append(f"{fn}: uso de '{u}' após drop ou movimento em {show(s)}")
        calls = []
        for e in _exprs(s):
            _calls(e, calls)
        for c in calls:
            g = sigs.get(c[1])
            if g is None:
                continue
            for (pn, PT), a in zip(g.params, c[2:]):
                if isinstance(PT, list) and PT[0] == "own":
                    if a not in owned:
                        errs.append(f"{fn}: '{a}' não é (own ...), mas {g.name} exige posse em '{pn}'")
                    else:
                        dropped.add(a)  # movido para o chamado
        h = s[0]
        if h == "drop":
            x = s[1]
            if x not in owned:
                errs.append(f"{fn}: drop de '{x}', que não é (own ...)")
            elif x in dropped:
                errs.append(f"{fn}: drop duplo de '{x}'")
            dropped.add(x)
        elif h == "if":
            th = [f for f in s[2:] if f[0] == "then"]
            el = [f for f in s[2:] if f[0] == "else"]
            d1, t1 = _block(th[0][1:] if th else [], dropped, owned, errs, fn, sigs)
            d2, t2 = _block(el[0][1:] if el else [], dropped, owned, errs, fn, sigs)
            if t1 and t2:
                return dropped, True
            if not t1 and not t2 and d1 != d2:
                errs.append(f"{fn}: ramos do if discordam sobre a posse de {sorted(d1 ^ d2)}")
            dropped = d2 if t1 else d1
        elif h == "while":
            body = [f for f in s[2:] if f[0] not in ("invariant", "decreases")]
            d, _ = _block(body, dropped, owned, errs, fn, sigs)
            if d != dropped:
                errs.append(f"{fn}: drop dentro de while (posse mudaria a cada iteração)")
        elif h in ("return", "sys_exit"):
            for x in sorted(owned - dropped):
                errs.append(f"{fn}: vazamento de '{x}' (falta drop antes de {h})")
            return dropped, True
    return dropped, False


def check_linear(fn, sigs=None):
    # Atomics are exempt from linear checking (like ptr regions)
    owned = {n for n, T in fn.params if isinstance(T, list) and T[0] == "own"}
    errs = []
    dropped, term = _block(fn.body, set(), owned, errs, fn.name, sigs or {})
    if not term:
        for x in sorted(owned - dropped):
            errs.append(f"{fn.name}: vazamento de '{x}' (falta drop no fim da função)")
    return errs
