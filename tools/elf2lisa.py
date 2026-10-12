#!/usr/bin/env python3
"""Convert a linked m68k ELF (from lisalink.py) into a Lisa executable object file.

Produces a main program in the Workshop 3.0 object format (Lisa Development
System Internals Documentation, Feb 1984, "Lisa Object File Formats"),
shaped like the Workshop's own linked programs:

  VersionCtrl, B2 (reserved, zero), UnitTable, Executable (header + jump
  table), SegmentTable, then per code segment ModuleName [StartAddress]
  CodeBlock EndBlock, and EOFMark.

Code segments are the ELF sections SEG1..SEGn, mapped at MMU n (n * 128K;
code at +8, after the CodeBlock header the loader places at the segment
base).  SEG1 also carries the initial data-segment image (.data, loaded by
runtime/lisa.c at __data_load).

Like the Lisa linker, every reference to code in another segment goes
through the jump table: the ELF must be linked with --emit-relocs, and each
absolute reference into code is redirected to a JMP.L descriptor unless it is
a JSR/JMP within its own segment.  Code addresses stored in data (function
pointers) are always redirected, as are LEA/PEA/MOVE of code addresses.

The unit and segment tables (tools/lisa_tables.py) are the PASLIB closure,
or with --tool the SYS1LIB closure of an Office System tool.

A configurable driver (--driver; lisalink.py --driver) is written the way
the OS's own SYSTEM.CD_ files are: VersionCtrl, Executable (one segment),
ModuleName, StartAddress, CodeBlock, EndBlock, EOFMark.  LOAD_DRIVER copies
its code into the driver space wherever there is room and enters it at the
first byte, with no relocation, so the code must not depend on its address.
Driver sources are compiled with -mpcrel; the absolute references library
code still makes to code in the segment (JSR/JMP/LEA/PEA abs.L) are rewritten
to their d16(PC) forms, padded with a NOP, and any other absolute reference
is an error.

usage: elf2lisa.py [--tool | --driver] input.elf output.obj
  --tool: Office System tool: SYS1LIB unit/segment closure and tool VersionCtrl
  --driver: configurable driver (SYSTEM.CD_ file)
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

JT_LADDR = 0xF802A0         # JTLaddr field value, as in Workshop programs
JT_TOP = 0xF80000           # descriptors end here at run time (top of the stack segment)
MAIN_SIZE = 0x10            # must match MAINSIZE in runtime/lisa.inc

from lisa_tables import PASLIB_UNITS, PASLIB_SEGMENTS, UI_UNITS, UI_SEGMENTS  # noqa: E402

# VersionCtrl as found in Office System tools (all LOS 3.1 tools carry these values);
# Workshop programs leave it zero.
TOOL_VERSION = struct.pack('>6L', 0, 0, 0x40000, 0x47FFF, 0x40001, 0)

# Symbols defined by the tools/lisalink.py linker scripts (addresses, not code).
LINKER_SYMBOL = re.compile(r'^(__data_|__bss_|__preinit_array|__init_array|__fini_array|__bothinit_array|LISA_)')

R_68K_32, R_68K_16, R_68K_8, R_68K_PC32, R_68K_PC16, R_68K_PC8 = 1, 2, 3, 4, 5, 6
STT_FUNC, STT_SECTION = 2, 3


class Elf:
    def __init__(self, path):
        d = self.d = open(path, 'rb').read()
        assert d[:4] == b'\x7fELF' and d[4] == 1 and d[5] == 2, 'need ELF32 big-endian'
        self.entry = struct.unpack_from('>L', d, 24)[0]
        shoff, = struct.unpack_from('>L', d, 32)
        shentsize, shnum, shstrndx = struct.unpack_from('>HHH', d, 46)
        self.sh = [struct.unpack_from('>10L', d, shoff + i * shentsize) for i in range(shnum)]
        names = self.sh[shstrndx]
        self.names = [self._str(names[4], s[0]) for s in self.sh]
        self.by_name = {n: i for i, n in enumerate(self.names)}
        self.syms = []
        for i, s in enumerate(self.sh):
            if s[1] == 2:                                   # SHT_SYMTAB
                strtab = self.sh[s[6]]
                for off in range(s[4], s[4] + s[5], 16):
                    name, value, size, info, other, shndx = struct.unpack_from('>LLLBBH', d, off)
                    stype = info & 15
                    sname = self._str(strtab[4], name)
                    if (stype == 0 and info >> 4 == 1      # global STT_NOTYPE: an assembly routine
                            and not LINKER_SYMBOL.match(sname)):  # without .type (e.g. lb1sf68.S),
                        stype = STT_FUNC                     # but not a linker-script symbol
                    self.syms.append((sname, value, stype, shndx))

    def _str(self, base, off):
        end = self.d.index(b'\0', base + off)
        return self.d[base + off:end].decode('latin-1')

    def section(self, name):
        i = self.by_name.get(name)
        if i is None:
            return None, 0
        s = self.sh[i]
        return self.d[s[4]:s[4] + s[5]] if s[1] != 8 else bytes(s[5]), s[3]   # (bytes, addr)

    def symbol(self, name):
        for n, v, _, _ in self.syms:
            if n == name:
                return v
        raise KeyError(name)

    def relas(self, target):
        """Yield (offset_in_section, type, symbol index, addend) for relocations against section `target`."""
        ti = self.by_name[target]
        for s in self.sh:
            if s[1] == 4 and s[7] == ti:                    # SHT_RELA, sh_info = target
                for off in range(s[4], s[4] + s[5], 12):
                    r_off, info, addend = struct.unpack_from('>LLl', self.d, off)
                    yield r_off, info & 0xFF, info >> 8, addend


def name8(s):
    return s.encode('ascii').ljust(8, b' ')[:8]


def record(rtype, body):
    return bytes([rtype]) + (4 + len(body)).to_bytes(3, 'big') + body


def build(elf, tool=False):
    UNITS, SEGMENTS = (UI_UNITS, UI_SEGMENTS) if tool else (PASLIB_UNITS, PASLIB_SEGMENTS)
    segs = []                                   # [(mmu, base_addr, bytearray)]
    n = 1
    while True:
        data, addr = elf.section(f'SEG{n}')
        if data is None:
            break
        assert addr == n * 0x20000 + 8, f'SEG{n} at {addr:#x}'
        segs.append([n, addr, bytearray(data)])
        n += 1
    if not segs:
        sys.exit('no SEG1 section: link with tools/lisalink.py')

    data_img, data_vma = elf.section('.data')
    if data_img:
        load = elf.symbol('__data_load')
        seg1 = segs[0][2]
        off = load - segs[0][1]
        seg1.extend(bytes(off + len(data_img) - len(seg1)))
        seg1[off:off + len(data_img)] = data_img

    def seg_of(addr):
        for i, (_, base, body) in enumerate(segs):
            if base <= addr < base + len(body):
                return i
        return None

    # Jump table descriptors: [0] = entry point, then one per redirected target.
    # The loader copies the descriptors to the top of the stack segment, ending
    # at $F80000 (measured in granny-smith: 3 descriptors at $F7FFEE..$F7FFFF;
    # consistent with the d(A5) jump-table calls in Pascal code), so a
    # descriptor's address depends on the final count: patch in a second pass.
    descs = [elf.entry]
    desc_index = {elf.entry: 0}
    patches = []                                    # (image, offset, target)

    def jt_addr(target):
        if target not in desc_index:
            desc_index[target] = len(descs)
            descs.append(target)
        return target

    funcs = {v for n, v, t, sh in elf.syms if t == STT_FUNC and sh != 0}
    data_load_off = elf.symbol('__data_load') - segs[0][1] if data_img else 0
    redirected = 0
    for secname, site_seg in [(f'SEG{i + 1}', i) for i in range(len(segs))] + [('.data', None)]:
        if elf.by_name.get(secname) is None:
            continue
        for r_off, rtype, symi, addend in elf.relas(secname):    # ET_EXEC: r_off is an address
            sname, svalue, stype, shndx = elf.syms[symi]
            target = svalue + addend
            tseg = seg_of(target) if shndx != 0 else None
            if tseg is None:
                continue                                    # not a code address
            if LINKER_SYMBOL.match(sname):
                continue                                    # a linker-script address (the data image in
                                                            # SEG1, read once at startup): absolute
            if rtype in (R_68K_PC16, R_68K_PC8, R_68K_PC32, R_68K_16, R_68K_8):
                if site_seg != tseg:
                    sys.exit(f'{secname}@{r_off:#x}: PC-relative/short reference to {sname} in another segment')
                continue
            if rtype != R_68K_32:
                sys.exit(f'unsupported relocation type {rtype} at {secname}@{r_off:#x}')
            if site_seg is None:                            # code address stored in the data image
                img, off = segs[0][2], data_load_off + (r_off - data_vma)
            else:
                img, off = segs[site_seg][2], r_off - segs[site_seg][1]
                if tseg == site_seg and (target not in funcs or
                                         (off >= 2 and img[off - 2:off] in (b'\x4e\xb9', b'\x4e\xf9'))):
                    continue                                # within the segment: direct
            if target not in funcs:
                sys.exit(f'{secname}@{r_off:#x}: reference to non-function code address {target:#x} '
                         f'({sname}) from another segment or from data')
            assert struct.unpack_from('>L', img, off)[0] == target, f'{secname}@{r_off:#x}'
            jt_addr(target)
            patches.append((img, off, target))
            redirected += 1

    jt_desc_base = JT_TOP - 6 * len(descs)
    for img, off, target in patches:
        struct.pack_into('>L', img, off, jt_desc_base + 6 * desc_index[target])

    for s in segs:
        if len(s[2]) % 2:
            s[2].append(0)
        if len(s[2]) + 8 > 32767:
            sys.exit(f'segment {s[0]} is {len(s[2])} bytes (> 32 KB)')

    out = bytearray()
    out += record(0x99, TOOL_VERSION if tool else bytes(24))         # VersionCtrl
    out += record(0xB2, bytes(0x202))                                # reserved, zero
    body = struct.pack('>HH', len(UNITS), max(u[1] for u in UNITS))
    for name, num, typ in UNITS:
        body += name8(name) + struct.pack('>HH', num, typ)
    out += record(0x9B, body)                                        # UnitTable

    jt_len = 2 + 12 * len(segs) + 2 + 6 * len(descs)
    exe_off = len(out)
    segtab = struct.pack('>H', len(SEGMENTS))
    for name, num in SEGMENTS:
        segtab += name8(name) + struct.pack('>HLL', num, 0, 0)
    segtab_rec = record(0x9A, segtab)
    pos = exe_off + 4 + 40 + jt_len + len(segtab_rec)
    code_recs, file_addrs = [], []
    for i, (mmu, base, img) in enumerate(segs):
        recs = record(0x80, name8('MainProg') + name8('' if i == 0 else f'SEG{mmu}') + struct.pack('>L', 0))
        if i == 0:
            recs += record(0x84, struct.pack('>LL', 0, MAIN_SIZE))
        file_addrs.append(pos + len(recs))
        cb = record(0x85, struct.pack('>L', base - 8) + bytes(img))
        recs += cb + record(0x81, struct.pack('>L', len(img)))
        code_recs.append((recs, len(cb)))
        pos += len(recs)

    hdr = struct.pack('>L9L', JT_LADDR, jt_len, 0, MAIN_SIZE, 0x100, 0x100,
                      0x2800, 0x20000, 0x1000, 0x20000)
    jt = struct.pack('>H', len(segs))
    for (mmu, base, img), fa, (_, cblen) in zip(segs, file_addrs, code_recs):
        jt += struct.pack('>LHHL', fa, 0, cblen, base - 8)               # unpacked
    jt += struct.pack('>H', len(descs))
    for t in descs:
        jt += struct.pack('>HL', 0x4EF9, t)                              # JMP.L target
    out += record(0x98, hdr + jt)                                     # Executable
    out += segtab_rec
    for recs, _ in code_recs:
        out += recs
    out += record(0x00, b'')                                          # EOFMark
    out += bytes(-len(out) % 512)
    return bytes(out), len(segs), len(descs), redirected


# abs.L forms whose d16(PC) form is the next opcode and 2 bytes shorter
PCREL_FORMS = [(0xFFFF, 0x4EB9, 'JSR'), (0xFFFF, 0x4EF9, 'JMP'), (0xF1FF, 0x41F9, 'LEA'), (0xFFFF, 0x4879, 'PEA')]


def build_driver(elf):
    img, base = elf.section('SEG1')
    if img is None:
        sys.exit('no SEG1 section: link with tools/lisalink.py --driver')
    img = bytearray(img)
    if elf.entry != base:
        sys.exit(f'the entry point is at {elf.entry:#x}, not the start of the code ({base:#x})')
    rodata = elf.symbol('__driver_rodata')
    end = base + len(img)
    rewritten = 0
    for r_off, rtype, symi, addend in elf.relas('SEG1'):
        sname, svalue, stype, shndx = elf.syms[symi]
        target = svalue + addend
        if shndx == 0 or not base <= target <= end:
            sys.exit(f'{r_off:#x}: reference to {sname} ({target:#x}), outside the driver')
        if rtype in (R_68K_PC16, R_68K_PC8, R_68K_PC32):
            continue
        if rtype != R_68K_32 or r_off >= rodata:
            where = 'constant data' if r_off >= rodata else 'code'
            sys.exit(f'{r_off:#x}: absolute reference to {sname} in {where}: a driver must be '
                     f'position-independent (no code or data addresses in initialized tables)')
        off = r_off - base
        op = struct.unpack_from('>H', img, off - 2)[0]
        for mask, abs_op, name in PCREL_FORMS:
            if op & mask == abs_op:
                break
        else:
            sys.exit(f'{r_off:#x}: absolute reference to {sname} (opcode {op:04x}): a driver must be '
                     f'position-independent; compile it with -mpcrel')
        disp = target - r_off                       # d16(PC): PC = the extension word's address
        if not -32768 <= disp <= 32767:
            sys.exit(f'{r_off:#x}: {name} to {sname} out of d16(PC) range')
        struct.pack_into('>HhH', img, off - 2, op + 1, disp, 0x4E71)     # ... d16(PC); NOP
        rewritten += 1
    if len(img) % 2:
        img.append(0)
    if len(img) + 8 > 32767:
        sys.exit(f'the driver is {len(img)} bytes (> 32 KB)')

    out = bytearray()
    out += record(0x99, bytes(24))                                   # VersionCtrl
    jt_len = 2 + 12 + 2 + 6
    pos = len(out) + 4 + 40 + jt_len
    mod = record(0x80, name8('MainProg') + name8('') + struct.pack('>L', 0))
    start = record(0x84, struct.pack('>LL', 0, 0))
    cb = record(0x85, struct.pack('>L', base - 8) + bytes(img))
    hdr = struct.pack('>L9L', JT_LADDR, jt_len, 0, 0, 0x100, 0x100, 0x2800, 0x20000, 0x1000, 0x20000)
    jt = struct.pack('>H', 1) + struct.pack('>LHHL', pos + len(mod) + len(start), 0, len(cb), base - 8)
    jt += struct.pack('>HHL', 1, 0x4EF9, base)                         # the entry: the first byte
    out += record(0x98, hdr + jt)                                     # Executable
    out += mod + start + cb + record(0x81, struct.pack('>L', len(img)))
    out += record(0x00, b'')                                          # EOFMark
    out += bytes(-len(out) % 512)
    return bytes(out), len(img), rewritten


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if len(args) != 2:
        sys.exit(__doc__)
    elf = Elf(args[0])
    if '--driver' in sys.argv:
        obj, size, nrew = build_driver(elf)
        open(args[1], 'wb').write(obj)
        print(f'{args[1]}: driver, {size} bytes of code, {nrew} absolute references made PC-relative',
              file=sys.stderr)
        return
    obj, nseg, ndesc, nred = build(elf, tool='--tool' in sys.argv)
    open(args[1], 'wb').write(obj)
    print(f'{args[1]}: {nseg} segment(s), {ndesc} jump-table entries, {nred} references redirected',
          file=sys.stderr)


if __name__ == '__main__':
    main()
