/* loopdrv: a minimal configurable driver -- a sequential device that reads
 * back what was written to it.
 *
 * Build:  make PROG=loopdrv driver  -> build/loopdrv.drv, to be installed as
 * SYSTEM.CD_LOOP on the boot volume.  examples/drvtest attaches it to Serial B
 * with CDMAKE, writes to it and reads it back.
 *
 * Every request completes at once, in the seqio call: the OS's Wait_IO then
 * finds it complete and does not block.  A real driver queues requests
 * (ENQUEUE on its control block) and completes them from its interrupt or
 * alarm code with UNBLK_REQ. */
#include "lisa_driver.h"

#define RING 256

/* The control block: GETSPACE'd in sysglobal at dinit, freed at ddown.  A
   driver has no globals (its code is mapped read-only and shared). */
typedef struct loop_cb {
    uint16_t head, tail;        /* ring indexes: bytes [tail, head) are unread */
    int32_t writes, reads;      /* requests served, for DEVICE_CONTROL */
    uint8_t ring[RING];
} loop_cb;

enum { e_badfunc = 656, e_nospace = 610, e_badcontrol = 657 };

static int16_t do_init(devrec *dev)
{
    absptr cb;

    if (!GETSPACE(sizeof(loop_cb), B_SYSGLOBAL, &cb))
        return e_nospace;
    __builtin_memset((void *)cb, 0, sizeof(loop_cb));
    dev->cb_addr = cb;
    return 0;
}

static int16_t do_down(devrec *dev)
{
    if (dev->cb_addr) {
        RELSPACE(dev->cb_addr, B_SYSGLOBAL);
        dev->cb_addr = 0;
    }
    return 0;
}

/* A read or write: copy between the ring and the caller's buffer, which
   FREEZE_SEG pins in memory and gives an address for. */
static int16_t do_seqio(devrec *dev, reqblk *req)
{
    loop_cb *cb = (loop_cb *)dev->cb_addr;
    seq_extend *ext = (seq_extend *)req->req_extent;
    absptr buf;
    int16_t err;
    int32_t n = 0;

    FREEZE_SEG(&err, ext->buff_rdb_ptr, ext->buff_offset, (absptr)req, &buf);
    if (err > 0) {
        req->hard_error = err;
    } else {
        uint8_t *p = (uint8_t *)buf;
        if (ext->read_flag) {
            for (; n < ext->num_bytes && cb->tail != cb->head; n++)
                p[n] = cb->ring[cb->tail++ % RING];
            cb->reads++;
        } else {
            for (; n < ext->num_bytes && (uint16_t)(cb->head - cb->tail) < RING; n++)
                cb->ring[cb->head++ % RING] = p[n];
            cb->writes++;
        }
        UNFREEZE_SEG(ext->buff_rdb_ptr);
    }
    ext->xfer_count = n;
    ADJ_IO_CNT(0, ext->buff_rdb_ptr);   /* SeqentIO pinned the buffer's segment */
    UNBLK_REQ(req, req->hard_error == 0);
    return 0;
}

/* DEVICE_CONTROL dcode 1: report the counters in ar10[0..2].
   dcode 2: ar10[0] / ar10[1] and the remainder, in ar10[2..3] -- 32-bit
   division is a libgcc call, which shows library code working in a driver. */
static int16_t do_control(devrec *dev, dc_rec *dc)
{
    loop_cb *cb = (loop_cb *)dev->cb_addr;

    switch (dc->dcode) {
    case 1:
        dc->ar10[0] = cb->writes;
        dc->ar10[1] = cb->reads;
        dc->ar10[2] = (uint16_t)(cb->head - cb->tail);
        return 0;
    case 2:
        if (dc->ar10[1] == 0)
            return e_badcontrol;
        dc->ar10[2] = dc->ar10[0] / dc->ar10[1];
        dc->ar10[3] = dc->ar10[0] % dc->ar10[1];
        return 0;
    default:
        return e_badcontrol;
    }
}

pascal int16_t DRIVER(params *p)
{
    switch (p->fnctn_code) {
    case dinit:      return do_init(p->configptr);
    case ddown:      return do_down(p->configptr);
    case seqio:      return do_seqio(p->configptr, p->req);
    case dcontrol:   return do_control(p->configptr, (dc_rec *)p->parptr);
    case dunattach:  p->still_inuse = 0; return 0;
    case dinterrupt:                    /* not enabled: nothing to do */
    case dattach:
    case ddiscon:    return 0;
    default:         return e_badfunc;
    }
}
