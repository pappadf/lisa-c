/* Minimal C runtime for Lisa Office System programs. */
#ifndef LISA_H
#define LISA_H

#include <stdint.h>

/* Console output through PASLIB (the program's standard OUTPUT file). */
void lisa_write_pstr(const unsigned char *pstr); /* Pascal string: length byte + chars */
void lisa_writeln(void);
void lisa_write(const char *s);                  /* C string, no newline */
void lisa_puts(const char *s);                   /* C string + newline */
void lisa_write_hex(unsigned long v);            /* "$XXXXXXXX" */
void lisa_write_char(int c);
/* Console input through PASLIB (the program's standard INPUT file). */
int lisa_read_char(void);
int lisa_eoln(void);
void lisa_readln(void);
/* OS process id of this program (My_ID). */
long lisa_my_id(void);
/* Map a Lisa OS error number to an errno value. */
int lisa_errno(int lisa_err);

/* Print "lisa-c runtime: <what> error <code>" and end the program. */
void lisa_fatal(const char *what, long code) __attribute__((noreturn));

/* Tdstype */
#define LISA_DS_SHARED  0
#define LISA_DS_PRIVATE 1

#endif
