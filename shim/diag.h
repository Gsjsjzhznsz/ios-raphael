#pragma once
#include <stdint.h>

/*
 * Reboot-coded stage diagnostics (RAPHAEL diag images, "shimstage=1").
 *
 * When the screen cannot light (no panel driver yet), flash writes may be
 * broken (crumbs are best effort) and USB may never enumerate, the only
 * channels left that nobody can take away are:
 *
 *   1. A DDR record in the stock ramoops region (raphael DTS:
 *      ramoops@a1600000 +0x800000, i.e. up to 0xa1e00000; the stock kernel
 *      never binds it because the DTS requests 0xc00000 of zones in an
 *      0x800000 region, so nothing zaps it). We keep a small binary record
 *      plus an ASCII line at the very end of that region and a second copy
 *      near its start. Read it from any recovery with toybox devmem:
 *         devmem 0xa1dff000   (magic 'STGD', then stage, crumb diag, ...)
 *   2. The auto-reboot delay itself: a shimstage=1 boot never jumps into
 *      xnu; it stops at the jump point and resets after
 *      20 + 20 * stage seconds (stage 6 -> 140 s). Timing the reboot with
 *      a watch decodes the furthest stage reached without any other
 *      channel. Existing signatures stay distinguishable: an exception
 *      still resets at ~40 s, a loader error path (DTB/payload checks)
 *      still resets at ~200 s, a hang never resets at all.
 *
 * Mode is opt-in per image: shimstage=1 in the payload command line (seen
 * after the payload header validates) or in the DTB /chosen bootargs or
 * commandline (seen even earlier). Without the token everything behaves
 * exactly as before: the marks are written, the jump happens.
 *
 * SWEET builds get no-ops; the shim binary for sweet is unchanged.
 */

extern int shim_stage_mode;

/* Mark the furthest stage reached (1..6). Monotonic; also recorded for
 * non-stage boots (the record is harmless and always useful). */
void stage_diag_mark(unsigned code);

/* Only in stage mode: record the final stage and reset without jumping.
 * Called at the exact point where a normal boot would enter xnu. */
void stage_diag_final(void) __attribute__((noreturn));

/* Non-zero if hay contains token (simple substring match). */
static inline int diag_has_token(const char *hay, const char *token)
{
	for (unsigned i = 0; hay[i]; i++) {
		unsigned j;
		for (j = 0; token[j] && hay[i + j] == token[j]; j++)
			;
		if (!token[j])
			return 1;
	}
	return 0;
}
