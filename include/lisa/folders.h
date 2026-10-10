/* Window Manager (Folders/Windows units, SYS1LIB) for C: the subset an
 * Office System tool needs to take over and maintain its document window. */
#ifndef LISA_FOLDERS_H
#define LISA_FOLDERS_H

#include "lisa/events.h"

typedef struct {
    Boolean visible, hasTab, okMove, okGrow, okFront, okClose, okActivate;
    uint8_t pad;                        /* Pascal records are a whole number of words */
} WindowInfo;

pascal void OpenWM(void) LISA_IU(OPENWM);           /* first call of a tool: connect to the window manager */
pascal void ImDying(void) LISA_IU(IMDYING);         /* first call of the terminate handler */
pascal void TakeWindow(WindowPtr window) LISA_IU(TAKEWIND);
pascal void FolderSize(WindowPtr folder, Integer width, Integer height, Boolean fUpdate) LISA_IU(FOLDERSI);
pascal void GetWindInfo(WindowPtr window, WindowInfo *info) LISA_IU(GETWINDI);
pascal void BeginUpdate(WindowPtr folder) LISA_IU(BEGINUPD);
pascal void EndUpdate(WindowPtr folder) LISA_IU(ENDUPDAT);
pascal void ValidRect(const Rect *goodRect) LISA_IU(VALIDREC);
pascal void InvalRect(const Rect *badRect) LISA_IU(INVALREC);      /* local to the current port */
pascal void InvalRgn(RgnHandle badRgn) LISA_IU(INVALRGN);
pascal void GetFldrTitle(WindowPtr folder, unsigned char *title) LISA_IU(GETFLDRT);  /* Str255 */
/* Standard activate/deactivate protocol for folderActivate/Deactivate events. */
pascal void TakeControl(const EventRecord *event, Boolean keepMenus, Boolean keepDialog) LISA_IU(TAKECONT);
pascal void GiveControl(const EventRecord *event) LISA_IU(GIVECONT);

#endif
