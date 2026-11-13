"""Mini-interpretador de GBNF (subconjunto usado em spec/prova.gbnf) para TESTAR a gramática.
Semântica por conjuntos de posições finais (sem backtracking exponencial)."""
import re

TOK = re.compile(r'\s*(?:("(?:[^"\\]|\\.)*")|(\[(?:[^\]\\]|\\.)*\])|;;[^\n]*\n|([A-Za-z_][\w-]*)|([()|*+?]))')
ESC = {"n": "\n", "t": "\t", "\\": "\\", '"': '"', "]": "]", "[": "[", "-": "-", "^": "^"}


def unescape(s):
    out, i = [], 0
    while i < len(s):
        if s[i] == "\\":
            out.append(ESC.get(s[i + 1], s[i + 1]))
            i += 2
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def charclass(body):
    neg = body.startswith("^")
    body = body[1:] if neg else body
    items, i = [], 0
    while i < len(body):
        c = body[i]
        if c == "\\":
            c = ESC.get(body[i + 1], body[i + 1])
            i += 1
        if i + 2 < len(body) and body[i + 1] == "-":
            hi = body[i + 2]
            items.append((c, hi))
            i += 3
        else:
            items.append((c, c))
            i += 1
    return lambda ch: (any(a <= ch <= b for a, b in items)) != neg


def parse_grammar(text):
    rules, cur = {}, None
    for line in text.splitlines():
        if line.strip().startswith("#") or not line.strip():
            continue
        m = re.match(r"^([A-Za-z_][\w-]*)\s*::=\s*(.*)$", line)
        if m:
            cur = m.group(1)
            rules[cur] = m.group(2)
        else:
            rules[cur] += " " + line.strip()
    return {k: _parse_rhs(v) for k, v in rules.items()}


def _parse_rhs(src):
    toks, pos = [], 0
    src = src.strip()
    while pos < len(src):
        m = TOK.match(src, pos)
        if not m:
            raise ValueError(f"token inválido em: {src[pos:pos+30]!r}")
        toks.append(m.group(m.lastindex))
        pos = m.end()
    i = 0

    def alt():
        nonlocal i
        seqs = [seq()]
        while i < len(toks) and toks[i] == "|":
            i += 1
            seqs.append(seq())
        return ("alt", seqs) if len(seqs) > 1 else seqs[0]

    def seq():
        nonlocal i
        items = []
        while i < len(toks) and toks[i] not in ("|", ")"):
            items.append(item())
        return ("seq", items)

    def item():
        nonlocal i
        t = toks[i]
        i += 1
        if t == "(":
            node = alt()
            assert toks[i] == ")", "faltou )"
            i += 1
        elif t.startswith('"'):
            node = ("lit", unescape(t[1:-1]))
        elif t.startswith("["):
            node = ("cls", charclass(t[1:-1]))
        else:
            node = ("ref", t)
        while i < len(toks) and toks[i] in ("*", "+", "?"):
            q = toks[i]
            i += 1
            node = ("rep", node, {"*": 0, "+": 1, "?": 0}[q], 1 if q == "?" else None)
        return node

    node = alt()
    assert i == len(toks), f"sobrou: {toks[i:]}"
    return node


class Matcher:
    def __init__(self, rules, text):
        self.rules, self.text, self.memo = rules, text, {}

    def m(self, node, pos):
        k = node[0]
        if k == "lit":
            return {pos + len(node[1])} if self.text.startswith(node[1], pos) else set()
        if k == "cls":
            return {pos + 1} if pos < len(self.text) and node[1](self.text[pos]) else set()
        if k == "ref":
            key = (node[1], pos)
            if key not in self.memo:
                self.memo[key] = set()  # corta recursão à esquerda (não usada)
                self.memo[key] = self.m(self.rules[node[1]], pos)
            return self.memo[key]
        if k == "seq":
            cur = {pos}
            for n in node[1]:
                nxt = set()
                for p in cur:
                    nxt |= self.m(n, p)
                cur = nxt
                if not cur:
                    break
            return cur
        if k == "alt":
            out = set()
            for n in node[1]:
                out |= self.m(n, pos)
            return out
        if k == "rep":
            _, n, mn, mx = node
            res, front, seen, cnt = set(), {pos}, {pos}, 0
            if mn == 0:
                res |= front
            while front and (mx is None or cnt < mx):
                nxt = set()
                for p in front:
                    nxt |= self.m(n, p)
                cnt += 1
                if cnt >= mn:
                    res |= nxt
                front = {p for p in nxt if p not in seen}
                seen |= front
            return res
        raise ValueError(k)


def accepts(rules, text, start="root"):
    # Strip ;; comments and normalize whitespace
    lines = text.splitlines()
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(";;"):
            continue
        cleaned_lines.append(stripped)
    cleaned = " ".join(cleaned_lines)
    return len(cleaned) in Matcher(rules, cleaned).m(("ref", start), 0)
