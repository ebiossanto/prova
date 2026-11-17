"""Efeitos nas assinaturas: quem faz syscall, usa atômicos ou acessa MMIO TEM que declarar. Sem (effects ...) = função pura.
Um efeito de um chamado propaga para o chamador (não existe efeito escondido atrás de uma chamada)."""
from .check import ATOMIC_OPS, MMIO_OPS, is_slice


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
            elif h in MMIO_OPS:
                eff.add("mmio")
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


def mutated_params(fn, sigs, memo=None):
    """Parâmetros-fatia em que a função escreve (direto ou passando a um chamado que escreve)."""
    memo = {} if memo is None else memo
    if fn.name in memo:
        return memo[fn.name]
    memo[fn.name] = set()  # o grafo de chamadas é acíclico (verificado antes)
    names = {n for n, T in fn.params if is_slice(T)}
    out = set()

    def walk(n):
        if isinstance(n, list) and n:
            if n[0] == "store" and len(n) > 1 and n[1] in names:
                out.add(n[1])
            elif n[0] == "call" and len(n) > 1 and n[1] in sigs:
                g = sigs[n[1]]
                gm = mutated_params(g, sigs, memo)
                for (pn, _), a in zip(g.params, n[2:]):
                    if pn in gm and isinstance(a, str) and a in names:
                        out.add(a)
            for x in n:
                walk(x)

    walk(fn.body)
    memo[fn.name] = out
    return out


def check_readonly_calls(fn, cx, sigs, memo):
    """Fatia somente-leitura (de data) não pode ir a um parâmetro em que o chamado escreve;
    e a mesma fatia não pode ser passada duas vezes quando pelo menos um dos parâmetros é escrito (aliasing mutável)."""
    errs = []

    def walk(n):
        if isinstance(n, list) and n:
            if n[0] == "call" and len(n) > 1 and n[1] in sigs:
                g = sigs[n[1]]
                gm = mutated_params(g, sigs, memo)
                seen_slices = {}
                for (pn, PT), a in zip(g.params, n[2:]):
                    if is_slice(PT) and isinstance(a, str):
                        if pn in gm and a in cx.readonly:
                            errs.append(f"{fn.name}: '{a}' é somente-leitura (vem de data), mas {g.name} escreve em '{pn}'")
                        if a in seen_slices:
                            prev_pn = seen_slices[a]
                            if pn in gm or prev_pn in gm:
                                w_pn = pn if pn in gm else prev_pn
                                errs.append(f"{fn.name}: aliasing mutável de '{a}' em chamada a {g.name}: "
                                            f"passada para '{prev_pn}' e '{pn}', mas {g.name} escreve em '{w_pn}'")
                        else:
                            seen_slices[a] = pn
            for x in n:
                walk(x)

    walk(fn.body)
    return errs
