#!/usr/bin/env python3
"""Extract intrinsic-library entry points into data/entries.tsv.

Each Workshop 3.0 intrinsic library (IOSPASLIB.OBJ, SYS1LIB.OBJ, ...) carries
EntryPoint ($82) records for its interface routines: an 8-character link name
and the absolute logical address of the routine's jump vector.  Programs call
these addresses with the IUJSR instruction ($A0xxxxxx).  The same vector
layout is used by the LOS 3.1 libraries (checked with tools/unpack_lisa.py).

The output is plain interoperability data: library, segment, link name and
address -- one line per entry point.

usage: gen_entries.py out.tsv lib.obj...
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from objdump_lisa import records  # noqa: E402


def entries(path):
    data = open(path, 'rb').read()
    seg, pending = '', []
    for _, t, size, body in records(data):
        if t == 0x80:
            seg = body[8:16].decode('latin-1').strip()
        elif t == 0x82:
            link = body[0:8].decode('latin-1').strip()
            addr, = struct.unpack('>L', body[16:20])
            pending.append((link, addr))
        elif t == 0x85:
            base, = struct.unpack('>L', body[:4])
            for link, addr in pending:          # entries precede their CodeBlock
                if addr >> 17 != base >> 17:
                    sys.exit(f'{path}: {link} at {addr:#x} not in segment {seg} at {base:#x}')
                yield seg, link, addr
            pending = []


def main():
    out, libs = sys.argv[1], sys.argv[2:]
    rows = []
    for lib in libs:
        name = os.path.splitext(os.path.basename(lib))[0].upper()
        rows += [(name, seg, link, addr) for seg, link, addr in entries(lib)]
    with open(out, 'w') as f:
        f.write('# library\tsegment\tlinkname\taddress\n')
        for name, seg, link, addr in sorted(rows, key=lambda r: (r[0], r[3])):
            f.write(f'{name}\t{seg}\t{link}\t{addr:06X}\n')
    print(f'{out}: {len(rows)} entry points from {len(libs)} libraries', file=sys.stderr)


if __name__ == '__main__':
    main()
