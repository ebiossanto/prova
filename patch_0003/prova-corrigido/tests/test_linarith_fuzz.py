"""Solidez do provador linear: zero falsos positivos, e o próprio fuzzer tem poder de detecção."""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
from fuzz_linarith import fuzz, fuzz_contradictory  # noqa: E402
from provac import linarith  # noqa: E402


def test_no_false_positives():
    for seed in (1, 2):
        proved, unsound, ex = fuzz(500, seed)
        assert unsound == 0, ex
        assert proved > 100, "o provador não está provando quase nada (teste sem poder)"


def test_fuzzer_detects_an_unsound_mutant():
    original = linarith.norm

    def unsound_norm(p):  # aperta demais a constante: prova "infeasível" o que é factível
        coefs, const = original(p)
        return coefs, (const - 1 if coefs else const)

    linarith.norm = unsound_norm
    try:
        _, unsound, _ = fuzz(500, 1)
    finally:
        linarith.norm = original
    assert unsound > 0, "o fuzzer não detectou um defeito insólito: ele perdeu o poder de detecção"


def test_contradiction_detector_never_raises_a_false_alarm():
    for seed in (1, 2):
        flagged, unsound = fuzz_contradictory(1200, seed)
        assert unsound == 0
        assert flagged > 50, "o detector não está detectando quase nada (teste sem poder)"
