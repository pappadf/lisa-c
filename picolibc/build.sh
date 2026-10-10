#!/usr/bin/env bash
# Build picolibc for the Lisa into lisa-c/build/sysroot (headers + libc.a + libm.a).
#   CROSS=<path>/m68k-apple-macos- picolibc/build.sh
# The compiler must be the one the programs are built with (Retro68's GCC):
# its C calling convention (D2 scratch, 2-byte short arguments) differs from
# other m68k GCCs, so objects from different compilers must not be mixed.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VER=1.8.12
CROSS="${CROSS:?set CROSS to the compiler prefix, e.g. .../bin/m68k-apple-macos-}"
SRC="${PICOLIBC_SRC:-$HERE/../../references/picolibc-src/picolibc-$VER}"
BUILD="$HERE/../build/picolibc"
PREFIX="$HERE/../build/sysroot"
if [ ! -d "$SRC" ]; then
    mkdir -p "$(dirname "$SRC")"
    curl -sSfL "https://github.com/picolibc/picolibc/releases/download/$VER/picolibc-$VER.tar.xz" \
        | tar xJ -C "$(dirname "$SRC")"
fi
rm -rf "$BUILD"
mkdir -p "$BUILD"
# meson cross file: 68000, no FPU, A5 reserved (Pascal/OS globals pointer)
cat > "$BUILD/cross.txt" <<CROSSFILE
[binaries]
c = ['${CROSS}gcc', '-m68000', '-ffixed-a5', '-fno-pic', '-static', '-nostdlib', '-fno-builtin-isinfl', '-fno-asynchronous-unwind-tables']
ar = '${CROSS}ar'
as = '${CROSS}as'
ld = '${CROSS}ld'
nm = '${CROSS}nm'
strip = '${CROSS}strip'

[host_machine]
system = 'none'
cpu_family = 'm68k'
cpu = '68000'
endian = 'big'

[properties]
skip_sanity_check = true
CROSSFILE
meson setup "$BUILD" "$SRC" --cross-file "$BUILD/cross.txt" \
    --prefix="$PREFIX" --libdir=lib --includedir=include \
    -Dmultilib=false -Dpicocrt=false -Dpicocrt-lib=false -Dsemihost=false \
    -Dthread-local-storage=false -Dsingle-thread=true -Datomic-ungetc=false \
    -Dposix-console=true -Dio-long-long=true -Dformat-default=double \
    -Dtests=false -Dspecsdir=none -Doptimization=s -Dwerror=false
ninja -C "$BUILD"
ninja -C "$BUILD" install
# The Lisa layer (runtime/posix.c) supplies sbrk on a growable data segment;
# drop picolibc's fixed-region fallback so it can never be linked instead.
"${CROSS}ar" d "$PREFIX/lib/libc.a" libos_fallback_sbrk.c.o
