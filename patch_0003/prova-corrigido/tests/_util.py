"""Utilidades compartilhadas pelos testes."""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import prova  # noqa: E402
from provac.check import ProvaError  # noqa: E402
from provac.sexp import ParseError  # noqa: E402

EX = os.path.join(ROOT, "examples")


def example(name):
    return open(os.path.join(EX, name + ".prova"), encoding="utf-8").read()


def build(src, frames=None):
    return prova.build_checked(src, frames)


def problems(P):
    """Tudo que reprova o programa: obrigações que falharam + erros de posse/política."""
    out = []
    for r in P.results:
        out += r["linear_errors"] + r.get("policy_errors", [])
        out += [o["label"] for o in r["obligations"] if o["status"] == "failed"]
    return out


def pending(P):
    return [o["label"] for r in P.results for o in r["obligations"] if o["status"] != "proved"]


def src_error(src):
    """Mensagem de erro (ProvaError/ParseError ou problemas de verificação) ou None se aceitou limpo."""
    try:
        P = build(src)
    except (ProvaError, ParseError) as e:
        return str(e)
    ps = problems(P)
    return "\n".join(ps) if ps else None
