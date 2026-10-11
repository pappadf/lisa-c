# lisa-c: agent instructions

lisa-c cross-compiles C into native programs for the Apple Lisa Office System 3.x
(LOS) and writes them to a floppy image that runs in the
[granny-smith](https://github.com/pappadf/granny-smith) emulator. Everything runs
on the host; nothing is compiled or linked on the Lisa.

Two kinds of program:
- **Desktop tools**: real Office System applications (window, QuickDraw, menus,
  the Desktop Manager's Filer protocol). `examples/hellotool` is the reference.
- **Workshop programs**: console programs (stdio via picolibc) run from the
  Lisa Workshop shell. `tests/*` are examples.

## Layout

| Path | What |
|---|---|
| `examples/<name>/` | Programs: every `.c` in the directory, and for a desktop tool `<name>.phrase` (menus, alerts). An app elsewhere passes `SRCDIR=/path` |
| `tests/<name>/` | Workshop test programs (`input.txt` = typed input) |
| `include/lisa/` | C headers for the Lisa libraries, one per unit (42), generated from Apple's Pascal interfaces: QuickDraw, Window Manager, menus, alerts, Filer protocol, Clipboard, field editor, printing, fonts, hardware, … `lisa/desktop.h` includes them all |
| `runtime/` | Startup code, PASLIB console glue, POSIX layer for picolibc |
| `tools/` | The pipeline: `lisalink.py` (link), `elf2lisa.py` (Lisa object format), `phrasec.py` (phrase files), `mklisafs.py` (floppy file system and desktop catalog), `lisadisk.py` (reading floppies the Lisa wrote: files, desktop objects), generators for library thunks and OS-call stubs |
| `emu/` | Emulator scripts (`env.sh` = settings; see the `lisa-emulator` skill) |
| `picolibc/` | Builds picolibc for the 68000 into `build/sysroot` |
| `media/` | **Not in git.** The user's own Apple software: `lisa.rom`, `los31.image`, `workshop.image` |
| `toolchain/` | **Not in git.** The compiler (`make toolchain`) |
| `build/` | Everything generated |

## Commands

```bash
make PROG=<name>               # Workshop program  -> build/<name>.obj
make PROG=<name> disk          # ... and its floppy -> build/<name>.dc42 (volume LisaC)
make PROG=<name> run           # build and run in the Workshop -> build/emu-<name>/run.png
make PROG=<name> tool          # desktop tool floppy -> build/<name>-tool.dc42
make test                      # all tests; PASS/FAIL/SKIP per test
make test-<name>               # one Workshop test
make test-tool-<name>          # one desktop-tool test (install, open, Set Aside on LOS)
make PROG=<name> serve         # run a desktop tool interactively in the browser (emu/serve.sh)
make clean
make toolchain                 # download the prebuilt compiler (once)
```

## Requirements

- The compiler: Retro68's GCC for m68k. `make toolchain` downloads the prebuilt
  one (a release of this repo, built by `.github/workflows/toolchain.yml`) into
  `toolchain/retro68` (`tools/build_toolchain.sh` + `tools/package_toolchain.sh`
  build the same thing from source); or set `CROSS` to another install's
  `.../bin/m68k-apple-macos-`. It is the only compiler: picolibc, the runtime
  and programs must all be built with it, because its C calling convention
  differs from other m68k GCCs.
- Python 3, make, meson + ninja (picolibc, built on first use).
- `data/entries.tsv` (`ENTRIES`): the libraries' entry points, link name ->
  jump-vector address (interface facts, made from the Workshop 3.0 library files
  with `tools/gen_entries.py`; the same vectors as LOS 3.1).
- To run anything: `gs-headless` and the files in `media/` (see `emu/env.sh`).
- `make test` compares screenshots with `EXPECT` (default `../lisa-c-private/tests`);
  a test without a reference screenshot reports SKIP.

## Rules

- **Never commit Apple software**: ROMs, disk images, library files, and LOS
  screenshots (which show Apple's screens). `media/` and `build/` are ignored.
  Interface facts are fine: routine names, entry addresses, record layouts.
- Library routines are called through the `pascal` declarations in
  `include/lisa/*.h`. Each goes through a generated register-saving thunk,
  because the Lisa libraries clobber registers C expects preserved (D3, A2, …).
- The headers are generated (`tools/gen_headers.py`, `make headers` with the
  Lisa source): do not edit them; notes and helpers go in
  `tools/header_notes.py`. `make test-headers` checks every record layout.
  Names are Apple's (Pascal is case-insensitive, so C uses the spelling of
  the interface source, e.g. `allOK`, `cmdClosAll`; routine names start with
  a capital: `InitMP`). Unit globals are macros (`thePort`, `deskPort`,
  `theHeap`, ...). Enumeration values that are plain lowercase words (`frame`,
  `draw`, `v`, `h`, ...) are left out so they do not take common names; text
  styles are bit masks (`bold | underline`).
- Pascal data layout in headers: bytes and booleans in the high byte of a word
  when passed by value; records rounded to whole words; packed boolean arrays
  are 1 bit per element (LSB first).
- Emulator runs are deterministic: compare PNGs byte for byte. A test that
  changes the screen on purpose needs its reference screenshot updated.
- After changing the runtime, headers or tools, run `make test`.

## Skills

Task-specific instructions are in `.agents/skills/` (also `.claude/skills/`):

| Skill | Use it for |
|---|---|
| `lisa-build` | Building programs, adding a new program, how the pipeline works, what C features are available |
| `lisa-desktop-tool` | Writing an Office System desktop tool: startup, event loop, Filer protocol, phrase files, tool names |
| `lisa-emulator` | Running and testing in granny-smith headless, screenshots, scripting input, debugging crashes |
