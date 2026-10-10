# Cross-build C programs for the Lisa Office System.
#
#   make                  build build/hello.obj
#   make PROG=globals     build examples/ or tests/ program "globals"
#   make disk             also put it on a floppy image (build/<prog>.dc42)
#   make run              boot the Workshop in granny-smith and run it
#   make test             run every test (Workshop programs and desktop tools)
#   make test-<name>      run one test
#   make toolchain        download the prebuilt compiler into toolchain/retro68
#   make PROG=x serve     build desktop tool x and run it in the browser (emu/serve.sh)

# Retro68 GCC (m68k-apple-macos): its `pascal` attribute is what the Lisa
# headers and OS-call stubs rely on.  Everything -- runtime, picolibc,
# programs -- must be built with this one compiler.
# Default: toolchain/retro68 (make toolchain), else ../toolchain/retro68.
CROSS   ?= $(abspath $(firstword $(wildcard toolchain/retro68/bin ../toolchain/retro68/bin) \
                                 toolchain/retro68/bin))/m68k-apple-macos-
CC      := $(CROSS)gcc
AR      := $(CROSS)ar
CFLAGS  := -m68000 -Os -ffreestanding -fno-builtin -fno-pic -ffixed-a5 \
           -fno-asynchronous-unwind-tables -fno-tree-loop-distribute-patterns \
           -ffunction-sections -fdata-sections \
           -Wall -Wextra -Iruntime -Iinclude -Ibuild/include -isystem build/sysroot/include
SYSROOT := build/sysroot/lib
LIBGCC  := $(shell $(CC) -m68000 -print-libgcc-file-name 2>/dev/null)
LIBS     = build/lib/liblisa.a build/lib/liblisaiu.a $(SYSROOT)/libc.a $(SYSROOT)/libm.a $(LIBGCC)

# A program is every .c file in SRCDIR (default examples/PROG or tests/PROG;
# an app kept elsewhere passes SRCDIR=/path/to/its/sources).
PROG    ?= hello
SRCDIR   = $(firstword $(wildcard examples/$(PROG) tests/$(PROG)))
SRCS     = $(if $(SRCDIR),$(wildcard $(SRCDIR)/*.c))
OBJS     = $(patsubst $(SRCDIR)/%.c,build/$(PROG)/%.o,$(SRCS))
TESTS   := $(notdir $(patsubst %/,%,$(wildcard tests/*/)))

# Data derived from Apple's software, kept outside this repository:
#   $(ENTRIES)  library entry points (link name -> jump vector), made from the
#               Workshop's library files by tools/gen_entries.py
#   $(EXPECT)   reference screenshots for `make test`: <test>/expected.png and
#               tools/<tool>/{opened,closed}.png
PRIVATE ?= ../lisa-c-private
ENTRIES ?= $(PRIVATE)/data/entries.tsv
EXPECT  ?= $(PRIVATE)/tests
TOOL_TESTS := $(notdir $(patsubst %/,%,$(wildcard $(EXPECT)/tools/*/)))

HEADERS := $(wildcard include/lisa/*.h)
RT_OBJS := build/rt/paslib.o build/rt/lisa.o build/rt/lisa_os.o build/rt/mem.o build/rt/posix.o

all: build/$(PROG).obj

build build/rt build/lib build/include:
	mkdir -p $@

# picolibc (C library), built for the 68000 into build/sysroot
$(SYSROOT)/libc.a $(SYSROOT)/libm.a: picolibc/build.sh | build
	CROSS=$(CROSS) picolibc/build.sh > build/picolibc.log 2>&1 || (tail -20 build/picolibc.log; exit 1)

# Generated lisa/traps.h (IUJSR words per library entry point)
$(ENTRIES):
	@echo "$@ is missing: make it with tools/gen_entries.py from the Workshop library files" >&2; exit 1

build/include/lisa/traps.h: $(ENTRIES) tools/gen_traps.py
	mkdir -p build/include/lisa
	python3 -I tools/gen_traps.py $< $@

# Register-saving thunks for the library routines declared in include/lisa
build/iu/.stamp: $(HEADERS) $(ENTRIES) tools/gen_iu_thunks.py
	rm -rf build/iu && python3 -I tools/gen_iu_thunks.py $(ENTRIES) build/iu $(filter-out include/lisa/traps.h,$(HEADERS))
	touch $@
build/lib/liblisaiu.a: build/iu/.stamp | build/lib
	cd build/iu && for f in *.S; do $(CC) -m68000 -c $$f -o $${f%.S}.o || exit 1; done
	rm -f $@ && $(AR) rcs $@ build/iu/*.o

# Generated OS system call stubs
build/rt/lisa_os.S build/include/lisa_os.h: tools/gen_syscalls.py | build/rt build/include
	python3 -I tools/gen_syscalls.py build/rt/lisa_os.S build/include/lisa_os.h

build/rt/%.o: runtime/%.S runtime/lisa.inc | build/rt
	$(CC) $(CFLAGS) -c $< -o $@
build/rt/%.o: runtime/%.c runtime/lisa.h build/include/lisa_os.h build/include/lisa/traps.h $(SYSROOT)/libc.a | build/rt
	$(CC) $(CFLAGS) -c $< -o $@
build/rt/lisa_os.o: build/rt/lisa_os.S
	$(CC) $(CFLAGS) -c $< -o $@

build/lib/liblisa.a: $(RT_OBJS) | build/lib
	rm -f $@ && $(AR) rcs $@ $^

build/$(PROG)/%.o: $(SRCDIR)/%.c $(wildcard $(SRCDIR)/*.h) runtime/lisa.h build/include/lisa_os.h \
                   build/include/lisa/traps.h $(SYSROOT)/libc.a $(HEADERS)
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -I$(SRCDIR) -c $< -o $@

build/$(PROG).elf: build/rt/crt0.o $(OBJS) $(LIBS) tools/lisalink.py
	@[ -n "$(OBJS)" ] || { echo "no sources for PROG=$(PROG) (SRCDIR=$(SRCDIR))" >&2; exit 1; }
	LISA_CROSS=$(CROSS) python3 -I tools/lisalink.py $@ build/rt/crt0.o $(OBJS) \
	    -Wl,--start-group $(LIBS) -Wl,--end-group

build/$(PROG).obj: build/$(PROG).elf tools/elf2lisa.py
	python3 -I tools/elf2lisa.py $(if $(TOOL),--tool) $< $@

disk: build/$(PROG).dc42
build/$(PROG).dc42: build/$(PROG).obj tools/mkdisk.sh
	tools/mkdisk.sh $@ $<

run: build/$(PROG).dc42
	emu/run-workshop.sh $< $(PROG) build/emu-$(PROG)

# Run in the emulator and compare the screen with $(EXPECT)/<name>/expected.png
# (SKIP when there is no reference screenshot).
test: $(addprefix test-,$(TESTS)) $(addprefix test-tool-,$(TOOL_TESTS))
test-%:
	@$(MAKE) --no-print-directory PROG=$* build/$*.dc42 >/dev/null
	@INPUT="$$(cat tests/$*/input.txt 2>/dev/null)" emu/run-workshop.sh build/$*.dc42 $* build/emu-$* >/dev/null
	@if [ ! -f $(EXPECT)/$*/expected.png ]; then echo "SKIP: $* (no $(EXPECT)/$*/expected.png; see build/emu-$*/run.png)"; \
	 elif cmp -s build/emu-$*/run.png $(EXPECT)/$*/expected.png; then echo "PASS: $*"; \
	 else echo "FAIL: $* (see build/emu-$*/run.png)"; exit 1; fi

# ---- Office System desktop tools ------------------------------------------
# make PROG=hellotool tool       -> build/hellotool-tool.dc42 with {T$(TOOLNUM)}obj/PHRASE
# make test-tool-hellotool       -> install + open + "Set Aside" on the LOS desktop,
#                                   compare with $(EXPECT)/tools/hellotool/{opened,closed}.png
# The phrase file (menus and alerts) is compiled from $(SRCDIR)/$(PROG).phrase
# by tools/phrasec.py.  TOOLNAME is the name the desktop shows for the tool
# (a file label on {Tn}obj); it defaults to the program name.
TOOLNUM ?= 20
TOOLNAME_hellotool := Hello
TOOLNAME ?= $(or $(TOOLNAME_$(PROG)),$(PROG))

build/%.phrase: $(SRCDIR)/%.phrase tools/phrasec.py | build
	python3 -I tools/phrasec.py $< $@

tool: build/$(PROG).phrase
	rm -f build/$(PROG).obj build/$(PROG).elf
	$(MAKE) --no-print-directory PROG=$(PROG) TOOL=1 build/$(PROG).obj
	rm -rf build/tool-$(PROG) && mkdir -p build/tool-$(PROG)
	cp build/$(PROG).obj 'build/tool-$(PROG)/{T$(TOOLNUM)}obj'
	cp build/$(PROG).phrase 'build/tool-$(PROG)/{T$(TOOLNUM)}PHRASE'
	tools/mkdisk.sh -t '$(TOOLNAME)' build/$(PROG)-tool.dc42 build/tool-$(PROG)/*

# make PROG=hellotool serve     -> build the tool's floppy and run it interactively in
#                                 granny-smith's web build (emu/serve.sh prints the link)
serve: tool
	emu/serve.sh build/$(PROG)-tool.dc42

test-tool-%:
	@$(MAKE) --no-print-directory PROG=$* tool >/dev/null
	@CLOSE=1 LATER=200000000 emu/run-los-tool.sh build/$*-tool.dc42 build/emu-tool-$* >/dev/null
	@if cmp -s build/emu-tool-$*/6-later.png $(EXPECT)/tools/$*/opened.png && \
	    cmp -s build/emu-tool-$*/8-closed.png $(EXPECT)/tools/$*/closed.png; then echo "PASS: tool $*"; \
	 else echo "FAIL: tool $* (see build/emu-tool-$*/)"; exit 1; fi

# ---- The compiler ------------------------------------------------------------
# Prebuilt by .github/workflows/toolchain.yml (Retro68 GCC for m68k, trimmed by
# tools/package_toolchain.sh) and published as a release of pappadf/lisa-c.
TOOLCHAIN_TAG  ?= toolchain-v1
TOOLCHAIN_ARCH := $(patsubst aarch64,arm64,$(shell uname -m))
TOOLCHAIN_URL  ?= https://github.com/pappadf/lisa-c/releases/download/$(TOOLCHAIN_TAG)/lisa-c-toolchain-$(TOOLCHAIN_TAG)-linux-$(TOOLCHAIN_ARCH).tar.xz

toolchain:
	rm -rf toolchain/retro68 && mkdir -p toolchain
	curl -fsSL --retry 3 '$(TOOLCHAIN_URL)' | tar -xJ -C toolchain
	toolchain/retro68/bin/m68k-apple-macos-gcc --version | head -1

clean:
	rm -rf build

.PHONY: all disk run test clean tool toolchain serve
.SECONDARY:
.DELETE_ON_ERROR:
