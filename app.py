from __future__ import annotations

import io
import os
import sys
import tempfile
import zipfile
import datetime
from decimal import Decimal
from pathlib import Path

# __file__ = _internal/app.py  →  _INTERNAL_DIR = _internal/  →  ROOT = project root
_INTERNAL_DIR = Path(__file__).resolve().parent
ROOT    = _INTERNAL_DIR.parent
SRC_DIR = _INTERNAL_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pandas as pd
import streamlit as st

from invoice_reconciliation.compare_engine import CompareEngine
from invoice_reconciliation.excel_exporter import ExcelExporter
from invoice_reconciliation.invoice_extractor import InvoiceExtractor
from invoice_reconciliation.receipt_parser import ReceiptParser

# ── CSS ──────────────────────────────────────────────────────────────────────
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0&display=swap');

:root {
    --bg:        #f7f9fb;
    --bg-low:    #f2f4f6;
    --white:     #ffffff;
    --on-bg:     #191c1e;
    --on-var:    #45464d;
    --outline:   #76777d;
    --border:    #c6c6cd;
    --primary:   #000000;
    --sec:       #505f76;
    --sec-ctr:   #d0e1fb;
    --on-sec-c:  #54647a;
    --accent:    #10B981;
    --acc-hover: #0ea472;
    --acc-bg:    #f0fdf4;
    --acc-border:#6ee7b7;
    --err:       #ba1a1a;
    --font:      'Inter', sans-serif;
}

html, body, [data-testid="stAppViewContainer"] {
    font-family: var(--font) !important;
    background: var(--bg) !important;
}

/* ── Reset chrome ── */
#MainMenu, .stDeployButton, footer,
[data-testid="stHeader"], [data-testid="stDecoration"],
[data-testid="stSidebarCollapseButton"] { display: none !important; }

/* ── Top Nav ── */
.top-nav {
    position: fixed; top: 0; left: 0; right: 0;
    height: 64px;
    background: var(--white);
    border-bottom: 1px solid var(--border);
    display: flex; align-items: center; justify-content: space-between;
    padding: 0 24px; z-index: 9999; font-family: var(--font);
}
.nav-brand { font-size: 18px; font-weight: 700; color: var(--primary); letter-spacing: -.02em; }
.nav-links { display: flex; align-items: center; gap: 28px; }
.nav-link {
    font-size: 14px; font-weight: 500; color: var(--sec);
    text-decoration: none; padding: 8px 2px;
    border-bottom: 2px solid transparent; transition: color .15s;
}
.nav-link.active { color: var(--primary); font-weight: 600; border-bottom-color: var(--primary); }
.nav-icons { display: flex; align-items: center; gap: 4px; }
.nav-icon-btn {
    width: 36px; height: 36px; border: none; background: transparent;
    color: var(--sec); border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    cursor: pointer; font-family: 'Material Symbols Outlined'; font-size: 22px;
}
.nav-icon-btn:hover { background: var(--bg-low); }
.nav-avatar {
    width: 32px; height: 32px; border-radius: 50%;
    background: var(--sec-ctr); border: 1px solid var(--border);
    display: flex; align-items: center; justify-content: center;
    font-size: 13px; font-weight: 600; color: var(--on-sec-c); margin-left: 4px;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: var(--bg-low) !important;
    border-right: 1px solid var(--border) !important;
    padding-top: 64px !important;
    min-width: 230px !important; max-width: 230px !important;
}
[data-testid="stSidebar"] > div:first-child { padding: 24px 16px !important; }
.sb-title { font-size: 22px; font-weight: 700; color: var(--primary); margin-bottom: 16px; }
.sb-divider { border: none; border-top: 1px solid var(--border); margin: 12px 0; }

/* ── Sidebar: Kiểm tra mới = primary black ── */
[data-testid="stSidebar"] [data-testid="stButton"] > button[kind="primary"] {
    background: var(--primary) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    font-size: 14px !important;
    font-weight: 600 !important;
    padding: 10px 14px !important;
    font-family: var(--font) !important;
    margin-bottom: 6px !important;
    width: 100% !important;
}
[data-testid="stSidebar"] [data-testid="stButton"] > button[kind="primary"]:hover {
    opacity: .85 !important;
}

/* ── Sidebar: nav items = transparent secondary ── */
[data-testid="stSidebar"] [data-testid="stButton"] > button:not([kind="primary"]) {
    background: #ddd !important;
    border: none !important;
    border-radius: 8px !important;
    text-align: left !important;
    justify-content: flex-start !important;
    padding: 10px 12px !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    color: var(--on-var) !important;
    font-family: var(--font) !important;
    width: 100% !important;
    margin-bottom: 2px !important;
}
[data-testid="stSidebar"] [data-testid="stButton"] > button:not([kind="primary"]):hover {
    background: #e6e8ea !important;
}

/* ── Push content below nav ── */
[data-testid="stMain"] { padding-top: 64px !important; }
[data-testid="stMainBlockContainer"] { padding-top: 2rem !important; padding-bottom: 3rem !important; }

/* ── Stepper ── */
.stepper-wrap {
    background: var(--white); border: 1px solid #e2e8f0;
    border-radius: 12px; padding: 20px 32px;
    display: flex; align-items: center; justify-content: space-between;
    box-shadow: 0 1px 3px rgba(0,0,0,.06); margin-bottom: 0;
}
.step-item { display: flex; flex-direction: column; align-items: center; gap: 6px; }
.step-circle {
    width: 40px; height: 40px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 15px; font-weight: 700; font-family: var(--font);
}
.step-circle.active  { background: var(--primary); color: #fff; }
.step-circle.done    { background: var(--accent);  color: #fff; }
.step-circle.pending { background: #eceef0; color: var(--on-var); }
.step-label { font-size: 13px; font-weight: 600; font-family: var(--font); }
.step-label.active  { color: var(--primary); }
.step-label.done    { color: var(--accent); }
.step-label.pending { color: var(--sec); opacity: .55; }
.step-line { flex: 1; height: 2px; background: #e0e3e5; margin: 0 12px; margin-top: -18px; }
.step-line.done { background: var(--accent); }

/* ── Upload card headers ── */
.upload-col-wrap {
    background: var(--white);
    border: 2px dashed var(--border);
    border-radius: 12px 12px 0 0;
    border-bottom: none;
    padding: 24px 20px 14px;
    text-align: center;
    transition: border-color .15s;
}
.upload-col-wrap:hover { border-color: var(--primary); }
.upload-icon-ring {
    width: 64px; height: 64px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    margin: 0 auto 10px;
    font-family: 'Material Symbols Outlined'; font-size: 34px;
}
.upload-icon-ring.pdf   { background: #fef2f2; color: #ef4444; }
.upload-icon-ring.excel { background: #f0fdf4; color: #16a34a; }
.upload-col-title { font-size: 15px; font-weight: 600; color: var(--on-bg); margin-bottom: 4px; }
.upload-col-hint  { font-size: 13px; color: var(--on-var); }
.upload-col-limit { font-size: 11px; color: var(--outline); margin-top: 4px; }

[data-testid="stFileUploaderDropzone"] {
    background: var(--white) !important;
    border: 2px dashed var(--border) !important;
    border-top: none !important;
    border-radius: 0 0 12px 12px !important;
    padding: 12px 16px !important;
}
[data-testid="stFileUploaderDropzoneInstructions"] { display: none !important; }
[data-testid="stFileUploaderDropzone"] button {
    background: var(--bg-low) !important;
    border: 1px solid var(--border) !important;
    color: var(--on-bg) !important;
    border-radius: 6px !important;
    font-size: 13px !important;
    font-family: var(--font) !important;
}
[data-testid="stFileUploader"] { margin-bottom: 0 !important; }

/* ── Status boxes ── */
.status-box {
    display: flex; align-items: center; gap: 10px;
    padding: 11px 14px; border-radius: 8px;
    background: rgba(208,225,251,.25);
    border: 1px solid rgba(208,225,251,.7);
    font-size: 14px; color: var(--on-sec-c); margin-bottom: 6px;
}
.status-box.ok {
    background: rgba(16,185,129,.08) !important;
    border-color: rgba(16,185,129,.3) !important;
    color: #065f46 !important;
}
.status-icon { font-family: 'Material Symbols Outlined'; font-size: 18px; flex-shrink: 0; }

/* ── Processing card ── */
@keyframes spin-ring { to { transform: rotate(360deg); } }
@keyframes fade-slide { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:translateY(0); } }

.proc-card {
    background: var(--white);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 48px 32px 40px;
    text-align: center;
    box-shadow: 0 2px 12px rgba(0,0,0,.06);
    animation: fade-slide .25s ease-out;
}
.proc-spinner {
    width: 64px; height: 64px;
    border: 5px solid #e2e8f0;
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin-ring .75s linear infinite;
    margin: 0 auto 24px;
}
.proc-spinner.done { border-color: var(--accent); animation: none; }
.proc-check-icon {
    font-family: 'Material Symbols Outlined'; font-size: 36px; color: var(--accent);
    line-height: 64px;
}
.proc-title { font-size: 20px; font-weight: 700; color: var(--on-bg); margin-bottom: 6px; }
.proc-subtitle { font-size: 14px; color: var(--on-var); margin-bottom: 32px; }
.proc-stages {
    display: flex; flex-direction: column; gap: 8px;
    max-width: 420px; margin: 0 auto; text-align: left;
}
.proc-stage-item {
    display: flex; align-items: center; gap: 12px;
    padding: 11px 16px; border-radius: 10px;
    font-size: 14px; font-weight: 500; color: var(--on-var);
    background: var(--bg-low); transition: all .2s;
}
.proc-stage-item.s-active {
    background: #ecfdf5; border: 1px solid #a7f3d0;
    color: #065f46; font-weight: 600;
}
.proc-stage-item.s-done { background: var(--bg-low); color: var(--outline); }
.proc-stage-item.s-done .psi-name { text-decoration: line-through; }
.psi-icon {
    font-family: 'Material Symbols Outlined'; font-size: 20px;
    flex-shrink: 0; min-width: 24px; text-align: center;
}
@keyframes spin-sm { to { transform: rotate(360deg); } }
.psi-icon.spinning { display: inline-block; animation: spin-sm .7s linear infinite; }
.psi-name { flex: 1; }
.proc-progress-bar-wrap {
    width: 100%; height: 6px; background: #e2e8f0;
    border-radius: 9999px; margin: 28px auto 0; max-width: 420px; overflow: hidden;
}
.proc-progress-bar-fill {
    height: 100%; background: var(--accent);
    border-radius: 9999px; transition: width .4s ease;
}

/* ── CTA button ── */
[data-testid="stButton"] > button[kind="primary"] {
    background: var(--accent) !important;
    border: none !important;
    border-radius: 12px !important;
    font-weight: 600 !important;
    font-size: 16px !important;
    padding: 14px 32px !important;
    box-shadow: 0 4px 14px rgba(16,185,129,.35) !important;
    transition: all .15s !important;
}
[data-testid="stButton"] > button[kind="primary"]:hover {
    background: var(--acc-hover) !important;
    box-shadow: 0 6px 18px rgba(16,185,129,.4) !important;
    transform: translateY(-1px) !important;
}
[data-testid="stButton"] > button[kind="primary"]:active { transform: scale(.98) !important; }

/* ── Secondary button (outside sidebar) ── */
[data-testid="stMain"] [data-testid="stButton"] > button:not([kind="primary"]) {
    border: 1.5px solid var(--border) !important;
    background: var(--white) !important;
    color: var(--on-bg) !important;
    border-radius: 8px !important;
    font-size: 13px !important;
}

/* ── Metrics ── */
[data-testid="metric-container"] {
    background: var(--white) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    padding: 14px 16px !important;
}
[data-testid="stMetricLabel"] { font-size: 12px !important; font-weight: 500 !important; color: var(--on-var) !important; letter-spacing: .03em !important; }
[data-testid="stMetricValue"] { font-size: 22px !important; font-weight: 700 !important; color: var(--on-bg) !important; }

/* ── Dataframe ── */
[data-testid="stDataFrame"] { border: 1px solid var(--border) !important; border-radius: 10px !important; overflow: hidden; }

/* ── Download button ── */
[data-testid="stDownloadButton"] > button {
    background: var(--white) !important;
    border: 1.5px solid var(--accent) !important;
    color: var(--accent) !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}
[data-testid="stDownloadButton"] > button:hover { background: var(--acc-bg) !important; }

/* ── Expander ── */
[data-testid="stExpander"] { border: 1px solid var(--border) !important; border-radius: 10px !important; background: var(--white) !important; }

/* ── Section title ── */
.sec-title {
    font-size: 12px; font-weight: 600; color: var(--on-var);
    text-transform: uppercase; letter-spacing: .05em;
    margin: 20px 0 10px; padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
}

/* ── Radio tabs ── */
[data-testid="stRadio"] > div { flex-direction: row !important; gap: 8px !important; flex-wrap: nowrap !important; }
[data-testid="stRadio"] label {
    background: var(--white) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    padding: 7px 16px !important;
    font-size: 13px !important; font-weight: 500 !important;
    color: var(--on-var) !important; cursor: pointer;
}
[data-testid="stRadio"] label:has(input:checked) {
    background: #f0fdf4 !important;
    border-color: var(--accent) !important;
    color: #065f46 !important;
}

/* ── Alert ── */
[data-testid="stAlert"] { border-radius: 8px !important; }

/* ── History card ── */
.hist-card {
    background: var(--white); border: 1px solid var(--border);
    border-radius: 12px; padding: 16px 20px;
    display: flex; align-items: center; gap: 16px;
    margin-bottom: 10px; transition: box-shadow .15s;
}
.hist-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,.08); }
.hist-ts { font-size: 12px; color: var(--outline); font-weight: 500; white-space: nowrap; }
.hist-files { flex: 1; }
.hist-inv { font-size: 14px; font-weight: 600; color: var(--on-bg); }
.hist-rcp { font-size: 13px; color: var(--on-var); }
.hist-badge {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 3px 10px; border-radius: 99px; font-size: 12px; font-weight: 600;
}
.hist-badge.ok  { background: #f0fdf4; color: #065f46; }
.hist-badge.err { background: #fff5f5; color: #9b1c1c; }

/* ── Support card ── */
.support-card {
    background: var(--white); border: 1px solid var(--border);
    border-radius: 16px; padding: 40px; text-align: center;
    max-width: 480px; margin: 0 auto;
}
.support-logo {
    width: 72px; height: 72px; border-radius: 16px;
    background: var(--primary);
    display: flex; align-items: center; justify-content: center;
    margin: 0 auto 20px;
    font-family: 'Material Symbols Outlined'; font-size: 36px; color: #fff;
}
.support-name { font-size: 22px; font-weight: 700; color: var(--on-bg); margin-bottom: 4px; }
.support-version { font-size: 13px; color: var(--outline); margin-bottom: 28px; }
.support-row {
    display: flex; justify-content: space-between; align-items: center;
    padding: 12px 0; border-bottom: 1px solid var(--border); font-size: 14px;
}
.support-row:last-child { border-bottom: none; }
.support-label { color: var(--on-var); font-weight: 500; }
.support-value { color: var(--on-bg); font-weight: 600; }
.support-copy { font-size: 12px; color: var(--outline); margin-top: 28px; }

/* ── Batch processing ── */
.batch-pair-hdr {
    background: var(--white); border: 1px solid var(--border);
    border-radius: 10px; padding: 14px 20px;
    display: flex; align-items: center; gap: 14px; margin-bottom: 12px;
}
.batch-pair-hdr.done { border-color: var(--acc-border); background: var(--acc-bg); }
.bph-badge {
    display: inline-block; background: var(--primary); color: #fff;
    font-size: 12px; font-weight: 700; padding: 4px 12px; border-radius: 99px;
    white-space: nowrap; letter-spacing: .02em;
}
.bph-badge.done { background: var(--accent); }
.bph-names { display: flex; align-items: center; gap: 8px; flex: 1; flex-wrap: wrap; }
.bph-inv  { font-size: 14px; font-weight: 600; color: var(--on-bg); }
.bph-sep  { font-size: 14px; color: var(--outline); }
.bph-rcp  { font-size: 14px; color: var(--on-var); }
.batch-overall-bar {
    display: flex; align-items: center; gap: 14px;
    margin-top: 12px; padding: 12px 20px;
    background: var(--white); border: 1px solid var(--border); border-radius: 10px;
}
.bob-label { font-size: 13px; font-weight: 500; color: var(--on-var); white-space: nowrap; }
.bob-bar-wrap { flex: 1; height: 8px; background: #e2e8f0; border-radius: 99px; overflow: hidden; }
.bob-bar-fill { height: 100%; background: var(--accent); border-radius: 99px; transition: width .4s ease; }
.bob-count { font-size: 13px; font-weight: 700; color: var(--on-bg); white-space: nowrap; min-width: 36px; text-align: right; }

/* Decorative circle */
.deco-circle {
    position: fixed; bottom: -80px; right: -80px;
    width: 200px; height: 200px;
    border: 12px solid var(--primary); border-radius: 50%;
    opacity: .04; pointer-events: none; z-index: 0;
}
</style>
"""

_TOP_NAV = """
<div class="top-nav">
    <span class="nav-brand">ĐỐI CHIẾU HÓA ĐƠN</span>
    <div class="nav-links">
        <a class="nav-link active" href="#">Trang chính</a>
    </div>
    <div class="nav-icons">
        <div class="nav-avatar" title="Tài khoản">T</div>
    </div>
</div>
<div class="deco-circle"></div>
"""

# ── Helpers ──────────────────────────────────────────────────────────────────
def _load_env():
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    with env_path.open() as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip(); v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v


_ROW_BG = {
    "PASS":               "background: #f0fdf4",
    "QTY_MISMATCH":       "background: #fffbeb",
    "PRICE_MISMATCH":     "background: #fffbeb",
    "AMOUNT_MISMATCH":    "background: #fffbeb",
    "MISSING_IN_INVOICE": "background: #fff5f5",
    "MISSING_IN_RECEIPT": "background: #fff5f5",
}

_PROC_STAGES = [
    ("picture_as_pdf",  "Đọc file hóa đơn PDF"),
    ("smart_toy",       "AI phân tích nội dung hóa đơn"),
    ("table_chart",     "Đọc phiếu nhận hàng Excel"),
    ("compare_arrows",  "So khớp từng dòng"),
    ("download",        "Xuất file kết quả"),
]


def _fmt(v):
    return "" if v is None else v


def _fmt_num(v):
    if v is None:
        return ""
    try:
        return "{:,.0f}".format(Decimal(v))
    except Exception:
        return str(v)


def _row_style(row):
    bg = _ROW_BG.get(str(row.get("Trạng thái", "")), "")
    return [bg] * len(row)


def _stepper_html(step: int) -> str:
    def circle_cls(n):
        if n < step: return "done"
        if n == step: return "active"
        return "pending"

    labels = ["1. Tải lên file", "2. Đang xử lý", "3. Xem kết quả"]
    circles = []
    for i, lbl in enumerate(labels, 1):
        c = circle_cls(i)
        icon_html = (
            '<span style="font-family:\'Material Symbols Outlined\';font-size:18px">done</span>'
            if c == "done" else str(i)
        )
        circles.append(
            f'<div class="step-item">'
            f'<div class="step-circle {c}">{icon_html}</div>'
            f'<span class="step-label {c}">{lbl}</span>'
            f'</div>'
        )

    l1 = "done" if step > 1 else ""
    l2 = "done" if step > 2 else ""
    return (
        '<div class="stepper-wrap">'
        + circles[0]
        + f'<div class="step-line {l1}"></div>'
        + circles[1]
        + f'<div class="step-line {l2}"></div>'
        + circles[2]
        + '</div>'
    )


def _proc_card_html(active: int) -> str:
    done = active == -1
    pct  = 100 if done else max(5, int(active / len(_PROC_STAGES) * 100))

    spinner_html = (
        '<div class="proc-spinner done"><span class="proc-check-icon">check_circle</span></div>'
        if done else '<div class="proc-spinner"></div>'
    )
    title    = "Hoàn tất!" if done else "Đang xử lý..."
    subtitle = "Kết quả đã sẵn sàng." if done else "Vui lòng đợi trong giây lát..."

    stages_html = ""
    for i, (icon, name) in enumerate(_PROC_STAGES):
        if done or i < active:
            cls, icon_cls, ico = "s-done", "", "check"
        elif i == active:
            cls, icon_cls, ico = "s-active", "spinning", "autorenew"
        else:
            cls, icon_cls, ico = "", "", icon
        stages_html += (
            f'<div class="proc-stage-item {cls}">'
            f'<span class="psi-icon {icon_cls}">{ico}</span>'
            f'<span class="psi-name">{name}</span>'
            f'</div>'
        )

    return f"""
<div class="proc-card">
    {spinner_html}
    <div class="proc-title">{title}</div>
    <div class="proc-subtitle">{subtitle}</div>
    <div class="proc-stages">{stages_html}</div>
    <div class="proc-progress-bar-wrap">
        <div class="proc-progress-bar-fill" style="width:{pct}%"></div>
    </div>
</div>"""


def _add_to_history(inv_name: str, rcp_name: str, result, out_bytes: bytes):
    if "_history" not in st.session_state:
        st.session_state["_history"] = []
    s = result.summary
    st.session_state["_history"].insert(0, {
        "ts":           datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "invoice":      inv_name,
        "receipt":      rcp_name,
        "matched":      s.matched_count,
        "mismatch":     s.mismatch_count,
        "missing":      s.missing_count,
        "output_bytes": out_bytes,
    })
    st.session_state["_history"] = st.session_state["_history"][:20]


# ── Render helpers ────────────────────────────────────────────────────────────
def render_summary(result):
    s = result.summary
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Khớp",            s.matched_count)
    c2.metric("Lệch",            s.mismatch_count)
    c3.metric("Thiếu",           s.missing_count)
    c4.metric("Tổng tiền HĐ",    _fmt_num(s.total_invoice_amount))
    c5.metric("Tổng tiền Phiếu", _fmt_num(s.total_receipt_amount))


def render_result_table(result):
    rows = []
    for row in result.rows:
        rows.append({
            "Phiếu số":         _fmt(row.receipt_no),
            "Mã hàng":          _fmt(row.item_code),
            "Mô tả":            _fmt(row.description),
            "Ngày":             _fmt(row.receipt_date),
            "SL HĐ":            _fmt_num(row.invoice_qty),
            "SL Phiếu":         _fmt_num(row.receipt_qty),
            "Đơn giá HĐ":       _fmt_num(row.invoice_unit_price),
            "Đơn giá Phiếu":    _fmt_num(row.receipt_unit_price),
            "Thành tiền HĐ":    _fmt_num(row.invoice_amount),
            "Thành tiền Phiếu": _fmt_num(row.receipt_amount),
            "P/O No":           _fmt(row.po_no),
            "Trạng thái":       row.final_status.value,
            "Ghi chú":          _fmt(row.note),
        })
    df     = pd.DataFrame(rows)
    styled = df.style.apply(_row_style, axis=1)
    st.dataframe(styled, use_container_width=True, hide_index=True, height=430)


def render_missing_section(result):
    missing_rows = [r for r in result.rows if r.final_status.value == "MISSING_IN_INVOICE"]
    if not missing_rows:
        return
    total = sum(
        Decimal(r.missing_amount if r.missing_amount is not None else r.receipt_amount or 0)
        for r in missing_rows
    )
    with st.expander(
        "Hàng chưa xuất hóa đơn — %d dòng | Tổng: %s VND" % (len(missing_rows), _fmt_num(total)),
        expanded=False,
    ):
        rows = []
        for r in missing_rows:
            rows.append({
                "Mã hàng":    _fmt(r.item_code),
                "Mô tả":      _fmt(r.description),
                "Số lượng":   _fmt_num(r.receipt_qty),
                "Đơn giá":    _fmt_num(r.receipt_unit_price),
                "Tiền thiếu": _fmt_num(r.missing_amount if r.missing_amount is not None else r.receipt_amount),
                "P/O No":     _fmt(r.po_no),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ── Processing (step 2) ───────────────────────────────────────────────────────
def _do_processing():
    inv_bytes = st.session_state.get("_inv_bytes", b"")
    rcp_bytes = st.session_state.get("_rcp_bytes", b"")
    inv_name  = st.session_state.get("_inv_name", "invoice.pdf")
    rcp_name  = st.session_state.get("_rcp_name", "receipt.xlsx")

    proc_ph   = st.empty()
    extractor = InvoiceExtractor()
    parser    = ReceiptParser()
    engine    = CompareEngine()
    exporter  = ExcelExporter()

    with tempfile.TemporaryDirectory() as tmp_dir:
        inv_path = Path(tmp_dir) / "invoice.pdf"
        rcp_path = Path(tmp_dir) / "receipt.xlsx"
        out_path = Path(tmp_dir) / "result.xlsx"
        inv_path.write_bytes(inv_bytes)
        rcp_path.write_bytes(rcp_bytes)

        proc_ph.markdown(_proc_card_html(active=0), unsafe_allow_html=True)
        invoice_text = extractor._read_pdf_text(str(inv_path))

        proc_ph.markdown(_proc_card_html(active=1), unsafe_allow_html=True)
        raw          = extractor._extract_with_openai(invoice_text)
        norm         = extractor._normalize_payload(raw)
        from invoice_reconciliation.models import InvoiceData
        invoice_data = InvoiceData.model_validate(norm)

        dbg = []
        for it in invoice_data.items[:3]:
            dbg.append("HDA code=%r qty=%s price=%s" % (it.item_code, it.quantity, it.unit_price))

        proc_ph.markdown(_proc_card_html(active=2), unsafe_allow_html=True)
        receipt_data = parser.parse(str(rcp_path))

        for it in receipt_data.items[:3]:
            dbg.append("RCP code=%r qty=%s price=%s" % (it.item_code, it.quantity, it.unit_price))
        st.session_state["_debug_extract"] = "\n".join(dbg)

        proc_ph.markdown(_proc_card_html(active=3), unsafe_allow_html=True)
        r = engine.compare(invoice_data, receipt_data)

        proc_ph.markdown(_proc_card_html(active=4), unsafe_allow_html=True)
        exporter.export(r, str(out_path))
        out_bytes = out_path.read_bytes()

        proc_ph.markdown(_proc_card_html(active=-1), unsafe_allow_html=True)

    _add_to_history(inv_name, rcp_name, r, out_bytes)
    st.session_state["_processing"]    = False
    st.session_state["_single_result"] = r
    st.session_state["_single_output"] = out_bytes
    st.rerun()


# ── Single mode ───────────────────────────────────────────────────────────────
def _run_single_mode():
    result     = st.session_state.get("_single_result")
    processing = st.session_state.get("_processing", False)
    step = 3 if result else (2 if processing else 1)

    st.markdown(
        '<div style="padding:14px 16px;background:#fff3cd;border:1px solid #ffc107;'
        'border-radius:8px;font-size:14px;margin-bottom:12px;color:#856404">'
        '⚠️ Tool chỉ hỗ trợ mang tính tương đối, không đảm bảo chính xác 100%</div>',
        unsafe_allow_html=True,
    )
    st.markdown(_stepper_html(step), unsafe_allow_html=True)
    st.write("")

    if processing:
        _do_processing()
        return

    if not result:
        col_left, col_right = st.columns(2, gap="medium")

        with col_left:
            st.markdown(
                '<div class="upload-col-wrap">'
                '<div class="upload-icon-ring pdf">picture_as_pdf</div>'
                '<div class="upload-col-title">Hóa đơn (PDF)</div>'
                '<div class="upload-col-hint">Kéo thả hoặc nhấn để chọn</div>'
                '<div class="upload-col-limit">Giới hạn 200MB mỗi file</div>'
                '</div>',
                unsafe_allow_html=True,
            )
            invoice_file = st.file_uploader(
                "Hóa đơn PDF", type=["pdf"], label_visibility="collapsed", key="inv_file"
            )

        with col_right:
            st.markdown(
                '<div class="upload-col-wrap">'
                '<div class="upload-icon-ring excel">table_chart</div>'
                '<div class="upload-col-title">Phiếu nhận hàng (Excel)</div>'
                '<div class="upload-col-hint">Kéo thả hoặc nhấn để chọn</div>'
                '<div class="upload-col-limit">Giới hạn 200MB mỗi file</div>'
                '</div>',
                unsafe_allow_html=True,
            )
            receipt_file = st.file_uploader(
                "Phiếu nhận hàng Excel", type=["xlsx"], label_visibility="collapsed", key="rcp_file"
            )

        if invoice_file:
            st.markdown(
                '<div class="status-box ok"><span class="status-icon">check_circle</span>'
                '<span>Đã chọn: <b>%s</b></span></div>' % invoice_file.name,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="status-box"><span class="status-icon">info</span>'
                '<span>Chưa chọn file hóa đơn.</span></div>',
                unsafe_allow_html=True,
            )

        if receipt_file:
            st.markdown(
                '<div class="status-box ok"><span class="status-icon">check_circle</span>'
                '<span>Đã chọn: <b>%s</b></span></div>' % receipt_file.name,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="status-box"><span class="status-icon">info</span>'
                '<span>Chưa chọn file phiếu nhận hàng.</span></div>',
                unsafe_allow_html=True,
            )

        st.write("")
        if st.button("Tạo kết quả đối chiếu", type="primary", use_container_width=True):
            if not invoice_file:
                st.error("Chưa chọn file Hóa đơn (PDF).")
                return
            if not receipt_file:
                st.error("Chưa chọn file Phiếu nhận hàng (.xlsx).")
                return
            st.session_state["_inv_bytes"]  = invoice_file.getvalue()
            st.session_state["_rcp_bytes"]  = receipt_file.getvalue()
            st.session_state["_inv_name"]   = invoice_file.name
            st.session_state["_rcp_name"]   = receipt_file.name
            st.session_state["_processing"] = True
            st.rerun()

    else:
        s = result.summary
        if s.mismatch_count == 0 and s.missing_count == 0:
            st.success("Kết quả: %d/%d dòng khớp hoàn toàn." % (
                s.matched_count, s.matched_count + s.mismatch_count + s.missing_count
            ))
        else:
            st.warning("Có %d dòng lệch / %d dòng thiếu cần kiểm tra lại." % (
                s.mismatch_count, s.missing_count
            ))

        render_summary(result)

        dbg = st.session_state.get("_debug_extract", "")
        if dbg:
            with st.expander("[Debug] Kiểm tra dữ liệu trích xuất", expanded=False):
                st.code(dbg)

        st.markdown('<div class="sec-title">Chi tiết đối chiếu</div>', unsafe_allow_html=True)
        render_result_table(result)
        render_missing_section(result)

        st.write("")
        col_dl, col_new = st.columns([3, 1], gap="medium")
        with col_dl:
            st.download_button(
                label="Tải file kết quả (.xlsx)",
                data=st.session_state["_single_output"],
                file_name="KetQuaDoiChieu.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with col_new:
            if st.button("Kiểm tra mới", use_container_width=True):
                st.session_state.pop("_single_result", None)
                st.session_state.pop("_single_output", None)
                st.rerun()


# ── Batch mode ────────────────────────────────────────────────────────────────
def _overall_bar_html(done: int, total: int) -> str:
    pct = int(done / total * 100) if total else 0
    return (
        '<div class="batch-overall-bar">'
        '<span class="bob-label">Tiến độ tổng thể</span>'
        '<div class="bob-bar-wrap"><div class="bob-bar-fill" style="width:%d%%"></div></div>'
        '<span class="bob-count">%d/%d</span>'
        '</div>' % (pct, done, total)
    )


def _show_batch_upload():
    st.info("PDF[1]+Excel[1], PDF[2]+Excel[2], ... — ghép theo thứ tự upload.")
    col_left, col_right = st.columns(2, gap="medium")
    with col_left:
        st.markdown(
            '<div class="upload-col-wrap">'
            '<div class="upload-icon-ring pdf">picture_as_pdf</div>'
            '<div class="upload-col-title">Nhiều Hóa đơn (PDF)</div>'
            '<div class="upload-col-hint">Chọn nhiều file cùng lúc</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        invoice_files = st.file_uploader(
            "PDFs", type=["pdf"], accept_multiple_files=True,
            label_visibility="collapsed", key="batch_inv",
        )
    with col_right:
        st.markdown(
            '<div class="upload-col-wrap">'
            '<div class="upload-icon-ring excel">table_chart</div>'
            '<div class="upload-col-title">Nhiều Phiếu nhận hàng (Excel)</div>'
            '<div class="upload-col-hint">Chọn nhiều file cùng lúc</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        receipt_files = st.file_uploader(
            "Excels", type=["xlsx"], accept_multiple_files=True,
            label_visibility="collapsed", key="batch_rcp",
        )

    n_inv = len(invoice_files) if invoice_files else 0
    n_rec = len(receipt_files) if receipt_files else 0
    if n_inv > 0 or n_rec > 0:
        if n_inv != n_rec:
            st.warning("Số file PDF (%d) và Excel (%d) không bằng nhau." % (n_inv, n_rec))
        else:
            st.info("Sẵn sàng xử lý %d cặp file." % n_inv)

    st.write("")
    if st.button("Xử lý tất cả", type="primary", use_container_width=True):
        if n_inv == 0:
            st.error("Chưa chọn file nào.")
            return
        if n_inv != n_rec:
            st.error("Số file PDF và Excel phải bằng nhau.")
            return
        st.session_state["_batch_inv_list"]   = [(f.getvalue(), f.name) for f in invoice_files]
        st.session_state["_batch_rcp_list"]   = [(f.getvalue(), f.name) for f in receipt_files]
        st.session_state["_batch_processing"] = True
        st.rerun()


def _do_batch_processing():
    from invoice_reconciliation.models import InvoiceData

    inv_list = st.session_state.get("_batch_inv_list", [])
    rcp_list = st.session_state.get("_batch_rcp_list", [])
    n        = len(inv_list)

    pair_hdr_ph = st.empty()
    proc_ph     = st.empty()
    overall_ph  = st.empty()
    results     = []

    for idx, ((inv_bytes, inv_name), (rcp_bytes, rcp_name)) in enumerate(zip(inv_list, rcp_list)):
        pair_hdr_ph.markdown(
            '<div class="batch-pair-hdr">'
            '<span class="bph-badge">Cặp %d/%d</span>'
            '<span class="bph-names">'
            '<span class="bph-inv">%s</span>'
            '<span class="bph-sep">+</span>'
            '<span class="bph-rcp">%s</span>'
            '</span>'
            '</div>' % (idx + 1, n, inv_name, rcp_name),
            unsafe_allow_html=True,
        )
        overall_ph.markdown(_overall_bar_html(idx, n), unsafe_allow_html=True)

        with tempfile.TemporaryDirectory() as tmp_dir:
            inv_path = Path(tmp_dir) / "invoice.pdf"
            rcp_path = Path(tmp_dir) / "receipt.xlsx"
            out_path = Path(tmp_dir) / "result.xlsx"
            inv_path.write_bytes(inv_bytes)
            rcp_path.write_bytes(rcp_bytes)

            try:
                extractor = InvoiceExtractor()
                parser    = ReceiptParser()
                engine    = CompareEngine()
                exporter  = ExcelExporter()

                proc_ph.markdown(_proc_card_html(active=0), unsafe_allow_html=True)
                invoice_text = extractor._read_pdf_text(str(inv_path))

                proc_ph.markdown(_proc_card_html(active=1), unsafe_allow_html=True)
                raw          = extractor._extract_with_openai(invoice_text)
                norm         = extractor._normalize_payload(raw)
                invoice_data = InvoiceData.model_validate(norm)

                proc_ph.markdown(_proc_card_html(active=2), unsafe_allow_html=True)
                receipt_data = parser.parse(str(rcp_path))

                proc_ph.markdown(_proc_card_html(active=3), unsafe_allow_html=True)
                r = engine.compare(invoice_data, receipt_data)

                proc_ph.markdown(_proc_card_html(active=4), unsafe_allow_html=True)
                exporter.export(r, str(out_path))
                out_bytes_pair = out_path.read_bytes()

                proc_ph.markdown(_proc_card_html(active=-1), unsafe_allow_html=True)

                _add_to_history(inv_name, rcp_name, r, out_bytes_pair)
                results.append({
                    "inv_name": inv_name, "rcp_name": rcp_name,
                    "result": r, "output_bytes": out_bytes_pair, "error": None,
                })
            except Exception as exc:
                results.append({
                    "inv_name": inv_name, "rcp_name": rcp_name,
                    "result": None, "output_bytes": None, "error": str(exc),
                })

    pair_hdr_ph.markdown(
        '<div class="batch-pair-hdr done">'
        '<span class="bph-badge done">Hoàn tất</span>'
        '<span class="bph-names">Đã xử lý tất cả %d cặp file</span>'
        '</div>' % n,
        unsafe_allow_html=True,
    )
    overall_ph.markdown(_overall_bar_html(n, n), unsafe_allow_html=True)

    st.session_state["_batch_processing"] = False
    st.session_state["_batch_results"]    = results
    st.rerun()


def _show_batch_results(results):
    n         = len(results)
    ok_count  = sum(1 for item in results if item["result"] and item["result"].summary.mismatch_count == 0 and item["result"].summary.missing_count == 0)
    err_count = sum(1 for item in results if item["error"])

    if err_count == 0 and ok_count == n:
        st.success("Hoàn tất: %d/%d cặp khớp hoàn toàn." % (ok_count, n))
    else:
        st.warning("Hoàn tất %d cặp — %d khớp hoàn toàn, %d cần kiểm tra lại." % (n, ok_count, n - ok_count))

    col_new, col_zip = st.columns([1, 2], gap="medium")
    with col_new:
        if st.button("Kiểm tra đợt mới", use_container_width=True):
            st.session_state.pop("_batch_results", None)
            st.session_state["_batch_processing"] = False
            st.rerun()
    with col_zip:
        if n > 1:
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for i, item in enumerate(results):
                    if item["output_bytes"]:
                        zf.writestr(
                            "Cap%d_%s.xlsx" % (i + 1, item["inv_name"].replace(".pdf", "")),
                            item["output_bytes"],
                        )
            zip_buf.seek(0)
            st.download_button(
                label="Tải tất cả (ZIP)",
                data=zip_buf.getvalue(),
                file_name="KetQua_HangLoat.zip",
                mime="application/zip",
                use_container_width=True,
            )

    st.markdown('<div class="sec-title">Kết quả từng cặp file</div>', unsafe_allow_html=True)

    for i, item in enumerate(results):
        r  = item["result"]
        ok = r and r.summary.mismatch_count == 0 and r.summary.missing_count == 0
        if item["error"]:
            lbl = "❌  Cặp %d: %s + %s" % (i + 1, item["inv_name"], item["rcp_name"])
        elif ok:
            lbl = "✅  Cặp %d: %s  |  Khớp: %d  Lệch: %d  Thiếu: %d" % (
                i + 1, item["inv_name"],
                r.summary.matched_count, r.summary.mismatch_count, r.summary.missing_count,
            )
        else:
            lbl = "⚠️  Cặp %d: %s  |  Khớp: %d  Lệch: %d  Thiếu: %d" % (
                i + 1, item["inv_name"],
                r.summary.matched_count, r.summary.mismatch_count, r.summary.missing_count,
            )

        with st.expander(lbl, expanded=(i == 0)):
            if item["error"]:
                st.error("Lỗi xử lý: %s" % item["error"])
                continue
            render_summary(r)
            st.markdown('<div class="sec-title">Chi tiết đối chiếu</div>', unsafe_allow_html=True)
            render_result_table(r)
            render_missing_section(r)
            st.write("")
            st.download_button(
                label="Tải kết quả cặp %d (.xlsx)" % (i + 1),
                data=item["output_bytes"],
                file_name="KetQua_Cap%d_%s.xlsx" % (i + 1, item["inv_name"].replace(".pdf", "")),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="batch_dl_%d" % i,
                use_container_width=True,
            )


def _run_batch_mode():
    batch_results    = st.session_state.get("_batch_results")
    batch_processing = st.session_state.get("_batch_processing", False)
    step = 3 if batch_results else (2 if batch_processing else 1)

    st.markdown(
        '<div style="padding:14px 16px;background:#fff3cd;border:1px solid #ffc107;'
        'border-radius:8px;font-size:14px;margin-bottom:12px;color:#856404">'
        '⚠️ Tool chỉ hỗ trợ mang tính tương đối, không đảm bảo chính xác 100%</div>',
        unsafe_allow_html=True,
    )
    st.markdown(_stepper_html(step), unsafe_allow_html=True)
    st.write("")

    if batch_processing:
        _do_batch_processing()
    elif not batch_results:
        _show_batch_upload()
    else:
        _show_batch_results(batch_results)


# ── History view ──────────────────────────────────────────────────────────────
def _render_history():
    st.markdown('<div class="sec-title">Lịch sử đối chiếu</div>', unsafe_allow_html=True)
    history = st.session_state.get("_history", [])
    if not history:
        st.info("Chưa có lần đối chiếu nào trong phiên này.")
        return

    for i, h in enumerate(history):
        ok        = h["mismatch"] == 0 and h["missing"] == 0
        badge_cls = "ok" if ok else "err"
        badge_txt = "Khớp hoàn toàn" if ok else "Có lệch / thiếu"
        summary   = "Khớp: %d  Lệch: %d  Thiếu: %d" % (h["matched"], h["mismatch"], h["missing"])
        st.markdown(
            '<div class="hist-card">'
            f'<div class="hist-ts">{h["ts"]}</div>'
            '<div class="hist-files">'
            f'<div class="hist-inv">{h["invoice"]}</div>'
            f'<div class="hist-rcp">{h["receipt"]}</div>'
            f'<div style="font-size:12px;color:var(--outline);margin-top:2px">{summary}</div>'
            '</div>'
            f'<span class="hist-badge {badge_cls}">{badge_txt}</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.download_button(
            label="Tải kết quả",
            data=h["output_bytes"],
            file_name="DoiChieu_%s.xlsx" % h["ts"].replace("/", "-").replace(" ", "_").replace(":", ""),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="hist_dl_%d" % i,
        )


# ── Support view ──────────────────────────────────────────────────────────────
def _render_support():
    st.markdown(
        '<div class="support-card">'
        '<div class="support-logo">receipt_long</div>'
        '<div class="support-name">Đối chiếu Hóa đơn</div>'
        '<div class="support-version">Phiên bản 1.0.0</div>'
        '<div class="support-row"><span class="support-label">Phát triển bởi</span><span class="support-value">TrungNP71</span></div>'
        '<div class="support-row"><span class="support-label">Mô hình AI</span><span class="support-value">GPT-4.1 mini</span></div>'
        '<div class="support-row"><span class="support-label">Nền tảng</span><span class="support-value">Streamlit + Python 3.12</span></div>'
        '<div class="support-copy">© 2026 TrungNP71 · All rights reserved</div>'
        '</div>',
        unsafe_allow_html=True,
    )


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    _load_env()
    st.set_page_config(
        page_title="Đối chiếu Hóa đơn",
        page_icon="🧾",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(_TOP_NAV, unsafe_allow_html=True)

    if not os.getenv("OPENAI_API_KEY"):
        st.error("Chưa thấy OPENAI_API_KEY. Vui lòng thêm key vào file .env trước khi mở app.")
        st.stop()

    if "_view" not in st.session_state:
        st.session_state["_view"] = "upload"

    view = st.session_state["_view"]

    # ── Sidebar ──
    with st.sidebar:
        st.markdown('<div class="sb-title">Trang chủ</div>', unsafe_allow_html=True)

        if st.button("+ Kiểm tra mới", key="_sb_new", type="primary", use_container_width=True):
            st.session_state["_view"] = "upload"
            st.session_state.pop("_single_result", None)
            st.session_state.pop("_single_output", None)
            st.session_state.pop("_batch_results", None)
            st.session_state["_processing"]       = False
            st.session_state["_batch_processing"] = False
            st.rerun()

        st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)

        if st.button("🕐  Lịch sử", key="_sb_hist", use_container_width=True):
            st.session_state["_view"] = "history"
            st.rerun()

        if st.button("❓  Hỗ trợ", key="_sb_sup", use_container_width=True):
            st.session_state["_view"] = "support"
            st.rerun()

        st.markdown('<hr class="sb-divider">', unsafe_allow_html=True)

    # ── Main content routing ──
    if view == "history":
        _render_history()
    elif view == "support":
        _render_support()
    else:
        mode = st.radio(
            "Chế độ",
            ["1 cặp file", "Nhiều cặp file (Hàng loạt)"],
            horizontal=True,
            label_visibility="collapsed",
        )
        st.write("")
        if mode == "1 cặp file":
            _run_single_mode()
        else:
            _run_batch_mode()


if __name__ == "__main__":
    main()
