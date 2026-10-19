#pragma once
#include <stdint.h>

void test_ufs(void);

#ifdef RAPHAEL
/* Flash breadcrumb: append one diagnostic record to the last 4 KiB block
 * of the userdata partition (written with a raw SCSI WRITE(10), MMU off).
 * Survives black screens / hard resets; read it back from any recovery:
 *   tail -c 4096 /dev/block/by-name/userdata | strings
 */
void ufs_crumb(const char *tag, uint64_t a, uint64_t b, uint64_t c, uint64_t d);
#else
static inline void ufs_crumb(const char *tag, uint64_t a, uint64_t b, uint64_t c, uint64_t d)
{
        (void)tag; (void)a; (void)b; (void)c; (void)d;
}
#endif
