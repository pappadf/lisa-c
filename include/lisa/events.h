/* Event Manager (Events unit, SYS1LIB) for C.
 *
 * Office System tools get their input -- mouse, keyboard, window activation
 * and messages from the Desktop Manager (the Filer) -- as events.  GetEvent
 * may suspend the calling process until an event arrives. */
#ifndef LISA_EVENTS_H
#define LISA_EVENTS_H

#include "lisa/quickdraw.h"

typedef GrafPtr WindowPtr;              /* windows (folders) are GrafPorts */
typedef LongInt ProcessId;

/* EventRecord.what */
enum {
    nilEvent = 0, buttonDown = 1, buttonUp = 2, keyDown = 3,
    folderActivate = 4, folderDeactivate = 5, folderUpdate = 6, folderMoved = 7,
    filerEvent = 8, abortEvent = 9, diedEvent = 10,
    private1 = 11, private2 = 12, private3 = 13, diskEvent = 14, catalogEvent = 15
};

typedef struct {
    WindowPtr who;                      /* window the event is for */
    Integer what;                       /* event kind (above) */
    Point where;                        /* mouse location, local to `who` */
    LongInt when;
    Integer why;
    Boolean shiftKey, alphaKey, codeKey, appleKey, mouseKey, repeatKey;
    uint8_t keyCap;                     /* key code 0..127 */
    char ascii;                         /* character for keyDown */
    ProcessId toProcess;
    ProcessId fromProcess;
    WindowPtr fromFolder;
    LongInt userData;
} EventRecord;

/* Window Manager globals (Events unit variables, unit 10). */
#define lisa_events_var(off, type) (*(type *)(lisa_unit_data(10) - (off)))
#define deskPort     lisa_events_var(8, GrafPtr)
#define menuFolder   lisa_events_var(12, WindowPtr)
#define alertFolder  lisa_events_var(16, WindowPtr)
#define dialogFolder lisa_events_var(20, WindowPtr)
#define filerFolder  lisa_events_var(24, WindowPtr)
#define scrapFolder  lisa_events_var(28, WindowPtr)
#define activeFolder lisa_events_var(32, WindowPtr)
#define keyWindow    lisa_events_var(36, WindowPtr)

pascal void GetEvent(EventRecord *event) LISA_IU(GETEVENT);
pascal Boolean EventAvail(void) LISA_IU(EVENTAVA);
pascal void GetMouse(Point *pt) LISA_IU(GETMOUSE);
pascal Boolean ImActive(void) LISA_IU(IMACTIVE);   /* does this process own the active window? */
pascal void LetOthersRun(void) LISA_IU(LETOTHER);
pascal Boolean PeekEvent(EventRecord *event) LISA_IU(PEEKEVEN);   /* next event, left in the queue */
/* Mouse tracking after a buttonDown: loop while StillDown(), reading GetMouse. */
pascal Boolean StillDown(void) LISA_IU(STILLDOW);  /* button still down since the buttonDown event? */
pascal Boolean Button(void) LISA_IU(BUTTON);       /* is the button down now? */
pascal LongInt Time(void) LISA_IU(TIME);           /* hundredths of a second since startup */

#endif
