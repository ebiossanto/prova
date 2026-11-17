import sys
sys.path.insert(0, r'D:\PROVA linguagem')
import importlib
import provac.check
importlib.reload(provac.check)

import subprocess
result = subprocess.run(
    [sys.executable, "prova.py", "check", "D:/PROVA linguagem/examples/atomic_test.prova", "--json"],
    capture_output=True, text=True
)
print(f"Return code: {result.returncode}")
print(f"Stdout: {result.stdout}")
print(f"Stderr: {result.stderr}")