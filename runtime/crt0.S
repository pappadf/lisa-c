| Lisa Office System main-program startup for C programs.
|
| Mirrors the prologue/epilogue the Lisa Pascal compiler emits for a main
| program (see QD/sample.Obj on the Workshop disk): PASLIB's %_BEGIN/%_INIT
| set up the runtime and the standard INPUT/OUTPUT files (pointers at 8(A5)
| and 12(A5)), %_TERM/%_END shut it down.
|
| Calls into intrinsic units use the IU emulated instructions: the 32-bit
| word $A0xxxxxx is an A-line trap whose low 24 bits are the absolute
| logical address of the routine's jump vector (see lisa.inc).

#include "lisa.inc"

        .section .text.entry,"ax"
        .globl  _start
        .type   _start,@function
_start:
        IUJSR   PL_BEGIN
        link.w  %fp,#0
        move.l  (%sp)+,%fp
        link.w  %a5,#-MAINSIZE          | main program global frame
        suba.l  16(%a5),%sp
        IUJSR   PL_INIT

        jsr     __lisa_init             | data segment, .data/.bss
        jsr     main
        move.l  %d0,-(%sp)
        jsr     __lisa_fini             | flush stdio etc.
        addq.l  #4,%sp

        .globl  __lisa_exit_tail
        .type   __lisa_exit_tail,@function
__lisa_exit_tail:                       | _exit() jumps here; unlk a5 resets sp
        IUJSR   PL_TERM
        unlk    %a5
        IUJSR   PL_END
        rts

        .section .note.GNU-stack,"",@progbits
