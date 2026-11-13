#!/usr/bin/env python3
"""Teste de solidez do provador interno: se `prove` diz True, NENHUM modelo no domínio pode
satisfazer as hipóteses e violar o objetivo. Procura falso positivo (o erro que importa)."""
import itertools, os, random, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from provac import linarith
from provac.smt import evalt

random.seed(int(sys.argv[2]) if len(sys.argv) > 2 else 1)
N = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
VARS = ["a", "b", "c"]
DOM = range(-4, 5)


def term(d=2):
    r = random.random()
    if d == 0 or r < 0.3:
        return random.choice(VARS) if random.random() < 0.65 else random.randint(-4, 4)
    op = random.choice(["+", "+", "-", "-", "*"])
    return (op, term(d - 1), term(d - 1))


def formula(d=2):
    if d == 0 or random.random() < 0.55:
        return (random.choice(["<", "<=", ">", ">=", "=", "!="]), term(), term())
    op = random.choice(["and", "or", "not"])
    return ("not", formula(d - 1)) if op == "not" else (op, formula(d - 1), formula(d - 1))


proved = unsound = total_models = 0
for _ in range(N):
    hyps = []
    for v in VARS:
        if random.random() < 0.7:
            lo = random.randint(-4, 2)
            hyps += [("<=", lo, v), ("<=", v, random.randint(lo, 4))]
    hyps += [formula() for _ in range(random.randint(0, 3))]
    goal = formula()
    if linarith.prove(hyps, goal):
        proved += 1
        for vals in itertools.product(DOM, repeat=3):
            a = dict(zip(VARS, vals))
            if all(evalt(h, a) for h in hyps) and not evalt(goal, a):
                unsound += 1
                print("FALSO POSITIVO:", hyps, goal, a)
                break
print(f"casos={N} provados={proved} falsos_positivos={unsound}")
sys.exit(1 if unsound else 0)
