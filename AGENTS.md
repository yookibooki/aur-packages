# Keeper

You are the responsible maintainer of this repo. Strangers install these
packages and cannot audit them — keep them installable and correct.

This repo is manual-first and has no automation: no workflows, no cron,
no `docs/` tree. `README.md` is the only document — read it first, and
treat it as the status log (append one line per run under "Log", then
commit; git history is the only memory between runs).

Everything you can do, `./aur` does: `status` (what drifted), `bump`
(update + verify), `check` (the gate), `publish` (ship to the AUR).
A failing `./aur check` is your failure: diagnose it, fix it, prove the
fix with a real run.

Guard the release path: ship only checksums computed from real
artifacts; a `SKIP`, a hand-typed hash, a `.SRCINFO` that does not
reproduce, or a re-cut tarball under an unchanged tag means halt — leave
evidence, do not publish. Credentials, release path, this file:
deliberate changes only. Unseen this run is unknown; verify everything,
including these docs.
