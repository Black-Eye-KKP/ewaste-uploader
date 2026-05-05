#!/usr/bin/env python3
"""
EVS Report Aggregator v2
─────────────────────────
Combines all per-image HTML reports into a dashboard.
Now reads embedded base64 images and real file info from patched HTMLs.
Run patch_images.py first, then this.
"""

import os
import re
import pathlib
import webbrowser
from datetime import datetime

REPORTS_FOLDER = pathlib.Path(os.getenv("REPORTS_FOLDER", r"D:\EVS\EVs\Reports"))
OUTPUT_FILE    = REPORTS_FOLDER / "dashboard.html"


# ── Helpers ────────────────────────────────────────────────────────────────────

def extract_title(html: str, fallback: str) -> str:
    m = re.search(r'<title[^>]*>EVS E-Waste Report\s*[—–-]\s*(.+?)\s*</title>',
                  html, re.IGNORECASE)
    return m.group(1).strip() if m else fallback


def extract_device_type(html: str) -> str:
    m = re.search(r'class=["\']device-badge["\'][^>]*>🔌\s*(.+?)</div>', html)
    return m.group(1).strip() if m else ''


def extract_thumbnail(html: str) -> str | None:
    """
    Extract base64 thumbnail from comp-img.
    Returns a short data URI (resize to thumbnail via CSS).
    """
    # Look for properly embedded image (not filesystem-v2)
    m = re.search(
        r'id=["\']comp-img["\'][^>]*src=["\'](data:image/[^"\']+)["\']',
        html
    )
    if not m:
        m = re.search(
            r'src=["\'](data:image/[^"\']+)["\'][^>]*id=["\']comp-img["\']',
            html
        )
    if m:
        uri = m.group(1)
        # Only return if not the broken filesystem placeholder
        if 'filesystem' not in uri and len(uri) > 100:
            return uri
    return None


def extract_file_info(html: str) -> dict:
    """Extract file name, size, date from img-info-bar."""
    info = {'name': '', 'size': '', 'date': ''}
    bar_m = re.search(r'id=["\']img-info-bar["\'][^>]*>([\s\S]*?)</div>', html)
    if bar_m:
        bar = bar_m.group(1)
        n = re.search(r'<strong>File:</strong>\s*([^\s<&]+)', bar)
        s = re.search(r'<strong>Size:</strong>\s*([^\s<&]+\s*KB)', bar)
        d = re.search(r'<strong>Date:</strong>\s*([^<&|]+)', bar)
        if n: info['name'] = n.group(1).strip()
        if s: info['size'] = s.group(1).strip()
        if d: info['date'] = d.group(1).strip()
    return info


def extract_summary(html: str) -> str:
    """Extract AI summary text."""
    m = re.search(r'class=["\']summary-p["\'][^>]*>([\s\S]*?)</div>', html)
    if m:
        text = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        return text[:120] + '…' if len(text) > 120 else text
    return ''


def extract_metals(html: str) -> list[str]:
    """Extract recoverable metals from badge.green spans."""
    rows = re.findall(r'<tr class=["\']mrow["\']>([\s\S]*?)</tr>', html)
    metals = []
    for row in rows:
        name_m = re.search(r'<strong>([^<]+)</strong>', row)
        if name_m and 'badge green' in row:
            metals.append(name_m.group(1).strip())
    return metals[:4]  # max 4 for sidebar


def get_report_files() -> list[pathlib.Path]:
    return sorted(
        [p for p in REPORTS_FOLDER.glob("*.html")
         if p.name != "dashboard.html"],
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )


# ── Build dashboard ────────────────────────────────────────────────────────────

def build_dashboard():
    files = get_report_files()
    if not files:
        print(f"No HTML report files found in {REPORTS_FOLDER}")
        return

    list_items_html = ""
    for idx, fpath in enumerate(files):
        html      = fpath.read_text(encoding='utf-8', errors='replace')
        title     = extract_title(html, fpath.stem)
        device    = extract_device_type(html)
        thumb     = extract_thumbnail(html)
        info      = extract_file_info(html)
        summary   = extract_summary(html)
        metals    = extract_metals(html)
        mtime     = datetime.fromtimestamp(fpath.stat().st_mtime).strftime("%d %b %Y, %H:%M")
        active    = "active" if idx == 0 else ""

        if thumb:
            thumb_html = f'<img src="{thumb}" alt="{title}" />'
        else:
            thumb_html = '<div class="no-thumb">♻</div>'

        metal_pills = ''.join(
            f'<span class="mpill">{m}</span>' for m in metals
        )

        list_items_html += f"""
<div class="report-item {active}" onclick="loadReport('{fpath.name}', this)" title="{title}">
  <div class="thumb">{thumb_html}</div>
  <div class="meta">
    <div class="ri-title">{title}</div>
    {'<div class="ri-device">'+device+'</div>' if device else ''}
    <div class="ri-summary">{summary}</div>
    <div class="ri-metals">{metal_pills}</div>
    <div class="ri-date">📅 {info['date'] or mtime} {'· '+info['size'] if info['size'] else ''}</div>
  </div>
</div>"""

    default_src = files[0].name if files else ""

    dashboard_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>EVS E-Waste Dashboard</title>
<style>
:root{{
  --bg:#060b14;--sidebar:#080d18;--panel:#0d1526;--border:#1a2840;
  --accent:#4f8ef7;--a2:#7c3aed;--text:#e2e8f0;--muted:#64748b;
  --green:#22c55e;--icon-w:56px;--list-w:300px;
}}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{display:flex;height:100vh;overflow:hidden;
  font-family:'Segoe UI',system-ui,sans-serif;
  background:var(--bg);color:var(--text);}}

/* ── Icon rail ── */
.icon-rail{{
  width:var(--icon-w);background:var(--sidebar);
  border-right:1px solid var(--border);
  display:flex;flex-direction:column;align-items:center;
  padding-top:14px;gap:6px;
}}
.rail-logo{{width:32px;height:32px;margin-bottom:10px;}}
.rail-btn{{
  width:40px;height:40px;background:none;border:none;
  border-radius:10px;cursor:pointer;color:var(--muted);
  font-size:20px;display:flex;align-items:center;justify-content:center;
  transition:background 0.15s,color 0.15s;
}}
.rail-btn:hover,.rail-btn.active{{background:#1a2840;color:var(--accent);}}

/* ── List panel ── */
.list-panel{{
  width:var(--list-w);background:var(--panel);
  border-right:1px solid var(--border);
  display:flex;flex-direction:column;overflow:hidden;
}}
.list-header{{
  padding:16px;font-size:11px;font-weight:700;
  color:var(--muted);text-transform:uppercase;letter-spacing:1px;
  border-bottom:1px solid var(--border);flex-shrink:0;
  display:flex;align-items:center;justify-content:space-between;
}}
.list-header span{{color:var(--accent);}}
.search-box{{
  padding:10px 14px;border-bottom:1px solid var(--border);flex-shrink:0;
}}
.search-box input{{
  width:100%;background:#080d18;border:1px solid var(--border);
  border-radius:8px;padding:7px 12px;color:var(--text);font-size:12px;
}}
.search-box input:focus{{outline:none;border-color:var(--accent);}}
.report-list{{overflow-y:auto;flex:1;}}
.report-list::-webkit-scrollbar{{width:4px;}}
.report-list::-webkit-scrollbar-thumb{{background:var(--border);border-radius:4px;}}

.report-item{{
  display:flex;gap:10px;padding:12px 14px;
  border-bottom:1px solid rgba(26,40,64,0.5);
  cursor:pointer;transition:background 0.12s;
}}
.report-item:hover{{background:#0f1828;}}
.report-item.active{{
  background:#0f1828;
  border-left:3px solid var(--accent);
  padding-left:11px;
}}
.thumb{{
  width:64px;height:64px;border-radius:8px;overflow:hidden;
  flex-shrink:0;background:#080d18;
  display:flex;align-items:center;justify-content:center;
  border:1px solid var(--border);
}}
.thumb img{{width:100%;height:100%;object-fit:cover;}}
.no-thumb{{font-size:22px;color:var(--muted);}}
.meta{{overflow:hidden;flex:1;}}
.ri-title{{font-size:12px;font-weight:600;color:var(--text);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:2px;}}
.ri-device{{font-size:10px;color:var(--accent);margin-bottom:3px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
.ri-summary{{font-size:10px;color:var(--muted);line-height:1.4;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;
  overflow:hidden;margin-bottom:4px;}}
.ri-metals{{display:flex;gap:4px;flex-wrap:wrap;margin-bottom:4px;}}
.mpill{{padding:1px 6px;border-radius:4px;font-size:9px;font-weight:700;
  background:rgba(34,197,94,0.12);color:var(--green);
  border:1px solid rgba(34,197,94,0.2);}}
.ri-date{{font-size:9px;color:var(--muted);}}

/* ── Main area ── */
.main-area{{flex:1;overflow:hidden;display:flex;flex-direction:column;}}
.main-topbar{{
  height:48px;background:var(--panel);border-bottom:1px solid var(--border);
  display:flex;align-items:center;padding:0 20px;gap:12px;flex-shrink:0;
}}
.topbar-icon{{font-size:18px;}}
#current-title{{font-size:13px;font-weight:600;color:var(--text);flex:1;}}
#current-device{{font-size:11px;color:var(--accent);}}
.topbar-right{{display:flex;align-items:center;gap:8px;}}
.tb-btn{{
  background:var(--accent);border:none;color:#fff;
  padding:5px 14px;border-radius:6px;cursor:pointer;font-size:12px;font-weight:600;
}}
.tb-btn.sec{{background:rgba(79,142,247,0.12);color:var(--accent);
  border:1px solid rgba(79,142,247,0.3);}}
#report-frame{{flex:1;border:none;background:var(--bg);}}
.empty-state{{
  flex:1;display:flex;flex-direction:column;
  align-items:center;justify-content:center;color:var(--muted);
}}
.empty-state .big-icon{{font-size:64px;margin-bottom:16px;}}

/* ── About panel ── */
#panel-about{{
  display:none;padding:48px;flex:1;overflow-y:auto;
  background:var(--bg);
}}
#panel-about h2{{
  font-size:28px;font-weight:800;margin-bottom:8px;
  background:linear-gradient(135deg,var(--accent),var(--a2));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
}}
#panel-about p{{line-height:1.8;color:#94a3b8;font-size:14px;margin-bottom:14px;}}
#panel-about code{{
  background:#0d1526;padding:3px 8px;border-radius:4px;
  font-size:12px;color:var(--accent);
}}
.about-stat{{
  display:inline-block;background:#0d1526;border:1px solid var(--border);
  border-radius:10px;padding:14px 20px;margin:6px 6px 0 0;
  text-align:center;min-width:120px;
}}
.about-stat .n{{font-size:28px;font-weight:800;color:var(--accent);}}
.about-stat .l{{font-size:11px;color:var(--muted);margin-top:2px;}}
</style>
</head>
<body>

<!-- Icon rail -->
<div class="icon-rail">
  <svg class="rail-logo" viewBox="0 0 36 36" fill="none">
    <rect width="36" height="36" rx="8" fill="#4f8ef722"/>
    <path d="M18 8L28 13V23L18 28L8 23V13L18 8Z" stroke="#4f8ef7" stroke-width="2" fill="none"/>
    <circle cx="18" cy="18" r="4" fill="#4f8ef7"/>
  </svg>
  <button class="rail-btn active" id="btn-reports" title="Reports"
    onclick="switchPanel('reports',this)">📋</button>
  <button class="rail-btn" id="btn-about" title="About"
    onclick="switchPanel('about',this)">ℹ️</button>
</div>

<!-- Report list -->
<div class="list-panel" id="list-panel">
  <div class="list-header">
    Reports <span>{len(files)}</span>
  </div>
  <div class="search-box">
    <input type="text" id="search-inp" placeholder="🔍 Search reports…"
      oninput="searchReports(this.value)"/>
  </div>
  <div class="report-list" id="report-list">
    {list_items_html}
  </div>
</div>

<!-- Main area -->
<div class="main-area" id="main-area">
  <div class="main-topbar">
    <span class="topbar-icon">♻</span>
    <div>
      <div id="current-title">{files[0].stem if files else 'No reports'}</div>
      <div id="current-device"></div>
    </div>
    <div class="topbar-right">
      <span style="font-size:11px;color:var(--muted)">{len(files)} report(s) &nbsp;·&nbsp; {datetime.now().strftime('%d %b %Y')}</span>
      <button class="tb-btn sec" onclick="openInNewTab()">🔗 Open in new tab</button>
    </div>
  </div>
  {'<iframe id="report-frame" src="' + default_src + '"></iframe>' if files else
   "<div class='empty-state'><div class='big-icon'>📭</div><p>No reports found.<br/>Run patch_images.py first.</p></div>"}
</div>

<!-- About panel -->
<div id="panel-about">
  <h2>♻ EVS E-Waste Dashboard</h2>
  <p>Aggregates all e-waste analysis reports generated by the n8n AI workflow.</p>
  <div>
    <div class="about-stat"><div class="n">{len(files)}</div><div class="l">Total Reports</div></div>
  </div>
  <br/><br/>
  <p><strong style="color:var(--text)">Reports folder:</strong><br/><code>{REPORTS_FOLDER}</code></p>
  <p><strong style="color:var(--text)">Each report contains:</strong><br/>
    • AI-identified device type and composition<br/>
    • All detected metals — recoverable and non-recoverable<br/>
    • AI-identified reusable components with images<br/>
    • 5 recovery methods (Student / Professional guides)<br/>
    • 12-month interactive metal market price charts<br/>
    • Research paper links per metal
  </p>
  <p><strong style="color:var(--text)">To rebuild this dashboard:</strong><br/>
    <code>python patch_images.py</code> — embed images into reports<br/>
    <code>python aggregator.py</code> — rebuild this dashboard<br/>
    <code>python clean_duplicates.py</code> — remove duplicate reports
  </p>
  <p style="font-size:12px;color:#334155;margin-top:24px;">
    © {datetime.now().year} EVS E-Waste Analyser &nbsp;·&nbsp; Educational use only
  </p>
</div>

<script>
let currentSrc = '{default_src}';

function loadReport(filename, el) {{
  document.querySelectorAll('.report-item').forEach(x => x.classList.remove('active'));
  el.classList.add('active');
  const frame = document.getElementById('report-frame');
  if (frame) frame.src = filename;
  currentSrc = filename;
  const stem = el.querySelector('.ri-title')?.textContent || filename;
  const device = el.querySelector('.ri-device')?.textContent || '';
  document.getElementById('current-title').textContent = stem;
  const cd = document.getElementById('current-device');
  if(cd) cd.textContent = device;
}}

function openInNewTab() {{
  if (currentSrc) window.open(currentSrc, '_blank');
}}

function switchPanel(panel, btn) {{
  document.querySelectorAll('.rail-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const listPanel = document.getElementById('list-panel');
  const mainArea  = document.getElementById('main-area');
  const about     = document.getElementById('panel-about');
  if (panel === 'reports') {{
    listPanel.style.display = '';
    mainArea.style.display  = '';
    about.style.display     = 'none';
  }} else {{
    listPanel.style.display = 'none';
    mainArea.style.display  = 'none';
    about.style.display     = '';
  }}
}}

function searchReports(q) {{
  const term = q.toLowerCase();
  document.querySelectorAll('.report-item').forEach(el => {{
    const text = el.textContent.toLowerCase();
    el.style.display = text.includes(term) ? '' : 'none';
  }});
}}
</script>
</body>
</html>"""

    OUTPUT_FILE.write_text(dashboard_html, encoding='utf-8')
    print(f"\n✓ Dashboard built: {OUTPUT_FILE}")
    print(f"  Reports: {len(files)}")
    try:
        webbrowser.open(OUTPUT_FILE.as_uri())
    except Exception:
        pass


if __name__ == '__main__':
    print(f"[Aggregator] Scanning {REPORTS_FOLDER}\n")
    build_dashboard()