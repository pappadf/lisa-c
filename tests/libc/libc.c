/* Step 4 test: picolibc on the Lisa -- stdio to the console, malloc,
 * strings, qsort, strtod, libm, and file I/O through the OS. */
#include <errno.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static int fails;

static void check(const char *what, int ok)
{
    if (!ok) {
        fails++;
        printf("  FAIL %s\n", what);
    }
}

static int cmp_int(const void *a, const void *b)
{
    return *(const int *)a - *(const int *)b;
}

int main(void)
{
    char buf[128];
    int i;

    printf("printf: %d %u %x %ld %lld %s %c %5.2f %e\n",
           -42, 4000000000U, 0xBEEF, 123456789L, -1234567890123LL, "str", 'L', 3.14159, 6.02e23);

    snprintf(buf, sizeof buf, "%08.3f|%-6s|%+d", 2.5, "ab", 7);
    check("snprintf", strcmp(buf, "0002.500|ab    |+7") == 0);

    /* malloc: small blocks, a large block, realloc, free */
    {
        char *p = malloc(100), *q = malloc(40000);
        long sum = 0;
        check("malloc", p && q);
        memset(q, 1, 40000);
        for (i = 0; i < 40000; i++)
            sum += q[i];
        check("malloc 40K", sum == 40000);
        strcpy(p, "hello");
        p = realloc(p, 5000);
        check("realloc", p && strcmp(p, "hello") == 0);
        free(q);
        free(p);
        q = malloc(200000);
        check("malloc 200K", q != NULL);
        if (q)
            q[199999] = 1;
        free(q);
    }

    {
        int v[8] = { 5, 3, 9, 1, 7, 2, 8, 4 };
        qsort(v, 8, sizeof v[0], cmp_int);
        check("qsort", v[0] == 1 && v[7] == 9 && v[3] == 4);
    }

    check("strtod", fabs(strtod("1234.5e-2", NULL) - 12.345) < 1e-12);
    check("strtol", strtol("-0x7f", NULL, 16) == -127);
    check("sqrt", fabs(sqrt(2.0) - 1.4142135623730951) < 1e-15);
    check("sin", fabs(sin(M_PI / 6) - 0.5) < 1e-12);

    /* file I/O on the Workshop's working volume */
    {
        FILE *f = fopen("lisactest", "w");
        long size;
        check("fopen w", f != NULL);
        if (f) {
            for (i = 0; i < 100; i++)
                fprintf(f, "line %d\n", i);
            fclose(f);
        }
        f = fopen("lisactest", "r");
        check("fopen r", f != NULL);
        if (f) {
            fgets(buf, sizeof buf, f);
            check("fgets", strcmp(buf, "line 0\n") == 0);
            fseek(f, 0, SEEK_END);
            size = ftell(f);
            check("ftell", size == 10 * 7 + 90 * 8);
            fseek(f, -8, SEEK_END);
            fgets(buf, sizeof buf, f);
            check("fseek", strcmp(buf, "line 99\n") == 0);
            fclose(f);
        }
        f = fopen("lisactest", "a");
        if (f) {
            fputs("tail\n", f);
            fclose(f);
        }
        f = fopen("lisactest", "r");
        if (f) {
            fseek(f, -5, SEEK_END);
            fgets(buf, sizeof buf, f);
            check("append", strcmp(buf, "tail\n") == 0);
            fclose(f);
        }
        check("remove", remove("lisactest") == 0);
        errno = 0;
        check("ENOENT", fopen("lisactest", "r") == NULL && errno == ENOENT);
    }

    {
        struct timespec ts = { 5, 0 };
        time_t t0 = time(NULL);
        check("nanosleep", nanosleep(&ts, NULL) == 0);
        check("time advances", time(NULL) - t0 >= 1);
    }

    {
        time_t t = time(NULL);
        struct tm *tm = gmtime(&t);
        printf("time: %04d-%02d-%02d %02d:%02d\n", tm->tm_year + 1900, tm->tm_mon + 1,
               tm->tm_mday, tm->tm_hour, tm->tm_min);
    }

    printf(fails ? "libc: FAIL\n" : "libc: PASS (stdio, malloc, string, qsort, math, files)\n");
    return 0;
}
