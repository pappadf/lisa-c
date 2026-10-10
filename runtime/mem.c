/* GCC may emit calls to these even in freestanding code (struct copies,
 * array initialisers). Weak, so a C library's versions win when linked. */
#include <stddef.h>

__attribute__((weak)) void *memcpy(void *dst, const void *src, size_t n)
{
    char *d = dst;
    const char *s = src;
    while (n--)
        *d++ = *s++;
    return dst;
}

__attribute__((weak)) void *memmove(void *dst, const void *src, size_t n)
{
    char *d = dst;
    const char *s = src;
    if (d < s)
        while (n--)
            *d++ = *s++;
    else
        while (n--)
            d[n] = s[n];
    return dst;
}

__attribute__((weak)) void *memset(void *dst, int c, size_t n)
{
    char *d = dst;
    while (n--)
        *d++ = (char)c;
    return dst;
}

__attribute__((weak)) int memcmp(const void *a, const void *b, size_t n)
{
    const unsigned char *p = a, *q = b;
    for (; n--; p++, q++)
        if (*p != *q)
            return *p - *q;
    return 0;
}
