"""Merge all PDFs from docs/pdf/ (+ any top-level docs/*.pdf) into a single PDF with bookmarks."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader, PdfWriter

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
PDF_DIR = DOCS / "pdf"
OUTPUT = DOCS / "Dharma-RAG_ALL_DOCS.pdf"


def collect_pdfs() -> list[Path]:
    files: list[Path] = []
    if PDF_DIR.is_dir():
        files.extend(sorted(PDF_DIR.glob("*.pdf")))
    for p in sorted(DOCS.glob("*.pdf")):
        if p.resolve() != OUTPUT.resolve() and p not in files:
            files.append(p)
    return files


def main() -> int:
    pdfs = collect_pdfs()
    if not pdfs:
        print("No PDFs found")
        return 1

    print(f"Merging {len(pdfs)} PDFs -> {OUTPUT.name}")
    writer = PdfWriter()
    total_pages = 0
    for i, pdf_path in enumerate(pdfs, 1):
        reader = PdfReader(str(pdf_path))
        page_count = len(reader.pages)
        start_page = total_pages
        for page in reader.pages:
            writer.add_page(page)
        total_pages += page_count
        writer.add_outline_item(title=pdf_path.stem, page_number=start_page)
        print(
            f"  [{i:2d}/{len(pdfs)}] {pdf_path.name:55s} +{page_count} pages (total {total_pages})"
        )

    with open(OUTPUT, "wb") as f:
        writer.write(f)
    size_mb = OUTPUT.stat().st_size / 1024 / 1024
    print(f"\nDone. {total_pages} pages, {size_mb:.1f} MB -> {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
