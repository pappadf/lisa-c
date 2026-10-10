/* Alert Manager (AlertMgr unit, SYS1LIB) for C.
 *
 * Alerts and menu texts of a tool live in its phrase file ({Tn}PHRASE).
 * InitMP opens the phrase file and builds the tool's menus from it. */
#ifndef LISA_ALERTS_H
#define LISA_ALERTS_H

#include "lisa/menus.h"

typedef struct {
    LongInt fAlerts;
    Integer fNumAlerts;
    Integer fRefNum;
    Integer fPos;
} TAlertRec, *PAlertRec;

/* toolPrefix: Pascal string[40], the tool's pathname prefix such as "-volume-{t20}". */
pascal void InitMP(void *heap, const unsigned char *toolPrefix, void *alertProc, Integer phraseVersion,
                   MenuInfo *menus, PAlertRec *alertFile, Integer *error) LISA_IU(INITMP);
pascal void InitAlerts(Integer cacheSize, Integer cacheBytes, void *heap, void *idleProc,
                       void *errProc) LISA_IU(INITALER);
pascal void GetAlert(PAlertRec alertFile, Integer alertNumber, unsigned char *str) LISA_IU(GETALERT);
pascal void NoteAlert(PAlertRec alertFile, Integer alertNumber) LISA_IU(NOTEALER);
pascal void StopAlert(PAlertRec alertFile, Integer alertNumber) LISA_IU(STOPALER);
pascal Boolean CautionAlert(PAlertRec alertFile, Integer alertNumber) LISA_IU(CAUTIONA);
pascal Integer AskAlert(PAlertRec alertFile, Integer alertNumber) LISA_IU(ASKALERT);

#endif
