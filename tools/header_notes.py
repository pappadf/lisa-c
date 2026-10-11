"""Hand-written notes and helpers for the generated headers (tools/gen_headers.py).

NOTES[unit] = {'doc': text placed at the top of the unit's header,
               'extra': C code appended after the unit's declarations}
Written for lisa-c; the declarations themselves are generated.
"""

NOTES = {
    'syscall': {'doc': '''Lisa OS types and constants (units SysCall, PSysCall): path names, file
and process information records, ... for use with the OS calls in
lisa_os.h (lisa_open, lisa_info, ...).  The calls themselves are not
declared here: lisa_os.h reaches them with TRAP #1.'''},
    'UnitStd': {'doc': 'Standard types and string utilities (UnitStd).'},
    'UnitHz': {'doc': 'Heap zones (UnitHz): allocation in a zone, handles, compaction.'},
    'Storage': {'doc': '''The QuickDraw / Window Manager storage manager (Storage).  A tool sets up
its heap with InitHeap before InitMP; theHeap is that heap.'''},
    'QuickDraw': {'doc': '''QuickDraw, the Lisa graphics package (as published in the Lisa Pascal 3.0
manual, section E.13).  InitGraf(&thePort) first.  Coordinates are
local to the current port; Lisa pixels are about 1.5 times taller than
wide (90 x 60 dots per inch).''',
                  'extra': '''
/* Style is a Pascal set of StyleItem, passed as a bit mask:
 * TextFace(bold | underline). */
enum { bold = 1 << 0, italic = 1 << 1, underline = 1 << 2, outline = 1 << 3,
       shadow = 1 << 4, condense = 1 << 5, extend = 1 << 6 };
'''},
    'HwInt': {'doc': '''Hardware interface (HwInt): mouse, keyboard, timers, the speaker, the
screen and the clock.'''},
    'FontMgr': {'doc': 'Font Manager (FontMgr): fonts by family, face and size.'},
    'Events': {'doc': '''Event Manager (Events).  Office System tools get their input -- mouse,
keyboard, window activation and messages from the Desktop Manager (the
Filer) -- as events.  GetEvent may suspend the process until an event
arrives; after a buttonDown, track the mouse with StillDown and GetMouse.'''},
    'Windows': {'doc': 'Window Manager (Windows): windows are GrafPorts.'},
    'Folders': {'doc': '''Window Manager (Folders): the document window ("folder") the Desktop
Manager hands a tool: TakeWindow, updates, activation, size.'''},
    'Menus': {'doc': '''Menu Manager (Menus).  A tool's menus come from its phrase file (InitMP
in AlertMgr fills an array of MenuInfo, one per menu).''',
              'extra': '''
/* enableFlags is a Pascal packed array of boolean: item i (0 = the whole
 * menu) is bit i % 8 of byte i / 8.  EnableItem/DisableItem change it. */
#define MenuEnabled(m, i) (((m)->enableFlags[(i) >> 3] >> ((i) & 7)) & 1)
'''},
    'WmlStd': {'doc': 'Window Manager library: common types (WmlStd).'},
    'WmlCrs': {'doc': 'Window Manager library: the standard cursors (WmlCrs): InitWmlCrs, SetStdCursor.'},
    'WmlGrow': {'doc': '''Window Manager library: the size control in the lower right corner
(WmlGrow): PaintGrow; on a buttonDown, FGrowHit then DragFrame, then
FolderSize with the new bottom right corner.'''},
    'WmlSb': {'doc': '''Window Manager library: scroll bars (WmlSb).  Office System windows draw
their own scroll bars, only while active:
  InitWmlSb(); InitSbList(&list, theHeap);
  h = SbCreate(&list, hsbNil, tyvhV, pt, 100);  SetSbIcons(h, sbAllIcons);
  SetPort(win); FlushRects(&rH, &rV); SetSbRect(h, &rV); PaintSbar(h);
  on deactivate HideSBorder(&win->portRect);
  buttonDown: FSbHit(&list, pt, &h, &icon) -> arrows: PaintArw and scroll
  while StillDown(); gray: a page at a time; thumb: DragThumb, SetThumb.
Thumb positions are in thousandths of the range.''',
              'extra': '''
/* A set of TIcon (bit i = icon i), passed by value. */
#define sbIcon(i)   (1 << (i))
#define sbAllIcons  (sbIcon(iconArwA) | sbIcon(iconPagA) | sbIcon(iconThumb) | \\
                     sbIcon(iconPagB) | sbIcon(iconArwB))
'''},
    'International': {'doc': 'International utilities (International): dates, numbers, sorting.'},
    'AlertMgr': {'doc': '''Alert Manager (AlertMgr): a tool's alerts and menus live in its phrase
file ({Tn}PHRASE).  InitMP reads them at startup; StopAlert, NoteAlert,
CautionAlert (true for OK), AskAlert show an alert by number.'''},
    'UnitFf': {'doc': 'Standard utilities: free-format numbers (UnitFf).'},
    'UnitCs': {'doc': 'Standard utilities: character sets and strings (UnitCs).'},
    'UnitFile': {'doc': 'Standard utilities: files (UnitFile).'},
    'FmgrUtil': {'doc': 'Font Manager utilities (FmgrUtil).'},
    'PMDecl': {'doc': 'Parameter memory: declarations (PMDecl).'},
    'PMM': {'doc': 'Parameter memory manager (PMM): the user\'s Preferences settings.'},
    'UnitFigAtom': {'doc': 'Standard utilities: figure atoms (UnitFigAtom).'},
    'Sys1Lock': {'doc': 'Locking of system library segments (Sys1Lock).'},
    'dbenv': {'doc': 'Data-base environment types used by the field editor (dbenv).'},
    'FEDec': {'doc': 'Field editor: declarations (FEDec).'},
    'FldUt': {'doc': 'Field editor: utilities (FldUt).'},
    'FieldEdit': {'doc': '''Field editor (FieldEdit): single- and multi-line editable text fields
with selection, typing, cut, copy and paste.'''},
    'Scrap': {'doc': '''The desktop Clipboard (Scrap): put the selection on it for Cut and Copy,
read it back for Paste.'''},
    'FilerComm': {'doc': '''Desktop Manager (Filer) communication (FilerComm).  The Filer starts a
tool with Make_Process and sends it filerEvents; GetAddParms fetches the
operation and the document's diskfile prefix:
  fcResume: open the document (window event.who, prefix thePrefix);
  fcNone: the tool icon was opened (no document);
  fcClose, fcSuspend, fcPut, fcCopy, fcShred: save as needed, then
    TellFiler(&err, docClosd, allOk, event.who);
  fcTerminate: end the process (the SYS_TERMINATE handler calls ImDying).
Menu commands: Set Aside = DoFilingCmd(cmdClose), Set Aside Everything =
DoFilingCmd(cmdClosAll).'''},
    'PrPublic': {'doc': 'Printing: the public interface (PrPublic).'},
    'PrStdInfo': {'doc': 'Printing: print records and printer information (PrStdInfo).'},
    'PrStdProcs': {'doc': 'Printing: standard procedures (PrStdProcs).'},
    'PrFileProcs': {'doc': 'Printing: print files (PrFileProcs).'},
    'PrBuf': {'doc': 'Printing: buffers (PrBuf).'},
    'PrSpool': {'doc': 'Printing: spooling (PrSpool).'},
    'Queues': {'doc': 'Printing: queues (Queues).'},
    'PrEvents': {'doc': 'Printing: events (PrEvents).'},
    'PrDlgMgr': {'doc': 'Printing: the Format for Printer and Print dialogs (PrDlgMgr).'},
    'PrMgr': {'doc': 'Printing: the print manager (PrMgr).'},
}
