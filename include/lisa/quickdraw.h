/* QuickDraw (LisaGraf) for C.
 *
 * Written from the interface published in the Lisa Pascal 3.0 Reference
 * Manual (1984), appendix E.13 "QuickDraw Interface".  Calls go to the
 * QuickDraw routines of the GRAFSEG intrinsic segment (SYS1LIB).
 *
 * Conventions (see lisa/pascal.h): Pascal value parameters of record types
 * larger than 4 bytes (Rect, Pattern, BitMap, Cursor, PenState, strings) are
 * passed by address, so they appear here as const pointers; VAR parameters
 * are plain pointers.  Point (4 bytes) is passed by value. */
#ifndef LISA_QUICKDRAW_H
#define LISA_QUICKDRAW_H

#include "lisa/pascal.h"

/* ---- types ------------------------------------------------------------ */

typedef signed char QDByte;
typedef QDByte *QDPtr;                  /* blind pointer */
typedef QDPtr *QDHandle;                /* blind handle */

typedef struct { uint8_t pat[8]; } Pattern;
typedef Integer Bits16[16];

typedef uint8_t VHSelect;               /* (v, h) = 0, 1 */
typedef uint8_t GrafVerb;               /* (frame, paint, erase, invert, fill) = 0..4 */

/* Style = SET OF StyleItem: one byte, bit n = item n */
typedef uint8_t Style;
enum { bold = 1 << 0, italic = 1 << 1, underline = 1 << 2, outline = 1 << 3,
       shadow = 1 << 4, condense = 1 << 5, extend = 1 << 6 };

typedef struct {
    Integer ascent, descent, widMax, leading;
} FontInfo;

typedef struct {
    Integer v, h;
} Point;

typedef struct {
    Integer top, left, bottom, right;
} Rect;

typedef struct {
    QDPtr baseAddr;
    Integer rowBytes;
    Rect bounds;
} BitMap;

typedef struct {
    Bits16 data;
    Bits16 mask;
    Point hotSpot;
} Cursor;

typedef struct {
    Point pnLoc;
    Point pnSize;
    Integer pnMode;
    Pattern pnPat;
} PenState;

typedef struct {
    Integer polySize;
    Rect polyBBox;
    Point polyPoints[1];
} Polygon, *PolyPtr, **PolyHandle;

typedef struct {
    Integer rgnSize;                    /* 10 for a rectangular region */
    Rect rgnBBox;
    /* more data if not rectangular */
} Region, *RgnPtr, **RgnHandle;

typedef struct {
    Integer picSize;
    Rect picFrame;
    /* picture byte codes follow */
} Picture, *PicPtr, **PicHandle;

typedef struct {
    QDPtr textProc, lineProc, rectProc, rRectProc, ovalProc, arcProc, polyProc,
          rgnProc, bitsProc, commentProc, txMeasProc, getPicProc, putPicProc;
} QDProcs, *QDProcsPtr;

typedef struct GrafPort {
    Integer device;
    BitMap portBits;
    Rect portRect;
    RgnHandle visRgn;
    RgnHandle clipRgn;
    Pattern bkPat;
    Pattern fillPat;
    Point pnLoc;
    Point pnSize;
    Integer pnMode;
    Pattern pnPat;
    Integer pnVis;
    Integer txFont;
    Style txFace;
    Integer txMode;
    Integer txSize;
    LongInt spExtra;
    LongInt fgColor;
    LongInt bkColor;
    Integer colrBit;
    Integer patStretch;
    QDHandle picSave;
    QDHandle rgnSave;
    QDHandle polySave;
    QDProcsPtr grafProcs;
} GrafPort, *GrafPtr;

/* Transfer modes and standard colors (Pascal manual, QuickDraw chapter). */
enum { srcCopy = 0, srcOr, srcXor, srcBic, notSrcCopy, notSrcOr, notSrcXor, notSrcBic,
       patCopy, patOr, patXor, patBic, notPatCopy, notPatOr, notPatXor, notPatBic };
#define blackColor   33L
#define whiteColor   30L
#define redColor     205L
#define greenColor   341L
#define blueColor    409L
#define cyanColor    273L
#define magentaColor 137L
#define yellowColor  69L

/* ---- QuickDraw globals --------------------------------------------------
 * In the QuickDraw unit's data area (unit 6, see lisa_unit_data); the address
 * passed to InitGraf is &thePort, the other public globals lie below it. */
#define lisa_qd_globals() (lisa_unit_data(6) - 4)
#define thePort    (*(GrafPtr *)lisa_qd_globals())
#define white      (*(Pattern *)(lisa_qd_globals() - 8))
#define black      (*(Pattern *)(lisa_qd_globals() - 16))
#define gray       (*(Pattern *)(lisa_qd_globals() - 24))
#define ltGray     (*(Pattern *)(lisa_qd_globals() - 32))
#define dkGray     (*(Pattern *)(lisa_qd_globals() - 40))
#define arrow      (*(Cursor *)(lisa_qd_globals() - 108))
#define screenBits (*(BitMap *)(lisa_qd_globals() - 122))
#define randSeed   (*(LongInt *)(lisa_qd_globals() - 126))

/* ---- GrafPort routines ------------------------------------------------ */

pascal void InitGraf(void *globalPtr) LISA_IU(INITGRAF);
pascal void OpenPort(GrafPtr port) LISA_IU(OPENPORT);
pascal void InitPort(GrafPtr port) LISA_IU(INITPORT);
pascal void ClosePort(GrafPtr port) LISA_IU(CLOSEPOR);
pascal void SetPort(GrafPtr port) LISA_IU(SETPORT);
pascal void GetPort(GrafPtr *port) LISA_IU(GETPORT);
pascal void GrafDevice(Integer device) LISA_IU(GRAFDEVI);
pascal void SetPortBits(const BitMap *bm) LISA_IU(SETPORTB);
pascal void PortSize(Integer width, Integer height) LISA_IU(PORTSIZE);
pascal void MovePortTo(Integer leftGlobal, Integer topGlobal) LISA_IU(MOVEPORT);
pascal void SetOrigin(Integer h, Integer v) LISA_IU(SETORIGI);
pascal void SetClip(RgnHandle rgn) LISA_IU(SETCLIP);
pascal void GetClip(RgnHandle rgn) LISA_IU(GETCLIP);
pascal void ClipRect(const Rect *r) LISA_IU(CLIPRECT);
pascal void BackPat(const Pattern *pat) LISA_IU(BACKPAT);

/* ---- cursor ----------------------------------------------------------- */

pascal void InitCursor(void) LISA_IU(INITCURS);
pascal void SetCursor(const Cursor *crsr) LISA_IU(SETCURSO);
pascal void HideCursor(void) LISA_IU(HIDECURS);
pascal void ShowCursor(void) LISA_IU(SHOWCURS);
pascal void ObscureCursor(void) LISA_IU(OBSCUREC);

/* ---- pen and lines ---------------------------------------------------- */

pascal void HidePen(void) LISA_IU(HIDEPEN);
pascal void ShowPen(void) LISA_IU(SHOWPEN);
pascal void GetPen(Point *pt) LISA_IU(GETPEN);
pascal void GetPenState(PenState *pnState) LISA_IU(GETPENST);
pascal void SetPenState(const PenState *pnState) LISA_IU(SETPENST);
pascal void PenSize(Integer width, Integer height) LISA_IU(PENSIZE);
pascal void PenMode(Integer mode) LISA_IU(PENMODE);
pascal void PenPat(const Pattern *pat) LISA_IU(PENPAT);
pascal void PenNormal(void) LISA_IU(PENNORMA);
pascal void MoveTo(Integer h, Integer v) LISA_IU(MOVETO);
pascal void Move(Integer dh, Integer dv) LISA_IU(MOVE);
pascal void LineTo(Integer h, Integer v) LISA_IU(LINETO);
pascal void Line(Integer dh, Integer dv) LISA_IU(LINE);

/* ---- text ------------------------------------------------------------- */

pascal void TextFont(Integer font) LISA_IU(TEXTFONT);
pascal void TextFace(Integer face) LISA_IU(TEXTFACE);   /* a Style: 1-byte set passed in the low byte of a word */
pascal void TextMode(Integer mode) LISA_IU(TEXTMODE);
pascal void TextSize(Integer size) LISA_IU(TEXTSIZE);
pascal void SpaceExtra(LongInt extra) LISA_IU(SPACEEXT);
pascal void DrawChar(char ch) LISA_IU(DRAWCHAR);
pascal void DrawString(const unsigned char *s) LISA_IU(DRAWSTRI);
pascal void DrawText(const void *textBuf, Integer firstByte, Integer byteCount) LISA_IU(DRAWTEXT);
pascal Integer CharWidth(char ch) LISA_IU(CHARWIDT);
pascal Integer StringWidth(const unsigned char *s) LISA_IU(STRINGWI);
pascal Integer TextWidth(const void *textBuf, Integer firstByte, Integer byteCount) LISA_IU(TEXTWIDT);
pascal void GetFontInfo(FontInfo *info) LISA_IU(GETFONTI);

/* ---- point calculations ----------------------------------------------- */

pascal void AddPt(Point src, Point *dst) LISA_IU(ADDPT);
pascal void SubPt(Point src, Point *dst) LISA_IU(SUBPT);
pascal void SetPt(Point *pt, Integer h, Integer v) LISA_IU(SETPT);
pascal Boolean EqualPt(Point pt1, Point pt2) LISA_IU(EQUALPT);
pascal void ScalePt(Point *pt, const Rect *fromRect, const Rect *toRect) LISA_IU(SCALEPT);
pascal void MapPt(Point *pt, const Rect *fromRect, const Rect *toRect) LISA_IU(MAPPT);
pascal void LocalToGlobal(Point *pt) LISA_IU(LOCALTOG);
pascal void GlobalToLocal(Point *pt) LISA_IU(GLOBALTO);

/* ---- rectangle calculations ------------------------------------------- */

pascal void SetRect(Rect *r, Integer left, Integer top, Integer right, Integer bottom) LISA_IU(SETRECT);
pascal void OffsetRect(Rect *r, Integer dh, Integer dv) LISA_IU(OFFSETRE);
pascal void MapRect(Rect *r, const Rect *fromRect, const Rect *toRect) LISA_IU(MAPRECT);
pascal void InsetRect(Rect *r, Integer dh, Integer dv) LISA_IU(INSETREC);
pascal Boolean SectRect(const Rect *src1, const Rect *src2, Rect *dstRect) LISA_IU(SECTRECT);
pascal void UnionRect(const Rect *src1, const Rect *src2, Rect *dstRect) LISA_IU(UNIONREC);
pascal Boolean PtInRect(Point pt, const Rect *r) LISA_IU(PTINRECT);
pascal void Pt2Rect(Point pt1, Point pt2, Rect *dstRect) LISA_IU(PT2RECT);

/* ---- drawing rectangles, round rects, ovals, arcs --------------------- */

pascal void FrameRect(const Rect *r) LISA_IU(FRAMEREC);
pascal void PaintRect(const Rect *r) LISA_IU(PAINTREC);
pascal void EraseRect(const Rect *r) LISA_IU(ERASEREC);
pascal void InvertRect(const Rect *r) LISA_IU(INVERTRE);
pascal void FillRect(const Rect *r, const Pattern *pat) LISA_IU(FILLRECT);

pascal void FrameRoundRect(const Rect *r, Integer ovWd, Integer ovHt) LISA_IU(FRAMEROU);
pascal void PaintRoundRect(const Rect *r, Integer ovWd, Integer ovHt) LISA_IU(PAINTROU);
pascal void EraseRoundRect(const Rect *r, Integer ovWd, Integer ovHt) LISA_IU(ERASEROU);
pascal void InvertRoundRect(const Rect *r, Integer ovWd, Integer ovHt) LISA_IU(INVERTRO);
pascal void FillRoundRect(const Rect *r, Integer ovWd, Integer ovHt, const Pattern *pat) LISA_IU(FILLROUN);

pascal void FrameOval(const Rect *r) LISA_IU(FRAMEOVA);
pascal void PaintOval(const Rect *r) LISA_IU(PAINTOVA);
pascal void EraseOval(const Rect *r) LISA_IU(ERASEOVA);
pascal void InvertOval(const Rect *r) LISA_IU(INVERTOV);
pascal void FillOval(const Rect *r, const Pattern *pat) LISA_IU(FILLOVAL);

pascal void FrameArc(const Rect *r, Integer startAngle, Integer arcAngle) LISA_IU(FRAMEARC);
pascal void PaintArc(const Rect *r, Integer startAngle, Integer arcAngle) LISA_IU(PAINTARC);
pascal void EraseArc(const Rect *r, Integer startAngle, Integer arcAngle) LISA_IU(ERASEARC);
pascal void InvertArc(const Rect *r, Integer startAngle, Integer arcAngle) LISA_IU(INVERTAR);
pascal void FillArc(const Rect *r, Integer startAngle, Integer arcAngle, const Pattern *pat) LISA_IU(FILLARC);
pascal void PtToAngle(const Rect *r, Point pt, Integer *angle) LISA_IU(PTTOANGL);

/* ---- polygons --------------------------------------------------------- */

pascal PolyHandle OpenPoly(void) LISA_IU(OPENPOLY);
pascal void ClosePoly(void) LISA_IU(CLOSEPOL);
pascal void KillPoly(PolyHandle poly) LISA_IU(KILLPOLY);
pascal void OffsetPoly(PolyHandle poly, Integer dh, Integer dv) LISA_IU(OFFSETPO);
pascal void MapPoly(PolyHandle poly, const Rect *fromRect, const Rect *toRect) LISA_IU(MAPPOLY);
pascal void FramePoly(PolyHandle poly) LISA_IU(FRAMEPOL);
pascal void PaintPoly(PolyHandle poly) LISA_IU(PAINTPOL);
pascal void ErasePoly(PolyHandle poly) LISA_IU(ERASEPOL);
pascal void InvertPoly(PolyHandle poly) LISA_IU(INVERTPO);
pascal void FillPoly(PolyHandle poly, const Pattern *pat) LISA_IU(FILLPOLY);

/* ---- regions ---------------------------------------------------------- */

pascal RgnHandle NewRgn(void) LISA_IU(NEWRGN);
pascal void DisposeRgn(RgnHandle rgn) LISA_IU(DISPOSER);
pascal void CopyRgn(RgnHandle srcRgn, RgnHandle dstRgn) LISA_IU(COPYRGN);
pascal void SetEmptyRgn(RgnHandle rgn) LISA_IU(SETEMPTY);
pascal void SetRectRgn(RgnHandle rgn, Integer left, Integer top, Integer right, Integer bottom) LISA_IU(SETRECTR);
pascal void RectRgn(RgnHandle rgn, const Rect *r) LISA_IU(RECTRGN);
pascal void OpenRgn(void) LISA_IU(OPENRGN);
pascal void CloseRgn(RgnHandle dstRgn) LISA_IU(CLOSERGN);
pascal void OffsetRgn(RgnHandle rgn, Integer dh, Integer dv) LISA_IU(OFFSETRG);
pascal void MapRgn(RgnHandle rgn, const Rect *fromRect, const Rect *toRect) LISA_IU(MAPRGN);
pascal void InsetRgn(RgnHandle rgn, Integer dh, Integer dv) LISA_IU(INSETRGN);
pascal void SectRgn(RgnHandle srcRgnA, RgnHandle srcRgnB, RgnHandle dstRgn) LISA_IU(SECTRGN);
pascal void UnionRgn(RgnHandle srcRgnA, RgnHandle srcRgnB, RgnHandle dstRgn) LISA_IU(UNIONRGN);
pascal void DiffRgn(RgnHandle srcRgnA, RgnHandle srcRgnB, RgnHandle dstRgn) LISA_IU(DIFFRGN);
pascal void XorRgn(RgnHandle srcRgnA, RgnHandle srcRgnB, RgnHandle dstRgn) LISA_IU(XORRGN);
pascal Boolean EqualRgn(RgnHandle rgnA, RgnHandle rgnB) LISA_IU(EQUALRGN);
pascal Boolean EmptyRgn(RgnHandle rgn) LISA_IU(EMPTYRGN);
pascal Boolean PtInRgn(Point pt, RgnHandle rgn) LISA_IU(PTINRGN);
pascal Boolean RectInRgn(const Rect *r, RgnHandle rgn) LISA_IU(RECTINRG);

pascal void FrameRgn(RgnHandle rgn) LISA_IU(FRAMERGN);
pascal void PaintRgn(RgnHandle rgn) LISA_IU(PAINTRGN);
pascal void EraseRgn(RgnHandle rgn) LISA_IU(ERASERGN);
pascal void InvertRgn(RgnHandle rgn) LISA_IU(INVERTRG);
pascal void FillRgn(RgnHandle rgn, const Pattern *pat) LISA_IU(FILLRGN);

/* ---- bit transfer ----------------------------------------------------- */

pascal void ScrollRect(const Rect *dstRect, Integer dh, Integer dv, RgnHandle updateRgn) LISA_IU(SCROLLRE);
pascal void CopyBits(const BitMap *srcBits, const BitMap *dstBits, const Rect *srcRect,
                     const Rect *dstRect, Integer mode, RgnHandle maskRgn) LISA_IU(COPYBITS);

/* ---- pictures --------------------------------------------------------- */

pascal PicHandle OpenPicture(const Rect *picFrame) LISA_IU(OPENPICT);
pascal void ClosePicture(void) LISA_IU(CLOSEPIC);
pascal void DrawPicture(PicHandle myPicture, const Rect *dstRect) LISA_IU(DRAWPICT);
pascal void PicComment(Integer kind, Integer dataSize, QDHandle dataHandle) LISA_IU(PICCOMME);
pascal void KillPicture(PicHandle myPicture) LISA_IU(KILLPICT);

/* ---- miscellaneous ---------------------------------------------------- */

pascal Boolean GetPixel(Integer h, Integer v) LISA_IU(GETPIXEL);
pascal Integer Random(void) LISA_IU(RANDOM);
pascal void StuffHex(void *thingPtr, const unsigned char *s) LISA_IU(STUFFHEX);
pascal void ForeColor(LongInt color) LISA_IU(FORECOLO);
pascal void BackColor(LongInt color) LISA_IU(BACKCOLO);
pascal void ColorBit(Integer whichBit) LISA_IU(COLORBIT);

#endif
