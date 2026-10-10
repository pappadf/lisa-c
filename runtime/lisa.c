#include "lisa.h"
#include "lisa_os.h"

/* Linker-script symbols (runtime/lisa.ld). */
extern char __data_load[], __data_start[], __data_end[], __bss_start[], __bss_end[];
extern char LISA_DATA_LDSN[];
extern void __lisa_exit_tail(void) __attribute__((noreturn));
extern void __libc_init_array(void) __attribute__((weak));   /* picolibc, if linked */

void lisa_write(const char *s)
{
    unsigned char buf[256];

    while (*s) {
        unsigned n = 0;
        while (*s && n < 255)
            buf[1 + n++] = (unsigned char)*s++;
        buf[0] = (unsigned char)n;
        lisa_write_pstr(buf);
    }
}

void lisa_puts(const char *s)
{
    lisa_write(s);
    lisa_writeln();
}

void lisa_write_hex(unsigned long v)
{
    char s[11] = "$";
    int i;

    for (i = 0; i < 8; i++, v <<= 4)
        s[1 + i] = "0123456789ABCDEF"[(v >> 28) & 15];
    s[9] = 0;
    lisa_write(s);
}

void lisa_fatal(const char *what, long code)
{
    lisa_write("lisa-c runtime: ");
    lisa_write(what);
    lisa_write(" error ");
    lisa_write_hex((unsigned long)code);
    lisa_writeln();
    __lisa_exit_tail();
}

/* Create the private data segment holding .data/.bss at its fixed LDSN
 * address, copy the initial .data image out of the code segment and clear
 * .bss.  Must not touch any global before the copy. */
void __lisa_init(void)
{
    static const unsigned char name[] = "\011LISACDATA";
    unsigned char path[256];
    unsigned long size = (unsigned long)(__bss_end - __data_start);
    int16_t err, refnum;
    void *segptr = 0;
    char *d;
    const char *s;
    unsigned i;

    if (size) {
        size = (size + 511) & ~511UL;
        for (i = 0; i <= name[0]; i++)
            path[i] = name[i];
        lisa_make_dataseg(&err, path, (int32_t)size, (int32_t)size, &refnum, &segptr,
                          (int16_t)(unsigned long)LISA_DATA_LDSN, LISA_DS_PRIVATE);
        if (err > 0)
            lisa_fatal("MAKE_DATASEG", err);
        if (segptr != (void *)__data_start)
            lisa_fatal("data segment address", (long)segptr);
    }
    for (d = __data_start, s = __data_load; d < __data_end; )
        *d++ = *s++;
    for (d = __bss_start; d < __bss_end; )
        *d++ = 0;
    if (__libc_init_array)
        __libc_init_array();
}

__attribute__((weak)) void __lisa_fini(int status)
{
    (void)status;
}
