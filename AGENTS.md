# Working on this repo (Redmi K20 Pro / raphael port)

- `README.md` is bilingual — Chinese first (default), English below — and covers
  the Redmi K20 Pro (`raphael`, SM8150 / Snapdragon 855) port only.
- Read `NOTES.md` before starting: it holds the register-level hardware
  evidence, touch/USB protocol details, firmware facts and the bring-up order.
- `docs/WORKLOG.md` is the shared work log. **After every completed step,
  append a section (Task ID / Agent / Task / Work Log / Stage Summary) and
  commit+push immediately** — the user requires worklog updates to be pushed
  as you go, to survive session memory loss. Keep the same log in sync with
  the local copy at `/home/z/my-project/worklog.md`.
- Commit completed changes. Use `gh` for GitHub Actions kernel builds and logs.
  Local single-file cross-compiles (`tools/xnu-cc.py`) are useful before
  spending a CI run.
- Device bring-up uses temporary `fastboot boot` images. Preserve partition
  backups. The iOS root goes into the existing `userdata` partition (no GPT
  changes); Android user data is erased by that design and the user has
  approved it. Keep bootloaders, recovery, modem, persist and the backups
  intact, and confirm each destructive step with the user before running it.
- Keep device dumps, serial numbers and downloaded Apple artifacts out of git.
