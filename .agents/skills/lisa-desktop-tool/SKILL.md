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
whole lifecycle and are covered by `make test-tool-hellotool`.

## What a tool is

Files named `{Tn}...` on a volume, n = tool number: `{Tn}obj` (the program,
built with `TOOL=1`) and `{Tn}PHRASE` (menus and alerts). `make PROG=x tool`
writes both to `build/x-tool.dc42`, plus a file label on `{Tn}obj` that names
the tool (`TOOLNAME`). Use tool numbers above 16.

Installing: insert the floppy in LOS, choose **Repair** when it says the disk
is not in the standard format. Repair registers the tool and adds its
"<name> Paper" stationery. Tear off a document and open it: the Desktop
Manager starts the tool (`Make_Process`). `emu/run-los-tool.sh` scripts this.

## Startup (order matters)

```c
InitGraf(&thePort);
OpenWM();                                     /* channel to the Desktop Manager */
lisa_declare_excep_hdl(&err, "\015SYS_TERMINATE" /* Pascal string, copied to RAM */,
                       (void *)LastWishes);   /* handler must call ImDying() */
SetPort(deskPort);                            /* before InitHeap/InitMP, or InitMP hangs */
InitHeap(heap, heap + sizeof heap, (void *)HeapFull);
InitMP(theHeap, prefix, (void *)FailedAlert, PHRASE_VERSION, menus, &alerts, &err);
if (err > 0) { TellFiler(&err, initFailed, internalError, 0); ImDying(); return 1; }
InitWmlCrs(&err);
```

- `prefix` is `-<volume>-{Tn}` (the phrase file's path without `PHRASE`);
  hellotool derives it from its own program path (`lisa_info_process`).
- `PHRASE_VERSION` must equal the first number in the phrase source.
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
| `fcResume`, `fcNone` | the document window is `ev.who`: `TakeWindow`, draw. No reply. |
| `fcClose`, `fcSuspend`, `fcPut`, `fcCopy`, `fcShred` | save if needed, then `TellFiler(&err, docClosd, allOk, ev.who)` |
| `fcTerminate` | leave the loop |
| anything else | `TellFiler(&err, docClosd, internalError, ev.who)` |

Menu commands: "Set Aside" = `DoFilingCmd(cmdClose)`, "Set Aside Everything" =
`DoFilingCmd(cmdCloseAll)`.

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
