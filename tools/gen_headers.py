#!/usr/bin/env python3
"""Generate the C headers in include/lisa/ from the Lisa Pascal unit interfaces.

    gen_headers.py iface.json data/entries.tsv include/lisa [probe.c]

probe.c (optional) receives compile-time assertions of every record's size
and field offsets and of every parameter's C size: compile it with the
headers to check them against the Pascal layouts.

iface.json comes from tools/pascal_iface.py run over the INTERFACE sections of
the intrinsic units an Office System tool can use (in dependency order).  For
each unit this writes include/lisa/<unit>.h with:

  - its constants (as enumerators, once even if several units declare them);
  - its types: typedefs, and records as structs with every field at the
    Pascal offset (explicit padding; variant parts as anonymous unions);
  - its global variables as macros into the unit's data area (the unit's
    data pointer is at $1FC + 4n (A5); variables lie below it in declaration
    order), unit numbers from the tool unit table (tools/lisa_tables.py);
  - its routines that have an entry point in a segment a tool can call, as
    `pascal` declarations: LISA_IU(LINK, ARGBYTES, RESULTBYTES), the byte
    counts computed from the Pascal passing rules for the thunk generator.

Interface facts only: names, types, layouts.  Hand-written notes and helpers
per unit come from tools/header_notes.py.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lisa_tables import UI_SEGMENTS, UI_UNITS  # noqa: E402
import header_notes  # noqa: E402

C_KEYWORDS = {
    'auto', 'break', 'case', 'char', 'const', 'continue', 'default', 'do', 'double', 'else', 'enum',
    'extern', 'float', 'for', 'goto', 'if', 'inline', 'int', 'long', 'register', 'restrict', 'return',
    'short', 'signed', 'sizeof', 'static', 'struct', 'switch', 'typedef', 'union', 'unsigned', 'void',
    'volatile', 'while', 'bool', 'true', 'false', 'pascal', 'asm', 'typeof', 'NULL',
}
# Types provided by lisa/pascal.h
BASE_TYPES = {'integer': 'Integer', 'longint': 'LongInt', 'boolean': 'Boolean'}
TYPES_ONLY = {'syscall', 'psyscall'}         # the OS interface: lisa_os.h has the calls
FILE_NAME = {'syscall': 'ostypes', 'psyscall': 'ostypes'}

UNIT_NUMBER = {name: num for name, num, _ in UI_UNITS}
TOOL_SEGMENTS = {s for s, _ in UI_SEGMENTS}


class Gen:
    def __init__(self, iface, entries):
        self.iface = iface
        self.entries = entries
        self.cname = {}          # lower Pascal type name -> C name
        self.kind = {}           # lower Pascal type name -> type descriptor
        self.declared = set()    # lower names whose C typedef has been emitted
        self.idents = {}         # C identifier -> what it is (to catch clashes)
        self.globals = set()     # names defined as macros (global variables)
        self.report = []
        self.probe = []          # compile-time checks
        self.skipped_enums = []
        self.fields = set()      # every record field name: a macro must not shadow one
        for u in iface.values():
            for name, t in u['types'].items():
                self.cname.setdefault(name.lower(), cid(name))
                self.kind.setdefault(name.lower(), t)
                self.collect_fields(t)

    def collect_fields(self, t):
        if t.get('kind') == 'record':
            for f in t['fields']:
                self.fields.add(fid(f['name']))
                self.collect_fields(f['tdesc'])
        elif t.get('kind') == 'array':
            self.collect_fields(t['of'])

    def claim(self, ident, what):
        """Register a global C identifier; False if already taken."""
        if ident in self.idents:
            if self.idents[ident] != what:
                self.report.append(f'{what} {ident}: already {self.idents[ident]}, skipped')
            return False
        self.idents[ident] = what
        return True

    # ---- C types -------------------------------------------------------------

    def ctype(self, t, name='', depth=0):
        """C declaration of `name` with Pascal type descriptor t."""
        sp = (' ' + name) if name else ''
        k = t['kind']
        tn = t.get('name')
        if tn and tn.lower() in self.cname and (k != 'pointer' or tn.lower() in self.declared):
            return self.cname[tn.lower()] + sp
        if k in BASE_TYPES:
            return BASE_TYPES[k] + sp
        if k == 'char':
            return 'char' + sp
        if k == 'byte':
            return 'int8_t' + sp
        if k == 'real':
            return 'float' + sp
        if k in ('double', 'comp'):
            return ('double' if k == 'double' else 'int64_t') + sp
        if k in ('ptr', 'text', 'univ', 'untyped', 'unknown'):
            return 'void *' + name if k != 'unknown' or t.get('size', 4) == 4 else f'uint8_t {name}[{t["size"]}]'
        if k == 'extended':
            return f'uint8_t {name}[10]'
        if k == 'pointer':
            pt = self.pointee(t['to'])
            return pt + ('*' if pt.endswith('*') else ' *') + name
        if k == 'string':                    # length byte + characters, padded to even
            return f'unsigned char {name}[{t["size"]}]'
        if k == 'set':
            return {1: 'uint8_t', 2: 'uint16_t', 4: 'uint32_t'}.get(t['size'], None) and \
                {1: 'uint8_t', 2: 'uint16_t', 4: 'uint32_t'}[t['size']] + sp or f'uint8_t {name}[{t["size"]}]'
        if k == 'enum':
            return ('uint8_t' if t['size'] == 1 else 'uint16_t') + sp
        if k == 'subrange':
            lo, hi, sz = t['lo'], t['hi'], t['size']
            if sz == 1:
                return ('int8_t' if lo < 0 else 'uint8_t') + sp
            if sz == 2:
                return ('uint16_t' if hi > 32767 else 'int16_t') + sp
            return 'int32_t' + sp
        if k == 'array':
            if t.get('elem_bits'):
                return f'uint8_t {name}[{t["size"]}]'
            dims = ''.join(f'[{d}]' for d in t['dims'])
            el = t['of']
            if el['size'] == 1 and t['elem_size'] == 2:      # byte-sized elements in words
                return f'uint16_t {name}{dims}'
            return self.ctype(el, name + dims, depth + 1)
        if k == 'record':
            return 'struct ' + self.struct_body(t, depth + 1) + sp
        raise ValueError(f'type {k}')

    def pointee(self, target):
        low = target.lower()
        t = self.kind.get(low)
        if t is None:
            return 'void'
        if t['size'] == 1 and t['kind'] not in ('record', 'array', 'string'):
            return 'void'                      # a blind pointer (^byte): void * in C
        if t['kind'] == 'string':
            return 'unsigned char'             # ^string: a pointer to its length byte
        if t['kind'] == 'array' and len(t['dims']) == 1 and not t.get('elem_bits') and \
                not (t['of']['size'] == 1 and t['elem_size'] == 2):
            el = t['of']                         # ^array: a pointer to its first element
            return self.pointee(el['name']) if el.get('name') else self.ctype(el)
        if t['kind'] == 'record':
            return 'struct ' + self.cname[low]
        if low in self.declared:
            return self.cname[low]
        if t['kind'] == 'pointer':               # a forward pointer type: follow it
            inner = self.pointee(t['to'])
            return (inner + ('*' if inner.endswith('*') else ' *')) if inner != 'void' else 'void'
        return 'void'

    # ---- records ---------------------------------------------------------------

    def struct_body(self, t, depth=1, tag=''):
        ind = '    ' * depth
        fields = t['fields']
        lines = []
        pad = [0]

        def pad_to(cur, off, ind2):
            if off > cur:
                pad[0] += 1
                lines.append(f'{ind2}uint8_t _pad{pad[0]}[{off - cur}];')
            return max(cur, off)

        def seq(fs, start, ind2):
            cur = start
            for f in fs:
                if f['offset'] < cur:
                    return None
                cur = pad_to(cur, f['offset'], ind2)
                lines.append(f'{ind2}{self.ctype(f["tdesc"], fid(f["name"]), depth + 1)};')
                cur += f['size']
            return cur

        common = [f for f in fields if 'variant' not in f]
        variants = {}
        for f in fields:
            if 'variant' in f:
                variants.setdefault(f['variant'], []).append(f)
        ok = True
        cur = seq(common, 0, ind)
        if cur is None:
            ok = False
        elif variants:
            vstart = min(f['offset'] for vs in variants.values() for f in vs)
            cur = pad_to(cur, vstart, ind)
            lines.append(f'{ind}union {{')
            vend = vstart
            for vs in variants.values():
                lines.append(f'{ind}    struct {{')
                e = seq(vs, vstart, ind + '        ')
                if e is None:
                    ok = False
                    break
                vend = max(vend, e)
                lines.append(f'{ind}    }};')
            lines.append(f'{ind}}};')
            cur = vend
            # C rounds a struct holding word-aligned members up to even
            if any(f['size'] > 1 for vs in variants.values() for f in vs):
                cur += cur & 1
        if not ok:                      # overlapping fields: place each one explicitly
            lines = [f'{ind}union {{']
            for i, f in enumerate(fields):
                lead = f'uint8_t _at{i}[{f["offset"]}]; ' if f['offset'] else ''
                lines.append(f'{ind}    struct {{ {lead}{self.ctype(f["tdesc"], fid(f["name"]), depth + 2)}; }};')
            lines.append(f'{ind}    uint8_t _size[{t["size"]}];')
            lines.append(f'{ind}}};')
            cur = t['size']
        pad_to(cur, t['size'], ind)
        close = '    ' * (depth - 1)
        return (tag + ' ' if tag else '') + '{\n' + '\n'.join(lines) + f'\n{close}}}'

    # ---- declarations ------------------------------------------------------------

    def typedef(self, name, t):
        c = cid(name)
        if not self.claim(c, 'type'):
            return None
        self.declared.add(name.lower())
        alias = t.get('name')
        if alias and alias.lower() in self.cname and alias.lower() != name.lower():
            return f'typedef {self.cname[alias.lower()]} {c};'    # T = OtherType
        if t['kind'] == 'record':
            self.probe.append(f'_Static_assert(sizeof({c}) == {t["size"]}, "size of {c}");')
            for f in t['fields']:
                self.probe.append(f'_Static_assert(offsetof({c}, {fid(f["name"])}) == {f["offset"]}, '
                                  f'"{c}.{f["name"]}");')
            return f'typedef struct {c} {self.struct_body(t, 1)} {c};'
        if t['kind'] in BASE_TYPES and t.get('name') is None:
            return f'typedef {BASE_TYPES[t["kind"]]} {c};'
        return f'typedef {self.ctype(t, c)};'

    def routine(self, r):
        link = r['link']
        e = self.entries.get(link)
        if not e or e[1] not in TOOL_SEGMENTS or '%' in r['name']:
            return None, None
        if any(p['kind'] == 'proc' for p in r['params']):
            self.report.append(f'{r["name"]}: procedural parameter, skipped')
            return None, None
        res = r['result']
        if res and res['kind'] == 'addr':
            self.report.append(f'{r["name"]}: large function result, skipped')
            return None, None
        cname = rname(r['name'])
        if not self.claim(cname, 'routine'):
            return None, None
        params, nbytes, used = [], 0, set()
        for p in r['params']:
            pname = fid(p['name'])
            if pname in self.globals or pname in self.idents or pname in used:
                pname += '_'
            used.add(pname)
            t = p['tdesc']
            if p['kind'] == 'var':
                params.append(self.ptr_param(t, pname, const=False))
                nbytes += 4
            elif p['kind'] == 'addr':
                params.append(self.ptr_param(t, pname, const=True))
                nbytes += 4
            else:
                want = {'long': 4, 'word': 2, 'byte': 1}[p['kind']]
                base = self.kind.get((t.get('name') or '').lower(), t)
                # Pascal passes a one-byte value in a stack word.  A BOOLEAN
                # is in the high byte, as C pushes a char; a one-byte set or a
                # CHAR is in the low byte (QuickDraw's DrawChar reads 7(SP)),
                # so C must pass it as an Integer.
                low = (t['kind'] == 'set' and t['size'] == 1) or base['kind'] == 'char'
                if low:
                    want = 2
                self.probe.append(f'_Static_assert(sizeof({self.ctype(t) if not low else "Integer"}) == {want}, '
                                  f'"{r["name"]}.{p["name"]}");')
                if low:
                    params.append(f'Integer {pname}')          # value in the low byte
                else:
                    params.append(self.ctype(t, pname))
                nbytes += 4 if p['kind'] == 'long' else 2
        rbytes = 0
        rtype = 'void'
        if res:
            rtype = self.ctype(res['tdesc'])
            rbytes = 4 if res['kind'] == 'long' else 2
        plist = ', '.join(params) if params else 'void'
        return (f'pascal {rtype} {cname}({plist}) LISA_IU({link}, {nbytes}, {rbytes});', link)

    def ptr_param(self, t, name, const):
        k = t['kind']
        q = 'const ' if const else ''
        tn = t.get('name')
        base = t
        if tn and tn.lower() in self.kind:
            base = self.kind[tn.lower()]
        if k in ('untyped', 'univ'):
            return f'{q}void *{name}'
        if base['kind'] == 'string':
            return f'{q}unsigned char *{name}'
        if base['kind'] == 'array' and not base.get('elem_bits'):
            el = base['of']
            if not (el['size'] == 1 and base['elem_size'] == 2) and len(base['dims']) == 1:
                return q + self.ctype(el, '*' + name)
        return q + self.ctype(t, '*' + name)

    def globals_of(self, unit, u):
        num = UNIT_NUMBER.get(unit[:8].upper())
        if num is None or not u['vars']:
            return []
        out, off = [], 0
        for v in u['vars']:
            size = v['size'] + (v['size'] & 1)
            off += size
            name = cid(v['name'])
            if name in self.fields:         # the macro would break .name / ->name
                self.report.append(f'global {name} of {unit} is also a record field: named {unit}_{name}')
                name = f'{unit}_{name}'
            if not self.claim(name, 'global'):
                continue
            self.globals.add(name)
            t = v['tdesc']
            tn = t.get('name')
            simple = (tn and tn.lower() in self.cname) or t['kind'] in BASE_TYPES or t['kind'] == 'pointer'
            if simple and t['kind'] != 'array':
                ctyp = self.ctype(t)
                out.append(f'#define {name} (*({ctyp} *)(lisa_unit_data({num}) - {off}))')
            else:
                out.append(f'typedef {self.ctype(t, "lisa_" + name + "_t")};')
                out.append(f'#define {name} (*(lisa_{name}_t *)(lisa_unit_data({num}) - {off}))')
        return out


def cid(name):
    return name + '_' if name in C_KEYWORDS else name


def rname(name):
    """Routine names start with a capital (Pascal does not care; a few
    interfaces write initMP, while the tools call InitMP)."""
    return cid(name[:1].upper() + name[1:])


def fid(name):
    return name + '_' if name in C_KEYWORDS else name


def enum_lines(items):
    if not items:
        return []
    body = ',\n'.join(f'    {n} = {v}' for n, v in items)
    return ['enum {', body, '};']


def main():
    iface_path, entries_path, outdir = sys.argv[1:4]
    iface = json.load(open(iface_path))
    entries = {}
    for line in open(entries_path):
        if not line.startswith('#'):
            lib, seg, link, a = line.rstrip('\n').split('\t')
            entries[link] = (lib, seg, int(a, 16))
    g = Gen(iface, entries)
    files = []                                   # (file, [lines])
    by_file = {}
    prev = 'lisa/pascal.h'
    stats = []
    for unit, u in iface.items():
        fname = FILE_NAME.get(unit, unit.lower())
        notes = header_notes.NOTES.get(unit, {})
        if fname not in by_file:
            lines = []
            by_file[fname] = lines
            files.append((fname, lines, prev, notes))
            prev = f'lisa/{fname}.h'
        lines = by_file[fname]
        lines.append(f'/* ---- unit {unit} ---- */')
        # constants: integers, in source order; the values of enumerated types
        consts = []
        for name, v in u['consts'].items():
            if isinstance(v, bool) or not isinstance(v, int):
                continue
            if not (-2**31 <= v < 2**31):
                continue
            cname = cid(orig_case(u, name))
            if g.claim(cname, 'constant'):
                consts.append((cname, v))
        for tname in u['order']:
            t = u['types'][tname]
            if t['kind'] == 'enum':
                for i, val in enumerate(t['values']):
                    # Pascal lets a program's names hide a unit's; C does not.
                    # Leave out values that would take common words (v, h,
                    # frame, paint, draw, ...): very short or plain lowercase.
                    if len(val) <= 2 or '%' in val or re.fullmatch(r'[a-z]+', val):
                        g.skipped_enums.append(val)
                        continue
                    if g.claim(cid(val), 'constant'):
                        consts.append((cid(val), i))
        lines += enum_lines(consts)
        # types, in declaration order
        for tname in u['order']:
            td = g.typedef(tname, u['types'][tname])
            if td:
                lines.append(td)
        # globals
        lines += g.globals_of(unit, u)
        # routines
        n = 0
        if unit not in TYPES_ONLY:
            for r in u['routines']:
                decl, link = g.routine(r)
                if decl:
                    lines.append(decl)
                    n += 1
        stats.append((unit, n))
        if notes.get('extra'):
            lines.append(notes['extra'].strip('\n'))
    os.makedirs(outdir, exist_ok=True)
    for fname, lines, inc, notes in files:
        guard = 'LISA_' + re.sub(r'\W', '_', fname.upper()) + '_H'
        doc = notes.get('doc', '').strip('\n')
        head = ['/* Generated by tools/gen_headers.py from the Lisa Pascal interfaces -- do not edit.',
                ' * Hand-written notes: tools/header_notes.py. */']
        if doc:
            head.append('/* ' + doc.replace('\n', '\n * ') + ' */')
        text = '\n'.join(head + [f'#ifndef {guard}', f'#define {guard}', f'#include "{inc}"', ''] +
                         lines + ['', '#endif', ''])
        open(os.path.join(outdir, fname + '.h'), 'w').write(text)
    if len(sys.argv) > 4:
        last = files[-1][0]
        open(sys.argv[4], 'w').write('/* Generated by tools/gen_headers.py -- do not edit.\n'
                                     ' * Compile-time checks of the headers against the Lisa Pascal\n'
                                     ' * interfaces: every record size and field offset, and the C size\n'
                                     ' * of every parameter passed by value (make test-headers). */\n'
                                     '#include <stddef.h>\n#include "lisa/' + last + '.h"\n' +
                                     '\n'.join(g.probe) + '\n')
    if g.skipped_enums:
        print('note: enum values left out (plain words): ' + ' '.join(sorted(set(g.skipped_enums))),
              file=sys.stderr)
    for line in g.report:
        print('note:', line, file=sys.stderr)
    print(f'{len(files)} headers, {sum(n for _, n in stats)} routines', file=sys.stderr)


def orig_case(u, low):
    return u.get('const_names', {}).get(low, low)


if __name__ == '__main__':
    main()
