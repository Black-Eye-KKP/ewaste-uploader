#!/usr/bin/env python3
"""
EVS Report Duplicate Cleaner — Content-Based
─────────────────────────────────────────────
Compares the INNER CONTENT of every HTML report file.
If two files are 100% identical in content, keeps the NEWER one and deletes the older.
Filename doesn't matter — only content hash is compared.

Usage:
  python clean_duplicates.py          → scan and delete duplicates
  python clean_duplicates.py --dry    → preview only, nothing deleted
"""

import os
import hashlib
import pathlib
import sys
from collections import defaultdict
from datetime import datetime

REPORTS_FOLDER = pathlib.Path(os.getenv("REPORTS_FOLDER", r"D:\EVS\EVs\Reports"))

def file_hash(path: pathlib.Path) -> str:
    """SHA-256 hash of file content."""
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()

def clean_duplicates(dry_run: bool = False):
    if not REPORTS_FOLDER.exists():
        print(f"Folder not found: {REPORTS_FOLDER}")
        return

    html_files = [
        f for f in REPORTS_FOLDER.iterdir()
        if f.is_file()
        and f.suffix == ".html"
        and f.name != "dashboard.html"
    ]

    if not html_files:
        print("No HTML report files found.")
        return

    print(f"Scanning {len(html_files)} file(s) in:\n  {REPORTS_FOLDER}\n")
    print("Computing content hashes...")

    # Group files by content hash
    hash_groups: dict[str, list[pathlib.Path]] = defaultdict(list)
    for f in html_files:
        try:
            h = file_hash(f)
            hash_groups[h].append(f)
        except Exception as e:
            print(f"  ⚠ Could not read {f.name}: {e}")

    total_kept    = 0
    total_deleted = 0
    duplicate_groups = 0

    print(f"\n{'─'*70}")

    for h, files in hash_groups.items():
        if len(files) == 1:
            print(f"  ✓ UNIQUE   {files[0].name}")
            total_kept += 1
            continue

        # Sort by modification time — keep the NEWEST
        files_sorted = sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)
        keep   = files_sorted[0]
        delete = files_sorted[1:]
        duplicate_groups += 1

        print(f"\n  📋 DUPLICATE GROUP (hash: {h[:12]}...)")
        print(f"  ✓ KEEP   → {keep.name}  [{datetime.fromtimestamp(keep.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}]")
        for d in delete:
            mtime = datetime.fromtimestamp(d.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            if dry_run:
                print(f"  ✗ WOULD DELETE → {d.name}  [{mtime}]")
            else:
                try:
                    d.unlink()
                    print(f"  ✗ DELETED  → {d.name}  [{mtime}]")
                except Exception as e:
                    print(f"  ⚠ FAILED to delete {d.name}: {e}")
            total_deleted += 1
        total_kept += 1

    print(f"\n{'─'*70}")
    print(f"  Total files scanned : {len(html_files)}")
    print(f"  Duplicate groups    : {duplicate_groups}")
    print(f"  Files kept          : {total_kept}")
    print(f"  Files deleted       : {total_deleted}")
    if dry_run:
        print("\n  ⚠  DRY RUN — nothing was actually deleted.")
        print("     Run without --dry to delete for real.")
    else:
        print(f"\n  ✅ Done. {total_deleted} duplicate(s) removed.")
    print(f"{'─'*70}")

if __name__ == "__main__":
    dry = "--dry" in sys.argv or "-d" in sys.argv
    if dry:
        print("DRY RUN MODE\n")
    clean_duplicates(dry_run=dry)
    input("\nPress Enter to exit...")
