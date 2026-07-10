"""Invoice File Organizer — scan, extract, rename, and sort invoice/receipt files.

Takes a chaotic folder of PDFs, images, and documents and produces:
  1. Renamed files: YYYY-MM-DD Vendor - Invoice - Description.ext
  2. Folder structure: Year/Category/Vendor/
  3. Summary CSV: date, vendor, invoice_number, description, amount, category, file_path

The organizer does NOT move original files by default — it copies to the output
directory, preserving originals. Use --move to move instead.

Usage:
  python3 scripts/invoice_file_organizer.py /path/to/messy/folder [--output /path/to/organized] [--move] [--dry-run]

Construction document types recognized:
  - Standard invoices/receipts (any vendor)
  - AIA G702/G703 pay applications
  - Change orders
  - Submittals
  - COIs (Certificates of Insurance)
  - Lien waivers
"""

import argparse
import csv
import hashlib
import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple


SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".gif", ".txt", ".eml"}

# Patterns for construction document identification
CONSTRUCTION_DOC_PATTERNS = {
    "aia_g702": {
        "pattern": re.compile(r"G702|G-702|application.*payment|continuation.*sheet", re.I),
        "category": "Pay Applications",
        "description": "AIA G702 Payment Application",
    },
    "aia_g703": {
        "pattern": re.compile(r"G703|G-703|continuation.*sheet|schedule.*values", re.I),
        "category": "Pay Applications",
        "description": "AIA G703 Continuation Sheet",
    },
    "change_order": {
        "pattern": re.compile(r"change.*order|CO\s*#|proposal.*request|directive", re.I),
        "category": "Change Orders",
        "description": "Change Order",
    },
    "submittal": {
        "pattern": re.compile(r"submittal|submittal.*transmittal|transmittal", re.I),
        "category": "Submittals",
        "description": "Submittal",
    },
    "coi": {
        "pattern": re.compile(r"certificate.*insurance|COI|ACORD\s*25", re.I),
        "category": "Insurance",
        "description": "Certificate of Insurance",
    },
    "lien_waiver": {
        "pattern": re.compile(r"lien.*waiver|waiver.*lien|conditional.*waiver|unconditional.*waiver", re.I),
        "category": "Legal",
        "description": "Lien Waiver",
    },
    "w9": {
        "pattern": re.compile(r"W-?9|request.*taxpayer|TIN", re.I),
        "category": "Tax Forms",
        "description": "W-9 Tax Form",
    },
}

# Standard invoice extraction patterns
INVOICE_PATTERNS = {
    "invoice_number": re.compile(r"(?:invoice|inv|receipt)\s*(?:#|no\.?|number)?\s*[:#]?\s*([A-Z0-9\-/]{3,20})", re.I),
    "date": re.compile(r"(?:date|dated|issued?)\s*[:#]?\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{4}[/\-]\d{1,2}[/\-]\d{1,2})", re.I),
    "amount": re.compile(r"(?:total|amount\s*due|balance\s*due|grand\s*total)\s*[:#]?\s*\$?\s*([\d,]+\.?\d{0,2})", re.I),
    "vendor": re.compile(r"(?:from|biller|vendor|company)\s*[:#]?\s*(.{2,50})", re.I),
}

# Common vendor name normalization
VENDOR_NORMALIZATIONS = {
    "home depot": "Home Depot",
    "lowes": "Lowes",
    "home depot usa": "Home Depot",
    "amazon": "Amazon",
    "staples": "Staples",
    "grainger": "Grainger",
    "fastenal": "Fastenal",
    "ferguson": "Ferguson",
    "supplyhouse": "SupplyHouse",
}


@dataclass
class ExtractedInvoice:
    """Extracted metadata from an invoice/receipt file."""
    original_path: str
    vendor: str = "Unknown"
    invoice_number: str = ""
    date: str = ""
    amount: str = ""
    description: str = ""
    category: str = "Uncategorized"
    doc_type: str = "invoice"  # invoice, aia_g702, change_order, etc.
    needs_review: bool = False
    review_reason: str = ""


def file_hash(path: str) -> str:
    """Compute SHA-256 hash of a file for duplicate detection."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_vendor(name: str) -> str:
    """Normalize vendor name to Title Case, handle common variations."""
    name = name.strip().rstrip(",.")
    lower = name.lower()
    if lower in VENDOR_NORMALIZATIONS:
        return VENDOR_NORMALIZATIONS[lower]
    # Title case, but preserve LLC, Inc, etc.
    parts = name.split()
    result = []
    for p in parts:
        if p.upper() in ("LLC", "INC", "CO", "CORP", "LTD", "LP"):
            result.append(p.upper())
        else:
            result.append(p.capitalize())
    return " ".join(result)


def parse_date(date_str: str) -> Optional[str]:
    """Parse various date formats and return YYYY-MM-DD."""
    if not date_str:
        return None
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%m-%d-%Y", "%m-%d-%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def extract_from_filename(filename: str) -> Dict:
    """Extract clues from filename when content extraction isn't available."""
    result = {}
    name = Path(filename).stem

    # Try to find a date in the filename
    date_match = re.search(r"(\d{4})[-_](\d{1,2})[-_](\d{1,2})|(\d{1,2})[-_](\d{1,2})[-_](\d{2,4})", name)
    if date_match:
        raw = date_match.group(0).replace("_", "-")
        parsed = parse_date(raw)
        if parsed:
            result["date"] = parsed

    # Try vendor name from common patterns
    vendor_match = re.match(r"(?:invoice|inv|receipt)_([a-zA-Z]+)", name, re.I)
    if vendor_match:
        result["vendor"] = vendor_match.group(1)

    return result


def identify_construction_doc(text: str) -> Optional[Tuple[str, str, str]]:
    """Check if text matches a construction document type.
    Returns (doc_type, category, description) or None.
    """
    for doc_type, config in CONSTRUCTION_DOC_PATTERNS.items():
        if config["pattern"].search(text):
            return (doc_type, config["category"], config["description"])
    return None


def extract_invoice_metadata(file_path: str, text_content: str = "") -> ExtractedInvoice:
    """Extract metadata from invoice file. Uses text_content if provided (from OCR/PDF extraction)."""
    result = ExtractedInvoice(original_path=file_path)

    # Check for construction document types first
    if text_content:
        construction = identify_construction_doc(text_content)
        if construction:
            result.doc_type, result.category, result.description = construction

        # Extract standard invoice fields
        for field_name, pattern in INVOICE_PATTERNS.items():
            match = pattern.search(text_content)
            if match:
                value = match.group(1).strip()
                if field_name == "date":
                    parsed = parse_date(value)
                    if parsed:
                        setattr(result, field_name, parsed)
                elif field_name == "vendor":
                    result.vendor = normalize_vendor(value)
                else:
                    setattr(result, field_name, value)

    # Fall back to filename clues
    filename_clues = extract_from_filename(os.path.basename(file_path))
    if not result.date and "date" in filename_clues:
        result.date = filename_clues["date"]
    if not result.vendor or result.vendor == "Unknown":
        if "vendor" in filename_clues:
            result.vendor = normalize_vendor(filename_clues["vendor"])

    # If we still don't have enough data, flag for review
    if result.vendor == "Unknown" and not result.date:
        result.needs_review = True
        result.review_reason = "Could not extract vendor or date from file"
    elif result.vendor == "Unknown":
        result.needs_review = True
        result.review_reason = "Could not extract vendor name"
    elif not result.date:
        result.needs_review = True
        result.review_reason = "Could not extract date"

    # Use file modification date as last-resort date (only if file exists)
    if not result.date and os.path.exists(file_path):
        mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
        result.date = mtime.strftime("%Y-%m-%d")
        if not result.needs_review:
            result.needs_review = True
            result.review_reason = "Date inferred from file modification time"

    if not result.description:
        result.description = result.doc_type.replace("_", " ").title()

    return result


def build_output_path(invoice: ExtractedInvoice, output_root: Path) -> Path:
    """Build the output path: Year/Category/Vendor/filename.ext"""
    year = invoice.date[:4] if invoice.date and len(invoice.date) >= 4 else "Unknown-Date"
    vendor = invoice.vendor if invoice.vendor != "Unknown" else "Unknown-Vendor"
    category = invoice.category

    # Sanitize for filesystem
    vendor_safe = re.sub(r"[^\w\s.-]", "", vendor).strip() or "Unknown-Vendor"
    return output_root / year / category / vendor_safe


def build_filename(invoice: ExtractedInvoice, original_ext: str) -> str:
    """Build standardized filename: YYYY-MM-DD Vendor - Invoice - Description.ext"""
    date_part = invoice.date or "0000-00-00"
    vendor = invoice.vendor if invoice.vendor != "Unknown" else "Unknown"
    desc = invoice.description or invoice.doc_type

    # Sanitize
    vendor_safe = re.sub(r"[^\w\s.-]", "", vendor).strip()
    desc_safe = re.sub(r"[^\w\s.-]", "", desc).strip()

    filename = f"{date_part} {vendor_safe} - Invoice - {desc_safe}{original_ext}"
    return filename


def organize_invoices(input_dir: str, output_dir: str, move: bool = False, dry_run: bool = False) -> Dict:
    """Scan input directory, extract metadata, organize files into output directory.

    Returns summary dict with counts, file list, and review items.
    """
    input_path = Path(input_dir).resolve()
    output_path = Path(output_dir).resolve()

    if not input_path.exists():
        raise FileNotFoundError(f"Input directory not found: {input_path}")

    # Find all supported files
    files = []
    for f in input_path.rglob("*"):
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(str(f))

    # Track hashes for dedup
    seen_hashes: Dict[str, str] = {}
    duplicates: List[Dict] = []
    organized: List[ExtractedInvoice] = []
    review_items: List[Dict] = []
    errors: List[Dict] = []

    for file_path in files:
        try:
            # Compute hash for dedup
            h = file_hash(file_path)
            if h in seen_hashes:
                duplicates.append({
                    "file": file_path,
                    "duplicate_of": seen_hashes[h],
                })
                continue
            seen_hashes[h] = file_path

            # Extract metadata (text content would come from OCR/PDF reader in full impl)
            invoice = extract_invoice_metadata(file_path)

            # Build output path
            dest_dir = build_output_path(invoice, output_path)
            original_ext = Path(file_path).suffix.lower()
            dest_filename = build_filename(invoice, original_ext)
            dest_path = dest_dir / dest_filename

            # Handle filename collisions
            if dest_path.exists():
                base = dest_path.stem
                dest_path = dest_dir / f"{base} (1){original_ext}"

            invoice.original_path = file_path
            # Store relative output path for the CSV
            invoice.description = str(dest_path.relative_to(output_path))

            if not dry_run:
                dest_dir.mkdir(parents=True, exist_ok=True)
                if move:
                    shutil.move(file_path, dest_path)
                else:
                    shutil.copy2(file_path, dest_path)

            organized.append(invoice)

            if invoice.needs_review:
                review_items.append({
                    "file": file_path,
                    "reason": invoice.review_reason,
                    "vendor": invoice.vendor,
                    "date": invoice.date,
                })

        except Exception as e:
            errors.append({"file": file_path, "error": str(e)})

    # Generate summary CSV
    csv_path = output_path / "invoice-summary.csv"
    if not dry_run:
        output_path.mkdir(parents=True, exist_ok=True)
        with open(csv_path, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["Date", "Vendor", "Invoice Number", "Description", "Amount", "Category", "File Path"])
            for inv in organized:
                writer.writerow([
                    inv.date,
                    inv.vendor,
                    inv.invoice_number,
                    inv.description,
                    inv.amount,
                    inv.category,
                    inv.original_path,
                ])

    return {
        "total_files_found": len(files),
        "files_organized": len(organized),
        "duplicates_found": len(duplicates),
        "needs_review": len(review_items),
        "errors": len(errors),
        "duplicates": duplicates,
        "review_items": review_items,
        "errors_detail": errors,
        "csv_path": str(csv_path) if not dry_run else "(dry run - not written)",
        "output_dir": str(output_path),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Organize chaotic invoice/receipt folders into a clean, tax-ready filing system."
    )
    parser.add_argument("input_dir", help="Directory containing disorganized invoice files")
    parser.add_argument("--output", "-o", default=None, help="Output directory (default: input_dir/organized)")
    parser.add_argument("--move", action="store_true", help="Move files instead of copying (preserves originals by default)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without moving/copying files")
    args = parser.parse_args()

    output_dir = args.output or os.path.join(args.input_dir, "organized")

    print(f"Scanning: {args.input_dir}")
    if args.dry_run:
        print("DRY RUN — no files will be moved or copied")

    result = organize_invoices(args.input_dir, output_dir, move=args.move, dry_run=args.dry_run)

    print(f"\nResults:")
    print(f"  Files found: {result['total_files_found']}")
    print(f"  Organized: {result['files_organized']}")
    print(f"  Duplicates: {result['duplicates_found']}")
    print(f"  Needs review: {result['needs_review']}")
    print(f"  Errors: {result['errors']}")

    if result["review_items"]:
        print(f"\nFiles needing manual review:")
        for item in result["review_items"]:
            print(f"  {item['file']} — {item['reason']}")

    print(f"\nSummary CSV: {result['csv_path']}")
    print(f"Output: {result['output_dir']}")


if __name__ == "__main__":
    main()
