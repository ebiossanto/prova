"""Relatório de auditoria: o que um humano precisa ler (contratos + efeitos + regiões), sem ler o corpo."""
from .check import base, is_slice, show, is_ptr


def effects(fn):
    reads, writes, sysc, calls, drops = set(), set(), set(), set(), set()
    regions = set()  # Track regions on pointers

    def walk(n):
        if not isinstance(n, list) or not n:
            return
        h = n[0]
        if h == "load" and len(n) > 1:
            reads.add(n[1])
        elif h == "store" and len(n) > 1:
            writes.add(n[1])
        elif h == "sys_write":
            sysc.add("write")
            reads.add(n[2])
        elif h == "sys_exit":
            sysc.add("exit")
        elif h == "call":
            calls.add(n[1])
        elif h == "drop":
            drops.add(n[1])
        # Track ptr regions
        if is_ptr(n):
            # Extract region from (ptr mmio) etc.
            if len(n) >= 3 and isinstance(n[2], str):
                regions.add(n[2])
        for x in n:
            walk(x)

    walk(fn.body)
    return reads, writes, sysc, calls, drops, regions


def sig(fn):
    ps = ", ".join(f"{n}: {show(T)}" for n, T in fn.params)
    return f"fn {fn.name}({ps})" + ("" if fn.ret == "unit" else f" -> {fn.ret}")


def audit(fns):
    out = []
    for fn in fns:
        r, w, s, c, d, regions = effects(fn)
        out.append(sig(fn))
        out.append("  exige    " + (" ".join(show(p) for p in fn.pre) or "—"))
        out.append("  garante  " + (" ".join(show(p) for p in fn.post) or "—"))
        eff = []
        if r: eff.append("lê " + ",".join(sorted(r)))
        if w: eff.append("escreve " + ",".join(sorted(w)))
        if s: eff.append("syscall " + ",".join(sorted(s)))
        if c: eff.append("chama " + ",".join(sorted(c)))
        if d: eff.append("consome " + ",".join(sorted(d)))
        if regions: eff.append("regiões " + ",".join(sorted(regions)))
        owned = [n for n, T in fn.params if isinstance(T, list) and T[0] == "own"]
        if owned: eff.append("recebe posse de " + ",".join(owned))
        out.append("  efeitos  " + ("; ".join(eff) or "puro"))
        out.append("")
    return "\n".join(out)
