/* Scroll bars and the size control (WM Library units WmlSb and WmlGrow,
 * SYS1LIB) for C.
 *
 * Office System windows draw their own view controls: a vertical scroll bar
 * along the right edge, a horizontal one along the bottom, and the size
 * control ("grow box") where they meet.  They are shown only while the
 * window is active.  Typical use:
 *
 *   InitWmlSb();  InitSbList(&list, theHeap);
 *   hsbV = SbCreate(&list, hsbNil, tyvhV, pt00, 100);
 *   hsbH = SbCreate(&list, hsbNil, tyvhH, pt00, 100);
 *   SetSbIcons(hsbV, sbAllIcons); ...
 *   SetPort(window); FlushRects(&rH, &rV);     standard places for the bars
 *   SetSbRect(hsbH, &rH); SetSbRect(hsbV, &rV);
 *   PaintSbar(hsbH); PaintSbar(hsbV); PaintGrow();       on activate/update
 *   HideSBorder(&window->portRect);                      on deactivate
 *   buttonDown: FGrowHit(pt) -> DragFrame + FolderSize;
 *               FSbHit(&list, pt, &hsb, &icon) -> arrows: PaintArw while
 *               StillDown(); gray: page; thumb: DragThumb + SetThumb.
 *
 * Thumb positions are in thousandths (0..1000) of the scroll range.
 * Coordinates are local to the current port (the window). */
#ifndef LISA_SCROLLBARS_H
#define LISA_SCROLLBARS_H
#include "lisa/quickdraw.h"

/* Sizes of the scroll box, its thumb ("elevator") and the split skewer. */
enum { dhSbox = 24, dvSbox = 16, dhThumb = 24, dvThumb = 16, dhSkewer = 6, dvSkewer = 4,
       dhGrow = 24, dvGrow = 16 };

/* Orientation (VHSelect). */
enum { tyvhV = 0, tyvhH = 1 };

/* The parts of a scroll bar, from top/left to bottom/right. */
typedef uint8_t TIcon;
enum { iconSkewer = 0, iconArwA, iconPagA, iconGryA, iconThumb, iconGryB, iconPagB, iconArwB };

/* A set of TIcon (bit i = icon i), passed by value as an Integer. */
#define sbIcon(i)   (1 << (i))
#define sbAllIcons  (sbIcon(iconArwA) | sbIcon(iconPagA) | sbIcon(iconThumb) | \
                     sbIcon(iconPagB) | sbIcon(iconArwB))

typedef struct TSb *TPSb;
typedef TPSb *THSb;                     /* a scroll bar (handle) */
#define hsbNil ((THSb)0)

typedef struct {
    void *hz;                           /* heap zone the bars are allocated in */
    THSb hsbFst;                        /* first bar on the list */
} TSbList;

pascal void InitWmlSb(void) LISA_IU(INITWMLS);
pascal void InitSbList(TSbList *sbList, void *hz) LISA_IU(INITSBLI);
pascal THSb SbCreate(TSbList *sbList, THSb hsbBefore, VHSelect tyvh, Point topLeft, Integer cdBotRt)
    LISA_IU(SBCREATE);
pascal void GetSbRect(THSb hsb, Rect *r) LISA_IU(GETSBREC);
pascal void SetSbRect(THSb hsb, const Rect *r) LISA_IU(SETSBREC);
pascal void SetSbIcons(THSb hsb, Integer sicon) LISA_IU(SETSBICO);
pascal Integer CThumbPos(THSb hsb) LISA_IU(CTHUMBPO);
pascal void SetThumb(THSb hsb, Integer cNewThumb) LISA_IU(SETTHUMB);
pascal void PaintSb(THSb hsb) LISA_IU(PAINTSB);
pascal void PaintSbar(THSb hsb) LISA_IU(PAINTSBA);
pascal void EraseSbar(THSb hsb) LISA_IU(ERASESBA);
pascal void PaintArw(THSb hsb, TIcon iconWhichArw, Boolean fBlack) LISA_IU(PAINTARW);
pascal Boolean FSbHit(TSbList *sbList, Point pt, THSb *hsbHit, TIcon *iconHit) LISA_IU(FSBHIT);
pascal void DragThumb(THSb hsb, Point ptMouse, Integer *cThumbUp) LISA_IU(DRAGTHUM);
/* The standard rectangles of the horizontal and vertical bars of the port. */
pascal void FlushRects(Rect *rH, Rect *rV) LISA_IU(FLUSHREC);
/* Erase the scroll bar border area of r (on deactivate). */
pascal void HideSBorder(const Rect *r) LISA_IU(HIDESBOR);

/* Size control (lower right corner of the port). */
pascal void GetGrowRect(Rect *rGrow) LISA_IU(GETGROWR);
pascal void PaintGrow(void) LISA_IU(PAINTGRO);
pascal Boolean FGrowHit(Point pt) LISA_IU(FGROWHIT);
/* Track an outline of the window while the button is down; ptNewBR is the
 * new bottom right corner (local).  Then call FolderSize. */
pascal void DragFrame(Point ptMouse, Boolean fDrawScrolls, Point *ptNewBR) LISA_IU(DRAGFRAM);

#endif
