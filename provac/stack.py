"""Orçamento de pilha: (stack-budget N) é provado pelo grafo de chamadas (sem recursão, então o pior caso
é finito): pilha(f) = quadro(f) + max(pilha(chamado)).

ATENÇÃO: o tamanho do quadro vem de um MODELO de custo (16 + 8 por variável + 16 por fatia) enquanto o
backend não é consultado. Para valores reais passe --frames frames.json (tamanhos medidos no código gerado,
p.ex. com `llc --stack-size-section` ou `-fstack-usage`); eles substituem o modelo função a função."""
from .effects import direct

MODEL = "modelo: 16 + 8/variável + 16/fatia"


def frame_model(cx):
    return 16 + 8 * len([x for x in cx.types if x != "result"]) + 16 * len(cx.slice_names)


def worst_case(fns, frames):
    """nome -> (bytes no pior caso, cadeia de chamadas)."""
    calls = {f.name: sorted(direct(f)[1]) for f in fns}
    memo = {}

    def go(n):
        if n not in memo:
            best = (0, [])
            for c in calls.get(n, ()):
                sub = go(c)
                if sub[0] > best[0]:
                    best = sub
            memo[n] = (frames[n] + best[0], [n] + best[1])
        return memo[n]

    return {f.name: go(f.name) for f in fns}


def stack_obligations(fns, cxs, override=None):
    override = override or {}
    frames = {f.name: override.get(f.name, frame_model(cxs[f.name])) for f in fns}
    how = "frames" if override and all(f.name in override for f in fns) else (
        "frames+modelo" if override else "modelo")
    wc = worst_case(fns, frames)
    out = []
    for f in fns:
        if f.budget is None:
            continue
        used, chain = wc[f.name]
        ok = used <= f.budget
        o = {"fn": f.name, "label": f"pilha: {f.name} ≤ {f.budget} bytes (pior caso {used}: {' → '.join(chain)}; {MODEL if how == 'modelo' else how})",
             "goal": f"{used} <= {f.budget}", "status": "proved" if ok else "failed", "how": how}
        if not ok:
            o["model"] = {"pior_caso_bytes": used, "orcamento": f.budget}
        out.append(o)
    return out, frames, wc
