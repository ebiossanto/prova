"""Relatório de auditoria: o que um humano precisa ler (contratos, efeitos, regiões, orçamento, políticas),
sem ler o corpo das funções."""
from .check import show


def accessed(fn):
    reads, writes, calls, drops = set(), set(), set(), set()

    def walk(n):
        if not isinstance(n, list) or not n:
            return
        h = n[0]
        if h == "load" and len(n) > 1:
            reads.add(n[1])
        elif h == "store" and len(n) > 1:
            writes.add(n[1])
        elif h == "sys_write":
            reads.add(n[2])
        elif h == "call":
            calls.add(n[1])
        elif h == "drop":
            drops.add(n[1])
        for x in n:
            walk(x)

    walk(fn.body)
    return reads, writes, calls, drops


def sig(fn):
    ps = ", ".join(f"{n}: {show(T)}" for n, T in fn.params)
    return f"fn {fn.name}({ps})" + ("" if fn.ret == "unit" else f" -> {fn.ret}")


def audit(fns, meta=None):
    out = []
    if meta:
        if meta["regions"] - {"rodata"}:
            out.append("regiões   " + ", ".join(sorted(meta["regions"] - {"rodata"})))
        for n, T in meta["statics"].items():
            out.append(f"static    {n}: (atomic {T}) = {meta['static_init'][n]}   [única memória compartilhada]")
        for a, b in meta["denies"]:
            out.append(f"política  deny-flow {a} {b}")
        if out:
            out.append("")
    for fn in fns:
        r, w, c, d = accessed(fn)
        out.append(sig(fn))
        out.append("  exige    " + (" ".join(show(p) for p in fn.pre) or "—"))
        out.append("  garante  " + (" ".join(show(p) for p in fn.post) or "—"))
        out.append("  efeitos  " + (", ".join(sorted(fn.effects)) or "nenhum (pura)"))
        if fn.budget:
            out.append(f"  pilha    ≤ {fn.budget} bytes")
        notes = []
        if r: notes.append("lê " + ",".join(sorted(r)))
        if w: notes.append("escreve " + ",".join(sorted(w)))
        if c: notes.append("chama " + ",".join(sorted(c)))
        if d: notes.append("consome " + ",".join(sorted(d)))
        owned = [n for n, T in fn.params if isinstance(T, list) and T[0] == "own"]
        if owned: notes.append("recebe posse de " + ",".join(owned))
        if notes:
            out.append("  corpo    " + "; ".join(notes))
        out.append("")
    return "\n".join(out)
