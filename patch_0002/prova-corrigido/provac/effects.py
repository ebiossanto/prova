"""Efeitos nas assinaturas: quem faz syscall ou usa atômicos TEM que declarar. Sem (effects ...) = função pura.
Um efeito de um chamado propaga para o chamador (não existe efeito escondido atrás de uma chamada)."""
from .check import ATOMIC_OPS


def direct(fn):
    """(efeitos do próprio corpo, nomes chamados)."""
    eff, calls = set(), set()

    def walk(n):
        if isinstance(n, list) and n:
            h = n[0]
            if h in ("sys_write", "sys_exit"):
                eff.add("syscall")
            elif h in ATOMIC_OPS:
                eff.add("atomic")
            elif h == "call" and len(n) > 1 and isinstance(n[1], str):
                calls.add(n[1])
            for x in n:
                walk(x)

    walk(fn.body)
    return eff, calls


def check_effects(fn, sigs):
    eff, calls = direct(fn)
    src = {}
    for e in eff:
        src.setdefault(e, set()).add("o corpo")
    for c in calls:
        for e in sigs[c].effects:
            src.setdefault(e, set()).add(f"a chamada a {c}")
    return [f"{fn.name}: efeito '{e}' não declarado (vem de {', '.join(sorted(src[e]))}); "
            f"declare (effects {e}) no contrato" for e in sorted(src) if e not in fn.effects]
