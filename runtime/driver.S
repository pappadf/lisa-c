| Configurable-driver runtime: the entry point and the OS service thunks
| (runtime/lisa_driver.h).
|
| The OS loads the driver's code anywhere in the driver space and enters it at
| its first byte, so .text.entry (linked first) branches to DRIVER, the
| driver's pascal function.
|
| The services are reached through the driver jump table whose address is the
| long at $210 (DRIVERASM: MOVE.L DRIVRJT,A0 / JMP n(A0)).  They are Lisa
| Pascal and do not preserve every register C expects (D3 and A2 at least), so
| each thunk saves D2-D7/A2-A6, copies the arguments and the result slot below
| the save area, calls the service, copies the result back, restores the
| registers and pops the arguments as a Pascal callee must -- the same shape
| as the library thunks (tools/gen_iu_thunks.py).  A5 is the OS's throughout.

        .section .text.entry,"ax"
        .globl  _driver_entry
_driver_entry:
        bra.w   DRIVER

        .text

| svc NAME, OFFSET (in the jump table), ARGBYTES, RESULTBYTES
        .macro  svc name, off, n, r
        .section .text.\name,"ax"
        .globl  \name
        .type   \name,@function
\name:
        movem.l %d2-%d7/%a2-%a6,-(%sp)
        .if     \n + \r
        lea     44+4+\n+\r(%sp),%a0     | end of the arguments and result slot
        moveq   #(\n+\r)/2-1,%d0
1:      move.w  -(%a0),-(%sp)
        dbf     %d0,1b
        .endif
        movea.l 0x210.w,%a0             | the driver jump table
        jsr     \off(%a0)
        .if     \r == 2
        move.w  (%sp)+,%d0
        move.w  %d0,44+4+\n(%sp)
        .endif
        .if     \r == 4
        move.l  (%sp)+,%d0
        move.l  %d0,44+4+\n(%sp)
        .endif
        movem.l (%sp)+,%d2-%d7/%a2-%a6
        move.l  (%sp)+,%a0
        .if     \n
        lea     \n(%sp),%sp
        .endif
        jmp     (%a0)
        .endm

        svc     CANCEL_REQ,     0,   4, 0
        svc     ENQUEUE,        6,  12, 0
        svc     DEQUEUE,       12,   8, 0
        svc     RELSPACE,      18,   8, 0
        svc     GETSPACE,      24,  10, 2
        svc     SYSTEM_ERROR,  30,   2, 0
        svc     MACH_INFO,     42,   8, 0
        svc     UNBLK_REQ,     48,   6, 0
        svc     BLK_REQ,       54,   8, 0
        svc     FREEZE_SEG,    66,  20, 0
        svc     UNFREEZE_SEG,  72,   4, 0
        svc     ADJ_IO_CNT,    78,   6, 0
        svc     CVT_BUFF_ADDR, 84,  22, 0
        svc     CALLDRIVER,    90,  12, 0
        svc     INTSOFF,       96,   6, 0
        svc     INTSON,       102,   2, 0
        svc     LOG,          114,   8, 0
        svc     LOGGING,      120,   0, 2
        svc     CHAIN_FORWARD,126,   4, 4
        svc     DISKSYNC,     132,   2, 0
        svc     MICROTIMER,   138,   0, 4
        svc     ALARM_ASSIGN, 144,  10, 0
        svc     ALARMRETURN,  150,   2, 0
        svc     ALARMRELATIVE,156,   6, 0
        svc     ALARMOFF,     162,   2, 0
        svc     LINK_TO_PCB,  168,   4, 0
        svc     KEYPUSHED,    192,   2, 0

        .section .note.GNU-stack,"",@progbits
