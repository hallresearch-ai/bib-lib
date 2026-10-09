# One-time audit tools

These scripts record the October 2026 cleanup of the July library. They use
original dated paths and, in several cases, temporary research inputs. They are
historical tools, not a sequence for rebuilding the manually reviewed library.

`migrate_workbook_keys.py` preserves the original one-time workbook-key migration.
Current key maintenance is handled by `workflow/update_citation_keys.py`.

For historical investigation, read the scripts and restore or adapt their
original inputs using the [relocation guide](../README.md). Sibling imports and
current helpers require both `old/audits/2026-10-08/tools` and `workflow` on
Python's module path. From the root, the corresponding setting is
`PYTHONPATH=workflow:old/audits/2026-10-08/tools`. Later manual corrections and
deletions are not reconstructed by these scripts.

Use the [current workflow](../../../../workflow/README.md) for routine updates.
