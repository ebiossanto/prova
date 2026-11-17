"""Laço fechado com a IA (ideia original): o modelo recebe erros matemáticos precisos e corrige o CORPO das
funções; o humano só audita os CONTRATOS, e por isso o modelo NÃO pode alterá-los.

Contrato travado = assinatura (params, returns), effects, stack-budget, pre, post de cada função existente,
mais regiões, políticas deny-flow e células static. Sem esse travamento a IA "corrigiria" o erro
enfraquecendo o contrato (por exemplo, com uma `pre` contraditória, que prova qualquer coisa).

O modelo é qualquer comando de shell: lê JSON no stdin e imprime o fonte .prova completo no stdout.
JSON de entrada: {"iteration", "source", "errors": [...], "locked": {...}, "feedback": "..."|null}."""
import json
import subprocess

from .check import ProvaError, show
from .program import build_safe, load_text
from .sexp import ParseError


def lock_of(text):
    _, fns, meta = load_text(text)
    funcs = {}
    for f in fns:
        funcs[f.name] = {"params": [(n, show(T)) for n, T in f.params], "returns": f.ret,
                         "effects": sorted(f.effects), "budget": f.budget,
                         "pre": [show(x) for x in f.pre], "post": [show(x) for x in f.post]}
    top = {"regions": sorted(meta["regions"]), "denies": sorted(meta["denies"]),
           "statics": {k: [v, meta["static_init"][k]] for k, v in sorted(meta["statics"].items())},
           "mmios": {k: [v["addr"], v["type"], v["region"]] for k, v in sorted(meta.get("mmios", {}).items())}}
    return funcs, top


def diff_lock(orig, cand):
    """Violações do contrato travado (lista vazia = respeitado). Funções novas (auxiliares) são permitidas."""
    (of, ot), (cf, ct) = orig, cand
    out = []
    for name, spec in of.items():
        if name not in cf:
            out.append(f"função '{name}' removida")
            continue
        for k, v in spec.items():
            if cf[name][k] != v:
                out.append(f"'{name}': {k} era {v} e agora é {cf[name][k]}")
    if not set(ot["regions"]) <= set(ct["regions"]):
        out.append("região removida")
    if ot["denies"] != ct["denies"]:
        out.append(f"políticas deny-flow alteradas: eram {ot['denies']}, agora {ct['denies']}")
    if ot["statics"] != ct["statics"]:
        out.append("células static alteradas")
    if ot.get("mmios", {}) != ct.get("mmios", {}):
        out.append("registradores mmio alterados")
    return out


def evaluate(text, strict=False):
    """(ok, erros para o modelo)."""
    try:
        P = build_safe(text)
    except (ParseError, ProvaError) as e:
        return False, [{"kind": "erro", "msg": str(e)}]
    errs, pending = [], 0
    for r in P.results:
        for m in r["linear_errors"]:
            errs.append({"kind": "posse", "fn": r["fn"], "msg": m})
        for m in r["policy_errors"]:
            errs.append({"kind": "política", "fn": r["fn"], "msg": m})
        for o in r["obligations"]:
            if o["status"] == "failed":
                errs.append({"kind": "obrigação", "fn": r["fn"], "label": o["label"],
                             "goal": o.get("goal"), "counterexample": o.get("model")})
            elif o["status"] != "proved":
                pending += 1
                if strict:
                    errs.append({"kind": "não provada", "fn": r["fn"], "label": o["label"], "goal": o.get("goal")})
    return not errs, errs


def fix(path, model_cmd, max_iter=5, strict=False):
    src = open(path, encoding="utf-8").read()
    locked = lock_of(src)  # ProvaError aqui = o original já é inválido: o chamador mostra o erro
    history, feedback = [], None
    for it in range(max_iter + 1):
        ok, errs = evaluate(src, strict)
        if ok:
            history.append({"iteration": it, "outcome": "verificado: sem falhas"})
            return {"ok": True, "source": src, "history": history}
        if it == max_iter:
            history.append({"iteration": it, "outcome": f"limite de {max_iter} iterações; ainda há {len(errs)} erro(s)"})
            break
        payload = {"iteration": it, "source": src, "errors": errs, "locked": locked[0], "feedback": feedback}
        p = subprocess.run(model_cmd, shell=True, input=json.dumps(payload, ensure_ascii=False),
                           capture_output=True, text=True, encoding="utf-8", timeout=300)
        if p.returncode != 0:
            feedback = f"o comando do modelo falhou (código {p.returncode}): {p.stderr.strip()[:200]}"
            history.append({"iteration": it, "outcome": feedback})
            continue
        cand = p.stdout
        try:
            viol = diff_lock(locked, lock_of(cand))
        except (ParseError, ProvaError, IndexError, KeyError, TypeError, ValueError) as e:
            feedback = f"fonte inválido: {e}"
            history.append({"iteration": it, "outcome": f"rejeitado: {feedback}"})
            continue
        if viol:
            feedback = "CONTRATO ALTERADO (proibido): " + "; ".join(viol) + ". Corrija o corpo, não o contrato."
            history.append({"iteration": it, "outcome": f"rejeitado: {feedback}"})
            continue
        src, feedback = cand, None
        history.append({"iteration": it, "outcome": f"candidato aceito para verificação ({len(errs)} erro(s) antes)"})
    return {"ok": False, "source": src, "history": history}
