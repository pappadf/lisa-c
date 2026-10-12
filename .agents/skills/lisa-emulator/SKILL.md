---
name: lisa-emulator
description: >
  Run and test lisa-c programs in the granny-smith emulator (gs-headless):
  set up the emulator and the user's Lisa ROM and disk images, run Workshop
  programs and desktop tools, take and compare screenshots, type input, script
  mouse clicks, save the floppy the Lisa wrote, and debug crashes with
  logpoints.
---
# Running Lisa programs in granny-smith

## Setup (`emu/env.sh`)

- **Emulator:** `gs-headless` from `$GS_HEADLESS`, `build/gs/gs-headless`, the
  `PATH`, or `../granny-smith/build/headless/gs-headless`. Granny-smith releases
  carry static Linux binaries (`granny-smith-headless-<tag>-linux-<arch>.tar.gz`).
- **Apple software, supplied by the user** (never commit it):
  `media/lisa.rom` (Lisa 2 boot ROM, rev H), `media/los31.image` (Office
  System 3.1 installed on a ProFile), `media/workshop.image` (Workshop 3.0 on a
  ProFile). Override with `LISA_ROM`, `LOS_IMAGE`, `WORKSHOP_IMAGE`.

## Scripts

| Script | Does | Screenshots |
|---|---|---|
| `emu/run-workshop.sh floppy prog [out]` | boots the Workshop, inserts the floppy, types `r`, `-lisac-<prog>`, Return; `INPUT='text\n'` types into the program; `RUN_INSTR=N` runs longer | `shell.png`, `run.png` |
| `emu/serve.sh floppy [port]` (`make PROG=x serve`) | interactive: serves granny-smith's web build (release `GS_VERSION`, downloaded into `build/gs-web/`; or `GS_WEB=dir`) with the floppy on one local origin; opening `/` boots a Lisa 2 with LOS 3.1 from the ProFile and the floppy in the drive. ROM and ProFile: `media/` if present, else archive.org copies (`MEDIA=archive` forces those). In a Codespace it prints the forwarded address | (a browser) |
| `emu/run-los-tool.sh floppy [out]` | boots LOS, inserts the floppy, opens the diskette, tears off and opens a document; `CLOSE=1` then chooses File/Print > Set Aside; `LATER=N` runs N instructions after opening; `SAVE=file.dc42` saves the floppy as the Lisa left it | `1-inserted` ... `6-later`, `7-menu`, `8-closed` |
| `emu/boot-los.sh [floppy] [out]` | boots LOS (and inserts a floppy) | `desktop.png`, `floppy.png` |

Each writes its emulator script (`*.script`) and log (`*.log`) into the output
directory: start from those to write a new scenario. Screenshots are 720x364
PNGs; view them to see what happened.

`make PROG=x run` and `make test` use these scripts.

## Writing a scenario

Scripts are plain granny-smith shell commands:

```
machine.boot model="lisa" ram=2048 rom="media/lisa.rom"
machine.hd.attach "build/emu-x/profile.image"        # a scratch copy
assert machine.hd.pram_init(2, false) "pram_init failed"   # boot from the ProFile
scheduler.run 60000000                               # ~ boot to the desktop
machine.floppy.drive.0.insert "build/x-tool.dc42"
machine.adb.mouse.move 597 216 "global"
machine.adb.mouse.click true
scheduler.run 80000
machine.adb.mouse.click false
machine.adb.keyboard.type("text")                    # at most ~12 characters per call
machine.screen.save "build/emu-x/shot.png"
machine.floppy.drive.0.export "build/emu-x/after.dc42" # the floppy, with the Lisa's writes
quit
```

Run: `gs-headless --speed=turbo rom=<rom> model=lisa script=<file>`.

- Runs are deterministic: the same script gives byte-identical screenshots.
- Writes to disk images stay in a delta, not in the source file; use
  `machine.floppy.drive.0.export` (or `machine.hd.save`) to get them out.
- `run-los-tool.sh` takes `TOOLONLY=1` for a tool without stationery (it
  double-clicks the tool's icon, the first one on such a diskette, instead of
  tearing off a sheet), `POST=file` (commands after the tool's window has
  opened), `PRE=file` (granny-smith commands to run right
  after boot, e.g. `appletalk.afp.volumes.add("Name", "/host/dir")` to
  publish an AppleShare volume on the emulated network; the Lisa's Serial B is
  on that network), `SAVE=file.dc42` (the floppy as the Lisa left it, to
  read back with `tools/lisadisk.py`) and `RAM=1024` (a 1 MB Lisa, like
  granny-smith's web build and most real ones; the default is 2048). Test a
  tool at 1 MB too: one that does not fit hangs on "Just a moment, please...".
- Insert floppies after boot: a fresh Lisa may try to start from the floppy,
  and lisa-c floppies are not bootable.
- Icon and button positions on a single-tool diskette are
  fixed (see `run-los-tool.sh`) when the tool's name sorts after "Empty
  Folders" (the desktop lays out new icons in reverse name order): the
  stationery pad at (70, 58), the tool icon
  at (191, 58), a torn-off document at (36, 55); a set-aside document goes to
  the bottom left of the desktop (58, 338). Opening the tool icon starts the
  tool without a document (fcNone), in a smaller window than a document's.

## Tests

`make test` builds each test, runs it and compares the final screenshot(s)
byte for byte with `$(EXPECT)` (`<test>/expected.png`,
`tools/<tool>/{opened,closed}.png`). When a change alters the screen on
purpose, look at the new screenshot, then copy it over the reference.

## Debugging

- **Tool crash:** declare the `SYS_TERMINATE` handler (see `lisa-desktop-tool`)
  and log its data: first long = kind (21 = bus error), then the fault
  address, instruction and PC.
- **Logpoints:** `debug.logpoints.add addr=0x... message="d0=${machine.cpu.d0}"`
  before the run. Code reached through the library jump vectors (IUJSR) runs
  with `$A0` in the top byte of the PC, so library routines need
  `$A0xxxxxx` addresses.
- **Memory:** `machine.memory.peek.l <addr>`; the program's data segment is at
  `$D60000`, the heap at `$E00000`.
- **Which library routine is at a PC:** look the address up in the entry
  table `data/entries.tsv` (link name -> jump-vector address).
- Interactive debugging: `gs-headless --daemon` opens a TCP shell on port
  6800 (see granny-smith's `headless-debug` skill).
