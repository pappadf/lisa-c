/* POSIX system-call layer for picolibc on the Lisa Office System.
 *
 * fd 0/1/2 are the Workshop console (PASLIB INPUT/OUTPUT); other fds are OS
 * file refnums.  File positions are tracked here and every transfer uses
 * absolute mode, so lseek is free.  The heap is a private data segment bound
 * to LISA_HEAP_LDSN, grown with SIZE_DATASEG.
 *
 * Layout facts used below were measured on the emulated Lisa
 * (measured with a probe program): the open-mode set is a word with bit i = element i,
 * fs_info.size is at byte 300 of the INFO record, a read past LEOF returns
 * error 848 with the partial count. */
#include <errno.h>
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>
#include "lisa.h"
#include "lisa_os.h"

extern char LISA_HEAP_BASE[], LISA_HEAP_LDSN[];
extern void __lisa_exit_tail(void) __attribute__((noreturn));

/* Lisa OS constants (libpl-syscall.text) */
enum { M_DREAD = 1, M_DWRITE = 2, M_APPEND = 4, M_PRIVATE = 8 };       /* mset bits */
enum { IO_ABSOLUTE = 0, IO_RELATIVE = 1, IO_SEQUENTIAL = 2 };          /* iomode */
#define INFO_SIZE_OFFSET 300

#define MAX_FD 16
static struct {
    int16_t refnum;
    char used;
    char append;
    long pos;
} fds[MAX_FD];

/* ---- errors ---------------------------------------------------------- */

int lisa_errno(int lisa_err)
{
    switch (lisa_err) {
    case 888: case 894: case 948: case 972:     return ENOENT;
    case 890:                                    return EEXIST;
    case 921: case 926: case 941: case 946: case 971: return ENOENT;
    case 892: case 895:                          return EINVAL;
    case 854: case 855: case 882: case 891:      return ENOSPC;
    case 873: case 949: case 950: case 951:      return EBUSY;
    case 952: case 954: case 961: case 968: case 974: case 977: case 981: return EBADF;
    case 955: case 962:                          return EACCES;
    default:                                     return EIO;
    }
}

int lisa_last_error;        /* last Lisa OS error number seen by this layer */

static int fail(int lisa_err)
{
    lisa_last_error = lisa_err;
    errno = lisa_errno(lisa_err);
    return -1;
}

static void to_pstr(unsigned char *p, const char *s)
{
    size_t n = strlen(s);
    if (n > 255)
        n = 255;
    p[0] = (unsigned char)n;
    memcpy(p + 1, s, n);
}

static int file_fd(int fd)
{
    if (fd < 3 || fd >= MAX_FD || !fds[fd].used) {
        errno = EBADF;
        return 0;
    }
    return 1;
}

static long file_size(int16_t refnum, int16_t *err)
{
    static unsigned char info[1024];   /* fs_info is ~400 bytes */
    long size;

    lisa_info(err, refnum, info);
    memcpy(&size, info + INFO_SIZE_OFFSET, 4);
    return size;
}

/* ---- console (PASLIB) ------------------------------------------------ */

static ssize_t console_write(const char *buf, size_t n)
{
    unsigned char p[256];
    size_t i = 0;

    while (i < n) {
        size_t k = 0;
        while (i < n && buf[i] != '\n' && k < 255)
            p[1 + k++] = (unsigned char)buf[i++];
        if (k) {
            p[0] = (unsigned char)k;
            lisa_write_pstr(p);
        }
        if (i < n && buf[i] == '\n') {
            lisa_writeln();
            i++;
        }
    }
    return (ssize_t)n;
}

static ssize_t console_read(char *buf, size_t n)
{
    size_t i = 0;

    /* PASLIB returns the end of line as a space and sets EOLN when it is
     * read (Pascal semantics), so EOLN is tested after each character. */
    while (i < n) {
        int c = lisa_read_char();
        if (lisa_eoln()) {
            lisa_readln();          /* clear EOLN */
            buf[i++] = '\n';
            break;
        }
        buf[i++] = (char)c;
    }
    return (ssize_t)i;
}

/* ---- file system ----------------------------------------------------- */

int open(const char *path, int flags, ...)
{
    unsigned char p[256];
    int16_t err, refnum;
    uint16_t manip;
    int fd;

    for (fd = 3; fd < MAX_FD && fds[fd].used; fd++)
        ;
    if (fd == MAX_FD) {
        errno = EMFILE;
        return -1;
    }
    to_pstr(p, path);
    if (flags & O_CREAT) {
        lisa_make_file(&err, p, 0);
        if (err == 890 && (flags & O_EXCL))
            return fail(err);
        if (err > 0 && err != 890)
            return fail(err);
    }
    switch (flags & O_ACCMODE) {
    case O_RDONLY: manip = M_DREAD; break;
    case O_WRONLY: manip = M_DWRITE; break;
    default:       manip = M_DREAD | M_DWRITE; break;
    }
    lisa_open(&err, p, &refnum, manip);
    if (err > 0)
        return fail(err);
    if (flags & O_TRUNC) {
        lisa_truncate(&err, refnum);       /* at the file mark, which is 0 */
        if (err > 0 && err != 982) {       /* 982: empty file, nothing allocated */
            int16_t e2;
            lisa_close_object(&e2, refnum);
            return fail(err);
        }
    }
    fds[fd].used = 1;
    fds[fd].refnum = refnum;
    fds[fd].append = (flags & O_APPEND) != 0;
    fds[fd].pos = 0;
    return fd;
}

int close(int fd)
{
    int16_t err;

    if (fd >= 0 && fd < 3)
        return 0;
    if (!file_fd(fd))
        return -1;
    fds[fd].used = 0;
    lisa_close_object(&err, fds[fd].refnum);
    return err > 0 ? fail(err) : 0;
}

ssize_t read(int fd, void *buf, size_t n)
{
    int16_t err;
    int32_t actual = 0;

    if (fd == 0)
        return console_read(buf, n);
    if (!file_fd(fd))
        return -1;
    if (n == 0)
        return 0;
    lisa_read_data(&err, fds[fd].refnum, buf, (int32_t)n, &actual, IO_ABSOLUTE, fds[fd].pos);
    if (err > 0 && err != 848 && err != 881 && err != 883 && err != 956 && err != 963)
        return fail(err);                  /* the others are "end of file" */
    fds[fd].pos += actual;
    return actual;
}

ssize_t write(int fd, const void *buf, size_t n)
{
    int16_t err;
    int32_t actual = 0;

    if (fd == 1 || fd == 2)
        return console_write(buf, n);
    if (!file_fd(fd))
        return -1;
    if (n == 0)
        return 0;
    if (fds[fd].append) {
        fds[fd].pos = file_size(fds[fd].refnum, &err);
        if (err > 0)
            return fail(err);
    }
    lisa_write_data(&err, fds[fd].refnum, buf, (int32_t)n, &actual, IO_ABSOLUTE, fds[fd].pos);
    if (err > 0)
        return fail(err);
    fds[fd].pos += actual;
    return actual;
}

off_t lseek(int fd, off_t off, int whence)
{
    int16_t err;
    long base;

    if (fd < 3) {
        errno = ESPIPE;
        return -1;
    }
    if (!file_fd(fd))
        return -1;
    switch (whence) {
    case SEEK_SET: base = 0; break;
    case SEEK_CUR: base = fds[fd].pos; break;
    case SEEK_END:
        base = file_size(fds[fd].refnum, &err);
        if (err > 0)
            return fail(err);
        break;
    default:
        errno = EINVAL;
        return -1;
    }
    if (base + off < 0) {
        errno = EINVAL;
        return -1;
    }
    fds[fd].pos = base + off;
    return fds[fd].pos;
}

int fstat(int fd, struct stat *st)
{
    int16_t err;

    memset(st, 0, sizeof *st);
    if (fd >= 0 && fd < 3) {
        st->st_mode = S_IFCHR | 0666;
        return 0;
    }
    if (!file_fd(fd))
        return -1;
    st->st_mode = S_IFREG | 0666;
    st->st_size = file_size(fds[fd].refnum, &err);
    st->st_blksize = 512;
    return err > 0 ? fail(err) : 0;
}

int stat(const char *path, struct stat *st)
{
    int fd = open(path, O_RDONLY), r;

    if (fd < 0)
        return -1;
    r = fstat(fd, st);
    close(fd);
    return r;
}

int unlink(const char *path)
{
    unsigned char p[256];
    int16_t err;

    to_pstr(p, path);
    lisa_kill_object(&err, p);
    return err > 0 ? fail(err) : 0;
}

int isatty(int fd)
{
    if (fd >= 0 && fd < 3)
        return 1;
    errno = ENOTTY;
    return 0;
}

/* ---- heap ------------------------------------------------------------ */

#define HEAP_CHUNK (32L * 1024)
#define HEAP_MAX   ((17L - (long)LISA_HEAP_LDSN) * 128L * 1024)

static char *heap_brk;
static long heap_size;
static int16_t heap_refnum;

void *sbrk(ptrdiff_t incr)
{
    char *base = LISA_HEAP_BASE, *old;
    int16_t err;

    if (!heap_brk) {
        static const unsigned char name[] = "\011LISACHEAP";
        unsigned char p[16];
        void *segptr;
        memcpy(p, name, sizeof name);
        lisa_make_dataseg(&err, p, HEAP_CHUNK, HEAP_CHUNK, &heap_refnum, &segptr,
                          (int16_t)(long)LISA_HEAP_LDSN, LISA_DS_PRIVATE);
        if (err > 0 || segptr != base) {
            errno = ENOMEM;
            return (void *)-1;
        }
        heap_brk = base;
        heap_size = HEAP_CHUNK;
    }
    if (heap_brk + incr < base) {
        errno = EINVAL;
        return (void *)-1;
    }
    if (heap_brk + incr > base + heap_size) {
        long need = (long)(heap_brk + incr - base) - heap_size;
        long delta = (need + HEAP_CHUNK - 1) / HEAP_CHUNK * HEAP_CHUNK;
        int32_t newmem, newdisc;
        if (heap_size + delta > HEAP_MAX) {
            errno = ENOMEM;
            return (void *)-1;
        }
        lisa_size_dataseg(&err, heap_refnum, delta, &newmem, delta, &newdisc);
        if (err > 0) {
            errno = ENOMEM;
            return (void *)-1;
        }
        heap_size = newmem;
    }
    old = heap_brk;
    heap_brk += incr;
    return old;
}

/* ---- time ------------------------------------------------------------ */

int gettimeofday(struct timeval *tv, void *tz)
{
    unsigned char t[16];
    int16_t err;
    long days, y;
    (void)tz;

    lisa_get_time(&err, t);             /* time_rec: year@0 day@2 hour@4 minute@5 second@6 */
    if (err > 0)
        return fail(err);
    y = (t[0] << 8) | t[1];
    days = ((t[2] << 8) | t[3]) - 1;            /* julian day, 1-based */
    for (long yy = 1970; yy < y; yy++)
        days += (yy % 4 == 0 && (yy % 100 != 0 || yy % 400 == 0)) ? 366 : 365;
    tv->tv_sec = ((days * 24 + (signed char)t[4]) * 60 + (signed char)t[5]) * 60 + t[6];
    tv->tv_usec = 0;
    return 0;
}

int clock_gettime(clockid_t clk, struct timespec *ts)
{
    struct timeval tv;
    (void)clk;
    if (gettimeofday(&tv, 0) < 0)
        return -1;
    ts->tv_sec = tv.tv_sec;
    ts->tv_nsec = tv.tv_usec * 1000;
    return 0;
}

int nanosleep(const struct timespec *req, struct timespec *rem)
{
    /* DELAY_TIME(err, interval: timestmp_interval, clktime: time_rec) */
    struct { int32_t sec; int16_t msec; } interval = { req->tv_sec, (int16_t)(req->tv_nsec / 1000000) };
    unsigned char clktime[10] = { 0 };
    int16_t err;

    if (rem)
        rem->tv_sec = rem->tv_nsec = 0;
    lisa_delay_time(&err, &interval, clktime);
    return err > 0 ? fail(err) : 0;
}

/* ---- process --------------------------------------------------------- */

void _exit(int status)
{
    (void)status;
    __lisa_exit_tail();
}

/* Called by crt0 after main returns: run atexit handlers, flush stdio. */
void __lisa_fini(int status)
{
    exit(status);
}

int getentropy(void *buf, size_t n)
{
    (void)buf; (void)n;
    errno = ENOSYS;
    return -1;
}
