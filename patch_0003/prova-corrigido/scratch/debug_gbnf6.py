import sys
sys.path.insert(0, "D:/PROVA linguagem/tests")
from gbnf import accepts, parse_grammar
import glob, os

root = "D:/PROVA linguagem"

with open(os.path.join(root, "spec", "prova.gbnf"), encoding="utf-8") as f:
    rules = parse_grammar(f.read())

# Test each example
for f in sorted(glob.glob(os.path.join(root, "examples", "*.prova"))):
    with open(f, encoding="utf-8") as fh:
        text = fh.read()
    # Strip only ;; comment lines, keep everything else
    lines = text.splitlines()
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(";;"):
            continue
        cleaned_lines.append(line)  # keep original line (with indentation)
    cleaned = "\n".join(cleaned_lines)
    result = accepts(rules, cleaned)
    basename = os.path.basename(f)
    status = "OK" if result else "FAIL"
    print(f"{basename}: {status}")