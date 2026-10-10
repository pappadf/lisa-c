/* Desktop Manager (Filer) communication (FilerComm unit, SYS1LIB) for C.
 *
 * The Filer starts a tool with Make_Process and then sends it filerEvents:
 * GetAddParms fetches the operation and the document's diskfile prefix.
 * fcResume / fcNone: display the document in the window event.who (no reply).
 * fcClose, fcSuspend, fcPut, fcCopy, fcShred: save/close, then TellFiler(docClosd, ...).
 * fcTerminate: end the process. */
#ifndef LISA_FILER_H
#define LISA_FILER_H

#include "lisa/events.h"

typedef uint8_t FilerOp;
enum { fcClose = 0, fcCopy, fcDfClose, fcNone, fcPrint, fcPut, fcResume, fcShred, fcSuspend,
       fcTerminate, fcNameToPrefix, fcPrefixToName, fcDupIcon, fcMakeTool };

typedef uint8_t FReply;
enum { dfClosed = 0, dfNotClosed, docClosd, docNotClosed, docXfered, docNotXfered, initFailed };

typedef uint8_t FReason;
enum { allOk = 0, badData, cantConvert, cantRead, cantWrite, dirtyDoc, internalError, needToConvert,
       newerDoc, noDiskSpace, noMemory, noMoreDocs, okButNoMore, docPutBack, aUserAbort, wrongPassword };

typedef LongInt FilingCmd;
enum { cmdClose = 1001, cmdCloseAll = 1002 };

typedef struct {
    FilerOp theFlrOp;
    Integer theErr;
    Integer theOffset;
    Integer theDf;
    unsigned char thePassword[34];      /* string[32] */
    unsigned char thePrefix[256];       /* pathname prefix of the document's diskfiles */
    unsigned char theResult[256];
} FilerExt;

pascal void GetAddParms(Integer *error, const EventRecord *theEvent, FilerExt *theFilerExt) LISA_IU(GETADDPA);
pascal void TellFiler(Integer *error, FReply what, FReason why, WindowPtr myFolder) LISA_IU(TELLFILE);
pascal void DoFilingCmd(FilingCmd whichCmd) LISA_IU(DOFILING);

#endif
