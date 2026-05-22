# Contributing Assemblies

How to add or modify Inventor assemblies without breaking shared lab geometry.

---

## Shared references are intentional

Assemblies in this repository often reference parts from several folders. This
is normal. Shared vessel geometry, vacuum hardware, common flanges, and library
parts live in their existing locations and are reused by other systems.

**Do not duplicate shared geometry into your working folder.**

If your assembly needs a part from `Plasma Vessel/`, `ContentCenter/`, or
another established subsystem, reference it in place. Copying shared parts
creates nearly identical versions that drift apart and become hard to trust.

---

## Keep experiment changes local

If you need a modified version of a shared part, save the modified copy in your
own subsystem folder with a clear name.

Good:

```text
CF70-flange-modified-for-probe.ipt
PALP-feedthrough-bracket-short.ipt
```

Not useful:

```text
Part47_final2.ipt
copy-of-flange.ipt
```

The original shared part should stay untouched unless you are coordinating a
shared upgrade.

---

## Modified vacuum assemblies

If you are adapting the main vessel, plasma chamber, flanges, or other vacuum
hardware for one experiment, keep the modified assembly in that experiment's
folder.

Do not overwrite the canonical `Plasma Vessel/` geometry just to record an
experiment-specific fit. The shared vessel model should remain the common
reference.

---

## Addons

Addons should usually live near the subsystem they belong to. For example, a
probe mount, temporary camera bracket, or diagnostic adapter should be placed in
the folder for that probe or diagnostic.

Reference shared vessel and flange geometry in place. Put only the new or
modified addon parts in the local folder.

---

## Subsystem organization

Keep related parts, assemblies, drawings, and exported geometry together. A
folder should be understandable when opened later without asking the original
author.

New independent systems may become top-level folders. This makes sense for a
new probe, diagnostic, chamber, electronics enclosure family, or other assembly
that is not just an addon to an existing subsystem.

Avoid copying entire directory trees unless the old design must be preserved
intact as a reference. If that is necessary, `OldVersions/` inside the folder is
the usual place for older Inventor-managed revisions.

---

## Add a folder README

If you create a substantial new assembly or subsystem, add a `README.md` in that
folder. Keep it short. It is a map for the next student, not a report.

Include:

- Purpose
- Author
- Date
- Reused assemblies or components
- Notes or status

Example:

```markdown
# PALP Probe Adapter

Purpose: Adapter bracket for mounting the PALP probe on the 2024 flange.
Author: A. Student
Date: 2026-05-22

Reused components:
- `Plasma Vessel/Plasma-Flange-2024/...`
- `ContentCenter/KF/...`

Notes/status:
- Fit checked in Inventor.
- Not yet fabricated.
```

The main rule is simple: shared/common geometry stays shared;
experiment-specific modifications stay local.
