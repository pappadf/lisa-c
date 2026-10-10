| C-callable glue to PASLIB console output.
|
| Pascal routines pop their own arguments and may clobber D0-D2/A0-A1; GCC
| expects D2-D7/A2-A6 preserved, so each stub saves everything it might lose.

#include "lisa.inc"

#define SAVED   %d2-%d7/%a2-%a6
#define NSAVED  44                      /* 11 registers * 4 */

        .text

| void lisa_write_pstr(const unsigned char *pstr)  -- WRITE(OUTPUT, pstr)
        .globl  lisa_write_pstr
        .type   lisa_write_pstr,@function
lisa_write_pstr:
        movem.l SAVED,-(%sp)
        move.l  A5_OUTPUT(%a5),-(%sp)           | file
        move.l  NSAVED+4+4(%sp),-(%sp)          | @string
        clr.w   -(%sp)                          | field width 0
        IUJSR   PL_W_STR
        movem.l (%sp)+,SAVED
        rts

| void lisa_writeln(void)  -- WRITELN(OUTPUT)
        .globl  lisa_writeln
        .type   lisa_writeln,@function
lisa_writeln:
        movem.l SAVED,-(%sp)
        move.l  A5_OUTPUT(%a5),-(%sp)
        IUJSR   PL_W_LN
        movem.l (%sp)+,SAVED
        rts

| void lisa_write_char(int c)  -- WRITE(OUTPUT, c)
        .globl  lisa_write_char
        .type   lisa_write_char,@function
lisa_write_char:
        movem.l SAVED,-(%sp)
        move.l  A5_OUTPUT(%a5),-(%sp)
        move.b  NSAVED+4+4+3(%sp),-(%sp)        | char in the high byte of a word
        clr.w   -(%sp)
        IUJSR   PL_W_C
        movem.l (%sp)+,SAVED
        rts

| int lisa_read_char(void)  -- READ(INPUT, c)
        .globl  lisa_read_char
        .type   lisa_read_char,@function
lisa_read_char:
        movem.l SAVED,-(%sp)
        move.l  A5_INPUT(%a5),-(%sp)
        IUJSR   PL_R_C
        moveq   #0,%d0
        move.b  (%sp),%d0                       | result byte is the high byte
        addq.l  #2,%sp
        movem.l (%sp)+,SAVED
        rts

| int lisa_eoln(void)  -- EOLN(INPUT)
        .globl  lisa_eoln
        .type   lisa_eoln,@function
lisa_eoln:
        movem.l SAVED,-(%sp)
        move.l  A5_INPUT(%a5),-(%sp)
        IUJSR   PL_EOLN
        moveq   #0,%d0
        move.b  (%sp),%d0
        addq.l  #2,%sp
        movem.l (%sp)+,SAVED
        rts

| void lisa_readln(void)  -- READLN(INPUT)
        .globl  lisa_readln
        .type   lisa_readln,@function
lisa_readln:
        movem.l SAVED,-(%sp)
        move.l  A5_INPUT(%a5),-(%sp)
        IUJSR   PL_R_LN
        movem.l (%sp)+,SAVED
        rts

| long lisa_my_id(void)  -- OS function My_ID (subcode 59): the process id.
| An OS function returns its result in a slot the caller reserves.
        .globl  lisa_my_id
        .type   lisa_my_id,@function
lisa_my_id:
        movem.l SAVED,-(%sp)
        clr.l   -(%sp)                          | result slot
        jsr     1f
        move.l  (%sp)+,%d0
        movem.l (%sp)+,SAVED
        rts
1:      tst.w   -6144(%sp)
        move.w  #59,%d0
        move.w  #0,%d1
        trap    #1

        .section .note.GNU-stack,"",@progbits
