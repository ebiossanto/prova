"""Provador interno para aritmética linear inteira, arrays (McCarthy + Ackermann) e quantificadores limitados (sem Z3).

Prova `hipóteses => objetivo` mostrando que `hipóteses ∧ ¬objetivo` é insatisfatível:
  1. Quantificadores limitados `(forall v lo hi P)`: no objetivo, Skolemiza `v` com `lo <= v_sk < hi`;
     nas hipóteses, instancia `v` nos termos de índice relevantes (guardado por `lo <= idx < hi`).
  2. Teoria de arrays (McCarthy 1962 + Ackermann 1954): reduz `select(store_arr(A, i, v), j)` por igualdade
     polinomial, diferença constante não-nula ou disjunção `(i = j ∧ w = v) ∨ (i != j ∧ w = select(A, j))`,
     e aplica congruência `(i = j) => select(A, i) = select(A, j)` em leituras da mesma base.
  3. Polinômios: cada monômio não linear (ex.: i*i) vira uma variável inteira opaca (abstração sólida).
  4. Forma normal disjuntiva sobre comparações (!= vira dois casos; < vira ≥ com +1, válido em inteiros).
  5. Fourier–Motzkin por caso, com arredondamento inteiro (divide pelo mdc e toma o piso da constante).
Para termos não lineares, substitui igualdades entre variáveis e acrescenta envelopes de
McCormick (x*y) a partir de limites que o próprio FM deriva. Só responde "provado" quando TODOS os casos são infeasíveis; qualquer dúvida devolve None.
"""
from math import gcd

CMPS = ("<", "<=", ">", ">=", "=", "!=")
BITOPS = ("bit_and", "bit_or", "bit_xor", "shl", "shr", "add_wrap", "sub_wrap")
EXT_OPS = ("forall", "select", "store_arr") + BITOPS
MAX_CASES = 2048
MAX_CONS = 4000


class Giveup(Exception):
    pass


# ---------- polinômios: {monômio (tupla ordenada de variáveis): coeficiente int} ----------
def padd(a, b, k=1):
    r = dict(a)
    for m, c in b.items():
        r[m] = r.get(m, 0) + k * c
        if r[m] == 0:
            del r[m]
    return r


def pmul(a, b):
    r = {}
    for m1, c1 in a.items():
        for m2, c2 in b.items():
            m = tuple(sorted(m1 + m2))
            r[m] = r.get(m, 0) + c1 * c2
            if r[m] == 0:
                del r[m]
    return r


def poly(t):
    if isinstance(t, int):
        return {(): t} if t else {}
    if isinstance(t, str):
        return {(t,): 1}
    op = t[0]
    if op == "+":
        return padd(poly(t[1]), poly(t[2]))
    if op == "-":
        return padd(poly(t[1]), poly(t[2]), -1)
    if op == "*":
        return pmul(poly(t[1]), poly(t[2]))
    raise Giveup(f"termo aritmético desconhecido: {op}")


ONE = {(): 1}


def cmp_cases(op, a, b, neg):
    d = padd(poly(a), poly(b), -1)      # a - b
    nd = padd(poly(b), poly(a), -1)     # b - a
    if neg:
        op = {"<": ">=", "<=": ">", ">": "<=", ">=": "<", "=": "!=", "!=": "="}[op]
    if op == "<=":
        return [[nd]]
    if op == "<":
        return [[padd(nd, ONE, -1)]]
    if op == ">=":
        return [[d]]
    if op == ">":
        return [[padd(d, ONE, -1)]]
    if op == "=":
        return [[d, nd]]
    return [[padd(d, ONE, -1)], [padd(nd, ONE, -1)]]  # !=


def cross(xs, ys):
    if len(xs) * len(ys) > MAX_CASES:
        raise Giveup("explosão de casos")
    return [x + y for x in xs for y in ys]


def dnf(f, neg=False):
    if not isinstance(f, tuple):
        raise Giveup("fórmula inválida")
    op = f[0]
    if op in CMPS:
        return cmp_cases(op, f[1], f[2], neg)
    if op == "not":
        return dnf(f[1], not neg)
    if op in ("and", "or"):
        conj = (op == "and") != neg
        parts = [dnf(x, neg) for x in f[1:]]
        if conj:
            out = [[]]
            for p in parts:
                out = cross(out, p)
            return out
        out = []
        for p in parts:
            out += p
        if len(out) > MAX_CASES:
            raise Giveup("explosão de casos")
        return out
    raise Giveup(f"operador lógico desconhecido: {op}")


# ---------- Fourier–Motzkin com arredondamento inteiro ----------
INFEAS = object()


def pneg(p):
    return {m: -c for m, c in p.items()}


def norm(p):
    """p >= 0 sobre inteiros. Retorna (coefs, const) normalizado."""
    const = p.get((), 0)
    coefs = {m: c for m, c in p.items() if m != ()}
    if coefs:
        g = 0
        for c in coefs.values():
            g = gcd(g, abs(c))
        coefs = {m: c // g for m, c in coefs.items()}
        const = const // g  # piso: sólido para inteiros
    return coefs, const


def eliminate(polys, keep=frozenset()):
    """Elimina todas as variáveis fora de `keep`. INFEAS se achar 0 >= negativo (sólido)."""
    cons = {}
    for p in polys:
        coefs, c = norm(p)
        key = tuple(sorted(coefs.items()))
        cons[key] = min(c, cons.get(key, c))
    while True:
        work = []
        for key, c in cons.items():
            if not key:
                if c < 0:
                    return INFEAS
                continue
            work.append((dict(key), c))
        if not work:
            return {}
        vs = {}
        for coefs, _ in work:
            for v, a_ in coefs.items():
                if v not in keep:
                    pn = vs.setdefault(v, [0, 0])
                    pn[0 if a_ > 0 else 1] += 1
        if not vs:
            return {tuple(sorted(c_.items())): k for c_, k in work}
        v = min(vs, key=lambda x: vs[x][0] * vs[x][1])
        pos = [(c_, k) for c_, k in work if c_.get(v, 0) > 0]
        neg = [(c_, k) for c_, k in work if c_.get(v, 0) < 0]
        rest = [(c_, k) for c_, k in work if v not in c_]
        new = {}

        def put(coefs, c):
            n = norm({**coefs, (): c})
            key = tuple(sorted(n[0].items()))
            new[key] = min(n[1], new.get(key, n[1]))

        for c_, k in rest:
            put(c_, k)
        for (cp, kp) in pos:
            for (cn, kn) in neg:
                a_, b_ = cp[v], -cn[v]
                comb = {}
                for w, x in cp.items():
                    if w != v:
                        comb[w] = comb.get(w, 0) + b_ * x
                for w, x in cn.items():
                    if w != v:
                        comb[w] = comb.get(w, 0) + a_ * x
                put({w: x for w, x in comb.items() if x != 0}, b_ * kp + a_ * kn)
        if len(new) > MAX_CONS:
            raise Giveup("explosão de restrições")
        cons = new


def infeasible(polys):
    return eliminate(polys) is INFEAS


# ---------- reforço para termos não lineares (sólido) ----------
def subst(q, v, repl):
    out = {}
    for m, c in q.items():
        k = m.count(v)
        if k == 0:
            out = padd(out, {m: c})
            continue
        term = {tuple(x for x in m if x != v): c}
        for _ in range(k):
            term = pmul(term, repl)
        out = padd(out, term)
    return out


def subst_equalities(case):
    """Se o caso contém x - y + k >= 0 e o oposto, então y = x + k: troca dentro de produtos."""
    case = list(case)
    for _ in range(12):
        keys = {tuple(sorted(p.items())) for p in case}
        found = None
        for p in case:
            vars_ = [m for m in p if m != ()]
            if not 1 <= len(vars_) <= 2 or any(len(m) != 1 for m in vars_):
                continue
            if any(abs(p[m]) != 1 for m in vars_):
                continue
            if tuple(sorted(pneg(p).items())) not in keys:
                continue
            v = sorted(m[0] for m in vars_)[0]
            a_ = p[(v,)]
            rest = {m: c for m, c in p.items() if m != (v,)}
            found = (v, padd({}, rest, -a_))  # v = -rest / a  (a = ±1)
            break
        if not found:
            break
        v, repl = found
        case = [subst(q, v, repl) for q in case]
    return case


def bounds(case, v):
    r = eliminate(case, keep={(v,)})
    lo = hi = None
    if r is INFEAS:
        return lo, hi
    for key, c in r.items():
        if len(key) == 1 and key[0][0] == (v,):
            a_ = key[0][1]
            if a_ > 0:
                b_ = -(c // a_)
                lo = b_ if lo is None else max(lo, b_)
            else:
                b_ = c // (-a_)
                hi = b_ if hi is None else min(hi, b_)
    return lo, hi


def mccormick(m, xl, xu, yl, yu):
    x, y = m
    X, Y, M = {(x,): 1}, {(y,): 1}, {m: 1}

    def lin(*terms):
        out = {}
        for t, k in terms:
            out = padd(out, t, k)
        return out
    return [
        lin((M, 1), (X, -yl), (Y, -xl), (ONE, xl * yl)),     # (x-xl)(y-yl) >= 0
        lin((M, 1), (X, -yu), (Y, -xu), (ONE, xu * yu)),     # (xu-x)(yu-y) >= 0
        lin((M, -1), (X, yu), (Y, xl), (ONE, -xl * yu)),     # (x-xl)(yu-y) >= 0
        lin((M, -1), (X, yl), (Y, xu), (ONE, -xu * yl)),     # (xu-x)(y-yl) >= 0
    ]


def strengthen(case):
    case = subst_equalities(case)
    mons = {m for p in case for m in p if len(m) == 2}
    if not mons:
        return case
    extra, cache = [], {}
    for m in mons:
        for v in set(m):
            if v not in cache:
                cache[v] = bounds(case, v)
        (xl, xu), (yl, yu) = cache[m[0]], cache[m[1]]
        if None not in (xl, xu, yl, yu):
            extra += mccormick(m, xl, xu, yl, yu)
    return case + extra


# ---------- quantificadores limitados, arrays (McCarthy + Ackermann) e bitwise ----------
def has_ext(t):
    if isinstance(t, tuple):
        if t and t[0] in EXT_OPS:
            return True
        return any(has_ext(x) for x in t[1:])
    return False


def subst_var(t, var, repl):
    if t == var:
        return repl
    if isinstance(t, tuple):
        if t[0] == "forall":
            _, v, lo, hi, body = t
            lo2, hi2 = subst_var(lo, var, repl), subst_var(hi, var, repl)
            return ("forall", v, lo2, hi2, body if v == var else subst_var(body, var, repl))
        return (t[0],) + tuple(subst_var(x, var, repl) for x in t[1:])
    return t


def _flatten_and(fs):
    out = []
    for f in fs:
        if isinstance(f, tuple) and f[0] == "and":
            out.extend(_flatten_and(f[1:]))
        else:
            out.append(f)
    return out


def _collect_indices(t, out):
    if isinstance(t, str) and t.startswith("sk!"):
        out.append(t)
    elif isinstance(t, tuple):
        if t[0] == "select":
            out.append(t[2])
        elif t[0] == "store_arr":
            out.append(t[2])
        for x in t[1:]:
            _collect_indices(x, out)


def _reduce_ext(hyps, goal):
    """Skolemiza forall no goal, instancia forall nas hipóteses e reduz arrays/bitwise para LIA."""
    hyps = _flatten_and(hyps)
    sk_id = 0
    while isinstance(goal, tuple) and goal[0] == "forall":
        _, var, lo, hi, body = goal
        sk_id += 1
        sk = f"sk!{var}!{sk_id}"
        hyps.append(("<=", lo, sk))
        hyps.append(("<", sk, hi))
        goal = subst_var(body, var, sk)

    univs = [h for h in hyps if isinstance(h, tuple) and h[0] == "forall"]
    plain = [h for h in hyps if not (isinstance(h, tuple) and h[0] == "forall")]
    if univs:
        raw_idx = []
        for h in plain:
            _collect_indices(h, raw_idx)
        _collect_indices(goal, raw_idx)
        cands, seen = [], set()
        for idx in raw_idx:
            if not has_ext(idx) or (isinstance(idx, tuple) and idx[0] != "forall"):
                if idx not in seen:
                    seen.add(idx)
                    cands.append(idx)
        cands = cands[:6]
        for _, var, lo, hi, body in univs:
            use_cands = [idx for idx in cands if idx != hi]
            if not use_cands and lo != hi:
                use_cands = [lo]
            for idx in use_cands:
                inst = subst_var(body, var, idx)
                if idx == lo:
                    plain.append(("or", ("<=", hi, lo), inst))
                else:
                    plain.append(("or", ("<", idx, lo), ("or", ("<=", hi, idx), inst)))
    hyps = _flatten_and(plain)

    extra = []
    base_reads = {}   # (arr_name, idx_poly_key) -> (var_name, idx_term)
    store_cache = {}  # (arr_term, idx_poly_key) -> var_name
    op_cache = {}     # (op, a_key, b_key) -> var_name

    def pkey(t):
        return tuple(sorted(poly(t).items()))

    def rw(t):
        if isinstance(t, (int, str)):
            return t
        op = t[0]
        if op == "forall":
            raise Giveup("forall aninhado não redutível")
        if op == "select":
            arr = t[1]
            idx = rw(t[2])
            idx_p = poly(idx)
            idx_k = tuple(sorted(idx_p.items()))
            while isinstance(arr, tuple) and arr[0] == "store_arr":
                _, base_a, s_idx_raw, s_val_raw = arr
                s_idx = rw(s_idx_raw)
                s_val = rw(s_val_raw)
                d = padd(idx_p, poly(s_idx), -1)
                if not d:
                    return s_val
                if tuple(d.keys()) == ((),) and d[()] != 0:
                    arr = base_a
                    continue
                ckey = (arr, idx_k)
                if ckey not in store_cache:
                    w = f"sel!s{len(store_cache)}"
                    store_cache[ckey] = w
                    extra.append(("and", ("<=", 0, w), ("<=", w, 255)))
                    rest_sel = rw(("select", base_a, idx))
                    extra.append(("or",
                                  ("and", ("=", idx, s_idx), ("=", w, s_val)),
                                  ("and", ("!=", idx, s_idx), ("=", w, rest_sel))))
                return store_cache[ckey]
            if not isinstance(arr, str):
                raise Giveup("array base inválido")
            bkey = (arr, idx_k)
            if bkey not in base_reads:
                v = f"sel!{arr}!{len(base_reads)}"
                base_reads[bkey] = (v, idx)
                extra.append(("and", ("<=", 0, v), ("<=", v, 255)))
            return base_reads[bkey][0]
        if op in BITOPS:
            a, b = rw(t[1]), rw(t[2])
            if isinstance(a, int) and isinstance(b, int):
                if op == "bit_and":
                    return a & b
                if op == "bit_or":
                    return a | b
                if op == "bit_xor":
                    return a ^ b
                if op == "shl" and 0 <= b < 64:
                    return a << b
                if op == "shr" and 0 <= b < 64:
                    return a >> b
            okey = (op, pkey(a), pkey(b))
            if okey not in op_cache:
                bv = f"op!{op}!{len(op_cache)}"
                op_cache[okey] = bv
                if op == "bit_and":
                    if isinstance(b, int) and b >= 0:
                        extra.append(("and", ("<=", 0, bv), ("<=", bv, b)))
                    if isinstance(a, int) and a >= 0:
                        extra.append(("and", ("<=", 0, bv), ("<=", bv, a)))
            return op_cache[okey]
        return (op,) + tuple(rw(x) for x in t[1:])

    rw_hyps = [rw(h) for h in hyps]
    rw_goal = rw(goal)

    # Congruência de Ackermann para leituras da mesma base: (idx1 = idx2) => (v1 = v2)
    by_arr = {}
    for (arr, _), (v, idx) in base_reads.items():
        by_arr.setdefault(arr, []).append((v, idx))
    for reads in by_arr.values():
        for i in range(len(reads)):
            v1, idx1 = reads[i]
            p1 = poly(idx1)
            for j in range(i + 1, len(reads)):
                v2, idx2 = reads[j]
                d = padd(p1, poly(idx2), -1)
                if tuple(d.keys()) == ((),) and d[()] != 0:
                    continue
                extra.append(("or", ("!=", idx1, idx2), ("=", v1, v2)))

    return rw_hyps + extra, rw_goal


# ---------- interface ----------
def free_vars(t, acc):
    if isinstance(t, str):
        acc.add(t)
    elif isinstance(t, tuple):
        for x in t[1:]:
            free_vars(x, acc)


def cone(hyps, goal):
    """Mantém só hipóteses ligadas ao objetivo por variáveis compartilhadas (omitir hipótese é sólido)."""
    want = set()
    free_vars(goal, want)
    infos = []
    for h in hyps:
        vs = set()
        free_vars(h, vs)
        for v in vs:
            if isinstance(v, str) and v.startswith("sk!"):
                want.add(v)
        infos.append((h, vs))
    keep, changed = set(), True
    while changed:
        changed = False
        for i, (h, vs) in enumerate(infos):
            if i not in keep and (not vs or vs & want):
                keep.add(i)
                want |= vs
                changed = True
    return [infos[i][0] for i in sorted(keep)]


def _prove_core(hyps, goal):
    cases = [[]]
    for h in cone(hyps, goal):
        cases = cross(cases, dnf(h))
    cases = cross(cases, dnf(goal, neg=True))
    for case in cases:
        if infeasible(case):
            continue
        if not infeasible(strengthen(case)):
            return None
    return True


def prove(hyps, goal):
    """True se provado; None se não conseguiu (nunca devolve falso positivo)."""
    if isinstance(goal, tuple) and goal[0] == "and":
        return True if all(prove(hyps, g) for g in goal[1:]) else None
    # Caminho rápido: sem extensões no objetivo, tenta primeiro ignorando hipóteses com extensões (sempre sólido)
    if not has_ext(goal):
        try:
            simple_hyps = [h for h in _flatten_and(hyps) if not has_ext(h)]
            if _prove_core(simple_hyps, goal):
                return True
        except Giveup:
            pass
    if any(has_ext(h) for h in hyps) or has_ext(goal):
        try:
            r_hyps, r_goal = _reduce_ext(cone(hyps, goal), goal)
            if isinstance(r_goal, tuple) and r_goal[0] == "and":
                return True if all(_prove_core(r_hyps, g) for g in r_goal[1:]) else None
            return _prove_core(r_hyps, r_goal)
        except Giveup:
            return None
    return None


def contradictory(hyps):
    """True se as hipóteses são PROVADAMENTE insatisfatíveis (então qualquer objetivo seria 'provado' no vazio).
    Sólido: nunca acusa contradição que não exista; na dúvida devolve False."""
    try:
        if any(has_ext(h) for h in hyps):
            hyps, _ = _reduce_ext(hyps, ("=", 0, 0))
        cases = [[]]
        for h in hyps:
            cases = cross(cases, dnf(h))
        return all(infeasible(c) or infeasible(strengthen(c)) for c in cases)
    except Giveup:
        return False
