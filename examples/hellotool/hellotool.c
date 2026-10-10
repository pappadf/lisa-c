/* A minimal Lisa Office System desktop tool in C.
 *
 * The Desktop Manager (the "Filer") starts the tool with Make_Process when
 * the user opens one of its documents, then talks to it with filerEvents
 * (lisa/filer.h): show the document in the window it provides (fcResume,
 * fcNone), close it (fcClose, fcSuspend, ...), terminate (fcTerminate).
 * The File/Print menu comes from the tool's phrase file ({T20}PHRASE) via
 * InitMP; choosing "Set Aside" asks the Filer to close the document.
 *
 * Build:  make PROG=hellotool TOOL=1 tool   (see the Makefile)
 * The startup order follows the Office System tools (e.g. the Clock). */
#include <string.h>
#include "lisa.h"
#include "lisa_os.h"
#include "lisa/desktop.h"

#define TOOL_NUMBER "20"
enum { mSetAsideAll = 1, mSetAside = 2, mPutBack = 4 };   /* File/Print items */

static char heap[8192];                 /* QuickDraw / Window Manager heap */
static MenuInfo menus[1];               /* built from the phrase file */
static PAlertRec alertFile;
static WindowPtr myWindow;

static pascal Integer HeapFull(void *zone, Integer bytesNeeded)
{
    (void)zone; (void)bytesNeeded;
    return 0;
}

static pascal void FailedAlert(void)
{
}

/* SYS_TERMINATE exception handler: the protocol requires ImDying first. */
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

/* "-volume-{T20}": the prefix of this tool's files, from its program path. */
static void tool_prefix(unsigned char prefix[42])
{
    static unsigned char info[600];     /* procinfoRec: progpathname first */
    Integer err;
    int n;

    lisa_info_process(&err, lisa_my_id(), info);
    for (n = 1; n + 1 <= info[0] && !(info[n] == '-' && info[n + 1] == '{'); n++)
        ;
    memcpy(prefix + 1, info + 1, n - 1);
    memcpy(prefix + n, "-{T" TOOL_NUMBER "}", 6);
    prefix[0] = (unsigned char)(n - 1 + 6);
}

static void draw(void)
{
    unsigned char s[64];
    Rect r = myWindow->portRect;

    SetPort(myWindow);
    EraseRect(&r);
    InsetRect(&r, 12, 12);
    FrameRect(&r);
    InsetRect(&r, 3, 3);
    FrameRect(&r);
    MoveTo(r.left + 16, r.top + 24);
    pstr(s, "Hello from C on the Apple Lisa!");
    DrawString(s);
    MoveTo(r.left + 16, r.top + 44);
    pstr(s, "Cross-compiled with lisa-c, drawn with QuickDraw.");
    DrawString(s);
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
    Integer err;

    if (menu != menus[0].menuId)
        return;
    switch (item) {
    case mSetAsideAll: DoFilingCmd(cmdCloseAll); break;
    case mSetAside:    DoFilingCmd(cmdClose); break;
    case mPutBack:
        TellFiler(&err, docClosd, docPutBack, myWindow);
        myWindow = 0;
        break;
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
        draw();
        if (myWindow == activeFolder)
            activate();
        break;
    case fcClose:
    case fcSuspend:
    case fcPut:
    case fcCopy:
    case fcShred:
        TellFiler(&err, docClosd, allOk, ev->who);
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
        TellFiler(&err, initFailed, internalError, 0);
        ImDying();
        return 1;
    }
    InitWmlCrs(&err);

    while (!done) {
        /* As the Office System tools do: block in GetEvent while inactive;
         * while active, poll and let the other processes run. */
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
