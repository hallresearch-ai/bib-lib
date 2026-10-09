"""Assign missing CSV citation keys and synchronize the export.

Existing registry assignments stay fixed. Uses the same options as write_all.py.
The original one-time workbook migration is archived under old/audits/2026-10-08/tools/.
"""
from write_all import main


if __name__ == '__main__':
    main()
