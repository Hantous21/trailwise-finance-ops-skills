---
name: payment-app-html
description: Render a structured G702/G703 pay app as a self-contained, print-ready HTML document. Use when the bank, owner, or bonding agent needs the pay app as a PDF and you have the numbers from payment-app-generator.
---

# Payment App HTML (Print-Ready G702/G703)

## Overview

Renders the JSON output of `payment-app-generator` (`{"g702": {...}, "g703": [...]}`)
as a single self-contained HTML file. The user opens it in a browser, hits
File → Print → Save as PDF. No fonts, images, or stylesheets are loaded from
the network — the file is offline-openable, dependency-free, and prints on
plain paper.

## Workflow

1. Generate the structured pay app with `payment-app-generator` and dump
   it to JSON:
   ```bash
   python3 1_Trailwise_Toolkit/payment-app-generator/scripts/payment_app.py
   # ... (or use the test fixture at fixtures/input/pay_app.json)
   ```
2. Render to HTML:
   ```bash
   python3 scripts/payment_app_html.py \
       fixtures/input/pay_app.json \
       --out pay_app.html
   ```
3. Open `pay_app.html` in any browser, print to PDF.
4. Send the PDF to the bank, owner, or bonding agent. Keep the source JSON
   in the project folder for audit.

## Controls

- **Never retype numbers into the document** — it renders
  `payment-app-generator` output only, one source of math.
- **The HTML must stay dependency-free and offline-openable** — no CDN
  fonts, no external images, no `<link rel="stylesheet">` to third parties.
- **Print to PDF, don't email the raw HTML to a bank** — the HTML is a
  rendering target, not a delivery format. PDF is the signed document.

---

**[Book a consultation →](https://trailwiseai.com/#contact)** — we'll configure your entire finance ops workflow in 2 business days.
