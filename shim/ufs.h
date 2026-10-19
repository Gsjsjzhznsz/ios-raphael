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

/* Why the breadcrumbs are not landing (u32):
 *   bits 0-7   init failure step: 1 host not ready, 2 list takeover,
 *              3 TUR failed, 4 GPT read, 5 bad GPT, 6 no userdata,
 *              7 LBA overflow; 0 = init passed (bit 16 also set)
 *   bits 8-15  last WRITE(10) failure: 0x10|rc with rc from scsi()
 *              (1 timeout, 2 OCS error, 3 no response UPIU, 4 check cond);
 *   bit 16     init ok
 * Zero everywhere means ufs_crumb never ran (call it first!). */
uint32_t ufs_crumb_diag(void);
#else
static inline void ufs_crumb(const char *tag, uint64_t a, uint64_t b, uint64_t c, uint64_t d)
{
        (void)tag; (void)a; (void)b; (void)c; (void)d;
}
static inline uint32_t ufs_crumb_diag(void) { return 0; }
#endif
