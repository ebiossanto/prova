"""Emissor MLIR (dialetos func/arith/memref/cf/llvm). As provas viram otimizações:
aritmética já provada sem overflow recebe flags nsw/nuw."""
from .check import ARITH, BIT_OPS, CMP, MMIO_OPS, SHIFT_OPS, WRAP_OPS, ProvaError, base, is_slice, show, ty

MLT = {"i64": "i64", "usize": "i64", "u8": "i8"}
# Ordens de memória: nomes do dialeto `llvm` (relaxed = monotonic). NÃO validado com mlir-opt.
MO = {"relaxed": "monotonic", "acquire": "acquire", "release": "release",
      "acq_rel": "acq_rel", "seq_cst": "seq_cst"}

# Convenção de syscalls Linux por arquitetura: registrador do número, de argumentos, de saída, clobbers.
ABI = {
    "x86_64": dict(insn="syscall", nr="rax", args=["rdi", "rsi", "rdx"], out="rax", clob=["rcx", "r11"]),
    "aarch64": dict(insn="svc #0", nr="x8", args=["x0", "x1", "x2"], out="x0", clob=[]),
    "riscv64": dict(insn="ecall", nr="a7", args=["a0", "a1", "a2"], out="a0", clob=[]),
}
NR = {"write": {"x86_64": 1, "aarch64": 64, "riscv64": 64},
      "exit": {"x86_64": 60, "aarch64": 93, "riscv64": 93}}
TRIPLE = {"x86_64": "x86_64-unknown-linux-gnu", "aarch64": "aarch64-unknown-linux-gnu",
          "riscv64": "riscv64-unknown-linux-gnu"}


class Em:
    def __init__(self, fn, cx, target, sigs=None, meta=None):
        self.fn, self.cx, self.target, self.sigs = fn, cx, target, sigs or {}
        self.meta = meta or {"statics": {}, "static_init": {}, "mmios": {}}
        self.o, self.n, self.term = [], 0, False
        self.params = {n for n, T in fn.params if not is_slice(T)}

    def t(self):
        self.n += 1
        return f"%t{self.n}"

    def bb(self):
        self.n += 1
        return f"^bb{self.n}"

    def w(self, line):
        self.o.append("    " + line)

    def label(self, l):
        self.o.append(f"  {l}:")
        self.term = False

    # ---- syscalls ----
    def syscall(self, name, args):
        abi = ABI[self.target]
        nr = self.t()
        self.w(f"{nr} = arith.constant {NR[name][self.target]} : i64")
        regs = ["{%s}" % abi["nr"]] + ["{%s}" % r for r in abi["args"][:len(args)]]
        cons = ",".join(["={%s}" % abi["out"]] + regs + ["~{%s}" % c for c in abi["clob"]] + ["~{memory}"])
        r = self.t()
        ops = ", ".join([nr] + args)
        tys = ", ".join(["i64"] * (1 + len(args)))
        self.w(f'{r} = llvm.inline_asm has_side_effects "{abi["insn"]}", "{cons}" {ops} : ({tys}) -> i64')
        return r

    def addr(self, b):
        x, y = self.t(), self.t()
        self.w(f"{x} = memref.extract_aligned_pointer_as_index %p_{b} : memref<?xi8> -> index")
        self.w(f"{y} = arith.index_cast {x} : index to i64")
        return y

    # ---- expressões ----
    def ex(self, e, want=None):
        cx = self.cx
        if isinstance(e, int):
            T = want or "i64"
            r = self.t()
            v = e - 256 if (T == "u8" and e > 127) else e  # i8 é com sinal no MLIR
            self.w(f"{r} = arith.constant {v} : {MLT[T]}")
            return r, T
        if isinstance(e, str):
            T = cx.types[e]
            if e in self.params:
                return f"%p_{e}", T
            r = self.t()
            self.w(f"{r} = memref.load %v_{e}[] : memref<{MLT[T]}>")
            return r, T
        op = e[0]
        if op in ARITH:
            T = ty(e, cx) or want or "i64"
            a, _ = self.ex(e[1], T)
            b, _ = self.ex(e[2], T)
            r = self.t()
            name = {"+": "addi", "-": "subi", "*": "muli"}[op]
            flag = "nsw" if T == "i64" else "nuw"
            self.w(f"{r} = arith.{name} {a}, {b} overflow<{flag}> : {MLT[T]}")
            return r, T
        if op in WRAP_OPS:
            T = ty(e, cx) or want or "usize"
            a, _ = self.ex(e[1], T)
            b, _ = self.ex(e[2], T)
            r = self.t()
            name = "addi" if op == "add_wrap" else "subi"
            self.w(f"{r} = arith.{name} {a}, {b} : {MLT[T]}")
            return r, T
        if op in BIT_OPS:
            T = ty(e, cx) or want or "usize"
            a, _ = self.ex(e[1], T)
            b, _ = self.ex(e[2], T)
            r = self.t()
            name = {"bit_and": "andi", "bit_or": "ori", "bit_xor": "xori"}[op]
            self.w(f"{r} = arith.{name} {a}, {b} : {MLT[T]}")
            return r, T
        if op in SHIFT_OPS:
            T = ty(e, cx) or want or "usize"
            a, _ = self.ex(e[1], T)
            b, _ = self.ex(e[2], T)
            r = self.t()
            name = "shli" if op == "shl" else ("shrsi" if T == "i64" else "shrui")
            self.w(f"{r} = arith.{name} {a}, {b} : {MLT[T]}")
            return r, T
        if op in CMP:
            T = ty(e[1], cx) or ty(e[2], cx) or "i64"
            a, _ = self.ex(e[1], T)
            b, _ = self.ex(e[2], T)
            sg = T == "i64"
            pred = {"<": "slt" if sg else "ult", "<=": "sle" if sg else "ule",
                    ">": "sgt" if sg else "ugt", ">=": "sge" if sg else "uge",
                    "=": "eq", "!=": "ne"}[op]
            r = self.t()
            self.w(f"{r} = arith.cmpi {pred}, {a}, {b} : {MLT[T]}")
            return r, "bool"
        if op in ("and", "or"):
            acc, _ = self.ex(e[1])
            for x in e[2:]:
                b, _ = self.ex(x)
                r = self.t()
                self.w(f"{r} = arith.{'andi' if op == 'and' else 'ori'} {acc}, {b} : i1")
                acc = r
            return acc, "bool"
        if op == "not":
            a, _ = self.ex(e[1])
            one, r = self.t(), self.t()
            self.w(f"{one} = arith.constant true")
            self.w(f"{r} = arith.xori {a}, {one} : i1")
            return r, "bool"
        if op == "len":
            c0, d, r = self.t(), self.t(), self.t()
            self.w(f"{c0} = arith.constant 0 : index")
            self.w(f"{d} = memref.dim %p_{e[1]}, {c0} : memref<?xi8>")
            self.w(f"{r} = arith.index_cast {d} : index to i64")
            return r, "usize"
        if op == "load":
            i, _ = self.ex(e[2], "usize")
            ix, r = self.t(), self.t()
            self.w(f"{ix} = arith.index_cast {i} : i64 to index")
            self.w(f"{r} = memref.load %p_{e[1]}[{ix}] : memref<?xi8>")
            return r, "u8"
        if op == "cast":
            T = e[1]
            v, Ti = self.ex(e[2])
            if MLT[Ti] == MLT[T]:
                return v, T
            r = self.t()
            if Ti == "u8":
                self.w(f"{r} = arith.extui {v} : i8 to i64")
            else:
                self.w(f"{r} = arith.trunci {v} : i64 to i8")
            return r, T
        if op == "sys_write":
            fd, _ = self.ex(e[1], "i64")
            p = self.addr(e[2])
            n, _ = self.ex(e[3], "usize")
            return self.syscall("write", [fd, p, n]), "i64"
        if op == "call":
            g = self.sigs[e[1]]
            args, tys = [], []
            for (pn, PT), a in zip(g.params, e[2:]):
                if is_slice(PT):
                    args.append(f"%p_{a}")
                    tys.append("memref<?xi8>")
                else:
                    v, _ = self.ex(a, PT)
                    args.append(v)
                    tys.append(MLT[PT])
            head = f"func.call @{g.name}({', '.join(args)}) : ({', '.join(tys)})"
            if g.ret == "unit":
                self.w(head + " -> ()")
                return None, "unit"
            r = self.t()
            self.w(f"{r} = {head} -> {MLT[g.ret]}")
            return r, g.ret
        if op in ("atomic_load", "atomic_store", "atomic_fetch_add", "atomic_cas"):
            return self.atomic(e)
        if op in MMIO_OPS:
            return self.mmio(e)
        raise ProvaError(f"emissão: forma desconhecida {show(e)}")

    def atomic(self, e):
        """Atômicos sobre (static ...): ops reais do dialeto llvm, com a ordem escolhida pelo programa."""
        op, name = e[0], e[1]
        T = self.meta["statics"][name]
        p = self.t()
        self.w(f"{p} = llvm.mlir.addressof @{name} : !llvm.ptr")
        if op == "atomic_load":
            r = self.t()
            self.w(f"{r} = llvm.load {p} atomic {MO[e[2]]} {{alignment = 8 : i64}} : !llvm.ptr -> i64")
            return r, T
        v, _ = self.ex(e[2], T)
        if op == "atomic_store":
            self.w(f"llvm.store {v}, {p} atomic {MO[e[3]]} {{alignment = 8 : i64}} : i64, !llvm.ptr")
            return None, "unit"
        if op == "atomic_fetch_add":
            r = self.t()
            self.w(f"{r} = llvm.atomicrmw add {p}, {v} {MO[e[3]]} : !llvm.ptr, i64")
            return r, T
        n, _ = self.ex(e[3], T)
        c, r = self.t(), self.t()
        self.w(f"{c} = llvm.cmpxchg {p}, {v}, {n} {MO[e[4]]} {MO[e[5]]} : !llvm.ptr, i64")
        self.w(f"{r} = llvm.extractvalue {c}[0] : !llvm.struct<(i64, i1)>")
        return r, T

    def mmio(self, e):
        """Acesso volátil a registrador mapeado em memória (mmio nome endereco T regiao)."""
        op, name = e[0], e[1]
        info = self.meta["mmios"][name]
        T, addr = info["type"], info["addr"]
        align = 1 if T == "u8" else 8
        a, p = self.t(), self.t()
        self.w(f"{a} = arith.constant {addr} : i64")
        self.w(f"{p} = llvm.inttoptr {a} : i64 to !llvm.ptr")
        if op == "mmio_read":
            r = self.t()
            self.w(f"{r} = llvm.load volatile {p} {{alignment = {align} : i64}} : !llvm.ptr -> {MLT[T]}")
            return r, T
        v, _ = self.ex(e[2], T)
        self.w(f"llvm.store volatile {v}, {p} {{alignment = {align} : i64}} : {MLT[T]}, !llvm.ptr")
        return None, "unit"

    # ---- instruções ----
    def block(self, stmts):
        for s in stmts:
            if self.term:
                break
            self.stmt(s)

    def stmt(self, s):
        h = s[0]
        cx = self.cx
        if h in ("let", "var"):
            v, _ = self.ex(s[3], s[2])
            self.w(f"memref.store {v}, %v_{s[1]}[] : memref<{MLT[s[2]]}>")
        elif h == "set":
            T = cx.types[s[1]]
            v, _ = self.ex(s[2], T)
            self.w(f"memref.store {v}, %v_{s[1]}[] : memref<{MLT[T]}>")
        elif h == "let_slice":
            pass  # emitido no bloco de entrada (domina todos os usos)
        elif h == "store":
            i, _ = self.ex(s[2], "usize")
            v, _ = self.ex(s[3], "u8")
            ix = self.t()
            self.w(f"{ix} = arith.index_cast {i} : i64 to index")
            self.w(f"memref.store {v}, %p_{s[1]}[{ix}] : memref<?xi8>")
        elif h == "do":
            self.ex(s[1])
        elif h in ("atomic_store", "mmio_write"):
            self.ex(s)
        elif h in ("assert", "drop"):
            pass  # provado em tempo de compilação: nenhum código em tempo de execução
        elif h == "return":
            if self.fn.ret == "unit":
                self.w("func.return")
            else:
                v, _ = self.ex(s[1], self.fn.ret)
                self.w(f"func.return {v} : {MLT[self.fn.ret]}")
            self.term = True
        elif h == "sys_exit":
            c, _ = self.ex(s[1], "i64")
            self.syscall("exit", [c])
            self.w("llvm.unreachable")
            self.term = True
        elif h == "if":
            c, _ = self.ex(s[1])
            bt, be, bj = self.bb(), self.bb(), self.bb()
            self.w(f"cf.cond_br {c}, {bt}, {be}")
            th = [f for f in s[2:] if f[0] == "then"]
            el = [f for f in s[2:] if f[0] == "else"]
            for lab, part in ((bt, th), (be, el)):
                self.label(lab)
                self.block(part[0][1:] if part else [])
                if not self.term:
                    self.w(f"cf.br {bj}")
            self.label(bj)
        elif h == "while":
            bh, bb_, bx = self.bb(), self.bb(), self.bb()
            self.w(f"cf.br {bh}")
            self.label(bh)
            c, _ = self.ex(s[1])
            self.w(f"cf.cond_br {c}, {bb_}, {bx}")
            self.label(bb_)
            self.block([f for f in s[2:] if f[0] not in ("invariant", "decreases")])
            self.w(f"cf.br {bh}")
            self.label(bx)
        else:
            raise ProvaError(f"emissão: instrução desconhecida {show(s)}")

    def hoist(self, node):
        if isinstance(node, list):
            if node and node[0] == "let_slice":
                name, d = node[1], node[2][1]
                L = self.cx.data[d]
                self.w(f"%g_{name} = memref.get_global @{d} : memref<{L}xi8>")
                self.w(f"%p_{name} = memref.cast %g_{name} : memref<{L}xi8> to memref<?xi8>")
            else:
                for x in node:
                    self.hoist(x)

    def emit(self):
        fn, cx = self.fn, self.cx
        sig = []
        for n, T in fn.params:
            sig.append(f"%p_{n}: " + ("memref<?xi8>" if is_slice(T) else MLT[T]))
        ret = "" if fn.ret == "unit" else f" -> {MLT[fn.ret]}"
        # _start recebe a pilha do kernel sem alinhamento de chamada: pede realinhamento ao LLVM.
        attrs = ' attributes {passthrough = ["noreturn", "stackrealign"]}' if fn.name == "_start" else ""
        out = [f"  func.func @{fn.name}({', '.join(sig)}){ret}{attrs} {{"]
        for x, T in cx.types.items():
            if x not in self.params:
                self.w(f"%v_{x} = memref.alloca() : memref<{MLT[T]}>")
        self.hoist(fn.body)
        self.block(fn.body)
        if not self.term:
            self.w("func.return" if fn.ret == "unit" else "llvm.unreachable")
        return "\n".join(out + self.o + ["  }"])


def emit_module(fns_cx, data_bytes, target, meta=None):
    meta = meta or (fns_cx[0][1].meta if fns_cx else None) or {"statics": {}, "static_init": {}, "mmios": {}}
    parts = ["module {"]
    for name in meta["statics"]:
        parts.append(f"  llvm.mlir.global internal @{name}({meta['static_init'][name]} : i64) : i64")
    for name, b in data_bytes.items():
        vals = ", ".join(str(x - 256 if x > 127 else x) for x in b)
        parts.append(f'  memref.global "private" constant @{name} : memref<{len(b)}xi8> = dense<[{vals}]>')
    sigs = {fn.name: fn for fn, _ in fns_cx}
    for fn, cx in fns_cx:
        parts.append(Em(fn, cx, target, sigs, meta).emit())
    parts.append("}")
    return "\n".join(parts) + "\n"
