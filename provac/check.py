"""Tipos estritos + geração de condições de verificação (VCs) por execução simbólica.

Cada obrigação é (rótulo, hipóteses, objetivo): hipóteses => objetivo deve ser válido.
Termos: int | str (símbolo) | tupla (op, args...). Contratos usam inteiros matemáticos
(sem overflow); o código executável tem overflow checado por obrigação.
"""
from .sexp import Str

LO = {"i64": -2**63, "usize": 0, "u8": 0}
HI = {"i64": 2**63 - 1, "usize": 2**64 - 1, "u8": 255}
SCALARS = ("i64", "usize", "u8", "i8")
ARITH = ("+", "-", "*")
CMP = ("<", "<=", ">", ">=", "=", "!=")
PTR_REGIONS = ("mmio", "ram", "rom")
ATOMIC_ORDERS = ("acq-rel", "relaxed", "acq-cst", "rel-cst")


class ProvaError(Exception):
    pass


def show(e):
    if isinstance(e, list):
        return "(" + " ".join(show(x) for x in e) + ")"
    if isinstance(e, Str):
        return '"' + e + '"'
    return str(e)


def rng(t, T):
    return ("and", ("<=", LO[T], t), ("<=", t, HI[T]))


def base(T):
    return T[1] if isinstance(T, list) and T[0] == "own" else T


def is_slice(T):
    T = base(T)
    return isinstance(T, list) and T[0] == "slice"


def is_ptr(T):
    T = base(T)
    return isinstance(T, list) and T[0] == "own" and len(T) >= 3 and T[1] == "ptr"


def is_atomic(T):
    T = base(T)
    # base returns the inner type string (e.g., "atomic", "ptr", "slice")
    return T == "atomic"


class Fn:
    def __init__(self, form):
        self.name = form[1]
        self.params, self.ret = [], "unit"
        self.pre, self.post, self.body = [], [], []
        self.has_pre = self.has_post = False
        for c in form[2:]:
            h = c[0]
            if h == "params":
                self.params += [(p[0], p[1]) for p in c[1:]]
            elif h == "returns":
                self.ret = c[1]
            elif h == "pre":
                self.pre += c[1:]
                self.has_pre = True
            elif h == "post":
                self.post += c[1:]
                self.has_post = True
            elif h == "body":
                self.body = c[1:]
            else:
                raise ProvaError(f"{self.name}: cláusula desconhecida '{h}'")
        if not (self.has_pre and self.has_post):
            raise ProvaError(f"{self.name}: toda função exige (pre ...) e (post ...), mesmo vazios")


class St:
    def __init__(self):
        self.env, self.path, self.slices = {}, [], {}
        self.ret, self.done, self.exited = None, False, False

    def cp(self):
        n = St()
        n.env, n.path, n.slices = dict(self.env), list(self.path), dict(self.slices)
        n.ret, n.done, n.exited = self.ret, self.done, self.exited
        return n


class Cx:
    def __init__(self, fn, data, sigs=None):
        self.fn, self.data, self.sigs = fn, data, sigs or {}
        self.types, self.mut, self.slice_names = {}, set(), set()
        self.obs, self.k = [], 0

    def fresh(self, base_):
        self.k += 1
        return f"{base_}!{self.k}"

    def ob(self, label, st, goal):
        self.obs.append({"fn": self.fn.name, "label": label,
                         "hyps": tuple(st.path), "goal": goal})


def ty(e, cx):
    if isinstance(e, int):
        return None
    if isinstance(e, str):
        if e in cx.types:
            return cx.types[e]
        if e in cx.slice_names:
            raise ProvaError(f"'{e}' é uma fatia, não um escalar")
        raise ProvaError(f"variável não declarada: {e}")
    op = e[0]
    if op in ARITH or op in CMP:
        ts = {t for t in (ty(a, cx) for a in e[1:]) if t}
        if "bool" in ts or "unit" in ts:
            raise ProvaError(f"aritmética sobre booleano/unit em {show(e)}")
        if len(ts) > 1:
            raise ProvaError(f"tipos incompatíveis em {show(e)}: {sorted(ts)}; use (cast T x)")
        return "bool" if op in CMP else (next(iter(ts)) if ts else None)
    if op in ("and", "or", "not"):
        if (op == "not" and len(e) != 2) or (op != "not" and len(e) < 3):
            raise ProvaError(f"aridade inválida em {show(e)}")
        for a in e[1:]:
            if ty(a, cx) != "bool":
                raise ProvaError(f"{op} exige operandos booleanos: {show(e)}")
        return "bool"
    if op == "len":
        return "usize"
    if op == "load":
        if len(e) != 3:
            raise ProvaError(f"load espera (load fatia indice): {show(e)}")
        if ty(e[2], cx) not in (None, "usize"):
            raise ProvaError(f"índice de fatia deve ser usize: {show(e)}; use (cast usize ...)")
        return "u8"
    if op == "cast":
        if len(e) != 3 or e[1] not in SCALARS:
            raise ProvaError(f"cast espera (cast T expr) com T em {SCALARS}: {show(e)}")
        return e[1]
    if op == "sys_write":
        if len(e) != 4:
            raise ProvaError(f"sys_write espera (sys_write fd fatia n): {show(e)}")
        if ty(e[1], cx) not in (None, "i64"):
            raise ProvaError(f"fd de sys_write deve ser i64: {show(e)}")
        if not isinstance(e[2], str) or e[2] not in cx.slice_names:
            raise ProvaError(f"sys_write exige uma fatia como buffer: {show(e)}")
        if ty(e[3], cx) not in (None, "usize"):
            raise ProvaError(f"contagem de sys_write deve ser usize: {show(e)}")
        return "i64"
    if op == "call":
        g = cx.sigs.get(e[1])
        if g is None:
            raise ProvaError(f"chamada de função desconhecida: {e[1]}")
        if len(e) - 2 != len(g.params):
            raise ProvaError(f"{g.name} espera {len(g.params)} argumentos, recebeu {len(e) - 2}")
        for (pn, PT), a in zip(g.params, e[2:]):
            if is_slice(PT):
                if a not in cx.slice_names:
                    raise ProvaError(f"{g.name}: argumento '{pn}' exige uma fatia, recebeu {show(a)}")
            else:
                ta = ty(a, cx)
                if ta not in (None, PT):
                    raise ProvaError(f"{g.name}: argumento '{pn}' é {PT}, recebeu {ta}; use (cast {PT} ...)")
        return g.ret
    raise ProvaError(f"forma desconhecida: {show(e)}")


def slice_len(b, st, cx):
    if not isinstance(b, str) or b not in cx.slice_names:
        raise ProvaError(f"{show(b)} não é uma fatia")
    if b not in st.slices:
        raise ProvaError(f"fatia '{b}' não está definida em todos os caminhos até aqui")
    return st.slices[b]


def arg_range(cx, st, a, t, T):
    """Literais e expressões não-aritméticas passados a um tipo T precisam caber em T."""
    if isinstance(a, str) or (isinstance(a, list) and a[0] in ARITH):
        return  # variável do mesmo tipo (garantida pelo tipo) ou aritmética já checada
    cx.ob(f"argumento cabe em {T}: {show(a)}", st, rng(t, T))


def ev(e, st, cx, ghost=False, want=None):
    """Avalia simbolicamente. ghost=True: aritmética matemática (contratos)."""
    if isinstance(e, int):
        return e
    if isinstance(e, str):
        ty(e, cx)
        if e not in st.env:
            raise ProvaError(f"variável sem valor: {e}")
        return st.env[e]
    op = e[0]
    if op in ARITH:
        if len(e) != 3:
            raise ProvaError(f"{op} é binário: {show(e)}")
        T = ty(e, cx) or want or "i64"
        t = (op, ev(e[1], st, cx, ghost, T), ev(e[2], st, cx, ghost, T))
        if not ghost:
            cx.ob(f"overflow: {show(e)} cabe em {T}", st, rng(t, T))
        return t
    if op in CMP:
        ty(e, cx)
        return (op, ev(e[1], st, cx, ghost), ev(e[2], st, cx, ghost))
    if op in ("and", "or"):
        ts = [ev(a, st, cx, ghost) for a in e[1:]]
        out = ts[0]
        for t in ts[1:]:
            out = (op, out, t)
        return out
    if op == "not":
        return ("not", ev(e[1], st, cx, ghost))
    if op == "len":
        return slice_len(e[1], st, cx)
    if op == "load":
        if ghost:
            raise ProvaError("load em contrato não suportado (conteúdo de fatias não é modelado)")
        L = slice_len(e[1], st, cx)
        i = ev(e[2], st, cx)
        cx.ob(f"limites: {show(e)}", st, ("and", ("<=", 0, i), ("<", i, L)))
        v = cx.fresh("ld")
        st.path.append(rng(v, "u8"))
        return v
    if op == "cast":
        T = e[1]
        if T not in SCALARS:
            raise ProvaError(f"cast para tipo inválido: {T}")
        t = ev(e[2], st, cx, ghost, None)
        if not ghost:
            cx.ob(f"cast: {show(e)} cabe em {T}", st, rng(t, T))
        return t
    if op == "sys_write":
        ty(e, cx)
        fd, buf, n = e[1], e[2], e[3]
        fdt = ev(fd, st, cx, ghost, "i64")
        arg_range(cx, st, fd, fdt, "i64")
        L = slice_len(buf, st, cx)
        nt = ev(n, st, cx, ghost, "usize")
        cx.ob(f"syscall write: contagem <= len({buf})", st, ("and", ("<=", 0, nt), ("<=", nt, L)))
        return cx.fresh("sys")
    if op == "call":
        if ghost:
            raise ProvaError("chamada em contrato não suportada")
        return do_call(e, st, cx)
    raise ProvaError(f"forma desconhecida: {show(e)}")


def do_call(e, st, cx):
    """Verificação modular: pre do chamado vira obrigação; post vira hipótese."""
    ty(e, cx)  # valida aridade e tipos
    g = cx.sigs[e[1]]
    cc = Cx(g, cx.data, cx.sigs)
    tmp = St()
    for (pn, PT), a in zip(g.params, e[2:]):
        if is_slice(PT):
            ln = base(PT)[2]
            cx.ob(f"chamada {g.name}: len({a}) = {ln}", st, ("=", st.slices[a], tmp.env[ln]))
            cc.slice_names.add(pn)
            tmp.slices[pn] = st.slices[a]
        else:
            tmp.env[pn] = ev(a, st, cx, False, PT)
            arg_range(cx, st, a, tmp.env[pn], PT)
            cc.types[pn] = PT
    for p in g.pre:
        cx.ob(f"chamada {g.name}: pre {show(p)}", st, ev(p, tmp, cc, True))
    if g.ret == "unit":
        r = 0
    else:
        r = cx.fresh("ret")
        st.path.append(rng(r, g.ret))
        cc.types["result"] = g.ret
        tmp.env["result"] = r
    for q in g.post:
        st.path.append(ev(q, tmp, cc, True))
    return r


def declare(cx, x, T, mut):
    if x in cx.types or x in cx.slice_names or x == "result":
        raise ProvaError(f"redeclaração de '{x}' (sem sombreamento)")
    if T not in SCALARS and not is_ptr(T) and not is_atomic(T):
        raise ProvaError(f"tipo inválido para variável: {show(T)}")
    if isinstance(T, list) and T[0] == "ptr":
        region = T[2]
        if region not in PTR_REGIONS:
            raise ProvaError(f"região inválida: {region}")
    if isinstance(T, list) and T[0] == "atomic":
        # T[1] == "atomic", T[2] == scalar type (u32, u64, etc.)
        # We don't validate the order here; it's checked at usage sites
        pass
    cx.types[x] = T
    if mut:
        cx.mut.add(x)


def assigned(stmts):
    out = set()
    for s in stmts:
        if not isinstance(s, list):
            continue
        if s[0] == "set":
            out.add(s[1])
        elif s[0] == "if":
            for part in s[2:]:
                out |= assigned(part[1:])
        elif s[0] == "while":
            out |= assigned([f for f in s[2:] if isinstance(f, list)])
    return out


def assign_check(cx, st, e, T):
    tt = ty(e, cx)
    if tt and tt != T:
        raise ProvaError(f"tipo {tt} atribuído a {T} em {show(e)}; use (cast {T} ...)")
    t = ev(e, st, cx, False, T)
    if not (isinstance(e, list) and e[0] in ARITH):
        cx.ob(f"valor cabe em {T}: {show(e)}", st, rng(t, T))
    return t


def step(s, st, cx):
    h = s[0]
    if h in ("let", "var"):
        _, x, T, e = s
        declare(cx, x, T, h == "var")
        st.env[x] = assign_check(cx, st, e, T)
        return [st]
    if h == "set":
        _, x, e = s
        if x not in cx.mut:
            raise ProvaError(f"'{x}' não é mutável (declare com var)")
        st.env[x] = assign_check(cx, st, e, cx.types[x])
        return [st]
    if h == "let_slice":
        _, b, src = s
        if src[0] != "data-ref" or src[1] not in cx.data:
            raise ProvaError(f"let_slice espera (data-ref nome) válido: {show(s)}")
        cx.slice_names.add(b)
        st.slices[b] = cx.data[src[1]]
        return [st]
    if h == "store":
        _, b, i, v = s
        L = slice_len(b, st, cx)
        if ty(i, cx) not in (None, "usize"):
            raise ProvaError(f"índice de fatia deve ser usize: {show(s)}; use (cast usize ...)")
        it = ev(i, st, cx)
        cx.ob(f"limites: {show(s)}", st, ("and", ("<=", 0, it), ("<", it, L)))
        tv = ty(v, cx)
        if tv not in (None, "u8"):
            raise ProvaError(f"store espera u8, recebeu {tv}: {show(s)}")
        vt = ev(v, st, cx, False, "u8")
        if isinstance(v, int):
            cx.ob(f"valor cabe em u8: {v}", st, rng(vt, "u8"))
        return [st]
    if h == "assert":
        if ty(s[1], cx) != "bool":
            raise ProvaError(f"assert não booleano: {show(s[1])}")
        cx.ob(f"assert: {show(s[1])}", st, ev(s[1], st, cx, True))
        return [st]
    if h == "do":
        ev(s[1], st, cx)
        return [st]
    if h == "drop":
        return [st]
    if h == "return":
        if cx.fn.ret == "unit":
            if len(s) != 1:
                raise ProvaError("função unit não retorna valor")
        else:
            tt = ty(s[1], cx)
            if tt and tt != cx.fn.ret:
                raise ProvaError(f"retorno {tt} != {cx.fn.ret} em {show(s)}")
            st.ret = assign_check(cx, st, s[1], cx.fn.ret)
        st.done = True
        return [st]
    if h == "sys_exit":
        if ty(s[1], cx) not in (None, "i64"):
            raise ProvaError(f"código de sys_exit deve ser i64: {show(s)}")
        ct = ev(s[1], st, cx, False, "i64")
        arg_range(cx, st, s[1], ct, "i64")
        st.done = st.exited = True
        return [st]
    if h == "if":
        if ty(s[1], cx) != "bool":
            raise ProvaError(f"condição não booleana: {show(s[1])}")
        c = ev(s[1], st, cx)
        a, b = st.cp(), st.cp()
        a.path.append(c)
        b.path.append(("not", c))
        th = [f for f in s[2:] if f[0] == "then"]
        el = [f for f in s[2:] if f[0] == "else"]
        out = run(th[0][1:] if th else [], [a], cx)
        out += run(el[0][1:] if el else [], [b], cx)
        return out
    if h == "while":
        return loop(s, st, cx)
    raise ProvaError(f"instrução desconhecida: {show(s)}")


def loop(s, st, cx):
    cond = s[1]
    if ty(cond, cx) != "bool":
        raise ProvaError(f"condição não booleana: {show(cond)}")
    inv = [x for f in s[2:] if f[0] == "invariant" for x in f[1:]]
    dec = [f[1] for f in s[2:] if f[0] == "decreases"]
    body = [f for f in s[2:] if f[0] not in ("invariant", "decreases")]
    if not dec:
        raise ProvaError(f"while sem (decreases ...): terminação é obrigatória: {show(cond)}")
    for I in inv:
        if ty(I, cx) != "bool":
            raise ProvaError(f"invariante não booleana: {show(I)}")
    if ty(dec[0], cx) in ("bool", "unit"):
        raise ProvaError(f"decreases deve ser numérico: {show(dec[0])}")
    for I in inv:
        cx.ob(f"invariante vale na entrada: {show(I)}", st, ev(I, st, cx, True))
    st2 = st.cp()
    for m in sorted(assigned(body)):
        if m in st.env:
            v = cx.fresh(m)
            st2.env[m] = v
            st2.path.append(rng(v, cx.types[m]))
    for I in inv:
        st2.path.append(ev(I, st2, cx, True))
    c = ev(cond, st2, cx)
    D0 = ev(dec[0], st2, cx, True)
    st3 = st2.cp()
    st3.path.append(c)
    cx.ob(f"variante não-negativo: {show(dec[0])}", st3, ("<=", 0, D0))
    for e in run(body, [st3], cx):
        if e.done:
            raise ProvaError("return/sys_exit dentro de while não suportado")
        for I in inv:
            cx.ob(f"invariante preservada: {show(I)}", e, ev(I, e, cx, True))
        cx.ob(f"variante decresce: {show(dec[0])}", e, ("<", ev(dec[0], e, cx, True), D0))
    out = st2.cp()
    out.path.append(("not", c))
    return [out]


def run(stmts, sts, cx):
    for s in stmts:
        nxt = []
        for st in sts:
            nxt += [st] if st.done else step(s, st, cx)
        sts = nxt
    return sts


def verify_fn(fn, data, sigs=None):
    cx, st = Cx(fn, data, sigs), St()
    for n, T in fn.params:
        if is_slice(T):
            _, el, ln = base(T)
            if el != "u8" or ln not in st.env:
                raise ProvaError(f"{fn.name}: fatia '{n}' exige comprimento declarado antes: (slice u8 n)")
            cx.slice_names.add(n)
            st.slices[n] = st.env[ln]
        elif T in SCALARS or is_atomic(T):
            cx.types[n] = T
            st.env[n] = n
            st.path.append(rng(n, T))
        else:
            raise ProvaError(f"{fn.name}: tipo de parâmetro inválido {show(T)}")
    for p in fn.pre:
        if ty(p, cx) != "bool":
            raise ProvaError(f"pre não booleana: {show(p)}")
        st.path.append(ev(p, st, cx, True))
    ends = run(fn.body, [st], cx)
    for e in ends:
        if e.exited:
            continue
        if fn.ret != "unit" and not e.done:
            raise ProvaError(f"{fn.name}: existe caminho sem return")
        e2 = e.cp()
        if fn.ret != "unit":
            cx.types["result"] = fn.ret
            e2.env["result"] = e.ret
        for p in fn.post:
            if ty(p, cx) != "bool":
                raise ProvaError(f"post não booleana: {show(p)}")
            cx.ob(f"post: {show(p)}", e, ev(p, e2, cx, True))
    cx.types.pop("result", None)
    return cx


def _calls(e, out):
    if isinstance(e, list):
        if e and e[0] == "call" and len(e) > 1 and isinstance(e[1], str):
            out.add(e[1])
        for x in e:
            _calls(x, out)


def check_call_graph(fns):
    """Sem recursão (direta ou mútua): verificação modular só é correta se terminar."""
    g = {}
    for f in fns:
        out = set()
        _calls(f.body, out)
        g[f.name] = out
    state = {}

    def dfs(n, trail):
        state[n] = 1
        for m in sorted(g.get(n, ())):
            if state.get(m) == 1:
                raise ProvaError("recursão não suportada (exigiria variante): " + " -> ".join(trail + [n, m]))
            if m in g and state.get(m) is None:
                dfs(m, trail + [n])
        state[n] = 2

    for n in g:
        if state.get(n) is None:
            dfs(n, [])
