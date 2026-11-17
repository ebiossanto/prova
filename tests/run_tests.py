#!/usr/bin/env python3
"""Runner sem dependências: descobre tests/test_*.py e roda as funções test_*.
Sai com código != 0 se QUALQUER teste falhar (nada de 'Atenção' que passa batido).
Uso: python tests/run_tests.py [-k trecho]      (também funciona com `pytest tests/`)"""
import importlib.util, os, sys, time, traceback, unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def main(argv):
    flt = argv[argv.index("-k") + 1] if "-k" in argv else ""
    sys.path.insert(0, HERE)
    passed = failed = skipped = 0
    t0 = time.time()
    for fn in sorted(os.listdir(HERE)):
        if not (fn.startswith("test_") and fn.endswith(".py")):
            continue
        spec = importlib.util.spec_from_file_location(fn[:-3], os.path.join(HERE, fn))
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception:
            failed += 1
            print(f"ERRO ao importar {fn}\n{traceback.format_exc()}")
            continue
        for name in sorted(dir(mod)):
            if not name.startswith("test_") or not callable(getattr(mod, name)) or flt not in name:
                continue
            try:
                getattr(mod, name)()
                passed += 1
                print(f"  ok     {fn}::{name}")
            except unittest.SkipTest as e:
                skipped += 1
                print(f"  SKIP   {fn}::{name}  ({e})")
            except BaseException:
                failed += 1
                print(f"  FALHOU {fn}::{name}\n{traceback.format_exc()}")
    print(f"\n{passed} passaram, {failed} falharam, {skipped} ignorados em {time.time() - t0:.1f}s")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
