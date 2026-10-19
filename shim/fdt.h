#pragma once
#include <stdint.h>

/* Read a u32/u64 (cell-size agnostic) property of /chosen. Returns 0 if absent. */
int fdt_chosen_u64(uintptr_t fdt, const char *prop, uint64_t *out);

/* Copy a string property of /chosen (bootargs, commandline, ...) into out
 * (always NUL-terminated, truncated to fit). Returns 1 if found. */
int fdt_chosen_str(uintptr_t fdt, const char *prop, char *out, unsigned max);
