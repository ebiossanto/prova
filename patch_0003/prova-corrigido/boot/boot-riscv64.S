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
2:      call    kmain
3:      wfi
        j       3b
