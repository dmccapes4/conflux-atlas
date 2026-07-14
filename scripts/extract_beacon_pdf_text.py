#!/usr/bin/env python3
"""Extract text sidecars from the beacon PDF library.

For every ``data/raw/beacons/<beacon>/*.pdf`` writes
``<beacon>/_text/<stem>.txt`` and classifies extractability:

  born_digital — usable text layer (mean chars/page >= threshold);
  needs_ocr    — scanned or image-only (text layer thin/absent);
  error        — unreadable / encrypted.

This is the deterministic front half of the ingestion forge: the HMI
window harness (HYPOTHESIS_HMI_WINDOWS.md) decides which model reads
these sidecars at which batch size; OCR is a separate pass for the
``needs_ocr`` set (ocrmypdf/tesseract), never silently mixed in.

Usage:
  python scripts/extract_beacon_pdf_text.py [--min-chars-per-page 200] [--force]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BEACONS = ROOT / "data" / "raw" / "beacons"
OUT = ROOT / "data-validation-reports"


def extract_pdf(path: Path) -> tuple[str, list[int]]:
    """Return (full_text, per-page char counts). Raises on hard failure."""
    from pypdf import PdfReader

    reader = PdfReader(path)
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:  # noqa: BLE001 — record, don't crash the pass
            raise RuntimeError(f"encrypted: {exc}") from exc
    texts: list[str] = []
    counts: list[int] = []
    for page in reader.pages:
        try:
            t = page.extract_text() or ""
        except Exception:  # noqa: BLE001 — a bad page must not kill the doc
            t = ""
        texts.append(t)
        counts.append(len(t.strip()))
    return "\n\f\n".join(texts), counts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-chars-per-page", type=int, default=200)
    ap.add_argument("--force", action="store_true", help="re-extract existing sidecars")
    args = ap.parse_args()

    if not BEACONS.exists():
        sys.exit(f"no beacon library at {BEACONS}")

    ocr_tool = shutil.which("ocrmypdf") or shutil.which("tesseract")
    rows: list[dict] = []
    for pdf in sorted(BEACONS.rglob("*.pdf")):
        beacon = pdf.parent.name
        sidecar = pdf.parent / "_text" / (pdf.stem + ".txt")
        row: dict = {
            "beacon": beacon,
            "pdf": str(pdf.relative_to(ROOT)),
            "sidecar": str(sidecar.relative_to(ROOT)),
        }
        try:
            if sidecar.exists() and not args.force:
                text = sidecar.read_text(encoding="utf-8")
                pages = text.split("\f")
                counts = [len(p.strip()) for p in pages]
            else:
                text, counts = extract_pdf(pdf)
                sidecar.parent.mkdir(parents=True, exist_ok=True)
                sidecar.write_text(text, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            row.update(status="error", error=str(exc)[:200])
            rows.append(row)
            print(f"❌ {pdf.name}: {str(exc)[:120]}", flush=True)
            continue
        n_pages = max(1, len(counts))
        mean_chars = sum(counts) / n_pages
        textless = sum(1 for c in counts if c < 20)
        status = (
            "born_digital"
            if mean_chars >= args.min_chars_per_page
            else "needs_ocr"
        )
        row.update(
            status=status,
            pages=len(counts),
            chars=sum(counts),
            mean_chars_per_page=round(mean_chars, 1),
            textless_pages=textless,
        )
        rows.append(row)
        icon = "📄" if status == "born_digital" else "🔍"
        print(
            f"{icon} {beacon}/{pdf.name}: {status} "
            f"({len(counts)}p · {round(mean_chars)} chars/p)",
            flush=True,
        )

    summary = {
        "pdfs": len(rows),
        "born_digital": sum(1 for r in rows if r["status"] == "born_digital"),
        "needs_ocr": sum(1 for r in rows if r["status"] == "needs_ocr"),
        "error": sum(1 for r in rows if r["status"] == "error"),
        "total_chars_extracted": sum(r.get("chars", 0) for r in rows),
        "min_chars_per_page": args.min_chars_per_page,
        "ocr_tool_available": ocr_tool,
        "by_beacon": {},
        "files": rows,
    }
    for r in rows:
        b = summary["by_beacon"].setdefault(
            r["beacon"], {"pdfs": 0, "born_digital": 0, "needs_ocr": 0, "error": 0}
        )
        b["pdfs"] += 1
        b[r["status"]] += 1

    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / "BEACON_PDF_TEXT.json"
    out_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(
        f"\n🏁 {summary['pdfs']} PDFs: {summary['born_digital']} born-digital, "
        f"{summary['needs_ocr']} need OCR, {summary['error']} errors "
        f"({summary['total_chars_extracted']:,} chars extracted)"
    )
    if summary["needs_ocr"] and not ocr_tool:
        print("⚠️  no ocrmypdf/tesseract on PATH — OCR pass deferred")
    print(f"💾 wrote {out_path}")


if __name__ == "__main__":
    main()
