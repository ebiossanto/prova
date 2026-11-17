import sys
sys.path.insert(0, "tests")
from gbnf import accepts, parse_grammar
import glob, os

root = "D:/PROVA linguagem"
with open(os.path.join(root, "spec", "prova.gbnf"), encoding="utf-8") as f:
    rules = parse_grammar(f.read())

# Test all examples with cleaned text (strip ;; comment lines)
for f in sorted(glob.glob(os.path.join(root, "examples", "*.prova"))):
    with open(f, encoding="utf-8") as fh:
        text = fh.read()
    # Clean: remove lines starting with ;;
    lines = text.splitlines()
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(";;"):
            continue
        cleaned_lines.append(line)  # keep original line with indentation
    cleaned = "\n".join(cleaned_lines)
    result = accepts(rules, cleaned)
    basename = os.path.basename(f)
    status = "ACEITA" if result else "REJEITA"
    print(f"{basename}: {status}")