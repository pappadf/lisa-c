/* Standard cursors (WmlCrs unit, SYS1LIB) for C. */
#ifndef LISA_CURSORS_H
#define LISA_CURSORS_H

#include "lisa/pascal.h"

enum { icrsHidden = -1, icrsEscape = 0, icrsInactive = 1, icrsUpDwn = 2, icrsLftRt = 3, icrsGrow = 4,
       icrsIBeam = 5, icrsMenu = 6, icrsVSkewer = 7, icrsHSkewer = 8, icrsLCCross = 9, icrsXIBeam = 10,
       icrsHrGlass = 11, icrsCheck = 12, icrsGECross = 13, icrsLFinger = 14, icrsGEIBeam = 15 };

pascal void InitWmlCrs(Integer *error) LISA_IU(INITWMLC);
pascal void SetStdCursor(Integer icrs) LISA_IU(SETSTDCU);

#endif
