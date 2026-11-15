# Unblock the vessel preview and clarify export history

- The re-exported plasma-vessel assembly read successfully; fine preview
  tessellation kept its display worker pending. Start assemblies of at least
  200 occurrences at the existing second tolerance, retaining the triangle
  limit and normal fine display for smaller models. Invalidate display caches.
- The actual mirror produced renderable ranges for all 251 occurrences and
  394,836 triangles in about 22 seconds. No CAD, mirror or drawing-group edits.
- The export log records past attempts, not blockers. Keep skip events neutral
  and identify ones followed by success. Export scheduling is unchanged.
- Changed display meshing/cache, mirror history/template, tests and version.
  Next: reload the vessel viewer and refer to the current queue for blockers.
