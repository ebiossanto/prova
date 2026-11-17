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
        call    kmain
.Lhang:
        hlt
        jmp     .Lhang
