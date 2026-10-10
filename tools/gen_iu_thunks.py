#!/usr/bin/env python3
"""Generate register-saving thunks for the intrinsic-library routines declared
in include/lisa/*.h.

The Lisa libraries do not preserve every register a C compiler expects to
survive a call (PASLIB documents D3 and A2 as "registers used"; we have seen
D3 clobbered by SYS1LIB calls).  So C code does not IUJSR into a library
directly.  Each declaration

    pascal RESULT Name(params) LISA_IU(LINKNAME);

is a Pascal-convention call to the symbol NAME (Retro68 upper-cases pascal
names), and this tool emits a thunk for it that saves D2-D7/A2-A6, copies the
arguments and the function-result slot below the save area, IUJSRs to the
library's jump vector, copies the result back, restores the registers and
pops the arguments as a Pascal callee must.

One assembly file per routine, so an archive links only what is used.

usage: gen_iu_thunks.py data/entries.tsv out-dir header.h...
"""
import os
import re
import sys

BYTE = {'char', 'unsigned char', 'signed char', 'Boolean', 'bool', 'uint8_t', 'int8_t', 'GrafVerb',
        'VHSelect', 'FReply', 'FReason', 'FilerOp', 'Style'}
WORD = {'Integer', 'int16_t', 'uint16_t', 'short'}
LONG = {'LongInt', 'int32_t', 'uint32_t', 'long', 'Point', 'FilingCmd', 'ProcessId'}
SAVED = '%d2-%d7/%a2-%a6'
NSAVED = 44


def strip_comments(s):
    return re.sub(r'/\*.*?\*/', ' ', s, flags=re.S)


def slot_size(ctype, pointer_types):
    t = re.sub(r'\bconst\b', '', ctype).strip()
    if '*' in t:
        return 4
    base = re.sub(r'\s+\w+$', '', t).strip() if ' ' in t else t
    if base in pointer_types or base in LONG:
        return 4
    if base in BYTE or base in WORD:
        return 2
    raise ValueError(f'unknown parameter type {ctype!r}')


def main():
    entries, outdir, headers = sys.argv[1], sys.argv[2], sys.argv[3:]
    addr = {}
    for line in open(entries):
        if not line.startswith('#'):
            lib, seg, link, a = line.rstrip('\n').split('\t')
            addr[link.upper().replace('%', '_')] = int(a, 16)
    text = '\n'.join(strip_comments(open(h).read()) for h in headers)
    pointer_types = set(re.findall(r'typedef\s+[\w\s]+\*\s*(\w+)\s*;', text))
    for m in re.finditer(r'\}\s*([^;{}]+);', text):
        for part in m.group(1).split(','):
            if part.strip().startswith('*'):
                pointer_types.add(part.strip().lstrip('*').strip())
    for a, b in re.findall(r'typedef\s+(\w+)\s+(\w+)\s*;', text):  # aliases of pointer types
        if a in pointer_types:
            pointer_types.add(b)
    os.makedirs(outdir, exist_ok=True)
    count = 0
    for m in re.finditer(r'pascal\s+([\w\s\*]+?)\s*\b(\w+)\s*\(([^)]*)\)\s*LISA_IU\((\w+)\)\s*;', text):
        ret, name, params, trap = m.group(1).strip(), m.group(2), ' '.join(m.group(3).split()), m.group(4)
        plist = [] if params in ('', 'void') else [p.strip() for p in params.split(',')]
        n = sum(slot_size(p, pointer_types) for p in plist)
        r = 0 if ret == 'void' else slot_size(ret, pointer_types)
        a = addr[trap]
        label = name.upper()
        lines = [f'| {ret} {name}({params}) -> {trap} ${a:06X}: {n} bytes of arguments, {r} of result',
                 f'        .section .text.{label},"ax"', f'        .globl  {label}',
                 f'        .type   {label},@function', f'{label}:',
                 f'        movem.l {SAVED},-(%sp)']
        if n + r:
            lines += [f'        lea     {NSAVED + 4 + n + r}(%sp),%a0',
                      f'        moveq   #{(n + r) // 2 - 1},%d0',
                      '1:      move.w  -(%a0),-(%sp)',
                      '        dbf     %d0,1b']
        lines.append(f'        .short  0x{0xA000 | (a >> 16):04X}, 0x{a & 0xFFFF:04X}   | IUJSR')
        if r == 2:
            lines += ['        move.w  (%sp)+,%d0', f'        move.w  %d0,{NSAVED + 4 + n}(%sp)']
        elif r == 4:
            lines += ['        move.l  (%sp)+,%d0', f'        move.l  %d0,{NSAVED + 4 + n}(%sp)']
        lines += [f'        movem.l (%sp)+,{SAVED}', '        move.l  (%sp)+,%a0']
        if n:
            lines.append(f'        lea     {n}(%sp),%sp')
        lines += ['        jmp     (%a0)', '        .section .note.GNU-stack,"",@progbits', '']
        open(os.path.join(outdir, f'{label}.S'), 'w').write('\n'.join(lines))
        count += 1
    print(f'{outdir}: {count} thunks', file=sys.stderr)


if __name__ == '__main__':
    main()
