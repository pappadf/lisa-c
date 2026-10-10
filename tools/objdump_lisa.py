#!/usr/bin/env python3
"""Walk and dump the records of a Lisa object/executable file (Workshop 3.0 format)."""
import struct, sys

NAMES = {0x00: 'EOFMark', 0x80: 'ModuleName', 0x81: 'EndBlock', 0x82: 'EntryPoint', 0x83: 'External',
         0x84: 'StartAddress', 0x85: 'CodeBlock', 0x86: 'Relocation', 0x87: 'CommonReloc',
         0x89: 'ShortExternal', 0x92: 'UnitBlock', 0x98: 'Executable', 0x99: 'VersionCtrl',
         0x9A: 'SegmentTable', 0x9B: 'UnitTable', 0x9C: 'SegLocation', 0x9D: 'UnitLocation',
         0x9E: 'FilesBlock', 0xA0: 'PackedCode', 0xA1: 'PackTable'}

def name8(b):
    return b.decode('latin-1').rstrip()

def records(data):
    off = 0
    while off + 4 <= len(data):
        t = data[off]
        size = int.from_bytes(data[off + 1:off + 4], 'big')
        yield off, t, size, data[off + 4:off + size]
        if t == 0 or size < 4:
            return
        off += size

def describe(t, body):
    if t == 0x98:
        f = struct.unpack('>10L', body[:40])
        keys = 'JTLaddr JTSize DataSize MainSize JTSegDelta StkSegDelta DynStack MaxStack MinHeap MaxHeap'.split()
        s = ' '.join(f'{k}={v:#x}' for k, v in zip(keys, f))
        jt = body[40:]
        n = struct.unpack('>H', jt[:2])[0]
        p = 2
        segs = []
        for _ in range(n):
            a, sp, su, m = struct.unpack('>LHHL', jt[p:p + 12]); p += 12
            segs.append(f'(file@{a:#x} packed={sp:#x} unpacked={su:#x} mem={m:#x})')
        nd = struct.unpack('>H', jt[p:p + 2])[0]; p += 2
        descs = []
        for _ in range(nd):
            op, addr = struct.unpack('>HL', jt[p:p + 6]); p += 6
            descs.append(f'{op:04x}:{addr:#x}')
        return f'{s}\n      segs={segs}\n      descs={descs} extra={jt[p:].hex()}'
    if t == 0x9A:
        n = struct.unpack('>H', body[:2])[0]
        return ' '.join(f'{name8(body[2+i*18:10+i*18])}#{struct.unpack(">H", body[10+i*18:12+i*18])[0]}' for i in range(n))
    if t == 0x9B:
        n, mx = struct.unpack('>HH', body[:4])
        return f'max={mx} ' + ' '.join(f'{name8(body[4+i*12:12+i*12])}#{struct.unpack(">HH", body[12+i*12:16+i*12])}' for i in range(n))
    if t == 0x80:
        return f'module={name8(body[:8])!r} segment={name8(body[8:16])!r}'
    if t in (0x82, 0x83, 0x89):
        return f'link={name8(body[:8])!r} user={name8(body[8:16])!r} rest={body[16:].hex()}'
    if t in (0x85, 0xA0):
        return f'addr={struct.unpack(">L", body[:4])[0]:#x} len={len(body) - 4}' + (f' csize={struct.unpack(">L", body[4:8])[0]:#x}' if t == 0xA0 else '')
    if t == 0x81:
        return f'csize={struct.unpack(">L", body[:4])[0]:#x}'
    return body[:32].hex() + ('...' if len(body) > 32 else '')

if __name__ == '__main__':
    for path in sys.argv[1:]:
        data = open(path, 'rb').read()
        print(f'== {path} ({len(data)} bytes)')
        for off, t, size, body in records(data):
            print(f'  {off:06x} {t:02x} {NAMES.get(t, "?"):12s} size={size:#x}  {describe(t, body)}')
