/* Storage Manager heap setup (Storage unit, SYS1LIB) for C. */
#ifndef LISA_STORAGE_H
#define LISA_STORAGE_H

#include "lisa/pascal.h"

/* Make [startPtr, limitPtr) the QuickDraw/Window Manager heap of this process;
 * errorProc is called when it is full. */
/* The heap zone set up by InitHeap (Storage unit variable theHeap). */
#define theHeap (*(void **)(lisa_unit_data(5) - 4))

pascal void InitHeap(void *startPtr, void *limitPtr, void *errorProc) LISA_IU(INITHEAP);

#endif
