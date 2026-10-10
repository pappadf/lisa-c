#!/usr/bin/env bash
# Build the part of Retro68 that lisa-c uses: binutils and a C-only GCC with
# libgcc, for m68k-apple-macos (68000).
#
#   tools/build_toolchain.sh RETRO68_SRC BUILD_DIR PREFIX
#
# RETRO68_SRC is a checkout of https://github.com/autc04/Retro68 (its
# binutils/ and gcc/ trees carry the patches, e.g. the `pascal` attribute).
# Unlike Retro68's build-toolchain.bash this skips C++, the C library and
# other target libraries, the Mac runtime libraries and interfaces, Rez,
# Elf2Mac and hfsutils, which lisa-c does not use.  The linker is installed
# as ld.real (Retro68's name for the plain ELF linker), as
# tools/package_toolchain.sh expects.  Needs: a C/C++ compiler, make, bison,
# flex, texinfo, GMP, MPFR, MPC (dev packages).
set -euo pipefail
SRC="$(realpath "$1")"
BUILD="$(realpath -m "$2")"
PREFIX="$(realpath -m "$3")"
T=m68k-apple-macos
JOBS="${JOBS:-$(nproc)}"

mkdir -p "$BUILD/binutils" "$BUILD/gcc" "$PREFIX"

cd "$BUILD/binutils"
"$SRC/binutils/configure" --target=$T --prefix="$PREFIX" --disable-doc --disable-werror \
    --disable-nls --disable-gdb --disable-gdbserver --disable-sim
make -j"$JOBS"
make install

cd "$BUILD/gcc"
export target_configargs="--disable-nls"
"$SRC/gcc/configure" --target=$T --prefix="$PREFIX" \
    --enable-languages=c --with-arch=m68k --with-cpu=m68000 \
    --disable-libssp --disable-nls MAKEINFO=missing
make -j"$JOBS" all-gcc all-target-libgcc
make install-gcc install-target-libgcc

# Retro68's layout: the plain linker is ld.real (its `ld` is the Elf2Mac
# wrapper, which we do not build).
mv "$PREFIX/bin/$T-ld" "$PREFIX/bin/$T-ld.real"
mv "$PREFIX/$T/bin/ld" "$PREFIX/$T/bin/ld.real"
ln -s "$T-ld.real" "$PREFIX/bin/$T-ld"
ln -s ld.real "$PREFIX/$T/bin/ld"
"$PREFIX/bin/$T-gcc" --version | head -1
