"""Programa completo: leitura dos formulários de topo, verificação por função e análises de programa
(posse, efeitos, fluxo por região, orçamento de pilha)."""
import re

from .check import ATOMIC_T, HI, LO, Fn, ProvaError, check_call_graph, verify_fn
from .effects import check_effects, check_readonly_calls
from .flow import SINK, analyse_program, check_denies
from .linear import check_linear
from .sexp import parse
from .smt import discharge
from .stack import stack_obligations

NAME = re.compile(r"^[a-z_][a-z0-9_-]*$")


class Program:
    pass


def load_text(text):
    forms = parse(text)
    data, regions, data_region, statics, static_init, denies, fns = {}, {"rodata"}, {}, {}, {}, [], []
    for f in forms:
        if not isinstance(f, list) or not f or not isinstance(f[0], str):
            raise ProvaError(f"forma de topo inválida: {f!r} (esperado (fn ...), (data ...), (region ...), "
                             f"(static ...) ou (deny-flow ...))")
        h = f[0]
        if h == "data":
            if len(f) not in (3, 4) or not isinstance(f[1], str):
                raise ProvaError('data espera (data nome "texto" [região])')
            data[f[1]] = f[2].encode("utf-8")
            data_region[f[1]] = f[3] if len(f) == 4 else "rodata"
        elif h == "region":
            if len(f) != 2 or not isinstance(f[1], str) or not NAME.match(f[1]):
                raise ProvaError("region espera (region nome) com nome [a-z_][a-z0-9_-]*")
            regions.add(f[1])
        elif h == "static":
            if len(f) != 4 or not isinstance(f[1], str) or not (isinstance(f[2], list) and len(f[2]) == 2
                                                                 and f[2][0] == "atomic" and f[2][1] in ATOMIC_T):
                raise ProvaError(f"static espera (static nome (atomic {'|'.join(ATOMIC_T)}) inicial)")
            T = f[2][1]
            if not isinstance(f[3], int) or not LO[T] <= f[3] <= HI[T]:
                raise ProvaError(f"valor inicial de '{f[1]}' fora da faixa de {T}")
            statics[f[1]], static_init[f[1]] = T, f[3]
        elif h == "deny-flow":
            if len(f) != 3 or not all(isinstance(x, str) for x in f[1:]):
                raise ProvaError("deny-flow espera (deny-flow ORIGEM DESTINO)")
            denies.append((f[1], f[2]))
        elif h == "fn":
            fns.append(Fn(f))
        else:
            raise ProvaError(f"forma de topo desconhecida: {h}")
    ends = set(regions) | {SINK} | {"@static:" + s for s in statics}
    for d, r in data_region.items():
        if r not in regions:
            raise ProvaError(f"data '{d}': região '{r}' não declarada (use (region {r}))")
    for a, b in denies:
        for x in (a, b):
            if x not in ends:
                raise ProvaError(f"deny-flow: '{x}' não é região declarada, {SINK} nem @static:NOME")
    meta = {"regions": regions, "data_region": data_region, "statics": statics,
            "static_init": static_init, "denies": denies}
    return data, fns, meta


def build(text, frames=None, discharger=discharge):
    data, fns, meta = load_text(text)
    dlen = {k: len(v) for k, v in data.items()}
    sigs = {}
    for fn in fns:
        if fn.name in sigs:
            raise ProvaError(f"função duplicada: {fn.name}")
        sigs[fn.name] = fn
    check_call_graph(fns)
    P = Program()
    P.data, P.fns, P.sigs, P.meta = data, fns, sigs, meta
    P.compiled, P.results, cxs, ro_memo = [], [], {}, {}
    for fn in fns:
        lin = check_linear(fn, sigs)
        cx = verify_fn(fn, dlen, sigs, meta)
        cxs[fn.name] = cx
        P.compiled.append((fn, cx))
        obs = [{"label": ob["label"], "goal": str(ob["goal"]), **discharger(ob)} for ob in cx.obs]
        pol = check_effects(fn, sigs) + check_readonly_calls(fn, cx, sigs, ro_memo)
        if cx.pre_contradictory:
            pol.append(f"{fn.name}: pré-condição contraditória (insatisfatível): qualquer corpo seria 'provado' "
                       f"no vazio; revise o (pre ...)")
        P.results.append({"fn": fn.name, "linear_errors": lin, "policy_errors": pol, "obligations": obs})
    P.summaries = analyse_program(fns, sigs, meta)
    flow_errs = check_denies(fns, P.summaries, meta["denies"])
    stack_obs, P.frames, P.worst = stack_obligations(fns, cxs, frames)
    by = {r["fn"]: r for r in P.results}
    for o in stack_obs:
        by[o["fn"]]["obligations"].append({k: v for k, v in o.items() if k != "fn"})
    if flow_errs:
        P.results.append({"fn": "(programa)", "linear_errors": [], "policy_errors": flow_errs, "obligations": []})
    return P


def build_safe(text, frames=None, discharger=discharge):
    """Como build, mas formas malformadas viram ProvaError (nunca um traceback)."""
    try:
        return build(text, frames, discharger)
    except (IndexError, KeyError, TypeError, ValueError, AttributeError) as e:
        raise ProvaError("forma malformada (aridade ou estrutura inválida; confira spec/prova.gbnf): "
                         f"{type(e).__name__}: {e}")
