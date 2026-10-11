/* All the intrinsic-library units an Office System desktop tool can use:
 * QuickDraw, the Window Manager (Events, Windows, Folders, Menus, the WM
 * library: scroll bars, size control, cursors), the Alert Manager, the
 * Desktop Manager protocol (FilerComm), the Clipboard (Scrap), the field
 * editor, fonts, international utilities, parameter memory, the hardware
 * interface, printing and the standard utilities.
 *
 * Each unit also has its own header (lisa/quickdraw.h, lisa/events.h, ...),
 * generated from the units' Pascal interfaces by tools/gen_headers.py; each
 * includes the units it depends on.  OS calls: lisa_os.h. */
#ifndef LISA_DESKTOP_H
#define LISA_DESKTOP_H
#include "lisa/prspool.h"               /* the last unit: includes all the others */
#endif
