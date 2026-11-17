/* Gerado por `prova.py boot --target x86_64`: não edite. */
ENTRY(_boot)
SECTIONS
{
    . = 0x100000;
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
        . += 0x4000;
        __stack_top = .;
    }
    /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
