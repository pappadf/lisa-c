/* drvtest: install a configurable driver from the tool's floppy and use it.
 *
 * The floppy carries the driver examples/loopdrv as SYSTEM.CD_LOOP (make
 * PROG=drvtest tool puts it there; see TOOLFILES in the Makefile).  When the
 * tool opens a document it
 *
 *   1. copies SYSTEM.CD_LOOP to the boot volume, where the OS loads drivers
 *      from;
 *   2. detaches Serial B's driver (CDINFO saves it, CDKILL unmounts and
 *      removes it) and attaches the loopback driver there with CDMAKE, then
 *      MOUNTs the device (the file system opens only mounted devices);
 *   3. opens -RS232B-LOOP, writes a line to it, reads it back and calls the
 *      driver's DEVICE_CONTROL;
 *   4. detaches the loopback driver, attaches and mounts the serial driver
 *      again and deletes the driver file.
 *
 * The results are drawn in the window, one line per step.  The same steps
 * let a tool use its own driver with nothing to install. */
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include "lisa.h"
#include "lisa_os.h"
#include "lisa/desktop.h"

#define TOOL_NUMBER "24"
#define LOOP_ID 0x4C4F4F50L             /* 'LOOP': this example's driver ID */
enum { mSetAsideAll = 1, mSetAside = 2 };
enum { M_DREAD = 1, M_DWRITE = 2 };     /* mset bits */
enum { IO_SEQUENTIAL = 2 };             /* iomode */
enum { DEVT_SEQDEV = 2 };               /* devtype: a sequential device */

static char heap[8192];
static MenuInfo menus[1];
static TAlertFile alertFile;
static WindowPtr myWindow;

#define MAXLINES 20
static char lines[MAXLINES][80];
static int nlines;
static int done_test;

static pascal Integer HeapFull(void *zone, Integer bytesNeeded)
{
    (void)zone; (void)bytesNeeded;
    return 0;
}

static pascal void FailedAlert(void)
{
}

static pascal void LastWishes(void *environment, void *data)
{
    (void)environment; (void)data;
    ImDying();
}

static void pstr(unsigned char *p, const char *s)
{
    size_t n = strlen(s);
    p[0] = (unsigned char)n;
    memcpy(p + 1, s, n);
}

static void tool_prefix(unsigned char prefix[42])
{
    static unsigned char info[600];
    Integer err;
    int n;

    lisa_info_process(&err, lisa_my_id(), info);
    for (n = 1; n + 1 <= info[0] && !(info[n] == '-' && info[n + 1] == '{'); n++)
        ;
    memcpy(prefix + 1, info + 1, n - 1);
    memcpy(prefix + n, "-{T" TOOL_NUMBER "}", 6);
    prefix[0] = (unsigned char)(n - 1 + 6);
}

static void say(const char *fmt, ...)
{
    va_list ap;

    if (nlines == MAXLINES)
        return;
    va_start(ap, fmt);
    vsnprintf(lines[nlines++], sizeof lines[0], fmt, ap);
    va_end(ap);
}

static const char *devt_name(int t)
{
    static const char *names[] = {"diskdev", "pascalbd", "seqdev", "bitbkt", "non_io"};
    return t < 5 ? names[t] : "?";
}

static void cstr(char *out, const unsigned char *p)
{
    int n = p[0] > 32 ? 32 : p[0];
    memcpy(out, p + 1, n);
    out[n] = 0;
}

static int report(const char *label, cd_infobuf *buf)
{
    Integer err;
    char name[33];

    memset(buf, 0, sizeof *buf);
    lisa_cdinfo(&err, CD_POS(10, 2, 0), buf);
    if (err > 0) {
        say("CDINFO %s: error %d", label, err);
        return err;
    }
    cstr(name, buf->cd_drvrname);
    say("CDINFO %s: id %ld '%s' %s", label, (long)buf->cd_driverid, name, devt_name(buf->cd_devt));
    return 0;
}

/* "-<vol>-<name>" as a Pascal string */
static void path(unsigned char *p, const char *vol, const char *name)
{
    char s[80];
    snprintf(s, sizeof s, "-%s-%s", vol, name);
    pstr(p, s);
}

/* Copy a file (here: the driver, from the tool's floppy to the boot volume). */
static int copy_file(const unsigned char *src, const unsigned char *dst, long *total)
{
    static char buf[512];
    Integer err, e2, in, out;
    int32_t got, put;

    lisa_kill_object(&err, dst);        /* an older copy */
    lisa_make_file(&err, dst, 0);
    if (err > 0)
        return err;
    lisa_open(&err, src, &in, M_DREAD);
    if (err > 0)
        return err;
    lisa_open(&err, dst, &out, M_DWRITE);
    if (err > 0) {
        lisa_close_object(&e2, in);
        return err;
    }
    *total = 0;
    for (;;) {
        lisa_read_data(&err, in, buf, sizeof buf, &got, IO_SEQUENTIAL, 0);
        if (got <= 0)
            break;
        lisa_write_data(&e2, out, buf, got, &put, IO_SEQUENTIAL, 0);
        if (e2 > 0) {
            err = e2;
            break;
        }
        *total += put;
    }
    if (err == 848 || err == 956)       /* end of file (956: read at the logical end) */
        err = 0;
    lisa_close_object(&e2, in);
    lisa_close_object(&e2, out);
    return err > 0 ? err : 0;
}

static void use_device(void)
{
    static const char msg[] = "Hello from the loopback driver!";
    unsigned char dev[16];
    char back[64];
    dctype dc;
    Integer err, e2, refnum;
    int32_t actual;

    unsigned char file[20];

    /* a sequential device is opened with a dummy file name after it */
    pstr(file, "-RS232B-LOOP");
    lisa_open(&err, file, &refnum, M_DREAD | M_DWRITE);
    say("OPEN -RS232B-LOOP: error %d", err);
    if (err > 0)
        return;
    lisa_write_data(&err, refnum, msg, sizeof msg - 1, &actual, IO_SEQUENTIAL, 0);
    say("WRITE_DATA: error %d, %ld bytes", err, (long)actual);
    memset(back, 0, sizeof back);
    lisa_read_data(&err, refnum, back, sizeof back - 1, &actual, IO_SEQUENTIAL, 0);
    say("READ_DATA: error %d, %ld bytes: \"%s\"", err, (long)actual, back);
    memset(&dc, 0, sizeof dc);
    dc.dcversion = 2;
    dc.dccode = 1;
    pstr(dev, "-RS232B");
    lisa_device_control(&err, dev, &dc);
    say("DEVICE_CONTROL 1: error %d, writes %ld, reads %ld, unread %ld", err, (long)dc.dcdata[0],
        (long)dc.dcdata[1], (long)dc.dcdata[2]);
    memset(&dc, 0, sizeof dc);
    dc.dcversion = 2;
    dc.dccode = 2;
    dc.dcdata[0] = 1000000;
    dc.dcdata[1] = 7;
    lisa_device_control(&err, dev, &dc);
    say("DEVICE_CONTROL 2: error %d, 1000000 / 7 = %ld rem %ld", err, (long)dc.dcdata[2], (long)dc.dcdata[3]);
    lisa_close_object(&e2, refnum);
}

/* Mount Serial B: a device attached with CDMAKE is not mounted. */
static void mount_serial_b(void)
{
    unsigned char vname[34], password[34], devname[34];
    Integer err;

    pstr(devname, "RS232B");
    password[0] = 0;
    lisa_mount(&err, vname, password, devname);
    say("MOUNT RS232B: error %d", err);
}

static void run_test(void)
{
    unsigned char boot[34], info[600], src[80], dst[80];
    char bootvol[33], toolvol[64];
    cd_infobuf serial, loop, now;
    Integer err, e2;
    long size = 0;
    int n;

    /* the volumes: the boot volume (where drivers load from) and the tool's */
    lisa_osbootvol(&err, boot);
    cstr(bootvol, boot);
    lisa_info_process(&err, lisa_my_id(), info);  /* progpathname: -<vol>-{T24}obj */
    for (n = 2; n <= info[0] && info[n] != '-'; n++)
        ;
    memcpy(toolvol, info + 2, n - 2);
    toolvol[n - 2] = 0;
    path(src, toolvol, "SYSTEM.CD_LOOP");
    path(dst, bootvol, "SYSTEM.CD_LOOP");
    err = copy_file(src, dst, &size);
    say("Copy SYSTEM.CD_LOOP from '%s' to '%s': error %d, %ld bytes", toolvol, bootvol, err, size);
    if (err > 0)
        return;

    if (report("Serial B", &serial) > 0)
        return;
    lisa_cdkill(&err, CD_POS(10, 2, 0));
    say("CDKILL Serial B: error %d", err);
    if (err > 0)
        return;

    memset(&loop, 0, sizeof loop);
    loop.cd_driverid = LOOP_ID;
    pstr(loop.cd_drvrname, "LOOP");
    loop.cd_devt = DEVT_SEQDEV;
    lisa_cdmake(&err, CD_POS(10, 2, 0), &loop);
    say("CDMAKE LOOP at Serial B: error %d", err);
    if (err <= 0) {
        report("Serial B", &now);
        mount_serial_b();
        use_device();
        lisa_cdkill(&err, CD_POS(10, 2, 0));
        say("CDKILL LOOP: error %d", err);
    }

    lisa_cdmake(&err, CD_POS(10, 2, 0), &serial);
    say("CDMAKE Serial B (as before): error %d", err);
    mount_serial_b();
    report("Serial B", &now);
    lisa_kill_object(&e2, dst);
    say("Delete the driver file: error %d", e2);
}

static void draw(void)
{
    unsigned char s[82];
    Rect r = myWindow->portRect;
    int i;

    SetPort(myWindow);
    EraseRect(&r);
    for (i = 0; i < nlines; i++) {
        MoveTo(r.left + 10, r.top + 16 + 14 * i);
        pstr(s, lines[i]);
        DrawString(s);
    }
}

static void activate(void)
{
    InsertMenu(&menus[0], 0);
    DrawMenuBar();
    SetPort(myWindow);
    InitCursor();
}

static void menu_command(Integer menu, Integer item)
{
    if (menu != menus[0].menuId)
        return;
    switch (item) {
    case mSetAsideAll: DoFilingCmd(cmdClosAll); break;
    case mSetAside:    DoFilingCmd(cmdClose); break;
    }
}

static void filer_event(EventRecord *ev, int *done)
{
    FilerExt fx;
    Integer err;

    GetAddParms(&err, ev, &fx);
    switch (fx.theFlrOp) {
    case fcResume:
    case fcNone:
        myWindow = ev->who;
        TakeWindow(myWindow);
        if (!done_test) {
            done_test = 1;
            run_test();
        }
        draw();
        if (myWindow == activeFolder)
            activate();
        break;
    case fcClose:
    case fcSuspend:
    case fcPut:
    case fcCopy:
    case fcShred:
        TellFiler(&err, docClosd, allOK, ev->who);
        myWindow = 0;
        break;
    case fcTerminate:
        *done = 1;
        break;
    default:
        TellFiler(&err, docClosd, internalError, ev->who);
        break;
    }
}

int main(void)
{
    static const unsigned char excep_name[] = "\015SYS_TERMINATE";
    unsigned char name[18], prefix[42];
    EventRecord ev;
    Integer err;
    int done = 0;

    InitGraf(&thePort);
    OpenWM();
    memcpy(name, excep_name, sizeof excep_name);
    lisa_declare_excep_hdl(&err, name, (void *)LastWishes);
    SetPort(deskPort);
    InitHeap(heap, heap + sizeof heap, (void *)HeapFull);
    tool_prefix(prefix);
    InitMP(theHeap, prefix, (void *)FailedAlert, 2, menus, &alertFile, &err);
    if (err > 0) {
        TellFiler(&err, InitFailed, internalError, 0);
        ImDying();
        return 1;
    }
    InitWmlCrs(&err);

    while (!done) {
        if (ImActive() && !EventAvail()) {
            LetOthersRun();
            continue;
        }
        GetEvent(&ev);
        switch (ev.what) {
        case filerEvent:
            filer_event(&ev, &done);
            break;
        case folderActivate:
            TakeControl(&ev, false, false);
            activate();
            break;
        case folderDeactivate:
            GiveControl(&ev);
            break;
        case folderUpdate:
            BeginUpdate(ev.who);
            if (myWindow && ev.who == myWindow)
                draw();
            EndUpdate(ev.who);
            break;
        case buttonDown:
            if (ev.who == menuFolder) {
                Integer menu, item;
                MenuSelect(ev.where, &menu, &item);
                menu_command(menu, item);
                HiLiteMenu(0);
            }
            break;
        }
    }
    ImDying();
    return 0;
}
