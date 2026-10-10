/* Console input through stdin (PASLIB INPUT). The test runner types the
 * line from tests/stdin/input.txt after the program starts. */
#include <stdio.h>
#include <string.h>

int main(void)
{
    char line[80];
    int a, b;

    printf("Enter two numbers: ");
    fflush(stdout);
    if (!fgets(line, sizeof line, stdin)) {
        printf("stdin: FAIL (EOF)\n");
        return 1;
    }
    line[strcspn(line, "\n")] = 0;
    if (sscanf(line, "%d %d", &a, &b) == 2 && a + b == 42)
        printf("got \"%s\", sum %d\nstdin: PASS\n", line, a + b);
    else
        printf("got \"%s\"\nstdin: FAIL\n", line);
    return 0;
}
