"""Fluxo de dados por região (abordagem 3 da ideia original): mostra por onde um dado entra e onde toca a memória,
e aplica políticas (deny-flow A B). Só fluxo EXPLÍCITO de valores (load/mmio → variável → store/syscall/atômico/mmio);
fluxo implícito por controle (if/while) e vazamento por comprimento NÃO são rastreados.

Rótulos: região concreta ("net-rx"), sumidouro "@write", célula "@static:NOME", registrador "@mmio:NOME",
ou ("p", i) = região/valor do parâmetro i (para funções genéricas). Resumos por função são instanciados em cada chamada."""
from .check import ATOMIC_OPS, BIN_INT_OPS, CMP, MMIO_OPS, atomic_vals, is_slice, slice_parts

SINK = "@write"


def topo(fns):
    by = {f.name: f for f in fns}
    seen, order = set(), []
    from .effects import direct

    def go(n):
        if n in seen:
            return
        seen.add(n)
        for c in sorted(direct(by[n])[1]):
            go(c)
        order.append(by[n])
    for f in fns:
        go(f.name)
    return order


def _subst(lab, sigma):
    return set(sigma.get(lab[1], set())) if isinstance(lab, tuple) else {lab}


class Summary:
    def __init__(self, flows, ret):
        self.flows, self.ret = flows, ret


def analyse_fn(fn, sigs, summaries, meta):
    label, taint = {}, {}
    for i, (n, T) in enumerate(fn.params):
        if is_slice(T):
            r = slice_parts(T)[1]
            label[n] = r if r else ("p", i)
        else:
            taint[n] = {("p", i)}

    def prescan(n):
        if isinstance(n, list):
            if n and n[0] == "let_slice":
                label[n[1]] = meta["data_region"].get(n[2][1], "rodata")
            for x in n:
                prescan(x)
    prescan(fn.body)
    flows, ret = set(), set()

    def link(srcs, dst):
        for s in srcs:
            if s != dst:
                flows.add((s, dst))

    def atomic(e):
        cell = "@static:" + e[1]
        for v in atomic_vals(e):
            link(tx(v), cell)
        return set() if e[0] == "atomic_store" else {cell}

    def mmio(e):
        reg = e[1]
        info = meta.get("mmios", {}).get(reg, {})
        r = info.get("region")
        ep = "@mmio:" + reg
        if e[0] == "mmio_write":
            srcs = tx(e[2])
            if r:
                link(srcs, r)
            link(srcs, ep)
            return set()
        return ({r, ep} if r else {ep})

    def call(e):
        g = sigs[e[1]]
        sigma = {}
        for i, ((_, PT), a) in enumerate(zip(g.params, e[2:])):
            sigma[i] = {label[a]} if is_slice(PT) else tx(a)
        sm = summaries[g.name]
        for (s, d) in sm.flows:
            for s2 in _subst(s, sigma):
                for d2 in _subst(d, sigma):
                    if s2 != d2:
                        flows.add((s2, d2))
        out = set()
        for lab in sm.ret:
            out |= _subst(lab, sigma)
        return out

    def tx(e):
        if isinstance(e, int):
            return set()
        if isinstance(e, str):
            return set(taint.get(e, set()))
        op = e[0]
        if op in BIN_INT_OPS or op in CMP or op in ("and", "or", "not"):
            return set().union(*[tx(x) for x in e[1:]])
        if op == "cast":
            return tx(e[2])
        if op == "load":
            return {label[e[1]]} | tx(e[2])
        if op == "sys_write":
            link({label[e[2]]}, SINK)
            return set()
        if op == "call":
            return call(e)
        if op in ATOMIC_OPS:
            return atomic(e)
        if op in MMIO_OPS:
            return mmio(e)
        return set()  # len e afins: sem dado

    def stmts(ss):
        for s in ss:
            h = s[0]
            if h in ("let", "var"):
                taint.setdefault(s[1], set()).update(tx(s[3]))
            elif h == "set":
                taint.setdefault(s[1], set()).update(tx(s[2]))
            elif h == "store":
                link(tx(s[3]), label[s[1]])
            elif h in ("do", "sys_exit"):
                tx(s[1])
            elif h in ("atomic_store", "mmio_write"):
                tx(s)
            elif h == "return" and len(s) > 1:
                ret.update(tx(s[1]))
            elif h == "if":
                for part in s[2:]:
                    stmts(part[1:])
            elif h == "while":
                stmts([f for f in s[2:] if f[0] not in ("invariant", "decreases")])

    for _ in range(6):  # ponto fixo (variáveis são flow-insensitive: união de todas as atribuições)
        snap = (frozenset(flows), frozenset(ret), tuple(sorted((k, frozenset(v)) for k, v in taint.items())))
        stmts(fn.body)
        if snap == (frozenset(flows), frozenset(ret), tuple(sorted((k, frozenset(v)) for k, v in taint.items()))):
            break
    return Summary(flows, ret)


def analyse_program(fns, sigs, meta):
    summaries = {}
    for f in topo(fns):
        summaries[f.name] = analyse_fn(f, sigs, summaries, meta)
    return summaries


def concrete_edges(fns, summaries):
    """(origem, destino) -> primeira função (callee primeiro) em que o fluxo aparece."""
    edges = {}
    for f in topo(fns):
        for (a, b) in sorted(summaries[f.name].flows, key=str):
            if isinstance(a, str) and isinstance(b, str):
                edges.setdefault((a, b), f.name)
    return edges


def check_denies(fns, summaries, denies):
    """Violação = destino alcançável da origem pelo grafo de fluxos de TODO o programa (inclui via memória)."""
    edges = concrete_edges(fns, summaries)
    adj = {}
    for (a, b) in edges:
        adj.setdefault(a, []).append(b)
    errs = []
    for (a, b) in denies:
        prev, queue = {a: None}, [a]
        while queue:
            x = queue.pop(0)
            for y in adj.get(x, ()):
                if y not in prev:
                    prev[y] = x
                    queue.append(y)
        if b in prev:
            path, n = [], b
            while n is not None:
                path.append(n)
                n = prev[n]
            path.reverse()
            hops = ", ".join(f"{path[i]} → {path[i + 1]} em {edges[(path[i], path[i + 1])]}" for i in range(len(path) - 1))
            errs.append(f"fluxo proibido {a} → {b} (deny-flow {a} {b}): {hops}")
    return errs


def report(fns, summaries, denies, dot=False):
    edges = concrete_edges(fns, summaries)
    if dot:
        lines = ["digraph flow {", "  rankdir=LR;"]
        for (a, b), f in sorted(edges.items()):
            bad = " color=red" if (a, b) in denies else ""
            lines.append(f'  "{a}" -> "{b}" [label="{f}"{bad}];')
        return "\n".join(lines + ["}"]) + "\n"
    out = ["Fluxos de dados entre regiões (explícitos; sem fluxo por controle):"]
    for f in topo(fns):
        conc = sorted((a, b) for (a, b) in summaries[f.name].flows if isinstance(a, str) and isinstance(b, str))
        poly = sorted((a, b) for (a, b) in summaries[f.name].flows if not (isinstance(a, str) and isinstance(b, str)))
        if not (conc or poly):
            continue
        out.append(f"  fn {f.name}")
        for a, b in conc:
            out.append(f"    {a} → {b}")
        for a, b in poly:
            fmt = lambda x: f"param#{x[1]}" if isinstance(x, tuple) else x
            out.append(f"    {fmt(a)} → {fmt(b)}   (genérico: região do parâmetro)")
    if len(out) == 1:
        out.append("  (nenhum fluxo entre regiões distintas)")
    out.append("Políticas: " + (", ".join(f"deny-flow {a} {b}" for a, b in denies) or "nenhuma"))
    return "\n".join(out)
