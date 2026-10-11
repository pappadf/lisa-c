---
name: lisa-desktop-tool
description: >
  Write an Apple Lisa Office System desktop tool (application) in C with
  lisa-c: required startup order, the event loop, the Desktop Manager's Filer
  protocol (open, close, terminate), menus and alerts in the phrase file, the
  tool's name on the desktop, and the pitfalls that freeze or crash the desktop.
---
# Writing an Office System desktop tool

Start from `examples/hellotool/hellotool.c` and `hellotool.phrase`; they run the
whole lifecycle and are covered by `make test-tool-hellotool`. A full
application (palettes, scroll bars, size control, document files, alerts) is
LisaPaint, a separate project built with lisa-c (`SRCDIR=`, see lisa-build).

## What a tool is

Files named `{Tn}...` on a volume, n = tool number: `{Tn}obj` (the program,
built with `TOOL=1`) and `{Tn}PHRASE` (menus and alerts). `make PROG=x tool`
writes both to `build/x-tool.dc42`, plus a file label on `{Tn}obj` that names
the tool (`TOOLNAME`). Use tool numbers above 16.

Installing: insert the floppy in LOS, choose **Repair** when it says the disk
is not in the standard format. Repair registers the tool and adds its
"<name> Paper" stationery. Tear off a document and open it: the Desktop
Manager starts the tool (`Make_Process`). `emu/run-los-tool.sh` scripts this.
Opening the *tool* icon itself also starts it, but as `fcNone` with no
document (no prefix): test with a torn-off document.

## Startup (order matters)

```c
InitGraf(&thePort);
OpenWM();                                     /* channel to the Desktop Manager */
lisa_declare_excep_hdl(&err, "\015SYS_TERMINATE" /* Pascal string, copied to RAM */,
                       (void *)LastWishes);   /* handler must call ImDying() */
SetPort(deskPort);                            /* before InitHeap/InitMP, or InitMP hangs */
InitHeap(heap, heap + sizeof heap, (void *)HeapFull);
InitMP(theHeap, prefix, (void *)FailedAlert, PHRASE_VERSION, menus, &alerts, &err);
if (err > 0) { TellFiler(&err, InitFailed, internalError, 0); ImDying(); return 1; }
InitWmlCrs(&err);
```

- `prefix` is `-<volume>-{Tn}` (the phrase file's path without `PHRASE`);
  hellotool derives it from its own program path (`lisa_info_process`).
- `PHRASE_VERSION` must equal the first number in the phrase source.
- `alerts` is a `TAlertFile` (a handle, `static TAlertFile alerts;`), passed
  to StopAlert, CautionAlert, ... afterwards.
- `menus` is an array of `MenuInfo`, one per menu in the phrase file, filled by
  `InitMP` in file order.

## Event loop

```c
while (!done) {
    if (ImActive() && !EventAvail()) { LetOthersRun(); continue; }
    GetEvent(&ev);
    switch (ev.what) {
    case filerEvent:       /* see below */
    case folderActivate:   TakeControl(&ev, false, false); InsertMenu...; DrawMenuBar(); break;
    case folderDeactivate: GiveControl(&ev); break;
    case folderUpdate:     BeginUpdate(ev.who); draw(); EndUpdate(ev.who); break;
    case buttonDown:       if (ev.who == menuFolder) { MenuSelect(ev.where, &m, &i); ...; HiLiteMenu(0); }
    }
}
ImDying();
```

Block in `GetEvent` only while inactive; while active, poll `EventAvail` and
call `LetOthersRun`, as Apple's tools do.

## Filer protocol (`filerEvent`)

`GetAddParms(&err, &ev, &fx)`, then by `fx.theFlrOp`:

| Operation | Do |
|---|---|
| `fcResume` | open the document: window `ev.who` (`TakeWindow`), diskfile prefix `fx.thePrefix`. No reply. |
| `fcNone` | the tool icon was opened: a window but no document (empty prefix) |
| `fcClose` | make the edits permanent, then `TellFiler(&err, docClosd, allOK, ev.who)` |
| `fcSuspend` | save the working state (edits kept separate), reply as above |
| `fcPut`, `fcCopy` | write the document to the new prefix `fx.thePrefix`; reply `docXfered` (fcPut also closes) |
| `fcShred` | just close: `docClosd, allOK` |
| `fcTerminate` | leave the loop |
| anything else | `TellFiler(&err, docClosd, internalError, ev.who)` |

On failure reply `docNotClosed`/`docNotXfered` with a reason (`cantWrite`, ...).

**Document files.** The prefix is a volume plus the start of a file name, e.g.
`-#13-{D103T21}`; name the document's diskfiles by appending to it
(`-#13-{D103T21}PIC`) and use ordinary file calls (`open`, `write`). If none
exist yet, it is a new document.

Menu commands:
- "Set Aside" = `DoFilingCmd(cmdClose)`, "Set Aside Everything" =
  `DoFilingCmd(cmdClosAll)`. On LOS 3.1 Set Aside only hides the window: the
  tool keeps the document open and gets no event; reopening shows it again.
- "Save & Put Away": save as for `fcClose`, then
  `TellFiler(&err, docClosd, docPutBack, window)` and forget the document.
- "Save & Continue" and "Revert to Previous Version" are the tool's own (keep
  the saved version separate from the working state).
- Name the document in Set Aside: `GetFldrTitle(window, title)`, then `SetItem`.

## Window controls (`lisa/wmlsb.h`, `lisa/wmlgrow.h`)

Office System windows draw their own scroll bars and size control, only while
active:

```c
InitWmlSb(); InitSbList(&list, theHeap);                    /* once */
hsbV = SbCreate(&list, hsbNil, tyvhV, pt00, 100);  hsbH = ... tyvhH ...
SetPort(win); FlushRects(&rH, &rV); SetSbRect(hsbH, &rH); SetSbRect(hsbV, &rV);
SetSbIcons(h, sbAllIcons);  /* 0 = gray only: everything is visible */
SetThumb(h, pos * 1000 / range);
activate:   PaintSbar(hsbH); PaintSbar(hsbV); PaintGrow();
deactivate: HideSBorder(&win->portRect);
buttonDown: if (FGrowHit(pt)) { DragFrame(pt, true, &br); FolderSize(win, br.h, br.v, true); }
            else if (FSbHit(&list, pt, &hsb, &icon)) ...
              arrows: PaintArw(hsb, icon, true); scroll while StillDown(); PaintArw(..., false)
              gray (iconPagA/B): a page at a time while StillDown()
              iconThumb: DragThumb(hsb, pt, &c); SetThumb(hsb, c); jump to c
```

Track the mouse after a `buttonDown` with `while (StillDown()) GetMouse(&pt);`
(local coordinates of the current port). `Time()` counts hundredths of a second.

## Office System conventions

- File/Print first: Set Aside Everything, Set Aside "<doc>", Save & Put Away,
  Save & Continue, Revert to Previous Version, Format for Printer..., Print...,
  Monitor the Printer.... No New, Open, Save As, Close or Quit.
- Edit: Undo Last Change, Cut/X, Copy/C, Paste/V, Clear, Select All of Document/A.
- Dim commands that would do nothing (`DisableItem`); write mutually exclusive
  choices as two items with the one in effect dimmed, or check marks.
- Alerts in the phrase file, full sentences, two spaces after a period;
  irreversible actions end "Once you click OK, you will not be able to change
  your mind, even with Undo." `CautionAlert` returns true for OK.
- Pixels are about 1.5 times taller than wide (90 x 60 dpi): a circle is 3
  pixels wide for every 2 tall; draw icons and cursors for that.

## Phrase file (`<name>.phrase`, compiled by `tools/phrasec.py`)

```
2                 phrase version (passed to InitMP)
2                 alerts to cache
1000              alert cache bytes
?                 sign labels: ask, wait, stop, note, caution (one per line)
Wait
Stop
Note
Caution
Cancel            button labels, Cancel and OK first; blank line ends them
OK

1 note alert      alert 1 (required): shown for a missing alert; ^N = its number
Text ...

2 stop alert      alert 2 (required): fatal error
Text ...

0                 end of alerts

1                 menu id
File/Print        title
Set Aside Everything
Set Aside "Name"/W     "/W" = Apple-W shortcut
-                 separator (disabled; so is ".")

0                 end of menus
```

- `;` starts a comment line; a leading `~` quotes the next character.
- Alert header: `<n> <kind> <stages>`, kind `stop|note|wait|ask|caution
  [ok|cancel|stop|note|insist]`, stages like `alert`, `soft; medium alert`,
  `stop alert=1` (reuse alert 1's text). Text escapes: `^N` number, `^L` line
  break, `^0`..`^5` parameters.
- Check a compiled file with `python3 tools/phrasec.py --dump build/<name>.phrase`.

## Pitfalls

- **A crash without the `SYS_TERMINATE` handler freezes the whole desktop.**
  Declare it first. With it, LOS reports "technical difficulties"; the
  handler's data says why (first long: kind, 21 = bus error; then fault
  address, instruction, PC). Log it while debugging.
- Library calls must go through the headers (register-saving thunks).
- Pascal strings everywhere: `s[0]` is the length.
- Unit globals (`thePort`, `deskPort`, `menuFolder`, `activeFolder`, `theHeap`,
  ...) are macros in the headers; do not declare your own.
- Without `TOOLNAME`/a label the tool shows with an empty name on the desktop.
