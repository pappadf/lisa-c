#!/usr/bin/env python3
"""Generate C-callable stubs for Lisa OS system calls.

The OS calls are Pascal procedures entered through TRAP #1 (D0 = subcode,
D1 = number of parameters) with the parameters on the user stack in Pascal
order: pushed left to right, popped by the callee (see LIBPL/oslib.text and
OS/PROCASM.TEXT TRAP1).  The C prototypes are declared `pascal` (Retro68
GCC), so the compiler pushes the arguments in that layout; each stub then
only issues the trap, exactly like PASLIB's oslib entries, and does not
depend on any library's load address.

The trap subcodes are in SUBCODES below; the parameter types follow the
SYSCALL interface and are transcribed in SIGS.  `--check oslib.text` compares
the subcodes and parameter counts with a copy of PASLIB's oslib source (a
private check; that file is not needed to build).  Kinds:

  var   VAR parameter of any type     C: pointer        Pascal: 4-byte address
  long  longint value                 C: int32_t        Pascal: 4 bytes
  int   integer value                 C: int16_t        Pascal: 2 bytes
  byte  boolean/char/enum value       C: uint8_t        Pascal: word, value in high byte
  set   set of <=16 elements          C: uint16_t mask  Pascal: word, bit i = element i

usage: gen_syscalls.py [--check oslib.text] out.S out.h
"""
import re
import sys

# TRAP #1 subcode (D0) of each call
SUBCODES = {
    'make_file': 11, 'make_catalog': 13, 'kill_object': 15, 'rename_entry': 16, 'info': 18,
    'read_label': 23, 'write_label': 24, 'reset_catalog': 35, 'get_next_entry': 36,
    'open': 19, 'close_object': 20, 'read_data': 21, 'write_data': 22, 'device_control': 25,
    'truncate': 28, 'flush': 29, 'set_working_dir': 31, 'get_working_dir': 32, 'mount': 33, 'unmount': 34,
    'terminate_process': 51, 'info_process': 53, 'make_dataseg': 70, 'kill_dataseg': 71,
    'close_dataseg': 73, 'size_dataseg': 74, 'info_dataseg': 75, 'info_ldsn': 79,
    'declare_excep_hdl': 90, 'delay_time': 104, 'get_time': 105,
    'cdinfo': 140, 'cdmake': 141, 'cdkill': 142, 'osbootvol': 147,
}

# name: [(kind, param name, C type)]  -- the SYSCALL interface
SIGS = {
    'make_file':     [('var', 'ecode', 'int16_t *'), ('var', 'path', 'const unsigned char *'), ('int', 'label_size', 'int16_t')],
    'make_catalog':  [('var', 'ecode', 'int16_t *'), ('var', 'path', 'const unsigned char *'), ('int', 'label_size', 'int16_t')],
    'kill_object':   [('var', 'ecode', 'int16_t *'), ('var', 'path', 'const unsigned char *')],
    'rename_entry':  [('var', 'ecode', 'int16_t *'), ('var', 'path', 'const unsigned char *'), ('var', 'newname', 'const unsigned char *')],
    'info':          [('var', 'ecode', 'int16_t *'), ('int', 'refnum', 'int16_t'), ('var', 'refinfo', 'void *')],
    'open':          [('var', 'ecode', 'int16_t *'), ('var', 'path', 'const unsigned char *'), ('var', 'refnum', 'int16_t *'), ('set', 'manip', 'uint16_t')],
    'close_object':  [('var', 'ecode', 'int16_t *'), ('int', 'refnum', 'int16_t')],
    'read_data':     [('var', 'ecode', 'int16_t *'), ('int', 'refnum', 'int16_t'), ('long', 'data_addr', 'void *'),
                      ('long', 'count', 'int32_t'), ('var', 'actual', 'int32_t *'), ('byte', 'mode', 'uint8_t'), ('long', 'offset', 'int32_t')],
    'write_data':    [('var', 'ecode', 'int16_t *'), ('int', 'refnum', 'int16_t'), ('long', 'data_addr', 'const void *'),
                      ('long', 'count', 'int32_t'), ('var', 'actual', 'int32_t *'), ('byte', 'mode', 'uint8_t'), ('long', 'offset', 'int32_t')],
    'device_control': [('var', 'ecode', 'int16_t *'), ('var', 'path', 'const unsigned char *'), ('var', 'cparm', 'void *')],
    # file labels (the bytes kept with a file outside its data; up to 128)
    'read_label':    [('var', 'ecode', 'int16_t *'), ('var', 'path', 'const unsigned char *'), ('long', 'data_addr', 'void *'),
                      ('long', 'count', 'int32_t'), ('var', 'actual', 'int32_t *')],
    'write_label':   [('var', 'ecode', 'int16_t *'), ('var', 'path', 'const unsigned char *'), ('long', 'data_addr', 'const void *'),
                      ('long', 'count', 'int32_t'), ('var', 'actual', 'int32_t *')],
    # listing a volume: reset_catalog("-vol"), then get_next_entry(prefix, entry)
    # returns the names that begin with prefix, one per call, until error 848
    'reset_catalog': [('var', 'ecode', 'int16_t *'), ('var', 'path', 'const unsigned char *')],
    'get_next_entry': [('var', 'ecode', 'int16_t *'), ('var', 'prefix', 'const unsigned char *'), ('var', 'entry', 'unsigned char *')],
    'truncate':      [('var', 'ecode', 'int16_t *'), ('int', 'refnum', 'int16_t')],
    'flush':         [('var', 'ecode', 'int16_t *'), ('int', 'refnum', 'int16_t')],
    'set_working_dir': [('var', 'ecode', 'int16_t *'), ('var', 'path', 'const unsigned char *')],
    'get_working_dir': [('var', 'ecode', 'int16_t *'), ('var', 'path', 'unsigned char *')],
    # mount the volume (or sequential device) at devname; vname returns its volume name
    'mount':         [('var', 'ecode', 'int16_t *'), ('var', 'vname', 'unsigned char *'),
                      ('var', 'password', 'const unsigned char *'), ('var', 'devname', 'const unsigned char *')],
    'unmount':       [('var', 'ecode', 'int16_t *'), ('var', 'vname', 'const unsigned char *')],
    'declare_excep_hdl': [('var', 'errnum', 'int16_t *'), ('var', 'excep_name', 'const unsigned char *'), ('long', 'entry_point', 'void *')],
    'info_process':  [('var', 'errnum', 'int16_t *'), ('long', 'proc_id', 'int32_t'), ('var', 'proc_info', 'void *')],
    'terminate_process': [('var', 'errnum', 'int16_t *'), ('long', 'event_ptr', 'void *')],
    'make_dataseg':  [('var', 'errnum', 'int16_t *'), ('var', 'segname', 'const unsigned char *'), ('long', 'mem_size', 'int32_t'),
                      ('long', 'disc_size', 'int32_t'), ('var', 'refnum', 'int16_t *'), ('var', 'segptr', 'void **'),
                      ('int', 'ldsn', 'int16_t'), ('byte', 'dstype', 'uint8_t')],
    'kill_dataseg':  [('var', 'errnum', 'int16_t *'), ('var', 'segname', 'const unsigned char *')],
    'close_dataseg': [('var', 'errnum', 'int16_t *'), ('int', 'refnum', 'int16_t')],
    'size_dataseg':  [('var', 'errnum', 'int16_t *'), ('int', 'refnum', 'int16_t'), ('long', 'deltamemsize', 'int32_t'),
                      ('var', 'newmemsize', 'int32_t *'), ('long', 'deltadiscsize', 'int32_t'), ('var', 'newdiscsize', 'int32_t *')],
    'info_dataseg':  [('var', 'errnum', 'int16_t *'), ('int', 'refnum', 'int16_t'), ('var', 'dsinfo', 'void *')],
    'info_ldsn':     [('var', 'errnum', 'int16_t *'), ('int', 'ldsn', 'int16_t'), ('var', 'refnum', 'int16_t *')],
    'delay_time':    [('var', 'errnum', 'int16_t *'), ('var', 'interval', 'const void *'), ('var', 'clktime', 'const void *')],  # records > 4 bytes: by address
    'get_time':      [('var', 'errnum', 'int16_t *'), ('var', 'gmt_time', 'void *')],
    # configurable drivers: the_pos is a cd_position (CD_POS), the info a cd_infobuf (lisa/ostypes.h)
    'cdinfo':        [('var', 'error', 'int16_t *'), ('long', 'the_pos', 'uint32_t'), ('var', 'the_info', 'void *')],
    'cdmake':        [('var', 'error', 'int16_t *'), ('long', 'the_pos', 'uint32_t'), ('var', 'this_info', 'const void *')],
    'cdkill':        [('var', 'error', 'int16_t *'), ('long', 'the_pos', 'uint32_t')],
    'osbootvol':     [('var', 'error', 'int16_t *'), ('var', 'volname', 'unsigned char *')],
}

# Declared in lisa_os.h with the calls (cd_infobuf itself is in lisa/ostypes.h)
TYPES = '''/* cd_position (lisa/ostypes.h: slot, chan, dev bytes) is word-sized and so passed
   by value as a long; CD_POS builds it.  Positions are 1-based: slot 10 is the
   built-in serial ports, chan 1 = Serial A, chan 2 = Serial B; 0 = none. */
#define CD_POS(slot, chan, dev) \\
    (((uint32_t)(uint8_t)(slot) << 24) | ((uint32_t)(uint8_t)(chan) << 16) | ((uint32_t)(uint8_t)(dev) << 8))
'''


def cdecl(params):
    return ', '.join(c + ('' if c.endswith('*') else ' ') + p for _, p, c in params)


def parse_oslib(path):
    table, label = {}, None
    for line in open(path, encoding='latin-1'):
        m = re.match(r'^([a-z_%][a-z0-9_]*)\s*(;.*)?$', line, re.I)
        if m:
            label = m.group(1).lower()
        m = re.search(r'gentrap\s+#(\d+)\s*,\s*#(\d+)', line, re.I)
        if m and label and label not in table:
            table[label] = (int(m.group(1)), int(m.group(2)))
    return table


PASCAL_SIZE = {'var': 4, 'long': 4, 'int': 2, 'set': 2, 'byte': 2}
SAVED = '%d2-%d7/%a2-%a6'      # the OS calls do not preserve all of these (A2, D3 seen clobbered)
NSAVED = 44


def gen_stub(name, params, subcode):
    """Called as a Pascal procedure: the compiler (pascal attribute) has pushed
    the arguments in Pascal layout and JSRed here.  The OS calls clobber
    registers C code expects preserved, so the stub saves them, copies the
    arguments below the save area, enters the OS routine through the trap
    (which pops the copy), restores the registers and pops the original
    arguments -- a Pascal callee's duty."""
    label = f'LISA_{name.upper()}'          # Retro68 upper-cases pascal names
    nbytes = sum(PASCAL_SIZE[k] for k, _, _ in params)
    out = [f'| pascal void lisa_{name}({cdecl(params)})  -- {nbytes} bytes of arguments',
           f'        .globl  {label}', f'        .type   {label},@function', f'{label}:',
           f'        movem.l {SAVED},-(%sp)']
    if nbytes:
        out += [f'        lea     {NSAVED + 4 + nbytes}(%sp),%a0      | end of the arguments',
                f'        moveq   #{nbytes // 2 - 1},%d0',
                '1:      move.w  -(%a0),-(%sp)',
                '        dbf     %d0,1b']
    out += ['        jsr     2f',
            f'        movem.l (%sp)+,{SAVED}',
            '        move.l  (%sp)+,%a0',
            f'        lea     {nbytes}(%sp),%sp' if nbytes else '',
            '        jmp     (%a0)',
            '2:      tst.w   -6144(%sp)              | force stack expansion, as oslib does',
            f'        move.w  #{subcode},%d0', f'        move.w  #{len(params)},%d1', '        trap    #1', '']
    return '\n'.join(l for l in out if l != '')


def main():
    args = sys.argv[1:]
    if args[:1] == ['--check']:
        table = parse_oslib(args[1])
        for name, params in SIGS.items():
            if table.get(name) != (SUBCODES[name], len(params)):
                sys.exit(f'{name}: oslib says {table.get(name)}, we have {(SUBCODES[name], len(params))}')
        args = args[2:]
    out_s, out_h = args
    asm = ['| Generated by tools/gen_syscalls.py -- do not edit.', '        .text', '']
    hdr = ['/* Generated by tools/gen_syscalls.py -- do not edit. */',
           '/* Lisa OS system calls (Pascal procedures via TRAP #1). Pathnames are Pascal strings. */',
           '#ifndef LISA_OS_H', '#define LISA_OS_H', '#include <stdint.h>',
           '#if !defined(pascal)', '#error "lisa_os.h needs a compiler with the pascal attribute (Retro68 GCC)"', '#endif', '']
    hdr.append(TYPES)
    for name, params in SIGS.items():
        asm.append(gen_stub(name, params, SUBCODES[name]))
        hdr.append(f'pascal void lisa_{name}({cdecl(params)});')
    asm.append('        .section .note.GNU-stack,"",@progbits')
    hdr += ['', '#endif', '']
    open(out_s, 'w').write('\n'.join(asm) + '\n')
    open(out_h, 'w').write('\n'.join(hdr))


if __name__ == '__main__':
    main()
