/* Step 2 test: libgcc helpers (liblisagcc.a) on the 68000.
 * Inputs are volatile so the compiler cannot fold the operations away.
 * Expected integer values were computed exactly (Python, C semantics). */
#include <stdint.h>
#include "lisa.h"

static volatile int32_t a32 = 123456789, b32 = -9876;
static volatile uint32_t ua = 4000000000UL, ub = 65537, uc = 46341;
static volatile int64_t a64 = 1234567890123456789LL, b64 = -987654321LL;
static volatile uint64_t u64 = 18000000000000000000ULL, p64 = 1000000007ULL;
static volatile int sh = 13;
static volatile float fa = 3.5f, fb = -1.25f;
static volatile double da = 1234.5678, db = 0.001;

static int fails;

static void check(const char *what, int ok)
{
    if (!ok) {
        fails++;
        lisa_write("  FAIL ");
        lisa_puts(what);
    }
}

int main(void)
{
    check("mul32 (__mulsi3)", (int32_t)((uint32_t)a32 * (uint32_t)b32) == 511463900);
    check("umul32", ua * ub == 376121344UL);
    check("mul32 wrap", (int32_t)(uc * uc) == -2147479015L);
    check("div32 (__divsi3)", a32 / b32 == -12500);
    check("mod32 (__modsi3)", a32 % b32 == 6789);
    check("udiv32 (__udivsi3)", ua / ub == 61034);
    check("umod32 (__umodsi3)", ua % ub == 14742);

    check("mul64 (__muldi3)", (int64_t)((uint64_t)a64 * (uint64_t)b64) == 4036030183309260923LL);
    check("div64 (__divdi3)", a64 / b64 == -1249999988LL);
    check("mod64 (__moddi3)", a64 % b64 == 725308641LL);
    check("udiv64 (__udivdi3)", u64 / p64 == 17999999874ULL);
    check("umod64 (__umoddi3)", u64 % p64 == 882);
    check("shl64", (int64_t)((uint64_t)a64 << sh) == 4764403498523729920LL);
    check("shr64", (a64 >> sh) == 150704088149836LL);
    check("sar64", (-a64 >> sh) == -150704088149837LL);
    check("ushr64", (u64 >> sh) == 2197265625000000ULL);

    check("fadd", fa + fb == 2.25f);
    check("fmul", fa * fb == -4.375f);
    check("fdiv", fa / fb == -2.8f);
    check("dadd", da + db == 1234.5688);
    check("dmul", da * 2.0 == 2469.1356);
    check("ddiv", da / 0.5 == 2469.1356);
    check("d->int", (int32_t)(da * 100.0) == 123456);
    check("int->d", (double)a32 == 123456789.0);
    check("d->ll", (int64_t)(da * 1e12) == 1234567800000000LL);
    check("ll->d", (double)a64 == 1234567890123456789.0);
    check("f->d", (double)fb == -1.25);
    check("d->f", (float)da == 1234.5678f);
    check("dcmp", da > db && !(da < db) && da != db && db >= 0.001);

    lisa_puts(fails ? "arith: FAIL" : "arith: PASS (32/64-bit int, float, double)");
    return 0;
}
