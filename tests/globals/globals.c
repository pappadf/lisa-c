/* Step 1 test: writable .data and .bss in the LDSN data segment. */
#include "lisa.h"

static int counter = 41;                 /* .data */
int table[4] = { 10, 20, 30, 40 };        /* .data */
static char buf[64];                      /* .bss  */
static long zeros[32];                    /* .bss  */

static int check(const char *what, int ok)
{
    lisa_write(ok ? "  ok   " : "  FAIL ");
    lisa_puts(what);
    return ok;
}

int main(void)
{
    int i, all = 1;
    long sum = 0;

    lisa_puts((unsigned long)&counter >> 17 == 107 && (unsigned long)buf >> 17 == 107
                  ? "globals: .data and .bss in the LDSN 1 data segment"
                  : "globals: data NOT in the LDSN 1 data segment");

    all &= check("initialised int", counter == 41);
    counter++;
    all &= check("int written", counter == 42);

    for (i = 0; i < 4; i++)
        sum += table[i];
    all &= check("initialised array", sum == 100);
    table[2] = 300;
    all &= check("array written", table[2] == 300);

    for (i = 0; i < 32; i++)
        if (zeros[i] != 0)
            sum = -1;
    all &= check("bss zeroed", sum == 100 && buf[0] == 0 && buf[63] == 0);

    for (i = 0; i < 5; i++)
        buf[i] = "Lisa!"[i];
    all &= check("bss written", buf[0] == 'L' && buf[4] == '!');

    lisa_puts(all ? "globals: PASS" : "globals: FAIL");
    return 0;
}
