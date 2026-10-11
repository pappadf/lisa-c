#!/usr/bin/env python3
"""Extract Lisa Pascal unit interfaces into structured JSON (for cross-checking).

Reads the INTERFACE section of Lisa Pascal units (e.g. the user's copy of the
CHM source) and writes, per unit: constants, types with their Lisa Pascal
memory layout (size, field offsets), and procedure/function signatures.
The output is meant for *private* consistency checks of hand-written C
headers (tools/check_headers.py) and is never published.

Layout rules (Lisa Pascal, Development System Internals "Packing"):
  integer 2, longint/real/pointer 4, boolean/char 1 byte, enumerations with
  <= 256 values and subranges that fit in a byte take 1 byte, others 2;
  string[n] = n+1 bytes; set of 0..n = ceil((n+1)/8) bytes (even, except a
  1-byte set); arrays of byte-sized elements pack in unpacked records only
  when declared packed, and a packed array of boolean takes one bit per
  element (element i = bit i mod 8 of byte i div 8), sized like a set.  Record fields start on word boundaries except
  byte-sized fields, which take the next byte; records are word-sized.

usage: pascal_iface.py out.json unit.text...
"""
import json
import re
import sys

KEYWORDS = {'and', 'array', 'begin', 'case', 'const', 'div', 'do', 'downto', 'else', 'end', 'file',
            'for', 'function', 'goto', 'if', 'in', 'label', 'mod', 'nil', 'not', 'of', 'or',
            'packed', 'procedure', 'program', 'record', 'repeat', 'set', 'then', 'to', 'type',
            'until', 'var', 'while', 'with', 'string', 'unit', 'interface', 'implementation',
            'uses', 'intrinsic', 'shared', 'external', 'forward'}

BUILTIN = {'integer': (2, 2), 'longint': (4, 2), 'real': (4, 2), 'boolean': (1, 1), 'char': (1, 1),
           'byte': (1, 1), 'ptr': (4, 2), 'text': (4, 2), 'double': (8, 2), 'extended': (10, 2),
           'comp': (8, 2), 'univ': (4, 2)}


# ---------------------------------------------------------------- lexing

def strip_comments(src, flags):
    """Remove comments, evaluating {$IFC}/{$ELSEC}/{$ENDC} conditionals."""
    out, i, stack, active = [], 0, [], True
    n = len(src)
    while i < n:
        c = src[i]
        if c == '{' or src.startswith('(*', i):
            end = src.find('}', i) if c == '{' else src.find('*)', i)
            if end < 0:
                end = n
            body = src[i + 1:end] if c == '{' else src[i + 2:end]
            i = end + (1 if c == '{' else 2)
            m = re.match(r'\$(\w+)\s*(.*)', body.strip(), re.S)
            if m:
                d, arg = m.group(1).upper(), m.group(2)
                if d == 'SETC':
                    mm = re.match(r'(\w+)\s*:?=\s*(.*)', arg)
                    if mm and active:
                        flags[mm.group(1).lower()] = eval_flag(mm.group(2), flags)
                elif d == 'IFC':
                    stack.append((active, active and eval_flag(arg, flags)))
                    active = stack[-1][1]
                elif d == 'ELSEC':
                    outer, taken = stack[-1]
                    active = outer and not taken
                elif d == 'ENDC':
                    active = stack.pop()[0]
            out.append(' ')
            continue
        if c == "'":
            end = i + 1
            while end < n:
                if src[end] == "'":
                    if end + 1 < n and src[end + 1] == "'":
                        end += 2
                        continue
                    break
                end += 1
            if active:
                out.append(src[i:end + 1])
            i = end + 1
            continue
        if active:
            out.append(c)
        i += 1
    return ''.join(out)


def eval_flag(expr, flags):
    e = expr.strip().lower()
    e = re.sub(r'\b(true|false)\b', lambda m: 'True' if m.group(1) == 'true' else 'False', e)
    e = re.sub(r'\b([a-z_]\w*)\b', lambda m: m.group(1) if m.group(1) in ('and', 'or', 'not', 'True', 'False')
               else repr(flags.get(m.group(1), False)), e)
    e = e.replace('<>', '!=')
    e = re.sub(r'(?<![<>!=])=(?!=)', '==', e)
    try:
        return bool(eval(e, {'__builtins__': {}}))
    except Exception:
        return False


def tokens(src):
    for m in re.finditer(r"'(?:[^']|'')*'|\$[0-9a-fA-F]+|\d+\.\d+(?:[eE][-+]?\d+)?|\d+|[A-Za-z_%][\w%]*|\.\.|:=|<>|<=|>=|[^\s]", src):
        yield m.group(0)


class Parser:
    def __init__(self, toks):
        self.t = list(toks)
        self.i = 0

    def peek(self, k=0):
        j = self.i + k
        return self.t[j] if j < len(self.t) else ''

    def low(self, k=0):
        return self.peek(k).lower()

    def take(self):
        tok = self.peek()
        self.i += 1
        return tok

    def expect(self, s):
        tok = self.take()
        if tok.lower() != s:
            raise SyntaxError(f'expected {s!r}, got {tok!r} near {" ".join(self.t[self.i - 5:self.i + 5])}')
        return tok


# ---------------------------------------------------------------- layout

class Unit:
    def __init__(self, name, known):
        self.name, self.consts, self.types, self.routines, self.vars = name, {}, {}, [], []
        self.const_names = {}
        self.known = known              # types and consts from previously parsed units

    def const(self, name):
        n = name.lower()
        if n in self.consts:
            return self.consts[n]
        return self.known['consts'].get(n)

    def type(self, name):
        n = name.lower()
        return self.types.get(n) or self.known['types'].get(n)


def byte_sized(lo, hi):
    return -128 <= lo and hi <= 255


def parse_const_expr(p, unit):
    """Very small constant-expression evaluator: ints, names, + - * div, unary minus, strings."""
    def atom():
        tok = p.take()
        if tok == '-':
            return -atom()
        if tok == '(':
            v = expr()
            p.expect(')')
            return v
        if tok.startswith('$'):
            return int(tok[1:], 16)
        if tok.isdigit():
            return int(tok)
        if tok.startswith("'"):
            s = tok[1:-1].replace("''", "'")
            return ord(s) if len(s) == 1 else s
        if re.match(r'\d+\.\d+', tok):
            return float(tok)
        if tok.lower() in ('ord', 'chr', 'ord4', 'sizeof') and p.peek() == '(':
            p.take()
            v = expr()
            p.expect(')')
            return v
        v = unit.const(tok)
        if v is None:
            et = unit.known['enum_values'].get(tok.lower(), unit_enum_values(unit).get(tok.lower()))
            if et is not None:
                return et
            return 0
        return v

    def term():
        v = atom()
        while p.low() in ('*', 'div', 'mod'):
            op = p.take().lower()
            r = atom()
            v = v * r if op == '*' else (v // r if op == 'div' else v % r)
        return v

    def expr():
        v = term()
        while p.peek() in ('+', '-'):
            op = p.take()
            r = term()
            v = v + r if op == '+' else v - r
        return v
    return expr()


def unit_enum_values(unit):
    return unit.__dict__.setdefault('_enum_values', {})


def parse_type(p, unit, packed=False):
    """Return a type descriptor dict with 'kind', 'size', 'align'."""
    tok = p.low()
    if tok == 'packed':
        p.take()
        return parse_type(p, unit, packed=True)
    if tok == '^':
        p.take()
        target = p.take()
        return {'kind': 'pointer', 'to': target, 'size': 4, 'align': 2}
    if tok == '(':
        p.take()
        names = []
        while p.peek() != ')':
            names.append(p.take())
            if p.peek() == ',':
                p.take()
        p.take()
        for k, nm in enumerate(names):
            unit_enum_values(unit)[nm.lower()] = k
        size = 1 if len(names) <= 256 else 2
        return {'kind': 'enum', 'values': names, 'size': size, 'align': size}
    if tok == 'string':
        p.take()
        n = 255
        if p.peek() == '[':
            p.take()
            n = parse_const_expr(p, unit)
            p.expect(']')
        size = n + 1 + ((n + 1) & 1)
        return {'kind': 'string', 'max': n, 'size': size, 'align': 2}
    if tok == 'set':
        p.take()
        p.expect('of')
        base = parse_type(p, unit)
        hi = base.get('hi', 255 if base['kind'] == 'char' else len(base.get('values', [])) - 1)
        nbytes = (hi + 8) // 8
        size = 1 if nbytes == 1 else nbytes + (nbytes & 1)
        return {'kind': 'set', 'of': base, 'bits': hi + 1, 'size': size, 'align': min(size, 2)}
    if tok == 'array':
        p.take()
        p.expect('[')
        dims = []
        while True:
            idx = parse_type(p, unit)
            dims.append(idx['hi'] - idx['lo'] + 1 if 'lo' in idx else len(idx.get('values', [])))
            if p.peek() == ',':
                p.take()
                continue
            break
        p.expect(']')
        p.expect('of')
        elem = parse_type(p, unit)
        n = 1
        for d in dims:
            n *= d
        if packed and elem['kind'] == 'boolean':  # one bit each: element i = bit i mod 8 of byte i div 8
            size = (n + 7) // 8
            size = 1 if size == 1 else size + (size & 1)
            return {'kind': 'array', 'dims': dims, 'of': elem, 'elem_bits': 1, 'size': size, 'align': min(size, 2)}
        esize = elem['size']
        if esize == 1 and not packed:
            esize = 1 if elem['kind'] in ('char', 'byte') else 2
        size = n * esize
        size += size & 1
        return {'kind': 'array', 'dims': dims, 'of': elem, 'elem_size': esize, 'size': size, 'align': 2}
    if tok == 'record':
        p.take()
        fields, size = parse_fields(p, unit, packed)
        p.expect('end')
        return {'kind': 'record', 'fields': fields, 'size': size + (size & 1), 'align': 2, 'packed': packed}
    # subrange or named type
    start = p.i
    if p.peek(1) == '..' or p.peek().startswith(('-', "'")) or p.peek()[:1].isdigit() or p.peek().startswith('$'):
        lo = parse_const_expr(p, unit)
        p.expect('..')
        hi = parse_const_expr(p, unit)
        size = 1 if byte_sized(lo, hi) else (2 if -32768 <= lo and hi <= 65535 else 4)
        return {'kind': 'subrange', 'lo': lo, 'hi': hi, 'size': size, 'align': min(size, 2)}
    name = p.take()
    if p.peek() == '..':                       # enum-constant subrange
        p.i = start
        lo = parse_const_expr(p, unit)
        p.expect('..')
        hi = parse_const_expr(p, unit)
        return {'kind': 'subrange', 'lo': lo, 'hi': hi, 'size': 1 if byte_sized(lo, hi) else 2, 'align': 1}
    t = unit.type(name)
    if t is None:
        b = BUILTIN.get(name.lower())
        if b:
            kind = name.lower()
            d = {'kind': kind, 'size': b[0], 'align': b[1]}
            if kind == 'char':
                d.update(lo=0, hi=255)
            if kind == 'boolean':
                d.update(lo=0, hi=1, values=['false', 'true'])
            return d
        return {'kind': 'unknown', 'name': name, 'size': 4, 'align': 2}
    d = dict(t)
    d['name'] = name
    return d


def parse_fields(p, unit, packed, start=0):
    fields, off, maxend = [], start, start
    while p.low() not in ('end', ')', 'case', ''):
        names = [p.take()]
        while p.peek() == ',':
            p.take()
            names.append(p.take())
        p.expect(':')
        t = parse_type(p, unit, packed)
        for nm in names:
            if t['size'] == 1:
                fo = off
            else:
                fo = off + (off & 1)
            fields.append({'name': nm, 'offset': fo, 'type': describe(t), 'size': t['size'], 'tdesc': t})
            off = fo + t['size']
        if p.peek() == ';':
            p.take()
    maxend = off
    if p.low() == 'case':                      # variant part
        p.take()
        tagname = p.take()
        if p.peek() == ':':
            p.take()
            tag = parse_type(p, unit)
            fo = off if tag['size'] == 1 else off + (off & 1)
            fields.append({'name': tagname, 'offset': fo, 'type': describe(tag), 'size': tag['size'],
                           'tdesc': tag})
            off = fo + tag['size']
        p.expect('of')
        vstart = off + (off & 1)
        maxend = off
        nvariant = 0
        while p.low() not in ('end', ')', ''):
            while p.peek() != ':':
                p.take()
            p.take()
            p.expect('(')
            vf, vend = parse_fields(p, unit, packed, vstart)
            p.expect(')')
            for f in vf:
                f['variant'] = nvariant
            nvariant += 1
            fields += vf
            maxend = max(maxend, vend)
            if p.peek() == ';':
                p.take()
    return fields, maxend


def describe(t):
    k = t['kind']
    if 'name' in t and k not in ('pointer',):
        return t['name']
    if k == 'pointer':
        return '^' + t['to']
    if k == 'string':
        return f"string[{t['max']}]"
    if k == 'array':
        return f"array{t['dims']} of {describe(t['of'])}"
    if k == 'set':
        return f"set of {describe(t['of'])}"
    if k == 'subrange':
        return f"{t['lo']}..{t['hi']}"
    if k == 'enum':
        return '(' + ','.join(t['values']) + ')'
    return k


def param_kind(t, is_var):
    """How Lisa Pascal passes a parameter: 'var' (address), 'long', 'word', 'byte', 'addr' (large by value)."""
    if is_var:
        return 'var'
    if t['kind'] in ('record', 'array', 'string') and t['size'] > 4:
        return 'addr'
    if t['kind'] == 'string':
        return 'addr'
    if t['kind'] == 'set':
        return 'word' if t['size'] <= 2 else ('long' if t['size'] <= 4 else 'addr')
    if t['size'] == 1:
        return 'byte'
    if t['size'] == 2:
        return 'word'
    return 'long' if t['size'] <= 4 else 'addr'


def parse_routine(p, unit):
    kind = p.take().lower()
    name = p.take()
    params = []
    if p.peek() == '(':
        p.take()
        while p.peek() != ')':
            is_var = False
            if p.low() in ('var', 'const'):
                is_var = p.take().lower() == 'var'
            if p.low() in ('procedure', 'function'):     # procedural parameter
                pk = p.take().lower()
                pname = p.take()
                depth = 0
                while not (depth == 0 and p.peek() in (';', ')')):
                    tok = p.take()
                    depth += tok == '('
                    depth -= tok == ')'
                params.append({'name': pname, 'kind': 'proc', 'type': pk, 'size': 8})
            else:
                names = [p.take()]
                while p.peek() == ',':
                    p.take()
                    names.append(p.take())
                t = {'kind': 'untyped', 'size': 4, 'align': 2}
                univ = False
                if p.peek() == ':':
                    p.take()
                    if p.low() == 'univ':
                        p.take()
                        univ = True
                    t = parse_type(p, unit)
                for nm in names:
                    params.append({'name': nm, 'kind': param_kind(t, is_var or t['kind'] == 'untyped'),
                                   'type': describe(t), 'size': t['size'], 'tdesc': t, 'univ': univ,
                                   'var': is_var or t['kind'] == 'untyped'})
            if p.peek() == ';':
                p.take()
        p.take()
    result = None
    if kind == 'function' and p.peek() == ':':
        p.take()
        rt = parse_type(p, unit)
        result = {'type': describe(rt), 'size': rt['size'], 'kind': param_kind(rt, False), 'tdesc': rt}
    p.expect(';')
    while p.low() in ('external', 'forward', 'inline'):
        p.take()
        while p.peek() != ';':
            p.take()
        p.take()
    unit.routines.append({'name': name, 'link': name[:8].upper(), 'kind': kind,
                          'params': params, 'result': result})


def parse_unit(src, known, flags):
    text = strip_comments(src, flags)
    p = Parser(tokens(text))
    while p.low() and p.low() != 'unit':
        p.take()
    p.expect('unit')
    unit = Unit(p.take(), known)
    while p.low() != 'interface':
        p.take()
    p.take()
    section = None
    while p.low() and p.low() != 'implementation':
        tok = p.low()
        if tok == 'uses':
            while p.take() != ';':
                pass
        elif tok in ('const', 'type', 'var', 'label'):
            section = p.take().lower()
        elif tok in ('procedure', 'function'):
            parse_routine(p, unit)
        elif section == 'const':
            name = p.take()
            if p.peek() == ':':                 # typed constant: skip
                while p.take() != ';':
                    pass
                continue
            p.expect('=')
            unit.consts[name.lower()] = parse_const_expr(p, unit)
            unit.const_names[name.lower()] = name
            p.expect(';')
        elif section == 'type':
            name = p.take()
            p.expect('=')
            t = parse_type(p, unit)
            unit.types[name.lower()] = dict(t, declared=name)
            p.expect(';')
        elif section == 'var':                   # unit globals, in declaration order
            names = [p.take()]
            while p.peek() == ',':
                p.take()
                names.append(p.take())
            p.expect(':')
            t = parse_type(p, unit)
            for nm in names:
                unit.vars.append({'name': nm, 'size': t['size'], 'tdesc': t})
            p.expect(';')
        else:                                    # unexpected token: skip statement
            while p.take() not in (';', ''):
                pass
    return unit


def main():
    out, files = sys.argv[1], sys.argv[2:]
    known = {'consts': {}, 'types': {}, 'enum_values': {}}
    result = {}
    flags = {}
    for f in files:
        src = open(f, encoding='latin-1').read()
        try:
            u = parse_unit(src, known, flags)
        except (SyntaxError, IndexError, KeyError, TypeError) as e:
            print(f'{f}: {e}', file=sys.stderr)
            continue
        known['consts'].update(u.consts)
        known['types'].update(u.types)
        known['enum_values'].update(unit_enum_values(u))
        result[u.name] = {
            'consts': u.consts,
            'types': {t['declared']: {k: v for k, v in t.items() if k != 'declared'} for t in u.types.values()},
            'routines': u.routines,
            'vars': u.vars,
            'const_names': u.const_names,
            'order': [t['declared'] for t in u.types.values()],
        }
        print(f'{f}: unit {u.name}: {len(u.consts)} consts, {len(u.types)} types, '
              f'{len(u.routines)} routines', file=sys.stderr)
    json.dump(result, open(out, 'w'), indent=1, default=str)


if __name__ == '__main__':
    main()
