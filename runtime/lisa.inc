| Shared definitions for the Lisa C runtime assembly files.
|
| Jump-vector addresses of PASLIB routines in the Workshop 3.0 / LOS 3.x
| intrinsic library IOSPASLIB.OBJ (EntryPoint records of segments PASLIB1 at
| $220000 = MMU 17 and PASIOLIB at $C00000 = MMU 96).

#define MAINSIZE   0x10          /* bytes of main-program globals below A5 */

#define PL_BEGIN   0x220204      /* %_BEGIN */
#define PL_INIT    0x220238      /* %_INIT  */
#define PL_TERM    0x220290      /* %_TERM  */
#define PL_END     0x220220      /* %_END   */
#define PL_HALT    0x220230      /* %_HALT  */
#define PL_W_STR   0xC00088      /* %W_STR  (file, @str, width) */
#define PL_W_C     0xC00078      /* %W_C    (file, ch, width)   */
#define PL_W_LN    0xC00080      /* %W_LN   (file)              */
#define PL_R_C     0xC00060      /* %R_C    (file) -> char (ST.B) */
#define PL_R_LN    0xC00068      /* %R_LN   (file)              */
#define PL_EOLN    0xC000AC      /* %_EOLN  (file) -> bool (ST.B) */

#define A5_INPUT   8             /* offset of INPUT file pointer from A5  */
#define A5_OUTPUT  12            /* offset of OUTPUT file pointer from A5 */

| IUJSR addr: A-line trap word pair $A0xx,$xxxx (JSR to intrinsic unit routine)
        .macro  IUJSR addr
        .short  0xA000 + (((\addr) >> 16) & 0xFF), (\addr) & 0xFFFF
        .endm
