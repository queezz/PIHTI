# Submission intake: verify dependencies before merging

A student CAD submission is accepted only with evidence that its delivered
assemblies and drawings resolve under PIHTI.ipj, using the submitted files and
explicitly listed shared archive components.

## Required package

- Name the primary assemblies and drawings and explain whether this is a new
  design, a revision or an independent snapshot.
- List included native files, reused workspace-relative components and any
  required external Content Center/library assets. Avoid absolute workstation
  paths.
- Include source/vendor evidence for purchased components and preserve fabrication
  exports. An assembly thumbnail or cached drawing does not prove its links work.
- Inventory repeated filenames before importing. Same names with different bytes
  require review; hashes alone do not establish the intended reference.
- Use Pack-and-Go or an equivalent dependency collection, then check its result.
  Do not import vendor Design Data, Templates, OldVersions or lock/cache material
  as curated hardware.

## Acceptance check

1. Review the incoming branch/package separately from the curated working tree.
   Local unpacked intake belongs under ignored staging until reviewed. A Git merge
   copies committed files; it does not collect files named inside Inventor binaries.
2. Record a read-only duplicate inventory and the base/submit commit IDs.
3. Open PIHTI.ipj. Verify the primary assemblies AND every delivered IDW/IPN against
   Inventor native descriptors in the receiving environment. Include the dependency
   graph, not just top-level thumbnails. Reopen saved deliverables and record
   missing, ambiguous, suppressed and external dependencies separately.
4. Resolve missing submission dependencies in the submission. A filename that
   never entered Git cannot be recovered by merging again. Preserve unresolved
   imported work as review material; merging does not declare it canonical.
5. For intended renames, use Inventor to update affected drawing and assembly
   references. Save and reopen all affected deliverables. Binary strings may retain
   old names; register a scoped native verification only when Inventor proves
   that the exact referrer has no direct descriptor for that name.
6. Accept only when the delivered graph resolves and each intended reference has
   one documented target. List any intentionally suppressed/external exception
   with native evidence; no unexplained missing links. Record the result in the
   submission handoff before merging. Do not hide a real missing dependency with a
   Doctor-later disposition.
7. After the merge, repeat the native receiving-workspace check and keep submission
   provenance. Curated hardware replacement remains a separate review decision.

## Subsequent cleanup

Consolidating duplicate names is another reference operation. Use Inventor to
check and, when necessary, repoint every affected assembly AND drawing to the
reviewed survivor; save and reopen them before committing removal. A remaining
same-name survivor and byte/hash inventory alone do not prove that all native
descriptors resolved to it.

## Current investigation

See submission-reference-audit.json and
log/2026-10-08-student-merge-reference-investigation.md. PRs #1/#3 include genuine
unsubmitted dependencies and a renamed drawing with obsolete links. Some other
Doctor rows were staging/indirect-string noise, while two UFC-152 failures followed
later archive consolidation. These causes must not be blended into one student
failure count.
