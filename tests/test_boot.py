"""Boot bare-metal: arquivos em boot/ não derivam do gerador; estrutura por arquitetura; e, no x86-64
Linux com `as`/`ld`, o stub é MONTADO, LIGADO e EXECUTADO (pilha alinhada e na região, .bss zerado)."""
import os, platform, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from provac.boot import BASE, TARGETS, boot_asm, linker_script  # noqa: E402

KMAIN_SCAFFOLD = """\
        .text
        .globl kmain
kmain:                                   # andaime de teste; o kmain real vem do Prova
        mov     %rsp, %rax
        add     $8, %rax
        test    $15, %rax
        jnz     bad                      # pilha desalinhada antes do call
        lea     __stack_bottom(%rip), %rcx
        cmp     %rcx, %rsp
        jb      bad
        lea     __stack_top(%rip), %rcx
        cmp     %rcx, %rsp
        ja      bad
        cmpq    $0, probe(%rip)          # .bss precisa estar zerado
        jne     bad
        movq    $1, probe(%rip)          # e gravável
        xor     %edi, %edi
        jmp     done
bad:    mov     $1, %edi
done:   mov     $60, %eax
        syscall
        .bss
        .globl probe
probe:  .quad 0
"""


def read(path):
    return open(os.path.join(ROOT, path), encoding="utf-8").read()


def test_checked_in_boot_files_match_the_generator():
    for t in TARGETS:
        assert read(f"boot/boot-{t}.S") == boot_asm(t), f"boot/boot-{t}.S diverge do gerador (rode prova.py boot)"
        assert read(f"boot/linker-{t}.ld") == linker_script(t), f"boot/linker-{t}.ld diverge do gerador"


def test_stub_structure_per_architecture():
    marks = {"x86_64": ("call    kmain", "hlt", "rep stosb"),
             "aarch64": ("bl      kmain", "wfe", "CPACR_EL1"),
             "riscv64": ("call    kmain", "wfi", "bgeu")}
    for t, needed in marks.items():
        text = boot_asm(t)
        for sym in ("_boot", "__stack_top", "__bss_start", "__bss_end"):
            assert sym in text, (t, sym)
        for m in needed:
            assert m in text, (t, m)
    assert "call    meu_main" in boot_asm("x86_64", entry="meu_main")


def test_invalid_names_are_rejected():
    for bad in ("Kmain", "k main", "1k", "k;rm"):
        try:
            boot_asm("x86_64", entry=bad)
        except ValueError:
            continue
        raise AssertionError(f"entry inválido aceito: {bad!r}")
    try:
        boot_asm("mips")
    except ValueError:
        pass
    else:
        raise AssertionError("alvo desconhecido aceito")


def test_linker_script_layout():
    for t in TARGETS:
        ld = linker_script(t)
        assert "ENTRY(_boot)" in ld and hex(BASE[t]) in ld
        assert ld.index("__bss_start") < ld.index("__bss_end") < ld.index("__stack_bottom") < ld.index("__stack_top")
    assert "0x80200000" in linker_script("riscv64", base=0x80200000)  # com OpenSBI


def test_x86_64_stub_assembles_links_and_runs():
    if not (sys.platform.startswith("linux") and platform.machine() in ("x86_64", "AMD64")):
        raise unittest.SkipTest("precisa de Linux x86-64")
    if not (shutil.which("as") and shutil.which("ld")):
        raise unittest.SkipTest("precisa de `as` e `ld` (binutils)")
    with tempfile.TemporaryDirectory() as d:
        def w(name, text):
            p = os.path.join(d, name)
            open(p, "w", encoding="utf-8").write(text)
            return p
        boot, km, ld = w("boot.S", boot_asm("x86_64")), w("kmain.S", KMAIN_SCAFFOLD), w("k.ld", linker_script("x86_64"))
        for src, obj in ((boot, "boot.o"), (km, "kmain.o")):
            r = subprocess.run(["as", src, "-o", os.path.join(d, obj)], capture_output=True, text=True)
            assert r.returncode == 0, r.stderr
        exe = os.path.join(d, "kern")
        r = subprocess.run(["ld", "-T", ld, "-nostdlib", "-o", exe, os.path.join(d, "boot.o"), os.path.join(d, "kmain.o")],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        r = subprocess.run([exe])
        assert r.returncode == 0, f"stub de boot falhou (1 = pilha/alinhamento/.bss): código {r.returncode}"
