"""Boot bare-metal gerado por arquitetura: stub (pilha + zerar .bss + chamar a função Prova)
e linker script. Uma descrição por alvo; ninguém escreve assembly à mão por programa.

Estado de teste: x86_64 montado, ligado e EXECUTADO (tests/test_boot.py).
aarch64 e riscv64: só verificados estruturalmente (sem toolchain/QEMU no ambiente de desenvolvimento).
"""
import re

TARGETS = ("x86_64", "aarch64", "riscv64")
STACK_BYTES = 0x4000
# Endereços de carga: x86_64 = fora do 1º MiB (bootloader/teste em user-mode); aarch64 = RAM da `virt`
# do QEMU; riscv64 = RAM da `virt` com `-bios none` (com OpenSBI use --base 0x80200000).
BASE = {"x86_64": 0x100000, "aarch64": 0x40080000, "riscv64": 0x80000000}

_ASM = {
    "x86_64": """\
# Gerado por `prova.py boot --target x86_64`: não edite.
        .section .text.boot, "ax", @progbits
        .globl  _boot
        .type   _boot, @function
_boot:
        lea     __stack_top(%rip), %rsp      # pilha alinhada a 16 bytes
        lea     __bss_start(%rip), %rdi
        lea     __bss_end(%rip), %rcx
        sub     %rdi, %rcx
        xor     %eax, %eax
        cld
        rep stosb                            # zera .bss
        call    @ENTRY@
.Lhang:
        hlt
        jmp     .Lhang
""",
    "aarch64": """\
// Gerado por `prova.py boot --target aarch64`: não edite. Assume 1 núcleo (-smp 1).
        .section .text.boot, "ax", %progbits
        .globl  _boot
        .type   _boot, %function
_boot:
        mrs     x0, CPACR_EL1                // habilita FP/SIMD (o LLVM pode usar em memcpy/memset)
        orr     x0, x0, #(3 << 20)
        msr     CPACR_EL1, x0
        isb
        adrp    x0, __stack_top
        add     x0, x0, :lo12:__stack_top
        mov     sp, x0
        adrp    x1, __bss_start
        add     x1, x1, :lo12:__bss_start
        adrp    x2, __bss_end
        add     x2, x2, :lo12:__bss_end
1:      cmp     x1, x2
        b.hs    2f
        str     xzr, [x1], #8                // zera .bss (alinhado a 16 pelo linker script)
        b       1b
2:      bl      @ENTRY@
3:      wfe
        b       3b
""",
    "riscv64": """\
# Gerado por `prova.py boot --target riscv64`: não edite. Assume 1 hart (-smp 1).
        .section .text.boot, "ax", @progbits
        .globl  _boot
        .type   _boot, @function
_boot:
        la      sp, __stack_top
        la      t0, __bss_start
        la      t1, __bss_end
1:      bgeu    t0, t1, 2f
        sd      zero, 0(t0)                  # zera .bss (alinhado a 16 pelo linker script)
        addi    t0, t0, 8
        j       1b
2:      call    @ENTRY@
3:      wfi
        j       3b
""",
}

_LD = """\
/* Gerado por `prova.py boot --target @TARGET@`: não edite. */
ENTRY(_boot)
SECTIONS
{
    . = @BASE@;
    .text   : { KEEP(*(.text.boot)) *(.text .text.*) }
    .rodata : { *(.rodata .rodata.*) }
    .data   : { *(.data .data.*) }
    .bss (NOLOAD) : ALIGN(16)
    {
        __bss_start = .;
        *(.bss .bss.*) *(COMMON)
        . = ALIGN(16);
        __bss_end = .;
    }
    .stack (NOLOAD) : ALIGN(16)
    {
        __stack_bottom = .;
        . += @STACK@;
        __stack_top = .;
    }
    /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
"""


def _check(target, entry):
    if target not in TARGETS:
        raise ValueError(f"alvo desconhecido: {target}")
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", entry):
        raise ValueError(f"nome de entrada inválido: {entry!r}")


def boot_asm(target, entry="kmain"):
    _check(target, entry)
    return _ASM[target].replace("@ENTRY@", entry)


def linker_script(target, base=None, stack=STACK_BYTES, entry="kmain"):
    _check(target, entry)
    b = BASE[target] if base is None else base
    return (_LD.replace("@TARGET@", target).replace("@BASE@", hex(b))
            .replace("@STACK@", hex(stack)))
