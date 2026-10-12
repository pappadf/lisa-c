/* Configurable device drivers for the Lisa OS (LOS 3.x), in C.
 *
 * A configurable driver is a file SYSTEM.CD_<name> on the boot volume that
 * the OS loads when the device at a position (slot, channel, device) is first
 * used: at boot from the configuration in parameter memory, or at any time
 * after CDMAKE (lisa_os.h).  The OS copies its code into the shared driver
 * space at an address of its choosing, without relocating it, maps it
 * read-only, and calls its entry point, the function
 *
 *     pascal int16_t DRIVER(params *parameters)
 *
 * with the function code (dinit, seqio, dinterrupt, ...) in the parameter
 * record.  So a driver:
 *   - is position-independent (lisa-c compiles it with -mpcrel, and the
 *     linker rewrites the absolute calls left in library code);
 *   - has no writable globals: its state lives in a control block it takes
 *     with GETSPACE at dinit and hangs off configptr->cb_addr;
 *   - must not touch A5 (the OS's; lisa-c builds with -ffixed-a5);
 *   - calls the OS only through the services below (the driver jump table
 *     at $210), and wakes a process only by completing its request.
 *
 * Build:  make PROG=<name> driver  -> build/<name>.drv, the SYSTEM.CD_ file.
 * The layouts are Apple's unit DRIVERDEFS (Lisa Pascal), the services its
 * DRIVERSUBS; examples/loopdrv is a complete driver. */
#ifndef LISA_DRIVER_H
#define LISA_DRIVER_H
#include <stdint.h>
#if !defined(pascal)
#error "lisa_driver.h needs a compiler with the pascal attribute (Retro68 GCC)"
#endif

typedef int32_t absptr;

/* function codes (params.fnctn_code) */
enum {
    dinterrupt = 0, dinit = 1, ddown = 2, dskunclamp = 3, dskformat = 4, seqio = 5, dskio = 6,
    dcontrol = 7, reqrestart = 8, ddiscon = 9, dattach = 12, hdinit = 13, hdskio = 14,
    dunattach = 16, dalarms = 17, hddown = 18
};

/* interrupt levels for INTSOFF (intsoff_type) */
enum { allints = 0x700, rsints = 0x600, slotints = 0x500, copsints = 0x200, clokints = 0x100 };

/* devtype */
enum { diskdev, pascalbd, seqdev, bitbkt, non_io };

/* sysglobal: the base of the OS's system data area, for GETSPACE/RELSPACE,
   ENQUEUE/DEQUEUE (b_sysglobal_ptr, the long at bsysglob = $200).  Read with
   an instruction: GCC treats a pointer to a fixed low address as invalid. */
static inline absptr b_sysglobal(void)
{
    absptr v;
    __asm__ volatile("move.l 0x200.w,%0" : "=d"(v));
    return v;
}
#define B_SYSGLOBAL b_sysglobal()

typedef struct linkage {        /* relative links in sysglobal */
    int16_t fwd_link, bkwd_link;
} linkage;

typedef struct devrec {         /* a configinfo entry (68 bytes) */
    absptr entry_pt;            /* driver entry; 0 until loaded */
    absptr cb_addr;             /* the driver's control block for this device */
    absptr ext_addr;            /* ext_diskconfig for a disk device */
    absptr drvrec_ptr;          /* driver-loading record; 0: built-in */
    unsigned char devname[34];  /* e_name, string[32] */
    int8_t slot_no, iochannel, device_no;
    uint8_t devt;               /* devtype */
    uint8_t blockstructured, permanent;
    int16_t self_ident;
    struct devrec *required_drvr;   /* the parent's entry, or 0 */
    struct reqblk *permreq_ptr;     /* pre-allocated request block, or 0 */
    uint8_t preq_avail, pad;
} devrec;

typedef struct reqblk {         /* an I/O request (40 bytes) */
    absptr pcb_chain_headr;     /* rb_headT: pcb_chain */
    uint8_t pcb_chain_kind, pad0;
    linkage dev_chain;          /* the driver's queue */
    linkage list_chain;
    struct reqblk *unblk_chain;
    int8_t blk_in_pcb, pad1;
    uint8_t reqsrv_f, reqsuccess_f, reqabt_f, pad2;   /* reqsts_type */
    int8_t operatn, pad3;       /* 0 = write, 1 = read, ... */
    devrec *cfigptr;
    absptr req_extent;          /* seq_extend * (seqdev) or disk_extend * (diskdev) */
    int16_t hard_error;         /* error code when the request fails */
    int32_t reqspec_info;
} reqblk;

typedef struct seq_extend {     /* a sequential request's extension (22 bytes) */
    int32_t xfer_count;         /* bytes transferred: the driver sets it */
    uint8_t read_flag, pad;
    absptr buff_rdb_ptr;        /* the user buffer, for FREEZE_SEG/ADJ_IO_CNT */
    absptr buff_offset;
    absptr resolved_addr;
    int32_t num_bytes;          /* bytes asked for */
} seq_extend;

typedef struct params {         /* what DRIVER is called with (12 bytes) */
    devrec *configptr;
    int16_t fnctn_code;
    union {
        reqblk *req;            /* seqio, dskio, reqrestart */
        int16_t intpar;         /* dinterrupt (SCC: 0 Tx, 1 ext/status, 2 Rx, 3 special), dalarms */
        absptr parptr;          /* dcontrol: a dc_rec * */
        devrec *n_configptr;    /* dattach */
        devrec *o_configptr;    /* dunattach */
    };
    uint8_t still_inuse, pad;   /* dunattach */
} params;

typedef struct dc_rec {         /* DEVICE_CONTROL's parameter (44 bytes) */
    int16_t dversion;           /* 2 */
    int16_t dcode;
    int32_t ar10[10];
} dc_rec;

typedef struct minfo {
    int32_t cpu_board, io_board, memsize;
} minfo;

_Static_assert(sizeof(devrec) == 68 && __builtin_offsetof(devrec, slot_no) == 50 &&
               __builtin_offsetof(devrec, required_drvr) == 58, "devrec layout");
_Static_assert(sizeof(reqblk) == 40 && __builtin_offsetof(reqblk, operatn) == 24 &&
               __builtin_offsetof(reqblk, req_extent) == 30 && __builtin_offsetof(reqblk, hard_error) == 34,
               "reqblk layout");
_Static_assert(sizeof(seq_extend) == 22 && __builtin_offsetof(seq_extend, num_bytes) == 18, "seq_extend layout");
_Static_assert(sizeof(params) == 12 && __builtin_offsetof(params, req) == 6 &&
               __builtin_offsetof(params, still_inuse) == 10, "params layout");
_Static_assert(sizeof(dc_rec) == 44, "dc_rec layout");

/* The entry point: define it in the driver.  Returns 0 or an OS error. */
pascal int16_t DRIVER(params *parameters);

/* OS services (DRIVERSUBS), through the driver jump table at $210.  Booleans
   are uint8_t; `var` parameters are pointers. */
pascal void CANCEL_REQ(reqblk *req);
pascal void ENQUEUE(linkage *newlink, linkage *leftlink, absptr b_sysarea);
pascal void DEQUEUE(linkage *link, absptr b_sysarea);
pascal void RELSPACE(absptr ordaddr, absptr b_area);
pascal uint8_t GETSPACE(int16_t amount, absptr b_area, absptr *ordaddr);
pascal void SYSTEM_ERROR(int16_t errnum);
pascal void MACH_INFO(int16_t *error, minfo *the_info);
pascal void UNBLK_REQ(reqblk *req, uint8_t success);
pascal void BLK_REQ(reqblk *req_list, reqblk **first_req);
pascal void FREEZE_SEG(int16_t *errnum, absptr c_sdb, int32_t offset, absptr ioreq_addr, absptr *buffaddr);
pascal void UNFREEZE_SEG(absptr c_sdb);
pascal void ADJ_IO_CNT(uint8_t inc_io_count, absptr c_sdb);
pascal void CVT_BUFF_ADDR(int16_t *errnum, uint8_t mem_write, absptr buffaddr, int32_t byte_cnt,
                          absptr *ordsdb, int32_t *offset);
pascal void CALLDRIVER(int16_t *errnum, devrec *config_ptr, params *parameters);
pascal void INTSOFF(int16_t level, int16_t *status);
pascal void INTSON(int16_t status);
pascal uint8_t LOGGING(void);
pascal void LOG(int16_t *errnum, int32_t ptr_arr);
pascal reqblk *CHAIN_FORWARD(uint32_t current);   /* a linkage, by value */
pascal void DISKSYNC(uint8_t busy);
pascal int32_t MICROTIMER(void);
pascal void ALARM_ASSIGN(int16_t *alarm, devrec *pdr, int16_t status);
pascal void ALARMRETURN(int16_t alarm);
pascal void ALARMRELATIVE(int16_t alarm, int32_t delay);
pascal void ALARMOFF(int16_t alarm);
pascal void LINK_TO_PCB(reqblk *req);
pascal void KEYPUSHED(int8_t key);

#endif
