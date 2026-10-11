# lisa-c: C cross-compiler setup for the Apple Lisa Office System

C programs are built on the host into Lisa executable object files and written to a 400K LOS floppy image. They run in granny-smith either as **Office System desktop tools** (windows, menus, QuickDraw) or as Workshop console programs. Nothing is compiled or linked on the Lisa. Programs get a standard C library (picolibc), writable globals, a heap, console and file I/O, and C headers for QuickDraw, windows, scroll bars, events, menus, alerts and the Filer protocol. A program can have several source files and can live outside lisa-c (`SRCDIR=`).

The compiler is **Retro68's GCC** (68000 target). Its `pascal` attribute provides the Lisa Pascal calling convention. `make toolchain` downloads a prebuilt, trimmed copy (about 70 MB) into `toolchain/retro68`; `.github/workflows/toolchain.yml` builds it from a pinned Retro68 commit and publishes it as a release (push a `toolchain-*` tag). To build it yourself: `tools/build_toolchain.sh <Retro68 checkout> <build dir> <prefix>` (binutils and a C-only GCC with libgcc, about 25 minutes on 2 cores), then `tools/package_toolchain.sh <prefix> toolchain/retro68`.

```
make                  # build/hello.obj  (Lisa executable)
make PROG=libc        # build tests/libc/libc.c (or examples/<name>/<name>.c)
make disk             # build/<prog>.dc42  (400K floppy, volume "LisaC")
make run              # boot Workshop in granny-smith, Run -lisac-<prog>, screenshot
make test             # every test: Workshop programs (tests/<name>) and desktop tools; compares
                      # screenshots with $(EXPECT) (kept outside the repo; SKIP without them)
make test-<name>      # one test
make PROG=hellotool tool     # desktop tool: build/hellotool-tool.dc42 ({T20}obj + {T20}PHRASE)
make test-tool-hellotool     # install it on the LOS desktop, open a document, Set Aside
make PROG=hellotool serve    # run it interactively: granny-smith in the browser, LOS 3.1 booted
                             # with the floppy in the drive (prints the address to open)
```

- `make run` puts its screenshot in `build/emu-<prog>/run.png`.
- To type input into a running program, set `INPUT='text\n'` for `make run`, or add `tests/<name>/input.txt` for `make test`.
- A Workshop program builds and runs in about 10 seconds, and a desktop-tool test in about 90 seconds (it boots LOS, inserts the floppy, opens a document and sets it aside).

**Running needs the emulator and your own Apple software** (never part of this repository), set up in `emu/env.sh`:
- `gs-headless`, granny-smith's headless emulator: `GS_HEADLESS`, `build/gs/gs-headless`, the `PATH`, or a granny-smith checkout next to lisa-c.
- `media/lisa.rom` (Lisa 2 boot ROM, rev H), `media/los31.image` (Office System 3.1 on a ProFile) and `media/workshop.image` (Workshop 3.0 on a ProFile), or `LISA_ROM`, `LOS_IMAGE`, `WORKSHOP_IMAGE`.

Coding agents: see `AGENTS.md` and the skills in `.agents/skills/`.

## Tests (all pass)

| Test | What it covers |
|---|---|
| `hello` | minimal runtime, PASLIB console output |
| `globals` | `.data`/`.bss` in the data segment |
| `arith` | 32/64-bit multiply, divide, modulo and shifts; float/double arithmetic and conversions (Retro68's 68000 libgcc) |
| `libc` | `printf` (incl. `long long`, `%f`, `%e`), `snprintf`, `malloc`/`realloc` up to 200 KB, `qsort`, `strtod`, libm, file create/write/read/seek/append/remove, `errno`. Two code segments. |
| `stdin` | console input with `fgets`/`sscanf` (the runner types the line) |
| `tools/hellotool` | **Office System desktop tool** (`examples/hellotool`): the desktop starts it from a floppy, it draws in its document window, shows its File/Print menu, and "Set Aside" closes the document through the Filer protocol |

## Pipeline

1. Retro68's `m68k-apple-macos-gcc -m68000 -ffixed-a5 -ffunction-sections` compiles the program, the runtime and picolibc. A5 is reserved because it is the Pascal/OS globals pointer. Every object must come from this one compiler: its C convention (D2 scratch, 2-byte `short`/`char` arguments) differs from other m68k GCCs.
2. `tools/lisalink.py` links in two passes and packs the code into segments:
   - Pass 1 learns the size of every function.
   - The functions are then packed into code segments of at most 32 KB: SEG*n* at MMU *n* (*n* × 128K, code at +8 after the CodeBlock header), up to 16 segments.
   - Pass 2 links with a generated script and `--emit-relocs`.
   - Both passes call Retro68's real linker (`ld.real`) rather than its Elf2Mac wrapper, and set the entry point explicitly, because the driver's `-elf2mac` flag is otherwise read as `-e lf2mac`.
3. `tools/elf2lisa.py` writes the Workshop 3.0 object records:
   - VersionCtrl, a reserved `$B2` record, UnitTable, Executable (header + jump table), SegmentTable
   - then, per segment, ModuleName, CodeBlock and EndBlock
   - EOFMark

   It also routes code references through the **jump table**: calls between segments, function pointers, and `lea`/`pea` of functions. Calls within a segment stay direct. At run time the loader copies the jump-table descriptors to the top of the stack segment, so descriptor *i* of *n* is at `$F80000 − 6n + 6i` (measured).

   `tools/objdump_lisa.py` dumps any Lisa object file.
4. `tools/mklisafs.py` (via `tools/mkdisk.sh`) writes a new 400K diskette image, volume `LisaC`, holding the files. It builds the whole Office System 3.1 file system itself (MDDF, bitmap, s-list, B-tree catalog, file hint pages and sector tags), so no Apple disk is needed. The diskette has no boot tracks, so it is a data disk only. It also writes the Desktop Manager's catalog (`{!CATALOG}`), with the tool, its stationery pad and any documents given with `DISKARGS='--document NAME TOOLNUM SUFFIX=FILE'`, so the Office System uses the disk as it is. `tools/lisadisk.py` reads a diskette back, including one the Lisa has written (`files`, `desktop`, `extract`).

   For a desktop tool (`make tool`) the files are `{T20}obj` and `{T20}PHRASE`. The phrase file is compiled from `<prog>.phrase` by `tools/phrasec.py`, and `{T20}obj` gets a file label that names the tool on the desktop (`TOOLNAME`). The floppy is named `DISKNAME` (default: `TOOLNAME`) and holds the Desktop Manager's catalog (`{!CATALOG}`), which registers the tool and its stationery pad, so the Office System uses the disk without asking to Repair it.
5. To run:
   - **Workshop programs:** `emu/run-workshop.sh` boots the Workshop ProFile image, inserts the floppy, and types `r`, `-lisac-<prog>`, Return (and `INPUT`, if set).
   - **Desktop tools:** `emu/run-los-tool.sh` boots LOS 3.1, inserts the floppy, opens the diskette and a new document, and with `CLOSE=1` chooses File/Print > Set Aside.

## Memory layout

| What | Where |
|---|---|
| Code segments | MMU 1..16: `$20000`, `$40000`, … (code at +8) |
| `.data`, `.rodata`, `.bss` | private data segment bound to LDSN 1 at `$D60000`. The OS maps LDSN *n* at (106 + *n*) × 128K (OS manual fig. 3-1). |
| Heap (`malloc` → `sbrk`) | private data segment at LDSN 6 (`$E00000`), grown in 32 KB steps with `SIZE_DATASEG`, up to LDSN 16 (1.4 MB). LDSN 5 is left to PASLIB's own heap. |
| Stack, A5 globals frame | stack segment (MMU 123), set up by PASLIB `%_BEGIN` |

`.rodata` lives in RAM too, so code never reads constants out of another code segment. Its initial image, together with `.data`, is stored at the end of SEG1. `crt0` creates the data segment and copies the image in before `main`.

## Libraries

- **`runtime/` → `build/lib/liblisa.a`**:
  - **`crt0.S`**: the Pascal main-program skeleton (`%_BEGIN`, `link a5`, `%_INIT`, `__lisa_init`, `main`, `exit`, `%_TERM`, `%_END`).
  - **`lisa.c`**: data-segment setup, console helpers and `lisa_fatal`.
  - **`paslib.S`**: C stubs for PASLIB console I/O (`%W_STR`, `%W_C`, `%W_LN`, `%R_C`, `%_EOLN`, `%R_LN`).
  - **`posix.c`**: the system calls picolibc needs: `open`/`read`/`write`/`lseek`/`close`/`fstat`/`stat`/`unlink`/`isatty`, `sbrk`, `gettimeofday`/`clock_gettime`, `nanosleep`, `_exit`, plus Lisa error → `errno` mapping.
    - fd 0/1/2 are the console. Other fds are OS refnums, and positions are tracked in the layer.
    - `lisa_last_error` holds the last raw Lisa error.
  - **`mem.c`**: weak `memcpy` and friends for libc-less programs.
- **`build/rt/lisa_os.S` + `build/include/lisa_os.h`**: generated by `tools/gen_syscalls.py`. They provide `pascal` C prototypes and stubs for 26 OS calls (`lisa_open`, `lisa_read_data`, `lisa_make_dataseg`, `lisa_info_process`, `lisa_declare_excep_hdl`, …), plus `lisa_my_id()` in `paslib.S`.
  - The stubs issue `TRAP #1` exactly like PASLIB's `oslib`, so they don't depend on any library address. They save D2–D7/A2–A6 around the trap, because the OS calls clobber A2.
  - The trap subcodes and the parameter types (from the SYSCALL interface) are tables in the generator.
  - Pascal layout: arguments pushed left to right, callee pops; byte-sized values in the high byte of a word; small sets as a word with bit *i* = element *i*.
- **libgcc**: Retro68's default multilib is 68000-only (checked), so programs link its `libgcc.a`.
- **`include/lisa/` + `build/lib/liblisaiu.a`**: C headers for the intrinsic libraries:
  - One header per library unit a desktop tool can use, 42 in all, with 837 routines: QuickDraw, the Window Manager (`events.h`, `windows.h`, `folders.h`, `menus.h`, and the WM library `wmlsb.h` scroll bars, `wmlgrow.h` size control, `wmlcrs.h` cursors), `alertmgr.h`, `filercomm.h` (the Desktop Manager protocol), `scrap.h` (the Clipboard), `fieldedit.h` (editable text fields), `fontmgr.h`, `international.h`, `pmm.h` (parameter memory), `hwint.h` (hardware), the printing units (`prpublic.h`, `prmgr.h`, ...), the standard utilities (`unitcs.h`, `unitfile.h`, ...) and heap zones (`unithz.h`). `ostypes.h` has the OS's types for `lisa_os.h`. `desktop.h` includes them all.
  - Each routine is a `pascal` declaration. The call goes to a register-saving thunk generated by `tools/gen_iu_thunks.py`, which IUJSRs to the routine's jump vector; the addresses come from the entry-point table `data/entries.tsv` (made by `tools/gen_entries.py` from the Workshop's library files), through `tools/gen_traps.py`.
  - The headers are generated from the INTERFACE sections of the units' Pascal sources (`tools/pascal_iface.py` extracts them, `tools/gen_headers.py` writes C; `make headers LISA_SOURCE=.../Lisa_Source/LISA_OS/LIBS` regenerates). Records are structs with every field at the Pascal offset, variant records anonymous unions; each routine carries its argument and result byte counts. `tests/headers/layout.c` asserts every record size, field offset and parameter size (`make test-headers`, part of `make test`).
  - Names are Apple's (Pascal is case-insensitive, so C uses the spelling of the interface source, e.g. `allOK`, `cmdClosAll`; routine names start with a capital: `InitMP`). Unit globals are macros (`thePort`, `deskPort`, `theHeap`, ...). Enumeration values that are plain lowercase words (`frame`, `draw`, `v`, `h`, ...) are left out so they do not take common names; text styles are bit masks (`bold | underline`).
- **picolibc 1.8.12** (`picolibc/build.sh` → `build/sysroot`):
  - built with `-m68000 -ffixed-a5`, single-threaded, no thread-local storage, POSIX console, `long long` printf
  - its fallback `sbrk` is removed so ours always wins
- No 68020-only instructions appear anywhere in the built libraries (checked with objdump).

PASLIB calls use the IU instructions. `IUJSR` is the long word `$A0xxxxxx`, a Line-A trap to the routine's jump vector at absolute address `xxxxxx`: for example `%W_STR` at `$C00088` (PASIOLIB, MMU 96) and `%_BEGIN` at `$220204` (PASLIB1, MMU 17). The vectors come from `IOSPASLIB.OBJ`, so they are tied to Workshop 3.0 / LOS 3.x.

## Desktop tools

Key points:
- Build with `TOOL=1`. This writes the SYS1LIB unit/segment tables and the tool version record.
- Startup order, as in Apple's tools:
  1. `InitGraf(&thePort)` and `OpenWM()`
  2. declare a `SYS_TERMINATE` handler that calls `ImDying`
  3. `SetPort(deskPort)`, `InitHeap`, then `InitMP` (menus from the phrase file) and `InitWmlCrs`
- A tool that crashes without calling `ImDying` freezes the whole desktop, as the protocol memo warns.
- **Library calls go through register-saving thunks** (`liblisaiu.a`, generated by `tools/gen_iu_thunks.py` from the headers). The Lisa libraries clobber registers such as D3 and A2 that C code expects to be preserved. This was found when `InitWmlCrs` received a stale D3 as its error pointer.
- Unit globals (`thePort`, `theHeap`, `deskPort`, `menuFolder`, `activeFolder`, …) are reached through the program's data-pointer table at `$1FC + 4n(A5)` (`lisa_unit_data`).
- **Phrase files** (menus and alerts) are compiled on the host by `tools/phrasec.py` from Apple's phrase source format; see `examples/hellotool/hellotool.phrase`. `phrasec.py --dump` decodes any compiled phrase file.
- **Tool name:** for tool numbers above 16, the Desktop Manager takes the tool's name from the file label of `{Tn}obj`, which `mklisafs.py -t NAME` writes.

## Example application

**[LisaPaint](https://github.com/pappadf/lisa-paint)** is a complete Office System tool built with lisa-c: a MacPaint-style pixel painting program with tool and pattern palettes, the Lisa's own scroll bars and size control, menus and alerts from its phrase file, Undo, selections, magnified view, and documents saved through the Desktop Manager. It keeps lisa-c as a git submodule and builds its sources from its own directory (`SRCDIR`), so it doubles as a template for a new application: `make` builds the floppy, and `make serve` runs it in the browser.

## Current limitations

- **Data image:** the initial data image (`.data` + `.rodata`) has to fit in SEG1 next to the startup code. `.data`, `.rodata` and `.bss` must together fit in LDSN 1..5 (640 KB).
- **No stack probes:** the stack-probe prologue (`tst.w -4096(sp)`, Pascal's `$X+`) is not emitted, so avoid very large stack frames.
- **Fixed `fs_info` offset:** `fs_info.size` is read at a measured offset (300). `stat` is implemented by opening the file.
- **Packed code:** PackedCode (compressed segments) is never emitted; segments are stored unpacked.
- **Read-only code:** not verified directly; `.rodata` is placed in RAM regardless.

## Other tools

- `tools/objdump_lisa.py`: dump the records of any Lisa object file.
- `tools/unpack_lisa.py`: unpack PackedCode segments (the OS unpacker, with the `SYSTEM.UNPACK` table).
- `tools/gen_entries.py` → `data/entries.tsv`: 1,810 library entry points (link name → jump-vector address) from the Workshop's library files. They are valid for LOS 3.1 too.
- `tools/lisa_tables.py`: the unit and segment tables for PASLIB-only programs and for desktop tools.
- `tools/phrasec.py --dump file`: decode a compiled phrase file (menus, alert signs, buttons, alerts).

## A Note on AI

This project allows the use of AI. That isn't limited to code generation or
code review: it also covers documentation and research into how the Lisa
Office System works.
There is no intention to track, at the file or commit level, which code was
written with AI assistance and which wasn't. I know that AI may be a red flag
for some people, and I fully respect that.

## License

MIT; see `LICENSE`.
