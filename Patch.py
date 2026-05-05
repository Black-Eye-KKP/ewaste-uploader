#!/usr/bin/env python3
"""
EVS Image Patcher
─────────────────
Reads every .html report in D:\\EVS\\EVs\\Reports
Matches the image filename mentioned inside the HTML to an actual image file in D:\\EVS\\EVs\\Images
Embeds the image as base64 directly into the HTML (permanent change)
Removes the drag-and-drop section completely
Saves the patched HTML back in place

Usage:
    python patch_images.py          → patch all reports
    python patch_images.py --dry    → preview only, no changes saved
"""

import os
import re
import sys
import base64
import pathlib
import mimetypes
from datetime import datetime

REPORTS_FOLDER = pathlib.Path(os.getenv("REPORTS_FOLDER", r"D:\EVS\EVs\Reports"))
IMAGES_FOLDER  = pathlib.Path(os.getenv("IMAGES_FOLDER",  r"D:\EVS\EVs\Images"))

# ── Helpers ────────────────────────────────────────────────────────────────────

def find_image_in_folder(img_name: str) -> pathlib.Path | None:
    """
    Find an image file in IMAGES_FOLDER matching img_name.
    Tries exact match first, then case-insensitive, then stem-only match.
    """
    if not IMAGES_FOLDER.exists():
        return None

    # Normalise: replace spaces with underscores both ways for comparison
    target = img_name.strip()

    # 1. Exact match
    exact = IMAGES_FOLDER / target
    if exact.exists():
        return exact

    # 2. Case-insensitive match
    target_lower = target.lower()
    for f in IMAGES_FOLDER.iterdir():
        if f.name.lower() == target_lower:
            return f

    # 3. Stem-only match (ignore extension differences)
    target_stem = pathlib.Path(target).stem.lower()
    for f in IMAGES_FOLDER.iterdir():
        if f.stem.lower() == target_stem and f.suffix.lower() in \
                {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}:
            return f

    return None


def image_to_data_uri(img_path: pathlib.Path) -> str:
    """Read image file and return a data:image/...;base64,... URI."""
    mime, _ = mimetypes.guess_type(str(img_path))
    if not mime:
        ext = img_path.suffix.lower()
        mime = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                '.png': 'image/png', '.webp': 'image/webp',
                '.gif': 'image/gif', '.bmp': 'image/bmp'}.get(ext, 'image/jpeg')
    data = base64.b64encode(img_path.read_bytes()).decode('ascii')
    return f"data:{mime};base64,{data}"


def extract_image_name(html: str) -> str | None:
    """
    Extract the image filename from the HTML report.
    Looks at:
      1. <title>EVS E-Waste Report — filename.jpeg</title>
      2. img-info-bar: <strong>File:</strong> filename.jpeg
      3. alt="filename.jpeg" on the comp-img
    """
    # Method 1: title tag
    m = re.search(r'<title[^>]*>EVS E-Waste Report\s*[—–-]\s*(.+?)\s*</title>',
                  html, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # Method 2: img-info-bar File: field
    m = re.search(r'<strong>File:</strong>\s*([^\s<&]+)', html)
    if m:
        return m.group(1).strip()

    # Method 3: alt attribute on comp-img
    m = re.search(r'id=["\']comp-img["\'][^>]*alt=["\']([^"\']+)["\']', html)
    if not m:
        m = re.search(r'alt=["\']([^"\']+)["\'][^>]*id=["\']comp-img["\']', html)
    if m:
        return m.group(1).strip()

    return None


def extract_date(html: str) -> str:
    """Extract generated date from HTML."""
    m = re.search(r'Generated:\s*([^<|]+)', html)
    return m.group(1).strip() if m else datetime.now().strftime('%d %b %Y')


def patch_html(html: str, data_uri: str, img_name: str, img_path: pathlib.Path) -> str:
    """
    1. Replace src="data:image/...;base64,filesystem-v2" or empty src with real base64
    2. If no img tag exists in drop zone, inject one
    3. Remove drag-and-drop elements (hint, input, JS handler)
    4. Update img-info-bar with real file info
    """
    file_size_kb = round(img_path.stat().st_size / 1024, 1)
    date_str = extract_date(html)

    # ── 1. Fix the img src ──────────────────────────────────────────────────────
    # Replace any existing broken base64 on comp-img
    html = re.sub(
        r'(<img\s[^>]*id=["\']comp-img["\'][^>]*)src=["\'][^"\']*["\']',
        rf'\1src="{data_uri}"',
        html
    )
    html = re.sub(
        r'src=["\'][^"\']*["\']([^>]*id=["\']comp-img["\'])',
        rf'src="{data_uri}"\1',
        html
    )

    # If comp-img tag doesn't exist at all, inject inside dropZone
    if 'id="comp-img"' not in html and "id='comp-img'" not in html:
        html = re.sub(
            r'(<div[^>]*id=["\']dropZone["\'][^>]*>)',
            rf'\1<img id="comp-img" src="{data_uri}" alt="{img_name}" '
            r'style="max-width:100%;max-height:320px;object-fit:contain;border-radius:8px;"/>',
            html
        )

    # ── 2. Remove drag-and-drop elements ────────────────────────────────────────
    # Remove hidden file input
    html = re.sub(r'<input[^>]*id=["\']drop-input["\'][^>]*/>', '', html)
    html = re.sub(r'<input[^>]*id=["\']drop-input["\'][^>]*>', '', html)

    # Remove drop-hint div
    html = re.sub(
        r'<div[^>]*class=["\']drop-hint["\'][^>]*>.*?</div>',
        '', html, flags=re.DOTALL
    )

    # Make dropZone non-interactive (remove cursor pointer, keep as display container)
    html = html.replace('cursor:pointer;', 'cursor:default;')
    html = html.replace("zone.addEventListener('click',()=>inp.click());", '')
    html = html.replace("inp.addEventListener('change',", '//inp.addEventListener(\'change\',')
    html = html.replace("zone.addEventListener('dragover',", '//zone.addEventListener(\'dragover\',')
    html = html.replace("zone.addEventListener('dragleave',", '//zone.addEventListener(\'dragleave\',')
    html = html.replace("zone.addEventListener('drop',", '//zone.addEventListener(\'drop\',')

    # Remove the entire drop JS IIFE block
    html = re.sub(
        r'\(function\(\)\{[\s\S]*?const zone=document\.getElementById\(\'dropZone\'\)[\s\S]*?\}\)\(\);',
        '/* image embedded permanently */',
        html
    )

    # ── 3. Update img-info-bar ──────────────────────────────────────────────────
    new_bar = (
        f'<strong>File:</strong> {img_name} &nbsp;|&nbsp; '
        f'<strong>Size:</strong> {file_size_kb} KB &nbsp;|&nbsp; '
        f'<strong>Date:</strong> {date_str} &nbsp;|&nbsp; '
        f'<span style="color:var(--green)">✓ Image permanently embedded</span>'
    )
    html = re.sub(
        r'(<div[^>]*id=["\']img-info-bar["\'][^>]*>)[\s\S]*?(</div>)',
        rf'\1{new_bar}\2',
        html
    )

    # ── 4. Remove drag CSS that's no longer needed ───────────────────────────────
    html = html.replace('.img-drop-zone.dragover{border-color:var(--accent);background:rgba(79,142,247,0.05);}', '')

    return html


# ── Main ───────────────────────────────────────────────────────────────────────

def run(dry_run: bool = False):
    if not REPORTS_FOLDER.exists():
        print(f"Reports folder not found: {REPORTS_FOLDER}")
        return
    if not IMAGES_FOLDER.exists():
        print(f"⚠  Images folder not found: {IMAGES_FOLDER}")
        print("   Please create it and place your e-waste images there.")

    html_files = [
        f for f in REPORTS_FOLDER.iterdir()
        if f.is_file() and f.suffix == '.html'
        and f.name not in ('dashboard.html',)
    ]

    if not html_files:
        print("No HTML report files found.")
        return

    print(f"Scanning {len(html_files)} report(s) in {REPORTS_FOLDER}")
    print(f"Images folder: {IMAGES_FOLDER}\n{'─'*70}")

    patched = 0
    skipped = 0
    not_found = 0

    for fpath in sorted(html_files):
        html = fpath.read_text(encoding='utf-8', errors='replace')

        # Check if already properly embedded (not filesystem-v2)
        already_embedded = bool(re.search(
            r'id=["\']comp-img["\'][^>]*src=["\']data:image/[^;]+;base64,(?!filesystem)[A-Za-z0-9+/]{20,}',
            html
        ))
        if already_embedded:
            print(f"  ✓ SKIP (already embedded): {fpath.name}")
            skipped += 1
            continue

        img_name = extract_image_name(html)
        if not img_name:
            print(f"  ⚠ SKIP (no image name found): {fpath.name}")
            skipped += 1
            continue

        img_path = find_image_in_folder(img_name)
        if not img_path:
            print(f"  ✗ NOT FOUND — '{img_name}' not in Images folder: {fpath.name}")
            not_found += 1
            continue

        print(f"  ✓ PATCHING: {fpath.name}")
        print(f"    Image: {img_name} → {img_path.name} ({img_path.stat().st_size//1024} KB)")

        data_uri = image_to_data_uri(img_path)
        new_html = patch_html(html, data_uri, img_name, img_path)

        if not dry_run:
            fpath.write_text(new_html, encoding='utf-8')
            print(f"    ✅ Saved.")
        else:
            print(f"    [DRY RUN] Would save patched HTML.")

        patched += 1

    print(f"\n{'─'*70}")
    print(f"  Patched  : {patched}")
    print(f"  Skipped  : {skipped}")
    print(f"  Missing  : {not_found}")
    if not_found > 0:
        print(f"\n  ℹ  Place missing images in: {IMAGES_FOLDER}")
    if dry_run:
        print("\n  [DRY RUN] No files were changed.")
    print(f"{'─'*70}")


if __name__ == '__main__':
    dry = '--dry' in sys.argv or '-d' in sys.argv
    if dry:
        print("DRY RUN — no files will be saved\n")
    run(dry_run=dry)
    input("\nPress Enter to exit...")