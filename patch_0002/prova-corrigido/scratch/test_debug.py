import json
import subprocess
import os

filepath = r'D:\PROVA linguagem/examples/bad_move.prova'
abs_filepath = os.path.abspath(filepath)
result = subprocess.run(["python", "prova.py", "check", abs_filepath, "--json"], capture_output=True, text=True)
data = json.loads(result.stdout)
print(f"Number of results: {len(data)}")
for i, r in enumerate(data):
    print(f"Result {i}: fn={r.get('fn')}, linear_errors={r.get('linear_errors')}, obligations_count={len(r.get('obligations', []))}")