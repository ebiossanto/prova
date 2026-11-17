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
2:      bl      kmain
3:      wfe
        b       3b
