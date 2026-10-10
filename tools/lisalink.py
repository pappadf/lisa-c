#!/usr/bin/env python3
"""Link a Lisa program into up to 16 code segments of <= 32 KB each.

Pass 1 links everything into one unlimited .text to learn the size of every
input section (all code is compiled with -ffunction-sections).  The sections
are then packed, in link order, into segments SEG1..SEGn mapped at MMU n
(n * 128K, code at +8 after the CodeBlock header).  SEG1 always starts with
crt0 and also carries the initial image of the data segment (.data plus
.rodata, which live in RAM so that code never reads another code segment).
Pass 2 links with a generated script and --emit-relocs; elf2lisa.py then
routes cross-segment code references through the jump table.

usage: lisalink.py out.elf [gcc link args...]
"""
import os
import re
import subprocess
import sys

CROSS = os.environ.get('LISA_CROSS', 'm68k-apple-macos-')
CC = CROSS + 'gcc'
SEG_LIMIT = 32767 - 8 - 64      # SizeUnpacked is a 16-bit integer incl. the 8-byte header; margin
MAX_SEGS = 16                   # MMU 1..16 (17 = PASLIB1)
DATA_BASE = 0xD60000            # LDSN 1
DATA_LDSN = 1
HEAP_BASE = 0xE00000            # LDSN 6
HEAP_LDSN = 6

COMMON = f"""ENTRY(_start)
LISA_DATA_BASE = {DATA_BASE:#x};
LISA_DATA_LDSN = {DATA_LDSN};
LISA_HEAP_BASE = {HEAP_BASE:#x};
LISA_HEAP_LDSN = {HEAP_LDSN};
"""

DATA_SECTIONS = """
    .data LISA_DATA_BASE : AT(__data_load) {{
        __data_start = .;
        *(.rodata .rodata.*)
        . = ALIGN(4);
        __preinit_array_start = .;
        KEEP(*(.preinit_array))
        __preinit_array_end = .;
        __bothinit_array_start = .;
        __init_array_start = .;
        KEEP(*(SORT_BY_INIT_PRIORITY(.init_array.*)))
        KEEP(*(.init_array .ctors))
        __init_array_end = .;
        __bothinit_array_end = .;
        __fini_array_start = .;
        KEEP(*(SORT_BY_INIT_PRIORITY(.fini_array.*)))
        KEEP(*(.fini_array .dtors))
        __fini_array_end = .;
        *(.data .data.*) *(.sdata .sdata.*)
        . = ALIGN(4);
        __data_end = .;
    }}
    .bss (NOLOAD) : {{
        __bss_start = .;
        *(.bss .bss.*) *(.sbss .sbss.*) *(COMMON)
        . = ALIGN(4);
        __bss_end = .;
    }}
    /DISCARD/ : {{ *(.comment) *(.note*) *(.eh_frame*) *(.debug*) }}
    ASSERT(__bss_end - LISA_DATA_BASE <= 5 * 0x20000, "data segment exceeds LDSN 1..5")
"""


def pass1_script():
    return COMMON + """SECTIONS
{
    . = 0x20008;
    .text : { KEEP(*(.text.entry)) *(.text .text.*) }
    __data_load = .;
""" + DATA_SECTIONS.format() + "}\n"


def parse_map(path):
    """Return [(section, file, size)] for input sections of output section .text."""
    out, in_text, pending = [], False, None
    for line in open(path):
        if re.match(r'^\.text\s', line) or line.startswith('.text\n'):
            in_text = True
            continue
        if in_text and re.match(r'^\S', line) and not line.startswith(' '):
            if not line.startswith('.text'):
                in_text = False
            continue
        if not in_text:
            continue
        m = re.match(r'^ (\.text\S*)\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)\s+(\S+)', line)
        if m:
            out.append((m.group(1), m.group(4), int(m.group(3), 16)))
            pending = None
            continue
        m = re.match(r'^ (\.text\S*)\s*$', line)
        if m:
            pending = m.group(1)
            continue
        m = re.match(r'^\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)\s+(\S+)', line)
        if m and pending:
            out.append((pending, m.group(3), int(m.group(2), 16)))
            pending = None
    return out


def section_size(elf, name):
    r = subprocess.run([CROSS + 'objdump', '-h', elf], capture_output=True, text=True, check=True)
    for line in r.stdout.splitlines():
        f = line.split()
        if len(f) > 2 and f[1] == name:
            return int(f[2], 16)
    return 0


def pattern(file, sect):
    m = re.match(r'(.*)\((.*)\)$', file)        # lib.a(member.o)
    if m:
        return f'*{os.path.basename(m.group(1))}:{m.group(2)}({sect})'
    return f'{file}({sect})'


def real_ld_flags(tmp):
    """Retro68's `ld` is Elf2Mac, a wrapper that turns the output into a Mac
    application.  We want the plain ELF, so point gcc (-B) at a directory
    whose `ld` is the real linker (`ld.real`), when there is one."""
    r = subprocess.run([CC, '-print-prog-name=ld.real'], capture_output=True, text=True)
    real = r.stdout.strip()
    if r.returncode or not os.path.isabs(real) or not os.path.exists(real):
        return []
    d = os.path.join(os.path.dirname(tmp) or '.', 'ld-real')
    os.makedirs(d, exist_ok=True)
    link = os.path.join(d, 'ld')
    if not os.path.islink(link) or os.readlink(link) != real:
        if os.path.lexists(link):
            os.remove(link)
        os.symlink(real, link)
    return ['-B' + d + '/']


def main():
    out, args = sys.argv[1], sys.argv[2:]
    tmp = out[:-4] if out.endswith('.elf') else out
    common = ['-nostdlib', '-static', '-Wl,--no-warn-rwx-segments', '-Wl,--build-id=none',
              '-Wl,--no-warn-execstack',
              # Retro68's driver passes `-elf2mac` for its wrapper; the real ld
              # reads that as "-e lf2mac".  Set the entry point explicitly.
              '-Wl,-e,_start'] + real_ld_flags(tmp)

    open(tmp + '.pass1.ld', 'w').write(pass1_script())
    subprocess.run([CC] + common + ['-T', tmp + '.pass1.ld', f'-Wl,-Map={tmp}.pass1.map', '-o',
                                    tmp + '.pass1.elf'] + args, check=True)
    sections = parse_map(tmp + '.pass1.map')
    image = section_size(tmp + '.pass1.elf', '.data')

    segs = [[]]
    used = [image + 16]
    for sect, file, size in sections:
        size = (size + 3) & ~3
        if size > SEG_LIMIT:
            sys.exit(f'{sect} ({file}) is {size} bytes: larger than a segment')
        if used[-1] + size > SEG_LIMIT and segs[-1]:
            segs.append([])
            used.append(0)
        segs[-1].append(pattern(file, sect))
        used[-1] += size
    if len(segs) > MAX_SEGS:
        sys.exit(f'program needs {len(segs)} segments; at most {MAX_SEGS} supported')

    lines = [COMMON, 'SECTIONS\n{']
    for i, pats in enumerate(segs, start=1):
        lines.append(f'    SEG{i} {i * 0x20000 + 8:#x} : {{')
        if i == 1:
            lines.append('        KEEP(*(.text.entry))')
        lines += [f'        {p}' for p in pats if not p.endswith('(.text.entry)')]
        if i == len(segs):
            lines.append('        *(.text .text.*)')            # anything unplanned
        lines.append('        . = ALIGN(4);')
        if i == 1:
            lines.append('        __data_load = .;')
        lines.append('    }')
        lines.append(f'    ASSERT(SIZEOF(SEG{i}) + (({i} == 1) ? SIZEOF(.data) : 0) <= {SEG_LIMIT},'
                     f' "segment {i} exceeds 32 KB")')
    lines.append(DATA_SECTIONS.format())
    lines.append('}')
    open(tmp + '.ld', 'w').write('\n'.join(lines) + '\n')
    subprocess.run([CC] + common + ['-T', tmp + '.ld', '-Wl,--emit-relocs', f'-Wl,-Map={tmp}.map',
                                    '-o', out] + args, check=True)
    print(f'{out}: {len(segs)} segment(s), data image {image} bytes', file=sys.stderr)


if __name__ == '__main__':
    main()
