---
name: lisa-build
description: >
  Build C programs for the Apple Lisa with lisa-c: add a new program, build a
  Workshop program or a desktop-tool floppy, understand the pipeline (Retro68
  GCC -> lisalink -> elf2lisa -> mklisafs), what C library features exist,
  the memory layout and the current limitations.
---
# Building Lisa programs with lisa-c

## Add a program

1. Create `examples/<name>/<name>.c`. (The Makefile looks in `examples/<name>/`
   first, then `tests/<name>/`.) Every `.c` file in that directory is part of
   the program, and its headers are on the include path. An app kept in its
   own repository passes its source directory instead:
   `make -C path/to/lisa-c PROG=<name> SRCDIR=$PWD/src tool` (output in
   lisa-c's `build/`).
2. Workshop (console) program: an ordinary `int main(void)` using stdio.
   Build with `make PROG=<name>`; `make PROG=<name> run` runs it and saves
   `build/emu-<name>/run.png`.
3. Desktop tool: also write `examples/<name>/<name>.phrase` and follow the
   `lisa-desktop-tool` skill. Build with `make PROG=<name> tool`; the floppy is
   `build/<name>-tool.dc42`. Set the desktop name with `TOOLNAME=...` (default:
   the program name) and the tool number with `TOOLNUM=` (default 20; use
   numbers above 16, which the Office System does not know).
4. To make it a regression test, put a Workshop program in `tests/<name>/`
   (optionally `input.txt`) and add its reference screenshot as
   `$(EXPECT)/<name>/expected.png`.

## What the C environment offers

- picolibc: stdio (console through PASLIB: `printf`, `fgets`, `getchar`),
  `malloc`/`free`, string and math functions, `time`/`gettimeofday`,
  `nanosleep`.
- Files: `fopen`/`open`/`read`/`write`/`lseek`/`stat`/`unlink` map to Lisa OS
  calls (no `rename`). Lisa paths look like `-volume-name` (e.g. `-lisac-data.txt`);
  a bare name is relative to the working directory.
- Lisa OS calls directly: `#include "lisa_os.h"` (generated; `lisa_open`,
  `lisa_make_dataseg`, `lisa_info_process`, `lisa_delay_time`, ...). Each takes
  `int16_t *ecode` first; Pascal strings (length byte first) for paths.
- Lisa libraries: `#include "lisa/desktop.h"` (all 42 units) or a single
  `lisa/<unit>.h` (quickdraw, events, windows, folders, menus, alertmgr,
  filercomm, scrap, fieldedit, fontmgr, wmlsb, wmlgrow, wmlcrs, hwint,
  international, pmm, prmgr, ...). These are `pascal` functions: strings are
  Pascal strings (`unsigned char s[]`, `s[0]` = length), `VAR` parameters and
  records passed by value larger than 4 bytes are pointers. Names are Apple's
  (`allOK`, `cmdClosAll`, `InitMP`); unit globals are macros (`thePort`,
  `deskPort`, `theHeap`); text styles are masks (`bold | underline`);
  enumeration values that are plain lowercase words (`frame`, `draw`) are
  left out.
- The OS's record types (`fs_info`, `pathname`, ...) for `lisa_os.h` calls:
  `lisa/ostypes.h`.
- Multiple code segments are made automatically (up to 16 x 32 KB).

## Pipeline (what `make` runs)

1. Retro68 GCC (`-m68000`, A5 reserved) compiles C and the runtime.
2. `tools/lisalink.py` links twice with `ld.real`, packing functions into
   segments of at most 32 KB and placing data in a data segment.
3. `tools/elf2lisa.py` writes the Lisa Workshop 3.0 object format (code
   segments, jump table for calls between segments, unit/segment tables;
   `--tool` adds the desktop-tool tables). `tools/objdump_lisa.py` dumps it.
4. `tools/phrasec.py` compiles the phrase file (tools only).
5. `tools/mklisafs.py` writes a 400K Office System 3.1 floppy (volume LisaC,
   no boot tracks: a data disk).

Generated at build time: `build/include/lisa_os.h` + OS-call stubs
(`tools/gen_syscalls.py`), `build/include/lisa/traps.h` and the library thunks
`build/lib/liblisaiu.a` (`tools/gen_traps.py`, `tools/gen_iu_thunks.py`, from
the entry table `ENTRIES`).

## Memory layout

| What | Where |
|---|---|
| Code | segments at `$20000`, `$40000`, ... (code at +8) |
| `.data`/`.rodata`/`.bss` | data segment at `$D60000` (LDSN 1) |
| Heap | data segment at `$E00000` (LDSN 6), grown 32 KB at a time, up to 1.4 MB |
| Stack | the Lisa's stack segment; the jump table sits at its top (`$F80000`) |

## Limitations

- The initial `.data` + `.rodata` image must fit in the first segment next to
  the startup code; `.data` + `.rodata` + `.bss` must fit in 640 KB.
- No stack probes: avoid very large stack frames (several KB).
- No compressed (packed) code segments.
- Floppies are 400K data disks only (not bootable).

## Troubleshooting

- A routine missing from the headers (they cover the units in a tool's unit
  table): declare it in your own source as
  `pascal RESULT Name(params) LISA_IU(LINKNAME, ARGBYTES, RESULTBYTES);`
  with its link name from `data/entries.tsv`; the build makes its thunk only
  for declarations in `include/lisa`, so add it there or ask for the unit.
- Never link objects from another m68k compiler (D2 and `short` arguments are
  handled differently).
