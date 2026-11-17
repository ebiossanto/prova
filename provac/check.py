"""Tipos estritos + geração de condições de verificação (VCs) por execução simbólica.

Cada obrigação é (rótulo, hipóteses, objetivo): hipóteses => objetivo deve ser válido.
Termos: int | str (símbolo) | tupla (op, args...). Contratos usam inteiros matemáticos
(sem overflow); o código executável tem overflow e limites de shift checados por obrigação.
"""
from . import linarith
from .sexp import Str

LO = {"i64": -2**63, "usize": 0, "u8": 0}
HI = {"i64": 2**63 - 1, "usize": 2**64 - 1, "u8": 255}
WIDTH = {"i64": 64, "usize": 64, "u8": 8}
SCALARS = ("i64", "usize", "u8")
ARITH = ("+", "-", "*")
WRAP_OPS = ("add_wrap", "sub_wrap")
BIT_OPS = ("bit_and", "bit_or", "bit_xor")
SHIFT_OPS = ("shl", "shr")
BIN_INT_OPS = ARITH + WRAP_OPS + BIT_OPS + SHIFT_OPS
CMP = ("<", "<=", ">", ">=", "=", "!=")
EFFECTS = ("syscall", "atomic", "mmio")
ORDERS = ("relaxed", "acquire", "release", "acq_rel", "seq_cst")
ATOMIC_T = ("i64", "usize")  # tipos permitidos em (static nome (atomic T) init)
ATOMIC_OPS = ("atomic_load", "atomic_store", "atomic_fetch_add", "atomic_cas")
MMIO_OPS = ("mmio_read", "mmio_write")
LOAD_ORD = ("relaxed", "acquire", "seq_cst")
STORE_ORD = ("relaxed", "release", "seq_cst")
FAIL_ORD = ("relaxed", "acquire", "seq_cst")
# falha do cas não pode ser mais forte que o sucesso
STRONGER_OK = {"relaxed": ORDERS, "acquire": ("acquire", "acq_rel", "seq_cst"), "seq_cst": ("seq_cst",)}


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


def slice_parts(T):
    """(comprimento, região|None) de (slice u8 n [região]) ou (own (slice u8 n [região]))."""
    B = base(T)
    if len(B) not in (3, 4) or B[1] != "u8":
        raise ProvaError(f"tipo de fatia inválido: {show(T)} (esperado (slice u8 n [região]))")
    return B[2], (B[3] if len(B) == 4 else None)


class Fn:
    def __init__(self, form):
        self.name = form[1]
        self.params, self.ret = [], "unit"
        self.pre, self.post, self.body = [], [], []
        self.has_pre = self.has_post = False
        self.effects, self.budget = set(), None
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
            elif h == "effects":
                bad = [x for x in c[1:] if x not in EFFECTS]
                if bad:
                    raise ProvaError(f"{self.name}: efeito desconhecido {bad} (válidos: {list(EFFECTS)})")
                self.effects |= set(c[1:])
            elif h == "stack-budget":
                if len(c) != 2 or not isinstance(c[1], int) or c[1] <= 0:
                    raise ProvaError(f"{self.name}: (stack-budget N) exige um inteiro positivo de bytes")
                self.budget = c[1]
            else:
                raise ProvaError(f"{self.name}: cláusula desconhecida '{h}'")
        if not (self.has_pre and self.has_post):
            raise ProvaError(f"{self.name}: toda função exige (pre ...) e (post ...), mesmo vazios")


class St:
    def __init__(self):
        self.env, self.path, self.slices = {}, [], {}
        self.arr, self.arr0, self.env0 = {}, {}, {}
        self.ret, self.done, self.exited = None, False, False

    def cp(self):
        n = St()
        n.env, n.path, n.slices = dict(self.env), list(self.path), dict(self.slices)
        n.arr, n.arr0, n.env0 = dict(self.arr), dict(self.arr0), dict(self.env0)
        n.ret, n.done, n.exited = self.ret, self.done, self.exited
        return n


class Cx:
    def __init__(self, fn, data, sigs=None, meta=None):
        self.fn, self.data, self.sigs = fn, data, sigs or {}
        self.meta = meta or {"regions": {"rodata"}, "data_region": {}, "statics": {}, "mmios": {}}
        self.types, self.mut, self.slice_names = {}, set(), set()
        self.slice_region = {}  # nome da fatia -> região declarada (None = sem região)
        self.readonly = set()   # fatias vindas de (data ...): memória somente-leitura
        self.decl = {}          # variável -> id do comando que a declarou
        self.obs, self.k = [], 0
        self.pre_contradictory = False

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
    if op in BIN_INT_OPS or op in CMP:
        if len(e) != 3:
            raise ProvaError(f"{op} é binário: {show(e)}")
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
        if len(e) != 2 or not isinstance(e[1], str) or e[1] not in cx.slice_names:
            raise ProvaError(f"len espera uma fatia: {show(e)}")
        return "usize"
    if op == "load":
        if len(e) != 3:
            raise ProvaError(f"load espera (load fatia indice): {show(e)}")
        if not isinstance(e[1], str) or e[1] not in cx.slice_names:
            raise ProvaError(f"{show(e[1])} não é uma fatia em {show(e)}")
        if ty(e[2], cx) not in (None, "usize"):
            raise ProvaError(f"índice de fatia deve ser usize: {show(e)}; use (cast usize ...)")
        return "u8"
    if op == "old":
        if len(e) != 2:
            raise ProvaError(f"old espera (old expr): {show(e)}")
        return ty(e[1], cx)
    if op == "forall":
        if len(e) != 5 or not isinstance(e[1], str):
            raise ProvaError(f"forall espera (forall var inicio fim condicao): {show(e)}")
        var, lo, hi, body = e[1], e[2], e[3], e[4]
        if var in cx.types or var in cx.slice_names or var == "result":
            raise ProvaError(f"variável quantificada '{var}' sombreia nome existente em {show(e)}")
        if ty(lo, cx) not in (None, "usize") or ty(hi, cx) not in (None, "usize"):
            raise ProvaError(f"limites de forall devem ser usize em {show(e)}")
        cx.types[var] = "usize"
        try:
            if ty(body, cx) != "bool":
                raise ProvaError(f"corpo de forall deve ser booleano: {show(e)}")
        finally:
            cx.types.pop(var, None)
        return "bool"
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
                if not isinstance(a, str) or a not in cx.slice_names:
                    raise ProvaError(f"{g.name}: argumento '{pn}' exige uma fatia, recebeu {show(a)}")
                want_r, have_r = slice_parts(PT)[1], cx.slice_region.get(a)
                if want_r is not None and have_r != want_r:
                    raise ProvaError(f"{g.name}: região incompatível em '{pn}': exige {want_r}, '{a}' está em "
                                     f"{have_r or 'nenhuma região'}")
            else:
                ta = ty(a, cx)
                if ta not in (None, PT):
                    raise ProvaError(f"{g.name}: argumento '{pn}' é {PT}, recebeu {ta}; use (cast {PT} ...)")
        return g.ret
    if op in ATOMIC_OPS:
        return atomic_ty(e, cx)
    if op in MMIO_OPS:
        return mmio_ty(e, cx)
    raise ProvaError(f"forma desconhecida: {show(e)}")


def static_type(name, cx):
    if not isinstance(name, str) or name not in cx.meta["statics"]:
        raise ProvaError(f"'{show(name)}' não é um (static ...) atômico declarado")
    return cx.meta["statics"][name]


def mmio_info(name, cx):
    mmios = cx.meta.get("mmios", {})
    if not isinstance(name, str) or name not in mmios:
        raise ProvaError(f"'{show(name)}' não é um registrador (mmio ...) declarado")
    return mmios[name]


def mmio_ty(e, cx):
    op = e[0]
    if op == "mmio_read":
        if len(e) != 2:
            raise ProvaError(f"mmio_read espera (mmio_read reg): {show(e)}")
        return mmio_info(e[1], cx)["type"]
    if len(e) != 3:
        raise ProvaError(f"mmio_write espera (mmio_write reg valor): {show(e)}")
    T = mmio_info(e[1], cx)["type"]
    tv = ty(e[2], cx)
    if tv not in (None, T):
        raise ProvaError(f"mmio_write em '{e[1]}' ({T}) recebeu {tv}: {show(e)}; use (cast {T} ...)")
    return "unit"


def check_order(e, o, allowed, what):
    if o not in ORDERS:
        raise ProvaError(f"ordem de memória desconhecida '{show(o)}' em {show(e)} (válidas: {list(ORDERS)})")
    if o not in allowed:
        raise ProvaError(f"ordem '{o}' é ilegal em {what}: use uma de {list(allowed)} em {show(e)}")


def atomic_vals(e):
    """Operandos de valor de uma operação atômica (sem a célula e sem as ordens)."""
    n = {"atomic_load": 0, "atomic_store": 1, "atomic_fetch_add": 1, "atomic_cas": 2}[e[0]]
    return list(e[2:2 + n])


def atomic_ty(e, cx):
    op = e[0]
    n_args = {"atomic_load": 3, "atomic_store": 4, "atomic_fetch_add": 4, "atomic_cas": 6}[op]
    if len(e) != n_args:
        raise ProvaError(f"aridade inválida em {show(e)}")
    T = static_type(e[1], cx)
    for v in atomic_vals(e):
        tv = ty(v, cx)
        if tv not in (None, T):
            raise ProvaError(f"{op} em '{e[1]}' ({T}) recebeu {tv}: {show(e)}; use (cast {T} ...)")
    if op == "atomic_load":
        check_order(e, e[2], LOAD_ORD, "atomic_load")
        return T
    if op == "atomic_store":
        check_order(e, e[3], STORE_ORD, "atomic_store")
        return "unit"
    if op == "atomic_fetch_add":
        check_order(e, e[3], ORDERS, "atomic_fetch_add")
        return T
    check_order(e, e[4], ORDERS, "atomic_cas (sucesso)")
    check_order(e, e[5], FAIL_ORD, "atomic_cas (falha)")
    if e[4] not in STRONGER_OK[e[5]]:
        raise ProvaError(f"atomic_cas: a ordem de falha '{e[5]}' é mais forte que a de sucesso '{e[4]}': {show(e)}")
    return T


def slice_len(b, st, cx):
    if not isinstance(b, str) or b not in cx.slice_names:
        raise ProvaError(f"{show(b)} não é uma fatia")
    if b not in st.slices:
        raise ProvaError(f"fatia '{b}' não está definida em todos os caminhos até aqui")
    return st.slices[b]


def arg_range(cx, st, a, t, T):
    """Literais e expressões não-aritméticas passados a um tipo T precisam caber em T."""
    if isinstance(a, str) or (isinstance(a, list) and a[0] in BIN_INT_OPS):
        return  # variável do mesmo tipo (garantida pelo tipo) ou operação já checada
    cx.ob(f"argumento cabe em {T}: {show(a)}", st, rng(t, T))


def ev(e, st, cx, ghost=False, want=None, in_old=False):
    """Avalia simbolicamente. ghost=True: aritmética matemática (contratos)."""
    if isinstance(e, int):
        return e
    if isinstance(e, str):
        ty(e, cx)
        env = st.env0 if (in_old and e in st.env0) else st.env
        if e not in env:
            raise ProvaError(f"variável sem valor: {e}")
        return env[e]
    op = e[0]
    if op in ARITH:
        if len(e) != 3:
            raise ProvaError(f"{op} é binário: {show(e)}")
        T = ty(e, cx) or want or "i64"
        t = (op, ev(e[1], st, cx, ghost, T, in_old), ev(e[2], st, cx, ghost, T, in_old))
        if not ghost:
            cx.ob(f"overflow: {show(e)} cabe em {T}", st, rng(t, T))
        return t
    if op in WRAP_OPS:
        if len(e) != 3:
            raise ProvaError(f"{op} é binário: {show(e)}")
        T = ty(e, cx) or want or "usize"
        a_t = ev(e[1], st, cx, ghost, T, in_old)
        b_t = ev(e[2], st, cx, ghost, T, in_old)
        arg_range(cx, st, e[1], a_t, T)
        arg_range(cx, st, e[2], b_t, T)
        if isinstance(a_t, int) and isinstance(b_t, int) and T in ("usize", "u8"):
            mod = HI[T] + 1
            return (a_t + b_t) % mod if op == "add_wrap" else (a_t - b_t) % mod
        r = cx.fresh("wrap")
        st.path.append(rng(r, T))
        return r
    if op in BIT_OPS:
        if len(e) != 3:
            raise ProvaError(f"{op} é binário: {show(e)}")
        T = ty(e, cx) or want or "usize"
        a_t = ev(e[1], st, cx, ghost, T, in_old)
        b_t = ev(e[2], st, cx, ghost, T, in_old)
        if not ghost:
            arg_range(cx, st, e[1], a_t, T)
            arg_range(cx, st, e[2], b_t, T)
        if isinstance(a_t, int) and isinstance(b_t, int):
            return a_t & b_t if op == "bit_and" else a_t | b_t if op == "bit_or" else a_t ^ b_t
        if ghost:
            return (op, a_t, b_t)
        r = cx.fresh("bit")
        st.path.append(rng(r, T))
        if op == "bit_and" and T in ("usize", "u8"):
            st.path.append(("<=", r, a_t))
            st.path.append(("<=", r, b_t))
        st.path.append(("=", r, (op, a_t, b_t)))
        return r
    if op in SHIFT_OPS:
        if len(e) != 3:
            raise ProvaError(f"{op} é binário: {show(e)}")
        T = ty(e, cx) or want or "usize"
        W = WIDTH[T]
        a_t = ev(e[1], st, cx, ghost, T, in_old)
        b_t = ev(e[2], st, cx, ghost, T, in_old)
        if not ghost:
            arg_range(cx, st, e[1], a_t, T)
            cx.ob(f"shift: {show(e)} exige 0 <= deslocamento < {W}", st, ("and", ("<=", 0, b_t), ("<", b_t, W)))
        if isinstance(a_t, int) and isinstance(b_t, int) and 0 <= b_t < W:
            val = (a_t << b_t) if op == "shl" else (a_t >> b_t)
            if LO[T] <= val <= HI[T]:
                return val
        if ghost:
            return (op, a_t, b_t)
        r = cx.fresh("sh")
        st.path.append(rng(r, T))
        if op == "shr" and T in ("usize", "u8"):
            st.path.append(("<=", r, a_t))
        return r
    if op in CMP:
        ty(e, cx)
        return (op, ev(e[1], st, cx, ghost, None, in_old), ev(e[2], st, cx, ghost, None, in_old))
    if op in ("and", "or"):
        ts = [ev(a, st, cx, ghost, None, in_old) for a in e[1:]]
        out = ts[0]
        for t in ts[1:]:
            out = (op, out, t)
        return out
    if op == "not":
        return ("not", ev(e[1], st, cx, ghost, None, in_old))
    if op == "len":
        return slice_len(e[1], st, cx)
    if op == "old":
        if not ghost:
            raise ProvaError(f"old só é permitido em contratos/invariantes/assert: {show(e)}")
        return ev(e[1], st, cx, True, want, True)
    if op == "forall":
        if not ghost:
            raise ProvaError(f"forall só é permitido em contratos/invariantes/assert: {show(e)}")
        ty(e, cx)
        _, var, lo_e, hi_e, body = e
        lo_t = ev(lo_e, st, cx, True, "usize", in_old)
        hi_t = ev(hi_e, st, cx, True, "usize", in_old)
        cx.types[var] = "usize"
        st.env[var] = var
        try:
            body_t = ev(body, st, cx, True, "bool", in_old)
        finally:
            cx.types.pop(var, None)
            st.env.pop(var, None)
        return ("forall", var, lo_t, hi_t, body_t)
    if op == "load":
        L = slice_len(e[1], st, cx)
        i = ev(e[2], st, cx, ghost, "usize", in_old)
        arr = st.arr0[e[1]] if in_old else st.arr[e[1]]
        sel = ("select", arr, i)
        if ghost:
            return sel
        cx.ob(f"limites: {show(e)}", st, ("and", ("<=", 0, i), ("<", i, L)))
        v = cx.fresh("ld")
        st.path.append(rng(v, "u8"))
        st.path.append(("=", v, sel))
        return v
    if op == "cast":
        T = e[1]
        if T not in SCALARS:
            raise ProvaError(f"cast para tipo inválido: {T}")
        t = ev(e[2], st, cx, ghost, None, in_old)
        if not ghost:
            cx.ob(f"cast: {show(e)} cabe em {T}", st, rng(t, T))
        return t
    if op == "sys_write":
        ty(e, cx)
        fd, buf, n = e[1], e[2], e[3]
        fdt = ev(fd, st, cx, ghost, "i64", in_old)
        arg_range(cx, st, fd, fdt, "i64")
        L = slice_len(buf, st, cx)
        nt = ev(n, st, cx, ghost, "usize", in_old)
        cx.ob(f"syscall write: contagem <= len({buf})", st, ("and", ("<=", 0, nt), ("<=", nt, L)))
        return cx.fresh("sys")
    if op == "call":
        if ghost:
            raise ProvaError("chamada em contrato não suportada")
        return do_call(e, st, cx)
    if op in ATOMIC_OPS:
        if ghost:
            raise ProvaError("operação atômica em contrato não suportada (o valor depende de outras threads)")
        atomic_ty(e, cx)  # valida aridade, tipos e ordens
        T = static_type(e[1], cx)
        for v in atomic_vals(e):
            arg_range(cx, st, v, ev(v, st, cx, False, T), T)
        if op == "atomic_store":
            return 0
        r = cx.fresh("atm")  # valor lido: qualquer valor do tipo (outras threads podem ter escrito)
        st.path.append(rng(r, T))
        return r
    if op in MMIO_OPS:
        if ghost:
            raise ProvaError("operação mmio em contrato não suportada (registrador de hardware é volátil)")
        mmio_ty(e, cx)
        T = mmio_info(e[1], cx)["type"]
        if op == "mmio_write":
            vt = ev(e[2], st, cx, False, T)
            arg_range(cx, st, e[2], vt, T)
            return 0
        r = cx.fresh("mmio")
        st.path.append(rng(r, T))
        return r
    raise ProvaError(f"forma desconhecida: {show(e)}")


def do_call(e, st, cx):
    """Verificação modular: pre do chamado vira obrigação; post vira hipótese."""
    ty(e, cx)  # valida aridade e tipos
    g = cx.sigs[e[1]]
    cc = Cx(g, cx.data, cx.sigs, cx.meta)
    tmp = St()
    gm = written_slices(g.body, cx.sigs)
    for (pn, PT), a in zip(g.params, e[2:]):
        if is_slice(PT):
            ln = base(PT)[2]
            cx.ob(f"chamada {g.name}: len({a}) = {ln}", st, ("=", st.slices[a], tmp.env[ln]))
            cc.slice_names.add(pn)
            tmp.slices[pn] = st.slices[a]
            tmp.arr[pn] = st.arr[a]
            tmp.arr0[pn] = st.arr[a]
        else:
            tmp.env[pn] = ev(a, st, cx, False, PT)
            tmp.env0[pn] = tmp.env[pn]
            arg_range(cx, st, a, tmp.env[pn], PT)
            cc.types[pn] = PT
    for p in g.pre:
        cx.ob(f"chamada {g.name}: pre {show(p)}", st, ev(p, tmp, cc, True))
    for (pn, PT), a in zip(g.params, e[2:]):
        if is_slice(PT) and pn in gm:
            new_a = cx.fresh(f"arr!{a}")
            st.arr[a] = new_a
            tmp.arr[pn] = new_a
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


def declare(cx, x, T, mut, node):
    """Declara x. O MESMO comando executado em outro caminho (depois de um `if` que bifurcou estados) não é
    redeclaração; outro comando com o mesmo nome é (sem sombreamento)."""
    if x in cx.types and cx.decl.get(x) == id(node) and cx.types[x] == T:
        return
    if x in cx.types or x in cx.slice_names or x == "result":
        raise ProvaError(f"redeclaração de '{x}' (sem sombreamento)")
    if T not in SCALARS:
        raise ProvaError(f"tipo inválido para variável: {show(T)}")
    cx.types[x] = T
    cx.decl[x] = id(node)
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


def _call_nodes(e, out):
    if isinstance(e, list):
        if e and e[0] == "call" and len(e) > 1 and isinstance(e[1], str):
            out.append(e)
        for x in e:
            _call_nodes(x, out)


def written_slices(stmts, sigs=None):
    out = set()
    for s in stmts:
        if not isinstance(s, list) or not s:
            continue
        if s[0] == "store" and len(s) > 1:
            out.add(s[1])
        elif s[0] == "if":
            for part in s[2:]:
                out |= written_slices(part[1:], sigs)
        elif s[0] == "while":
            out |= written_slices([f for f in s[2:] if isinstance(f, list) and f[0] not in ("invariant", "decreases")], sigs)
        else:
            calls = []
            _call_nodes(s, calls)
            for c in calls:
                g = (sigs or {}).get(c[1])
                if g is not None:
                    gm = written_slices(g.body, sigs)
                    for (pn, _), a in zip(g.params, c[2:]):
                        if pn in gm and isinstance(a, str):
                            out.add(a)
    return out


def assign_check(cx, st, e, T):
    tt = ty(e, cx)
    if tt and tt != T:
        raise ProvaError(f"tipo {tt} atribuído a {T} em {show(e)}; use (cast {T} ...)")
    t = ev(e, st, cx, False, T)
    if not (isinstance(e, list) and e[0] in BIN_INT_OPS):
        cx.ob(f"valor cabe em {T}: {show(e)}", st, rng(t, T))
    return t


def step(s, st, cx):
    h = s[0]
    if h in ("let", "var"):
        _, x, T, e = s
        declare(cx, x, T, h == "var", s)
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
        cx.slice_region[b] = cx.meta["data_region"].get(src[1], "rodata")
        cx.readonly.add(b)
        st.slices[b] = cx.data[src[1]]
        st.arr[b] = f"arr0!{b}"
        st.arr0.setdefault(b, f"arr0!{b}")
        return [st]
    if h == "store":
        _, b, i, v = s
        L = slice_len(b, st, cx)
        if b in cx.readonly:
            raise ProvaError(f"escrita em fatia somente-leitura '{b}' (vem de data): {show(s)}")
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
        st.arr[b] = ("store_arr", st.arr[b], it, vt)
        return [st]
    if h == "assert":
        if ty(s[1], cx) != "bool":
            raise ProvaError(f"assert não booleano: {show(s[1])}")
        cx.ob(f"assert: {show(s[1])}", st, ev(s[1], st, cx, True))
        return [st]
    if h == "do":
        ev(s[1], st, cx)
        return [st]
    if h in ("atomic_store", "mmio_write"):
        ev(s, st, cx)
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
    for m in sorted(written_slices(body, cx.sigs)):
        if m in st.arr:
            st2.arr[m] = cx.fresh(f"arr!{m}")
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


def verify_fn(fn, data, sigs=None, meta=None):
    cx, st = Cx(fn, data, sigs, meta), St()
    for n, T in fn.params:
        if is_slice(T):
            ln, region = slice_parts(T)
            if ln not in st.env:
                raise ProvaError(f"{fn.name}: fatia '{n}' exige comprimento declarado antes: (slice u8 n)")
            if region is not None and region not in cx.meta["regions"]:
                raise ProvaError(f"{fn.name}: região '{region}' não declarada (use (region {region}))")
            cx.slice_names.add(n)
            cx.slice_region[n] = region
            st.slices[n] = st.env[ln]
            st.arr[n] = f"arr0!{n}"
            st.arr0[n] = f"arr0!{n}"
        elif T in SCALARS:
            cx.types[n] = T
            st.env[n] = n
            st.env0[n] = n
            st.path.append(rng(n, T))
        else:
            raise ProvaError(f"{fn.name}: tipo de parâmetro inválido {show(T)}")
    for p in fn.pre:
        if ty(p, cx) != "bool":
            raise ProvaError(f"pre não booleana: {show(p)}")
        st.path.append(ev(p, st, cx, True))
    cx.pre_contradictory = linarith.contradictory(st.path)
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
