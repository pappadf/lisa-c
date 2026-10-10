#!/usr/bin/env python3
"""Unpack Lisa PackedCode ($A0) records, as the OS does (OS/source-UNPACK.TEXT).

The packed stream is consumed backwards from its end.  The last byte holds a
slack flag (bit 0 clear: one padding byte precedes it) and the starting bit
number (bits 1-3).  Then flag bytes alternate with data: for each flag bit
(from the starting bit down to 0, then 7..0 for later flag bytes) a set bit
means "one index byte -> a word from the translation table", a clear bit
means "a literal word".  Output is also produced backwards, ending at the end
of the buffer.  The 256-word translation table is the PackTable ($A1) record
of SYSTEM.UNPACK (packversion 1).

usage: unpack_lisa.py SYSTEM.UNPACK in.obj [out-dir]
       prints each segment and, with out-dir, writes <segment>.bin files
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from objdump_lisa import records  # noqa: E402


def load_table(path):
    data = open(path, 'rb').read()
    for _, t, size, body in records(data):
        if t == 0xA1:
            version = struct.unpack('>L', body[:4])[0]
            return version, body[4:4 + 512]
    raise ValueError('no PackTable record in ' + path)


def unpack(packed, size_unpacked, table):
    out = bytearray(size_unpacked)
    i = len(packed)                 # input cursor (exclusive), moves down
    o = size_unpacked               # output cursor (exclusive), moves down
    count = len(packed)
    i -= 1
    last = packed[i]
    count -= 1
    bit = (last >> 1) & 7
    if not (last & 1):              # slack byte present
        i -= 1
        count -= 1
    while True:
        i -= 1
        flags = packed[i]
        count -= 1
        if count == 0:
            raise ValueError('ran out of input reading a flag byte')
        while True:
            if flags & (1 << bit):
                i -= 1
                idx = packed[i]
                o -= 2
                out[o:o + 2] = table[2 * idx:2 * idx + 2]
                count -= 1
            else:
                o -= 2
                out[o:o + 2] = packed[i - 2:i]
                i -= 2
                count -= 2
            if count <= 0:
                if count < 0:
                    raise ValueError('input overrun')
                return bytes(out[o:]) if o else bytes(out)
            bit -= 1
            if bit < 0:
                bit = 7
                break


def main():
    version, table = load_table(sys.argv[1])
    data = open(sys.argv[2], 'rb').read()
    outdir = sys.argv[3] if len(sys.argv) > 3 else None
    segname = '?'
    for off, t, size, body in records(data):
        if t == 0x80:
            segname = body[8:16].decode('latin-1').strip() or 'MAIN'
        if t == 0xA0:
            addr, csize = struct.unpack('>LL', body[:8])
            code = unpack(body[8:], csize, table)
            print(f'{segname:10s} addr={addr:#08x} packed={len(body) - 8} unpacked={len(code)}')
            if outdir:
                os.makedirs(outdir, exist_ok=True)
                open(os.path.join(outdir, f'{segname}.bin'), 'wb').write(code)


if __name__ == '__main__':
    main()
