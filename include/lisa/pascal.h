/* Calling Lisa intrinsic-library routines from C.
 *
 * Library routines are Pascal procedures: arguments are pushed left to
 * right, the callee pops them, function results are returned in a slot the
 * caller reserves on the stack.  VAR parameters and value parameters larger
 * than 4 bytes (records such as Rect, strings) are passed by address, so the
 * headers declare them as pointers.  Booleans, chars and small enumerations
 * occupy the high byte of a 16-bit stack word.
 *
 * A library routine is reached with the IUJSR instruction: the Line-A word
 * pair $A0xx,$xxxx whose low 24 bits are the routine's jump-vector address
 * (lisa/traps.h).  The libraries do not preserve all the registers C code
 * expects to survive a call (D3, A2, ...), so by default each declaration is
 * an ordinary pascal call to a generated thunk (liblisaiu.a,
 * tools/gen_iu_thunks.py) that saves the registers around the IUJSR.
 * Define LISA_IU_INLINE to emit the IUJSR inline instead (only safe where no
 * live value is held in D3-D7/A2-A4 across the call).
 *
 * Requires a compiler with Retro68's `pascal` attribute and inline-word
 * syntax.  With another compiler the declarations still parse (useful for
 * layout checks) but the calls do not work. */
#ifndef LISA_PASCAL_H
#define LISA_PASCAL_H

#include <stdbool.h>
#include <stdint.h>
#include "lisa/traps.h"

#if defined(pascal)                     /* Retro68: pascal = __attribute__((__pascal__)) */
#define LISA_HAVE_PASCAL 1
#ifdef LISA_IU_INLINE
#define LISA_IU(name) = { LISA_TRAP_##name }
#else
#define LISA_IU(name)
#endif
#else
#define LISA_HAVE_PASCAL 0
#define pascal
#define LISA_IU(name)
#endif

/* Global variables of intrinsic units (thePort, theHeap, menuFolder, ...)
 * live in each unit's data area.  A program reaches unit n through its
 * data-pointer table: the pointer is at $1FC + 4n (A5); the unit's variables
 * lie below it in declaration order, the first at -4.  Unit numbers are those
 * of the program's unit table (elf2lisa --tool: QuickDraw 6, Storage 5,
 * Events 10, ...). */
static inline char *lisa_unit_data(int unit)
{
    char *a5;
    __asm__("move.l %%a5,%0" : "=r"(a5));
    return *(char **)(a5 + 0x1FC + 4 * unit);
}

typedef int16_t Integer;                /* Pascal INTEGER */
typedef int32_t LongInt;                /* Pascal LONGINT */
typedef bool Boolean;                   /* Pascal BOOLEAN: one byte */
typedef unsigned char Str255[256];      /* Pascal string[255]: length byte + characters */
typedef unsigned char Str32[34];        /* string[32] (e_name), padded to even */

#endif
