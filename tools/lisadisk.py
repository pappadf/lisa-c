#!/usr/bin/env python3
"""Read a 400K Lisa Office System diskette image (DiskCopy 4.2), as written
by tools/mklisafs.py or by the Lisa (e.g. granny-smith's floppy export).

    lisadisk.py files   disk.dc42              files: s-file, size, name
    lisadisk.py desktop disk.dc42              the Desktop Manager's catalog:
                                               id, kind, tool, name
    lisadisk.py extract disk.dc42 NAME [OUT]   copy a file out (default ./NAME)

As a module: Disk(path).files() -> {name: bytes}; Disk(path).desktop() ->
[CatObject(id, parent, kind, tool, name)].  A document's files are named
{D<id>T<tool>}..., after its catalog id.

File system version 17 (Office System 3.x) only: the MDDF at sector 28, files
read through the s-list and each file's extent map (the small map in its
header page).
"""
import collections
import struct
import sys

FS_START = 28
KINDS = {4: 'document', 5: 'stationery', 6: 'wastebasket', 16: 'folder pad',
         17: 'clipboard', 24: 'tool', 25: 'disk'}
CatObject = collections.namedtuple('CatObject', 'id parent kind tool name')


class Disk:
    def __init__(self, path):
        b = open(path, 'rb').read()
        size = struct.unpack_from('>L', b, 64)[0]
        self.data = b[84:84 + size]
        m = self.page(0)
        if struct.unpack_from('>H', m, 0)[0] != 17:
            raise SystemExit(f'{path}: not an Office System 3.x volume')
        self.volname = m[13:13 + m[12]].decode('mac_roman')
        self.slist = struct.unpack_from('>L', m, 148)[0]
        self.sentpp, self.spages = struct.unpack_from('>HH', m, 152)

    def page(self, n):
        s = FS_START + n
        return self.data[s * 512:(s + 1) * 512]

    def files(self):
        out = {}
        for sf in range(self.sentpp * self.spages):
            hint, first, size, ver = struct.unpack_from(
                '>llLH', self.page(self.slist + sf // self.sentpp), (sf % self.sentpp) * 14)
            if hint <= 0 or sf < 5:
                continue
            h = self.page(hint)
            name = h[1:1 + h[0]].decode('mac_roman')
            nmap = struct.unpack_from('>H', h, 0x86)[0]
            data = b''
            for i in range(nmap):
                start, count = struct.unpack_from('>LH', h, 0x88 + 6 * i)
                data += b''.join(self.page(start + j) for j in range(count))
            out[name] = data[:size]
        return out

    def desktop(self):
        cat = self.files().get('{!CATALOG}')
        if cat is None:
            return []
        objs = []
        for p in range(512, len(cat), 2048):        # the leaf pages after the header
            page = cat[p:p + 2048]
            if len(page) < 2048 or struct.unpack_from('>H', page, 2038)[0] != 0x9999:
                continue
            for i in range(struct.unpack_from('>H', page, 2036)[0]):
                o = struct.unpack_from('>H', page, 2034 - 2 * i)[0]
                parent, nlen, noff, ident, kind = struct.unpack_from('>lHHlh', page, o)
                tool = struct.unpack_from('>l', page, o + 42)[0]
                name = page[o + noff:o + noff + nlen].decode('mac_roman')
                objs.append(CatObject(ident, parent, kind, tool, name))
        return objs


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ('files', 'desktop', 'extract'):
        sys.exit(__doc__.split('\n\n')[1])
    d = Disk(sys.argv[2])
    if sys.argv[1] == 'files':
        for name, data in sorted(d.files().items()):
            print(f'{len(data):8}  {name}')
    elif sys.argv[1] == 'desktop':
        for o in d.desktop():
            tool = '' if o.tool < 0 else o.tool
            print(f'{o.id:5}  {KINDS.get(o.kind, o.kind):12}  {tool:>4}  {o.name}')
    else:
        name = sys.argv[3]
        files = d.files()
        if name not in files:
            sys.exit(f'{name}: no such file on {d.volname}')
        open(sys.argv[4] if len(sys.argv) > 4 else name, 'wb').write(files[name])


if __name__ == '__main__':
    main()
