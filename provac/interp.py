"""Interpretador de referência da Prova.

NÃO é um backend: não gera código nativo. Serve para (1) EXECUTAR programas Prova onde não há LLVM e
(2) validar o verificador: confere em tempo de execução tudo que ele prometeu (pre, post, invariantes,
variante decrescente, limites, overflow, shifts, ordem das syscalls). Se um programa verificado violar algo aqui,
o bug é do verificador (ou do interpretador): é um teste diferencial."""
import random

from .check import (ARITH, BIT_OPS, CMP, HI, LO, MMIO_OPS, SHIFT_OPS, WIDTH, WRAP_OPS,
                    ProvaError, is_slice, show, slice_parts, ty)

FUEL = 5_000_000


class RunError(Exception):
    """Violação em tempo de execução (overflow, fora dos limites, contrato, invariante...)."""


class Inconclusive(RunError):
    """A execução gastou todo o combustível (passos/iterações). NÃO é violação: é só lenta demais para o teste."""


class Exit(Exception):
    def __init__(self, code):
        self.code = code


class Ret(Exception):
    def __init__(self, value):
        self.value = value


class Slice:
    def __init__(self, data):
        self.data = bytearray(data)


class Frame:
    def __init__(self, fn, cx):
        self.fn, self.cx, self.env, self.slices = fn, cx, {}, {}
        self.env0, self.slices0 = {}, {}


class Result:
    def __init__(self, exit_code, out, err, statics, returned, mmios=None):
        self.exit_code, self.stdout, self.stderr = exit_code, out, err
        self.statics, self.returned, self.mmios = statics, returned, mmios or {}


class Machine:
    def __init__(self, P, check=True, fuel=FUEL):
        self.P, self.check, self.fuel = P, check, fuel
        self.cx = {fn.name: cx for fn, cx in P.compiled}
        self.out, self.err = bytearray(), bytearray()
        self.statics = dict(P.meta["static_init"])
        self.mmios = {k: 0 for k in P.meta.get("mmios", {})}
        self.steps = 0

    def _wrap(self, v, T):
        if T == "u8":
            return v % 256
        if T == "usize":
            return v % (2**64)
        return (v + 2**63) % (2**64) - 2**63

    # ---------- contratos (inteiros matemáticos, sem faixa) ----------
    def gh(self, e, F, result=None, in_old=False):
        if isinstance(e, int):
            return e
        if isinstance(e, str):
            if e == "result":
                return result
            return F.env0[e] if (in_old and e in F.env0) else F.env[e]
        op = e[0]
        if op in ARITH:
            a, b = self.gh(e[1], F, result, in_old), self.gh(e[2], F, result, in_old)
            return a + b if op == "+" else a - b if op == "-" else a * b
        if op in WRAP_OPS:
            T = ty(e, F.cx) or "usize"
            a, b = self.gh(e[1], F, result, in_old), self.gh(e[2], F, result, in_old)
            return self._wrap(a + b if op == "add_wrap" else a - b, T)
        if op in BIT_OPS:
            a, b = self.gh(e[1], F, result, in_old), self.gh(e[2], F, result, in_old)
            return (a & b) if op == "bit_and" else (a | b) if op == "bit_or" else (a ^ b)
        if op in SHIFT_OPS:
            a, b = self.gh(e[1], F, result, in_old), self.gh(e[2], F, result, in_old)
            return (a << b) if op == "shl" else (a >> b)
        if op in CMP:
            a, b = self.gh(e[1], F, result, in_old), self.gh(e[2], F, result, in_old)
            return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b, "=": a == b, "!=": a != b}[op]
        if op == "and":
            return all(self.gh(x, F, result, in_old) for x in e[1:])
        if op == "or":
            return any(self.gh(x, F, result, in_old) for x in e[1:])
        if op == "not":
            return not self.gh(e[1], F, result, in_old)
        if op == "len":
            buf = F.slices0[e[1]] if (in_old and e[1] in F.slices0) else F.slices[e[1]].data
            return len(buf)
        if op == "load":
            b = e[1]
            i = self.gh(e[2], F, result, in_old)
            buf = F.slices0[b] if (in_old and b in F.slices0) else F.slices[b].data
            if not 0 <= i < len(buf):
                raise RunError(f"leitura fora dos limites em contrato: {show(e)} com índice {i} e tamanho {len(buf)}")
            return buf[i]
        if op == "occ":
            b = e[1]
            val = self.gh(e[2], F, result, in_old)
            buf = F.slices0[b] if (in_old and b in F.slices0) else F.slices[b].data
            return buf.count(val) if 0 <= val <= 255 else 0
        if op == "old":
            return self.gh(e[1], F, result, True)
        if op == "forall":
            _, var, lo_e, hi_e, body = e
            lo = self.gh(lo_e, F, result, in_old)
            hi = self.gh(hi_e, F, result, in_old)
            if hi - lo > self.fuel:
                raise Inconclusive("intervalo de forall excede o combustível")
            saved = F.env.get(var)
            try:
                for k in range(lo, hi):
                    self.steps += 1
                    if self.steps > self.fuel * 4:
                        raise Inconclusive("limite de passos excedido em forall")
                    F.env[var] = k
                    if not self.gh(body, F, result, in_old):
                        return False
                return True
            finally:
                if saved is None:
                    F.env.pop(var, None)
                else:
                    F.env[var] = saved
        if op == "cast":
            return self.gh(e[2], F, result, in_old)
        raise RunError(f"forma não avaliável em contrato: {show(e)}")

    def need(self, cond, what):
        if self.check and not cond:
            raise RunError(what)

    # ---------- expressões ----------
    def fit(self, v, T, what):
        if not LO[T] <= v <= HI[T]:
            raise RunError(f"{what}: {v} fora da faixa de {T}")
        return v

    def ex(self, e, F, want=None):
        if isinstance(e, int):
            return e
        if isinstance(e, str):
            return F.env[e]
        op = e[0]
        if op in ARITH:
            T = ty(e, F.cx) or want or "i64"
            a, b = self.ex(e[1], F, T), self.ex(e[2], F, T)
            v = a + b if op == "+" else a - b if op == "-" else a * b
            return self.fit(v, T, f"overflow em {show(e)}")
        if op in WRAP_OPS:
            T = ty(e, F.cx) or want or "usize"
            a = self.fit(self.ex(e[1], F, T), T, f"operando em {show(e)}")
            b = self.fit(self.ex(e[2], F, T), T, f"operando em {show(e)}")
            return self._wrap(a + b if op == "add_wrap" else a - b, T)
        if op in BIT_OPS:
            T = ty(e, F.cx) or want or "usize"
            a = self.fit(self.ex(e[1], F, T), T, f"operando em {show(e)}")
            b = self.fit(self.ex(e[2], F, T), T, f"operando em {show(e)}")
            v = (a & b) if op == "bit_and" else (a | b) if op == "bit_or" else (a ^ b)
            return self._wrap(v, T)
        if op in SHIFT_OPS:
            T = ty(e, F.cx) or want or "usize"
            W = WIDTH[T]
            a = self.fit(self.ex(e[1], F, T), T, f"operando em {show(e)}")
            b = self.fit(self.ex(e[2], F, T), T, f"deslocamento em {show(e)}")
            if not 0 <= b < W:
                raise RunError(f"shift fora da faixa em {show(e)}: deslocamento {b} fora de 0..{W - 1}")
            v = (a << b) if op == "shl" else (a >> b)
            return self._wrap(v, T)
        if op in CMP:
            a, b = self.ex(e[1], F), self.ex(e[2], F)
            return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b, "=": a == b, "!=": a != b}[op]
        if op == "and":
            return all(self.ex(x, F) for x in e[1:])
        if op == "or":
            return any(self.ex(x, F) for x in e[1:])
        if op == "not":
            return not self.ex(e[1], F)
        if op == "len":
            return len(F.slices[e[1]].data)
        if op == "load":
            s, i = F.slices[e[1]], self.ex(e[2], F, "usize")
            if not 0 <= i < len(s.data):
                raise RunError(f"leitura fora dos limites: {show(e)} com índice {i} e tamanho {len(s.data)}")
            return s.data[i]
        if op == "cast":
            return self.fit(self.ex(e[2], F), e[1], f"cast {show(e)}")
        if op == "sys_write":
            fd, s, n = self.ex(e[1], F, "i64"), F.slices[e[2]], self.ex(e[3], F, "usize")
            if not 0 <= n <= len(s.data):
                raise RunError(f"sys_write de {n} bytes excede o buffer de {len(s.data)}")
            if fd == 1:
                self.out += s.data[:n]
            elif fd == 2:
                self.err += s.data[:n]
            else:
                return -9  # EBADF
            return n
        if op == "call":
            g = self.P.sigs[e[1]]
            args = [F.slices[a] if is_slice(PT) else self.ex(a, F, PT) for (_, PT), a in zip(g.params, e[2:])]
            return self.call(g.name, args)
        if op in ("atomic_load", "atomic_store", "atomic_fetch_add", "atomic_cas"):
            return self.atomic(e, F)
        if op in MMIO_OPS:
            return self.mmio_op(e, F)
        raise RunError(f"forma desconhecida: {show(e)}")

    def atomic(self, e, F):
        name = e[1]
        T = self.P.meta["statics"][name]
        old = self.statics[name]
        if e[0] == "atomic_load":
            return old
        if e[0] == "atomic_store":
            self.statics[name] = self.fit(self.ex(e[2], F, T), T, f"atomic_store em {name}")
            return None
        if e[0] == "atomic_fetch_add":
            self.statics[name] = self._wrap(old + self.ex(e[2], F, T), T)
            return old
        exp, new = self.ex(e[2], F, T), self.ex(e[3], F, T)
        if old == exp:
            self.statics[name] = new
        return old

    def mmio_op(self, e, F):
        name = e[1]
        T = self.P.meta["mmios"][name]["type"]
        if e[0] == "mmio_read":
            return self.mmios.get(name, 0)
        self.mmios[name] = self.fit(self.ex(e[2], F, T), T, f"mmio_write em {name}")
        return None

    # ---------- instruções ----------
    def block(self, stmts, F):
        for s in stmts:
            self.stmt(s, F)

    def stmt(self, s, F):
        self.steps += 1
        if self.steps > self.fuel * 4:
            raise Inconclusive("limite de passos excedido")
        h = s[0]
        if h in ("let", "var"):
            F.env[s[1]] = self.fit(self.ex(s[3], F, s[2]), s[2], f"{h} {s[1]}")
        elif h == "set":
            F.env[s[1]] = self.fit(self.ex(s[2], F, F.cx.types[s[1]]), F.cx.types[s[1]], f"set {s[1]}")
        elif h == "let_slice":
            F.slices[s[1]] = Slice(self.P.data[s[2][1]])
            F.slices0.setdefault(s[1], bytes(F.slices[s[1]].data))
        elif h == "store":
            sl, i = F.slices[s[1]], self.ex(s[2], F, "usize")
            if not 0 <= i < len(sl.data):
                raise RunError(f"escrita fora dos limites: {show(s)} com índice {i} e tamanho {len(sl.data)}")
            sl.data[i] = self.fit(self.ex(s[3], F, "u8"), "u8", f"store {show(s)}")
        elif h in ("do", "atomic_store", "mmio_write"):
            self.ex(s[1] if h == "do" else s, F)
        elif h == "assert":
            self.need(self.gh(s[1], F), f"assert falhou: {show(s[1])}")
        elif h == "drop":
            pass
        elif h == "return":
            raise Ret(self.ex(s[1], F, F.fn.ret) if len(s) > 1 else None)
        elif h == "sys_exit":
            raise Exit(self.ex(s[1], F, "i64"))
        elif h == "if":
            branch = "then" if self.ex(s[1], F) else "else"
            for part in s[2:]:
                if part[0] == branch:
                    self.block(part[1:], F)
        elif h == "while":
            self.loop(s, F)
        else:
            raise RunError(f"instrução desconhecida: {show(s)}")

    def loop(self, s, F):
        inv = [x for f in s[2:] if f[0] == "invariant" for x in f[1:]]
        dec = next(f[1] for f in s[2:] if f[0] == "decreases")
        body = [f for f in s[2:] if f[0] not in ("invariant", "decreases")]
        prev = None
        for _ in range(self.fuel):
            for I in inv:
                self.need(self.gh(I, F), f"invariante violada: {show(I)}")
            if not self.ex(s[1], F):
                return
            d = self.gh(dec, F)
            self.need(d >= 0, f"variante negativa: {show(dec)} = {d}")
            self.need(prev is None or d < prev, f"variante não decresceu: {show(dec)} foi {prev} e agora é {d}")
            prev = d
            self.block(body, F)
        raise Inconclusive("laço excedeu o limite de iterações")

    # ---------- chamadas ----------
    def call(self, name, args):
        fn = self.P.sigs[name]
        F = Frame(fn, self.cx[name])
        for (pn, PT), a in zip(fn.params, args):
            if is_slice(PT):
                F.slices[pn] = a
            else:
                F.env[pn] = self.fit(a, PT, f"argumento {pn} de {name}")
        F.env0 = dict(F.env)
        F.slices0 = {k: bytes(v.data) for k, v in F.slices.items()}
        for p in fn.pre:
            self.need(self.gh(p, F), f"pré-condição de {name} violada: {show(p)}")
        ret = None
        try:
            self.block(fn.body, F)
        except Ret as r:
            ret = r.value
        for q in fn.post:
            self.need(self.gh(q, F, ret), f"pós-condição de {name} violada: {show(q)} (result = {ret})")
        return ret


def run(P, entry="_start", args=(), check=True):
    """Executa `entry`. Retorna Result; levanta RunError se o programa violar algo."""
    if entry not in P.sigs:
        raise ProvaError(f"função de entrada '{entry}' não existe")
    m = Machine(P, check)
    code = ret = None
    try:
        ret = m.call(entry, list(args))
        code = 0
    except Exit as e:
        code = e.code
    return Result(code, bytes(m.out), bytes(m.err), dict(m.statics), ret, dict(m.mmios)), m


# ---------- teste diferencial: entradas aleatórias que satisfazem a pre ----------
SCALAR_POOL = [0, 1, 2, 3, 5, 8, 10, 50, 100, 255, 256, 999, 1000, 4096, 4097, 65535]
SMALL_POOL = [0, 1, 2, 3, 5, 8, 10, 21, 48, 50, 100]   # a maioria das entradas é pequena: laços terminam rápido
FUZZ_FUEL = 5_000                                      # combustível curto: execução longa = inconclusivo, não falha


def gen_args(fn, rnd):
    lens = {slice_parts(T)[0] for _, T in fn.params if is_slice(T)}
    args, vals = [], {}
    for pn, T in fn.params:
        if is_slice(T):
            n = vals[slice_parts(T)[0]]
            args.append(Slice(bytes(rnd.randrange(256) for _ in range(n))))
        else:
            if pn in lens:
                v = rnd.choice([0, 1, 2, 3, 4, 7, 16, 33, 64, 100])
            elif rnd.random() < 0.6:
                v = max(LO[T], min(HI[T], rnd.choice(SMALL_POOL)))
            else:
                pool = SCALAR_POOL + [rnd.randrange(LO[T] if T != "i64" else -2**63, HI[T] + 1) % (HI[T] + 1)
                                       if T != "i64" else rnd.randrange(-2**63, 2**63)]
                if T == "i64":
                    pool += [-1, -2, 2**63 - 1, -2**63]
                v = rnd.choice(pool)
                if not LO[T] <= v <= HI[T]:
                    v = max(LO[T], min(HI[T], v))
            vals[pn] = v
            args.append(v)
    return args


def fuzz_function(P, name, runs=400, seed=1):
    """Chama `name` com entradas aleatórias; só conta as que satisfazem a pre e terminam dentro do combustível
    (execução longa demais é inconclusiva, não violação). Retorna (executadas, violações)."""
    fn, rnd = P.sigs[name], random.Random(seed)
    executed, violations = 0, []
    for _ in range(runs):
        args = gen_args(fn, rnd)
        m = Machine(P, check=True, fuel=FUZZ_FUEL)
        F = Frame(fn, m.cx[name])
        for (pn, PT), a in zip(fn.params, args):
            (F.slices if is_slice(PT) else F.env)[pn] = a
        F.env0 = dict(F.env)
        F.slices0 = {k: bytes(v.data) for k, v in F.slices.items()}
        try:
            if not all(m.gh(p, F) for p in fn.pre):
                continue
        except (RunError, KeyError):
            continue
        try:
            m.call(name, args)
            executed += 1
        except Exit:
            executed += 1
        except Inconclusive:
            continue
        except RunError as e:
            executed += 1
            violations.append((args if not any(isinstance(a, Slice) for a in args)
                               else [a if not isinstance(a, Slice) else bytes(a.data) for a in args], str(e)))
    return executed, violations
