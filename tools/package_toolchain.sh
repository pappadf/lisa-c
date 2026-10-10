#!/usr/bin/env bash
# Trim a Retro68 m68k install to what lisa-c uses and make it relocatable.
#
#   tools/package_toolchain.sh PREFIX OUT
#
# PREFIX is a Retro68 install (build-toolchain.bash --no-ppc --no-carbon);
# OUT/ receives: the C compiler driver, cc1 and collect2, binutils (ld is the
# plain ELF linker, not Retro68's Elf2Mac wrapper), libgcc for every 68k
# multilib and GCC's own headers.  Left out: C++, LTO, the Mac headers and
# libraries, Rez and the other Mac tools.
#
# Host binaries are stripped, and the shared libraries they need beyond glibc
# (GMP, MPFR, MPC, zstd) are copied to OUT/lib/host with an $ORIGIN rpath
# (needs patchelf), so the tree runs from any directory on any Linux with a
# glibc at least as new as the build machine's.
set -euo pipefail
PREFIX="$(realpath "$1")"
OUT="$(realpath -m "$2")"
T=m68k-apple-macos
V="$("$PREFIX/bin/$T-gcc" -dumpversion)"

rm -rf "$OUT"
mkdir -p "$OUT/bin" "$OUT/$T/bin" "$OUT/libexec/gcc/$T/$V" "$OUT/lib/gcc/$T" "$OUT/lib/host"

for b in gcc "gcc-$V" cpp gcc-ar gcc-nm gcc-ranlib ar as nm objcopy objdump ranlib readelf \
         strip size strings addr2line c++filt elfedit; do
    [ -e "$PREFIX/bin/$T-$b" ] && cp -L "$PREFIX/bin/$T-$b" "$OUT/bin/"
done
for b in ar as nm objcopy objdump ranlib readelf strip ld.real; do
    cp -L "$PREFIX/$T/bin/$b" "$OUT/$T/bin/"
done
ln -s ld.real "$OUT/$T/bin/ld"
ln -s "../$T/bin/ld.real" "$OUT/bin/$T-ld"
for f in cc1 collect2 lto-wrapper liblto_plugin.so; do
    cp -L "$PREFIX/libexec/gcc/$T/$V/$f" "$OUT/libexec/gcc/$T/$V/"
done
cp -a "$PREFIX/lib/gcc/$T/$V" "$OUT/lib/gcc/$T/"
rm -rf "$OUT/lib/gcc/$T/$V/plugin"

# Strip the host executables; bundle their non-glibc libraries.
hostbins=$(find "$OUT/bin" "$OUT/$T/bin" "$OUT/libexec" -type f -exec sh -c \
           'head -c4 "$1" | grep -q ELF' _ {} \; -print)
for f in $hostbins; do
    strip --strip-unneeded "$f"
done
for f in $hostbins; do
    libs=$(ldd "$f" | awk '/=> \// {print $3}' | grep -E 'lib(gmp|mpfr|mpc|zstd)\.so' || true)
    [ -z "$libs" ] && continue
    for l in $libs; do
        cp -Ln "$l" "$OUT/lib/host/" 2>/dev/null || true
    done
    rel=$(realpath --relative-to="$(dirname "$f")" "$OUT/lib/host")
    patchelf --set-rpath "\$ORIGIN/$rel" "$f"
done

cat > "$OUT/README.txt" <<EOF
Retro68 GCC $V for m68k (68000), trimmed for lisa-c.
Point lisa-c at it with CROSS=<this dir>/bin/$T- (the default location is
lisa-c/../toolchain/retro68).  See SOURCE.txt for where the sources are.
EOF
du -sh "$OUT"
