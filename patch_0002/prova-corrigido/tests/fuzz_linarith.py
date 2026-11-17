#!/usr/bin/env python3
"""Fuzzing de solidez do provador linear. Uso: python tests/fuzz_linarith.py [N] [semente]
Se `prove` diz True, NENHUM modelo no domínio pode satisfazer as hipóteses e violar o objetivo."""
import itertools, os, random, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from provac import linarith  # noqa: E402
from provac.smt import evalt  # noqa: E402

VARS = ["a", "b", "c"]
DOM = range(-4, 5)


def fuzz(n=3000, seed=1):
    """Retorna (provados, falsos_positivos, exemplos_de_falso_positivo)."""
    rnd = random.Random(seed)

    def term(d=2):
        if d == 0 or rnd.random() < 0.3:
            return rnd.choice(VARS) if rnd.random() < 0.65 else rnd.randint(-4, 4)
        return (rnd.choice(["+", "+", "-", "-", "*"]), term(d - 1), term(d - 1))

    def formula(d=2):
        if d == 0 or rnd.random() < 0.55:
            return (rnd.choice(["<", "<=", ">", ">=", "=", "!="]), term(), term())
        op = rnd.choice(["and", "or", "not"])
        return ("not", formula(d - 1)) if op == "not" else (op, formula(d - 1), formula(d - 1))

    proved = unsound = 0
    examples = []
    for _ in range(n):
        hyps = []
        for v in VARS:
            if rnd.random() < 0.7:
                lo = rnd.randint(-4, 2)
                hyps += [("<=", lo, v), ("<=", v, rnd.randint(lo, 4))]
        hyps += [formula() for _ in range(rnd.randint(0, 3))]
        goal = formula()
        if linarith.prove(hyps, goal):
            proved += 1
            for vals in itertools.product(DOM, repeat=3):
                a = dict(zip(VARS, vals))
                if all(evalt(h, a) for h in hyps) and not evalt(goal, a):
                    unsound += 1
                    if len(examples) < 3:
                        examples.append((hyps, goal, a))
                    break
    return proved, unsound, examples


def fuzz_contradictory(n=2000, seed=1):
    """Se `contradictory(hyps)` é True, NENHUM modelo do domínio pode satisfazer as hipóteses."""
    rnd = random.Random(seed)

    def term(d=2):
        if d == 0 or rnd.random() < 0.3:
            return rnd.choice(VARS) if rnd.random() < 0.65 else rnd.randint(-4, 4)
        return (rnd.choice(["+", "-", "*"]), term(d - 1), term(d - 1))

    def atom():
        return (rnd.choice(["<", "<=", ">", ">=", "=", "!="]), term(), term())

    flagged = unsound = 0
    for _ in range(n):
        hyps = [atom() if rnd.random() < 0.8 else ("or", atom(), atom()) for _ in range(rnd.randint(1, 4))]
        if linarith.contradictory(hyps):
            flagged += 1
            for vals in itertools.product(DOM, repeat=3):
                if all(evalt(h, dict(zip(VARS, vals))) for h in hyps):
                    unsound += 1
                    break
    return flagged, unsound


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    p, u, ex = fuzz(n, seed)
    for e in ex:
        print("FALSO POSITIVO:", e)
    print(f"casos={n} provados={p} falsos_positivos={u}")
    sys.exit(1 if u else 0)
