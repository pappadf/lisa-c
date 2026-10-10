#!/usr/bin/env python3
"""Compile a Lisa phrase file (menus + alerts) for an Office System tool.

The binary layout is what the Alert Manager's InitMP / ReadAlerts read
(LOS 3.x), all integers big-endian:

  menus:   count, then per menu: id, enable flags (32-bit packed boolean array,
           bit i of byte i/8 = item i, item 0 = whole menu), data length, data
           (title as Pascal string; per item a Pascal string and 3 attribute
           bytes: Apple-key character or space, 0, space; a 0 byte ends the list)
           then a mapping word (0)
  cache:   alerts to cache, cache bytes
  alerts:  version; for ask/wait/stop/note/caution: sign label (string[15],
           blank padded), number of outline points n, n+1 points (v, h);
           last button index, button labels (string[15]); number of alerts;
           6-byte alert records (number; kind:4 boxes:4 volumes:2x4; text
           length, or -index of an equated alert); the texts.  (Later AlertGens
           append a copyright string and a checksum byte; the LOS 3.1 files
           have neither, and neither do ours.)

Source format (Workshop/ToolKit phrase source; ';' lines are comments):

  <version>            the tool passes this to InitMP
  <alerts to cache>
  <alert cache bytes>
  ?  Wait  Stop  Note  Caution     one line each: alert sign labels
  Cancel  OK  [more buttons]       one per line, ended by a blank line
  <n> <kind> [<stages>]            alerts, ascending n, each followed by its
  text lines ...                   text and a blank line; '0' ends the alerts
                                   kinds: stop note wait ask draw caution
                                   [stop|note|ok|cancel|insist]; none = string
                                   stages: e.g. "alert", "soft; medium alert",
                                   "alert=1" (reuse alert 1's text)
  <menu id>                        menus: id, title, items (Name or Name/K for
  <title>                          Apple-K; "-" is a disabled separator; a
  items ...                        leading '(' disables an item); blank line
                                   ends a menu, '0' ends the menus

usage: phrasec.py source.text out.phrase
       phrasec.py --dump file.phrase
"""
import itertools
import os
import struct
import sys

SIGN_POINTS = {   # alert sign outlines: text center, then the polygon (h, v)
    'ask': [(66, 44), (66, 10), (117, 44), (66, 78), (15, 44)],
    'wait': [(66, 25), (65, 78), (67, 78), (116, 12), (116, 11), (115, 10), (17, 10), (16, 11), (16, 12)],
    'stop': [(66, 44), (87, 10), (117, 30), (117, 58), (87, 78), (45, 78), (15, 58), (15, 30), (45, 10)],
    'note': [(66, 44), (30, 20), (102, 20), (102, 68), (30, 68)],
    'caution': [(66, 68), (65, 7), (67, 7), (121, 79), (121, 80), (120, 81), (12, 81), (11, 80), (11, 79)],
}
SIGNS = ['ask', 'wait', 'stop', 'note', 'caution']
KIND = {'get': 0, 'draw': 1, 'ask': 2, 'wait': 3, 'stop': 4, 'note': 5, 'caution': 6,
        'caution ok': 7, 'caution cancel': 8, 'caution stop': 9, 'caution note': 10, 'caution insist': 11}
VOLUME = {'silent': 0, 'soft': 1, 'medium': 2, 'loud': 3}
CITE = {'L': -1, 'N': -4, 'C': -5, 'K': -12, '0': -6, '1': -7, '2': -8, '3': -9, '4': -10, '5': -11}
SIGN_LEN = 15


class PhraseError(Exception):
    pass


def lines_of(path):
    """Yield source lines as Latin-1 strings (bytes preserved), without comment
    lines; '$file' lines are replaced by that file's lines (relative to the
    including file; '.text' optional) and a leading '~' quotes the next character."""
    for raw in open(path, 'rb').read().replace(b'\r\n', b'\n').replace(b'\r', b'\n').split(b'\n'):
        line = raw.decode('latin-1').rstrip('\x00\x7f\xff')
        if line.startswith(';'):
            continue
        if line.startswith('$'):
            name = os.path.join(os.path.dirname(path), line[1:].strip())
            if not os.path.exists(name) and os.path.exists(name + '.text'):
                name += '.text'
            yield from lines_of(name)
            continue
        if line.startswith('~'):
            line = line[1:]
        yield line


def pstr(s, pad=None):
    b = s.encode('latin-1')
    if pad is not None:
        if len(b) > pad:
            raise PhraseError(f'"{s}" is longer than {pad} characters')
        b = b.ljust(pad, b' ')
    return bytes([len(s.encode('latin-1'))]) + b


def parse_stages(words):
    """'soft ; medium alert = 1' -> (boxes[4], volumes[4], equated alert or None)."""
    stages, cur, equated = [], {'box': False, 'vol': 0, 'any': False}, None
    i = 0
    while i < len(words):
        w = words[i]
        if w == '=':
            equated = int(words[i + 1])
            i += 1
        elif w in VOLUME:
            cur['vol'], cur['any'] = VOLUME[w], True
        elif w == 'alert':
            cur['box'], cur['any'] = True, True
        elif w == ';':
            stages.append(cur)
            cur = {'box': False, 'vol': 0, 'any': False}
        elif w != '+':
            raise PhraseError(f'bad word in stage: {w}')
        i += 1
    if cur['any']:
        stages.append(cur)
    if not stages:
        raise PhraseError('missing stage')
    while len(stages) < 4:
        stages.append(stages[-1])
    return [s['box'] for s in stages[:4]], [s['vol'] for s in stages[:4]], equated


def tokenize_header(line):
    out = []
    for part in line.replace('=', ' = ').replace(';', ' ; ').replace('+', ' + ').split():
        out.append(part.lower())
    return out


def encode_text(line):
    """One line of alert text -> word records (length byte + bytes; codes for ^x)."""
    out = bytearray()
    i, n = 0, len(line)

    def word(b):
        out.append(len(b))
        out.extend(b)
    while i < n:
        if line[i] == '^' and i + 1 < n:
            c = line[i + 1]
            i += 2
            cu = c.upper()
            if c == '^':
                word(b'^')
            elif cu in CITE:
                out.append((CITE[cu] + 256) & 0xFF)
            elif c in '?!':
                j = line.find('^', i)
                j = n if j < 0 else j
                out.append((-2 if c == '?' else -3) + 256)
                word(line[i:j].encode('latin-1'))
                i = j
            elif c in '789':
                digits = 1
                while i < n and line[i] == c:
                    digits = min(5, digits + 1)
                    i += 1
                out.append((-15 + 1 - digits - 5 * (ord(c) - ord('7'))) & 0xFF)
            else:
                word(('^' + c).encode('latin-1'))
            continue
        j = i
        while j < n and line[j] not in ' ^':
            j += 1
        while j < n and line[j] == ' ':
            j += 1
        w = line[i:j]
        if j >= n:
            w += ' '                     # a line end counts as a space
        word(w.encode('latin-1'))
        i = j
    return bytes(out)


def compile_phrase(path):
    src = iter(lines_of(path))

    def next_line():
        for line in src:
            return line
        raise PhraseError('unexpected end of file')

    def next_nonblank():
        while True:
            line = next_line()
            if line.strip():
                return line

    version = int(next_nonblank())
    line = next_nonblank()
    alerts_only = not line.strip().isdigit()        # a ReadAlerts file: no cache, no menus
    if alerts_only:
        src = itertools.chain([line], src)
    else:
        cache_size = int(line)
        cache_bytes = int(next_nonblank())

    alerts = bytearray(struct.pack('>H', version))
    for sign in SIGNS:
        label = next_line()
        pts = SIGN_POINTS[sign]
        alerts += pstr(label, SIGN_LEN) + struct.pack('>H', len(pts) - 1)
        for h, v in pts:
            alerts += struct.pack('>hh', v, h)
    buttons = []
    while True:
        line = next_line()
        if not line.strip():
            break
        buttons.append(line)
    if len(buttons) < 2:
        raise PhraseError('Cancel and OK button labels are required')
    alerts += struct.pack('>H', len(buttons) - 1)
    for b in buttons:
        alerts += pstr(b, SIGN_LEN)

    records, texts, numbers = [], [], []
    vols = [0] * 4
    while True:
        try:
            header = next_nonblank()
        except PhraseError:
            if alerts_only:
                break
            raise
        words = tokenize_header(header)
        number = int(words[0])
        if number == 0:
            break
        if numbers and number <= numbers[-1]:
            raise PhraseError(f'alert {number}: numbers must ascend')
        rest = words[1:]
        if rest[:1] == ['caution'] and len(rest) > 1 and rest[1] in ('stop', 'note', 'ok', 'cancel', 'insist'):
            kind, rest = KIND['caution ' + rest[1]], rest[2:]
        elif rest and rest[0] in KIND:
            kind, rest = KIND[rest[0]], rest[1:]
        elif not rest:
            kind = KIND['get']
        else:
            raise PhraseError(f'alert {number}: unknown kind {rest[0]}')
        boxes, equated = [False] * 4, None          # string alerts keep the volumes (as AlertGen does)
        if kind != KIND['get']:
            boxes, vols, equated = parse_stages(rest)
        text = bytearray()
        while True:
            line = next_line()
            if not line.strip():
                break
            if kind == KIND['get']:
                text += pstr(line)
            else:
                text += encode_text(line)
        if equated is not None:
            if text:
                raise PhraseError(f'alert {number}: text after an equated alert')
            if equated not in numbers:
                raise PhraseError(f'alert {number}: alert {equated} is not defined above')
            length = -(numbers.index(equated) + 1)
        else:
            length = len(text)
        flags = (kind << 12) | sum(1 << (11 - i) for i in range(4) if boxes[i]) | \
            sum(v << (6 - 2 * i) for i, v in enumerate(vols))
        records.append(struct.pack('>HHh', number, flags, length))
        texts.append(bytes(text) if equated is None else b'')
        numbers.append(number)
    if numbers[:2] != [1, 2]:
        raise PhraseError('alerts 1 (default) and 2 (swan song) must be defined')
    alerts += struct.pack('>H', len(records)) + b''.join(records) + b''.join(texts)

    if alerts_only:
        return bytes(alerts + b'\0' * (len(alerts) % 2))
    menus = []
    while True:
        line = next_nonblank()
        menu_id = int(line)
        if menu_id == 0:
            break
        title = next_line()
        data = bytearray(pstr(title))
        flags = 1                                   # item 0: the whole menu
        item = 0
        while True:
            line = next_line()
            if not line.strip():
                break
            item += 1
            key = b' '
            if len(line) >= 2 and line[-2] == '/' and line != '/':
                key, line = line[-1].upper().encode('latin-1'), line[:-2]
            if line not in ('-', '.'):                # separators are disabled
                flags |= 1 << item
            data += pstr(line) + key + b'\x00 '
        data.append(0)
        if len(data) % 2:
            data.append(0)
        if item > 31:
            raise PhraseError(f'menu {menu_id}: more than 31 items')
        flags |= ~((1 << (item + 1)) - 1) & 0xFFFFFFFF   # unused items: enabled, as in Apple's files
        menu_flags = bytes((flags >> (8 * k)) & 0xFF for k in range(4))
        menus.append(struct.pack('>H', menu_id) + menu_flags + struct.pack('>H', len(data)) + bytes(data))

    out = bytearray(struct.pack('>H', len(menus)) + b''.join(menus))
    out += struct.pack('>H', 0)                     # mapping
    out += struct.pack('>HH', cache_size, cache_bytes)
    out += alerts
    if len(out) % 2:
        out.append(0)                               # Apple's files have even lengths
    return bytes(out)


def dump(data, alerts_only=False):
    """Print a compiled phrase file section by section (for checking)."""
    pos = 0

    def take(fmt):
        nonlocal pos
        v = struct.unpack_from(fmt, data, pos)
        pos += struct.calcsize(fmt)
        return v if len(v) > 1 else v[0]

    def pstring(width=None):
        nonlocal pos
        n = data[pos]
        s = data[pos + 1:pos + 1 + n].decode('latin-1')
        pos += 1 + (width if width is not None else n)
        return s
    for _ in range(0 if alerts_only else take('>H')):
        mid, flags, n = take('>H4sH')
        end = pos + n
        title = pstring()
        items = []
        while data[pos]:
            name = pstring()
            items.append((name, data[pos:pos + 3]))
            pos += 3
        print(f'menu {mid} {title!r} flags {flags.hex()} len {n}')
        for name, attr in items:
            print(f'    {name!r} {attr.hex()}')
        if data[pos + 1:end]:
            print(f'    trailing {data[pos + 1:end].hex()}')
        pos = end
    if not alerts_only:
        print('mapping %d cache %d bytes %d' % (take('>H'), take('>H'), take('>H')))
    print('version', take('>H'))
    for sign in SIGNS:
        label = pstring(SIGN_LEN)
        pts = [take('>hh') for _ in range(take('>H') + 1)]
        print(f'sign {sign} {label!r} ' + ' '.join(f'({h},{v})' for v, h in pts))
    print('buttons', [pstring(SIGN_LEN) for _ in range(take('>H') + 1)])
    recs = [take('>HHh') for _ in range(take('>H'))]
    for num, flags, length in recs:
        text = b''
        if length > 0:
            text, pos = data[pos:pos + length], pos + length
        print(f'alert {num} kind {flags >> 12} boxes {flags >> 8 & 15:04b} vols {flags & 255:08b} '
              f'len {length} {text.hex()}')
    if data[pos:]:
        print('trailing', data[pos:].hex())


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--dump':
        data = open(sys.argv[2], 'rb').read()
        try:
            return dump(data)
        except (IndexError, struct.error, UnicodeDecodeError):
            print('(no menus: an alerts-only file)')
            return dump(data, alerts_only=True)
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    try:
        data = compile_phrase(sys.argv[1])
    except (PhraseError, ValueError, StopIteration) as e:
        sys.exit(f'{sys.argv[1]}: {e}')
    open(sys.argv[2], 'wb').write(data)


if __name__ == '__main__':
    main()
