#!/usr/bin/env python3
"""Make a 400K Lisa Office System (file system version 17) diskette image.

    mklisafs.py [-n NAME] [-t TOOLNAME] [--date YYYY-MM-DD] out.dc42 [file...]

Writes a DiskCopy 4.2 image of an initialized, empty volume (default name
"LisaC") holding the given host files, each under its basename.  The disk is
a data disk: it has no boot tracks, so it cannot start the Lisa.

With -t, a tool program ({Tn}obj) gets a file label naming the tool, as the
Desktop Manager reads it for tools it has no phrase string for (n > 16):
version 2, name (string[63]), kind 24 (tool), tools-only and many-documents
flags, window rectangle, split number, total size, parent id.

Layout (page numbers are relative to the first file-system block, sector 28
on a Sony diskette, as the Lisa's Sony driver configures it):

  page 0       MDDF (volume descriptor); a copy of its initial state at 270
  page 1       allocation bitmap, one bit per page, bit i of byte i/8
  pages 2..6   s-list: 14-byte entries (hint page, first data page, size,
               version) for s-files 0..143; s-files 1-4 are the volume's own
  pages 7..10  catalog: one 2048-byte B-tree leaf node (s-file 4) holding
               the root directory's thread record and one record per file
  then per file: a hint page (file header, small extent map) and its data

Every sector carries a 12-byte tag: version, volume, file id (s-file
number; -n on file n's hint page), page number within the file, and bytes
used plus next/previous page, packed 5+11 bits per word (0x7FF = none).
"""
import argparse
import datetime
import hashlib
import os
import re
import struct
import sys

SECTORS = 800             # 400K Sony diskette
FS_START = 28             # first file-system block (fs_start_block of the Sony driver)
LASTFSPAGE = SECTORS - FS_START - 1
PAGES = LASTFSPAGE + 1
MDDF_BACKUP = 270
SENTPP = 512 // 14        # s-list entries per page
MAXFILES = 143            # as an Office System 3.1 Initialize makes it
SPAGES = (MAXFILES + 1) // SENTPP + 1
SLIST = 2
CATALOG = SLIST + SPAGES  # first free page = catalog node
NODE_PAGES = 4
FIRSTFILE = 5             # s-files 1-4: MDDF, bitmap, s-list, catalog
CENTRY_SIZE = 68          # old catalog entry size, still used for fs_overhead
NONE = 0x7FF              # "no page" in a tag link
EPOCH = datetime.datetime(1901, 1, 1)


def lisa_time(date):
    return int((date - EPOCH).total_seconds())


class Volume:
    def __init__(self, name, when):
        self.data = bytearray(SECTORS * 512)
        self.tags = bytearray(SECTORS * 12)
        self.name = name.encode('mac_roman')
        self.when = when
        self.volid = hashlib.sha1(self.name + struct.pack('>L', when)).digest()[:8]
        self.bitmap = bytearray((PAGES + 7) // 8)
        self.files = []
        self.next_page = CATALOG + NODE_PAGES

    # ---- pages -----------------------------------------------------------
    def put(self, page, data, fileid, rel, used, fwd=NONE, bkwd=NONE, mark=True):
        s = FS_START + page
        self.data[s * 512:s * 512 + len(data)] = data
        self.tags[s * 12:s * 12 + 12] = struct.pack(
            '>HHHHHH', 0, 0, fileid & 0xFFFF, rel,
            (used >> 5) << 11 | (fwd & NONE), (used & 31) << 11 | (bkwd & NONE))
        if mark:
            self.bitmap[page // 8] |= 1 << (page % 8)

    def chain(self, first, n, fileid, data):
        """Write data on pages first..first+n-1, linked as one file."""
        for i in range(n):
            chunk = data[i * 512:(i + 1) * 512]
            self.put(first + i, chunk, fileid, i, 512 if i < n - 1 else len(chunk),
                     first + i + 1 if i < n - 1 else NONE, first + i - 1 if i else NONE)

    # ---- files -----------------------------------------------------------
    def alloc(self, n):
        """n contiguous free pages, stepping over the MDDF copy."""
        start = self.next_page
        if start <= MDDF_BACKUP < start + n:
            start = MDDF_BACKUP + 1
        if start + n > PAGES:
            raise SystemExit('diskette full')
        self.next_page = start + n
        return start

    def add(self, name, contents, label=b''):
        sfile = FIRSTFILE + len(self.files)
        if sfile > MAXFILES:
            raise SystemExit('too many files')
        bname = name.encode('mac_roman')
        if not 0 < len(bname) <= 32 or b'-' in bname[:1]:
            raise SystemExit(f'bad Lisa file name: {name!r}')
        npages = (len(contents) + 511) // 512
        hint = self.alloc(1)
        first = self.alloc(npages) if npages else 0
        if npages:
            self.chain(first, npages, sfile, contents)
        h = bytearray(512)                        # hint page: file header (hentry)
        struct.pack_into('>B32s', h, 0, len(bname), bname)
        h[0x22:0x2A] = hashlib.sha1(self.volid + struct.pack('>H', sfile)).digest()[:8]
        struct.pack_into('>HB', h, 0x2A, 21, 14)  # header version, ftype = userfile
        struct.pack_into('>LLL', h, 0x2E, self.when, self.when, self.when)   # DTC DTA DTM
        struct.pack_into('>hh', h, 0x6C, 0, 1)    # parentID = root, fsOverhead = 1 page
        struct.pack_into('>LHH', h, 0x80, npages, 9, 1 if npages else 0)     # small map
        h[384:384 + len(label)] = label           # file label (128 bytes at most)
        if npages:
            struct.pack_into('>LH', h, 0x88, first, npages)
        self.put(hint, h, -sfile, 0, 0)
        self.files.append((bname, sfile, hint, first, len(contents), npages))

    # ---- volume structures -----------------------------------------------
    def mddf(self, initial):
        m = bytearray(512)
        nfiles = len(self.files)
        used = sum(1 + f[5] for f in self.files)
        fpages = LASTFSPAGE - CATALOG + 1
        cat_pages = 1 + (MAXFILES * CENTRY_SIZE + 511) // 512
        struct.pack_into('>H8sH', m, 0, 17, self.volid, 0)
        struct.pack_into('>B32s', m, 12, len(self.name), self.name)
        struct.pack_into('>LLLLLL', m, 80, 0, 0, self.when, 0, 0, 0)
        struct.pack_into('>LLLLL', m, 104, 0, FS_START, FS_START + LASTFSPAGE, LASTFSPAGE, SECTORS)
        struct.pack_into('>HHHLHLLHH', m, 124, 536, 512, 1, 0, 314, 1, PAGES, len(self.bitmap), 1)
        struct.pack_into('>LHHHHH', m, 148, SLIST, SENTPP, SPAGES, FIRSTFILE,
                         FIRSTFILE + (0 if initial else nfiles), MAXFILES)
        struct.pack_into('>HHHHHHHH', m, 162, 1, 0, 1, 512 - 128, 0, 0, 84,
                         FIRSTFILE - 1 + (0 if initial else nfiles))
        struct.pack_into('>LLLHH', m, 178, CATALOG, 0,
                         fpages - (0 if initial else NODE_PAGES + used), 4, MAXFILES)
        m[194] = 0                                # mountinfo: unmounted
        struct.pack_into('>HH', m, 276, 128, 0)   # small map / hentry offsets
        struct.pack_into('>HHHHHL', m, 288, 128, 1 + 1 + SPAGES + cat_pages, 0, 0, 0, 0)
        struct.pack_into('>lHHHB', m, 302, -1 if initial else CATALOG, 0 if initial else 1, 0, 0, 0)
        return m

    def catalog(self):
        def key(parent, name):
            return struct.pack('>BH', 36, parent) + name.ljust(32, b'\0') + b'\0'

        def order(rec):
            k = rec[1:36]
            return bytes(c - 32 if 97 <= c <= 122 else c for c in k)
        recs = [key(0, b'') + struct.pack('>Hh', 0x0800, -1) + b'\0' * 38]   # root thread
        for bname, sfile, hint, first, size, npages in self.files:
            recs.append(key(0, bname) + struct.pack('>HHLLLLHHL', 0x0300, sfile, self.when, self.when,
                                                    size, npages * 512, 1, 0, 0))
        recs.sort(key=order)
        node = bytearray(NODE_PAGES * 512)
        pos = 0
        for i, r in enumerate(recs):
            struct.pack_into('>H', node, 2034 - 2 * i, pos)
            node[pos:pos + len(r)] = r
            pos += len(r)
        struct.pack_into('>H', node, 2034 - 2 * len(recs), pos)
        if pos > 2034 - 2 * len(recs):
            raise SystemExit('too many files for one catalog node')
        struct.pack_into('>HllBB', node, 2036, len(recs), -1, -1, 0, 0)
        return node

    def image(self):
        self.bitmap[MDDF_BACKUP // 8] |= 1 << (MDDF_BACKUP % 8)
        for p in range(CATALOG):
            self.bitmap[p // 8] |= 1 << (p % 8)
        self.put(MDDF_BACKUP, self.mddf(True)[:314], 1, 0, 314, NONE, MDDF_BACKUP - 1, mark=False)
        self.put(0, self.mddf(False)[:314], 1, 0, 314)
        sl = bytearray(SPAGES * 512)
        for i in range(FIRSTFILE):
            struct.pack_into('>llLH', sl, i * 14, -1, -1, 0, 0)
        for bname, sfile, hint, first, size, npages in self.files:
            struct.pack_into('>LLLH', sl, (sfile // SENTPP) * 512 + (sfile % SENTPP) * 14,
                             hint, first, size, 0)
        for i in range(SPAGES):
            self.put(SLIST + i, sl[i * 512:(i + 1) * 512], 3, i, 512 if i < SPAGES - 1 else 0,
                     SLIST + i + 1 if i < SPAGES - 1 else NONE, SLIST + i - 1 if i else NONE)
        self.chain(CATALOG, NODE_PAGES, 4, self.catalog())
        self.put(1, self.bitmap, 2, 0, len(self.bitmap), NONE, 0)
        return dc42(bytes(self.data), bytes(self.tags))


def tool_label(name):
    """The Desktop Manager's file label for a tool."""
    b = name.encode('mac_roman')
    if len(b) > 63:
        raise SystemExit('tool name longer than 63 characters')
    return struct.pack('>HB63sHBB4hhll', 2, len(b), b, 24, False, False, 40, 10, 290, 640, -32768, 0, 1)


def dc42_sum(b):
    s = 0
    for i in range(0, len(b), 2):
        s = (s + (b[i] << 8 | b[i + 1])) & 0xFFFFFFFF
        s = (s >> 1 | s << 31) & 0xFFFFFFFF
    return s


def dc42(data, tags):
    name = b'-not a Macintosh disk-'
    hdr = bytes([len(name)]) + name.ljust(63, b'\0')
    hdr += struct.pack('>LLLLBBH', len(data), len(tags), dc42_sum(data), dc42_sum(tags[12:]), 0, 2, 0x100)
    return hdr + data + tags


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('-n', '--name', default='LisaC', help='volume name (default LisaC)')
    ap.add_argument('-t', '--tool-name', help='name shown for the tool ({Tn}obj) on the desktop')
    ap.add_argument('--date', default='1984-01-24', help='creation date of the volume and files')
    ap.add_argument('out')
    ap.add_argument('files', nargs='*')
    a = ap.parse_args()
    if '-' in a.name or len(a.name.encode('mac_roman')) > 32:
        sys.exit('bad volume name')
    vol = Volume(a.name, lisa_time(datetime.datetime.fromisoformat(a.date)))
    for f in a.files:
        name = os.path.basename(f)
        label = b''
        if a.tool_name and re.fullmatch(r'\{T\d+\}obj', name, re.I):
            label = tool_label(a.tool_name)
        vol.add(name, open(f, 'rb').read(), label)
    open(a.out, 'wb').write(vol.image())


if __name__ == '__main__':
    main()
