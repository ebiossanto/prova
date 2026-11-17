"""Leitor de S-expressions. Gramática fechada: só parênteses, símbolos, inteiros e strings."""
import re


class Str(str):
    """Literal de string (distinto de símbolo)."""


class ParseError(Exception):
    pass


_ATOM = re.compile(r'[^\s()";]+')
_INT = re.compile(r'-?\d+$')


def parse(src):
    toks, i, line = [], 0, 1
    while i < len(src):
        c = src[i]
        if c == "\n":
            line += 1
            i += 1
        elif c.isspace():
            i += 1
        elif c == ";":
            while i < len(src) and src[i] != "\n":
                i += 1
        elif c in "()":
            toks.append((c, None, line))
            i += 1
        elif c == '"':
            j = src.find('"', i + 1)
            if j < 0:
                raise ParseError(f"linha {line}: string não terminada")
            toks.append(("str", Str(src[i + 1:j].replace("\\n", "\n")), line))
            i = j + 1
        else:
            m = _ATOM.match(src, i)
            a = m.group(0)
            i = m.end()
            toks.append(("int", int(a), line) if _INT.match(a) else ("sym", a, line))
    pos = 0

    def rd():
        nonlocal pos
        t = toks[pos]
        pos += 1
        if t[0] == "(":
            out = []
            while True:
                if pos >= len(toks):
                    raise ParseError(f"linha {t[2]}: '(' sem ')' correspondente")
                if toks[pos][0] == ")":
                    pos += 1
                    return out
                out.append(rd())
        if t[0] == ")":
            raise ParseError(f"linha {t[2]}: ')' inesperado")
        return t[1]

    forms = []
    while pos < len(toks):
        forms.append(rd())
    return forms
