"""Orçamento de pilha pelo grafo de chamadas: modelo de custo por padrão; --frames usa valores do backend."""
import json, os, subprocess, sys
from _util import ROOT, build, example, pending, problems


def test_budget_is_proved_with_worst_case_chain():
    P = build(example("stack_budget"))
    assert not problems(P) and not pending(P)
    assert P.worst["mid"] == (56, ["mid", "leaf"])     # 32 (mid) + 24 (leaf), no modelo
    assert P.worst["leaf"] == (24, ["leaf"])


def test_budget_violation_is_reported_with_numbers():
    P = build(example("bad_stack"))
    bad = [o for r in P.results for o in r["obligations"] if o["status"] == "failed"]
    assert len(bad) == 1 and bad[0]["model"] == {"pior_caso_bytes": 56, "orcamento": 40}


def test_backend_frames_override_the_model():
    src = example("stack_budget")
    assert not problems(build(src))
    P = build(src, frames={"leaf": 1000})              # backend mediu 1000 bytes para leaf
    assert any("pilha: leaf" in p for p in problems(P)), problems(P)
    assert any("pilha: mid" in p for p in problems(P))  # e o custo propaga para quem chama


def test_invalid_budget_clause():
    from _util import src_error
    assert "inteiro positivo" in src_error("(fn f (params) (returns unit) (stack-budget -3) (pre) (post) (body))")


def test_cli_stack_table_and_exit_code():
    run = lambda name: subprocess.run([sys.executable, os.path.join(ROOT, "prova.py"), "stack",
                                       os.path.join(ROOT, "examples", name + ".prova")],
                                      capture_output=True, text=True, encoding="utf-8")
    ok, bad = run("stack_budget"), run("bad_stack")
    assert ok.returncode == 0 and "mid → leaf" in ok.stdout
    assert bad.returncode == 1
