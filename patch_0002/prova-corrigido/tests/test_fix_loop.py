"""Laço fechado com a IA: o modelo corrige o CORPO; os contratos (que o humano audita) são travados.
Usa um 'modelo' determinístico (tests/fake_model.py): nenhuma IA real, só a mecânica do laço."""
import os, subprocess, sys, tempfile
from _util import ROOT, build, example, problems
from provac.loop import diff_lock, fix, lock_of

FAKE = os.path.join(ROOT, "tests", "fake_model.py")
cmd = lambda mode: f'"{sys.executable}" "{FAKE}" {mode}'


def run_fix(mode, src=None, max_iter=4, strict=False):
    with tempfile.NamedTemporaryFile("w", suffix=".prova", delete=False, encoding="utf-8") as f:
        f.write(src or example("bad_bounds"))
    try:
        return fix(f.name, cmd(mode), max_iter, strict)
    finally:
        os.unlink(f.name)


def test_honest_model_fixes_the_body_and_contracts_stay_identical():
    r = run_fix("honest")
    assert r["ok"] and "(while (< i len)" in r["source"]
    assert not problems(build(r["source"]))
    assert lock_of(r["source"]) == lock_of(example("bad_bounds"))


def test_model_cannot_fix_by_weakening_the_contract():
    r = run_fix("cheater")
    assert r["ok"]
    assert any("CONTRATO ALTERADO" in h["outcome"] for h in r["history"]), r["history"]
    assert "(< len 0)" not in r["source"]            # a trapaça nunca chegou ao resultado
    assert lock_of(r["source"]) == lock_of(example("bad_bounds"))


def test_the_cheat_would_be_accepted_without_the_lock_so_the_lock_matters():
    cheat = example("bad_bounds").replace("(pre (<= len n))", "(pre (<= len n) (< len 0))")
    P = build(cheat)  # o corpo continua com o bug, mas todas as obrigações são provadas no vazio...
    assert not [o for r in P.results for o in r["obligations"] if o["status"] == "failed"]
    # ...por isso existe a checagem de pré contraditória, que o verificador agora acusa:
    assert any("pré-condição contraditória" in p for p in problems(P))


def test_garbage_output_is_rejected_then_recovers():
    r = run_fix("garbage")
    assert r["ok"] and any("fonte inválido" in h["outcome"] for h in r["history"])


def test_gives_up_after_max_iterations():
    r = run_fix("stubborn", max_iter=2)
    assert not r["ok"] and "limite de 2 iterações" in r["history"][-1]["outcome"]


def test_correct_program_never_calls_the_model():
    r = fix(os.path.join(ROOT, "examples", "sum_to.prova"), f'"{sys.executable}" -c "import sys; sys.exit(9)"', 3)
    assert r["ok"] and len(r["history"]) == 1


def test_lock_allows_new_helpers_but_not_removing_or_changing_contracts():
    base = lock_of(example("calls"))
    added = example("calls") + "\n(fn helper (params) (returns unit) (pre) (post) (body))\n"
    assert diff_lock(base, lock_of(added)) == []
    removed = example("calls").split("(fn double_clamped")[0]
    assert any("removida" in v for v in diff_lock(base, lock_of(removed)))
    changed = example("calls").replace("(post (<= 0 result) (<= result 2000))", "(post (<= 0 result))")
    assert any("post era" in v for v in diff_lock(base, lock_of(changed)))
    eff = example("effects").replace("(effects syscall)", "(effects syscall atomic)", 1)
    assert any("effects" in v for v in diff_lock(lock_of(example("effects")), lock_of(eff)))


def test_policies_are_locked_too():
    base = lock_of(example("regions_flow"))
    dropped = example("regions_flow").replace("(deny-flow net-rx @write)\n", "")
    assert any("deny-flow" in v for v in diff_lock(base, lock_of(dropped)))


def test_cli_fix_writes_the_result():
    with tempfile.TemporaryDirectory() as d:
        src, out = os.path.join(d, "a.prova"), os.path.join(d, "fixed.prova")
        open(src, "w", encoding="utf-8").write(example("bad_bounds"))
        r = subprocess.run([sys.executable, os.path.join(ROOT, "prova.py"), "fix", src, "--model-cmd", cmd("honest"),
                            "--out", out], capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 0, r.stdout + r.stderr
        assert "(while (< i len)" in open(out, encoding="utf-8").read()
