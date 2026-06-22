# Duplicate Inventory Direction

Standing direction for PIHTI cleanup and staged imports.

## Principle

Prefer evidence before moving CAD. Most PIHTI junk appears to be copied files, so first do bit/hash inventory and only then decide canonical locations.

## Workflow

1. Keep imported material under ignored `staging/` until reviewed.
2. Run a read-only inventory before moving anything:

   ```bash
   python scripts/find_duplicates.py staging/hayashi BoronProbe SampleHolder ContentCenter "Plasma Vessel" --markdown .agents/duplicate-report.md --json .agents/duplicate-report.json
   ```

3. Treat SHA-256 duplicate groups as byte-for-byte copies. These catch pure file renames as well as copied paths.
4. Treat same-name/same-size groups as likely direct copies, but confirm by hash if hashing was disabled.
5. Treat same-name/different-size groups as possible version forks. Do not delete these without opening assemblies or checking references.
6. Do not delete or move `.iam`, `.ipt`, `.idw`, `.stp`, or `.stl` files until Inventor references have been checked or a clear replacement path is documented.
7. For a cleanup commit, delete duplicate copies only after the canonical file path is chosen and noted in `.agents/` or `docs/`.

## Limitations

Hash checking will not catch parts that were opened, regenerated, redrawn, or saved again by Inventor. Those need assembly/reference review and human judgment.