
**TAKEOVERS DATA/ML CHALLENGE: BILAN**

**Candidata:** Luiza Rafael Camargo

--


# Takeovers — Bilan Challenge

## What this does

A pipeline that reads the bundled OCR (`data/<siren>/bilans/ocr/<doc_id>/page_*.json`) for the 15 documents in scope, converts every text line's bounding box from 300-dpi pixels to normalized `[x0, y0, x1, y1]` coordinates, and extracts financial fields by matching a keyword label to the nearest numeric value on the same horizontal line.

No LLM, no external OCR, no API calls of any kind, everything runs on the OCR shipped in the repo plus `pymupdf` for page geometry.


## How to run it

----------------------------
pip install pymupdf
python readerOCR.py
----------------------------

This processes all 15 documents listed in `DOCUMENTOS_ESCOPO` and writes `results.json` at the repository root No environment variables or API keys are needed — see `.env.example` (empty on purpose).


## What's actually covered

The code tests 6 keywords in total across the 15 documents. Of those, 5 map to fields from the official 12-field schema, and 1 (PL_NET_INCOME_FRGAAP) is an extra field outside the schema that I added while testing keyword matching.

Of the 5 official fields attempted, 4 produced results:

BS_TOTAL_ASSETS_FRGAAP — extracted successfully across most documents
BS_TOTAL_EQUITY_FRGAAP — extracted successfully across most documents
PL_INCOME_TAX_FRGAAP — extracted successfully across most documents
META_AVG_WORKFORCE_FRGAAP — extracted for a couple of documents
PL_REVENUE_FRGAAP — attempted (keyword "Chiffre d'affaires net"), but returned no result on any of the 15 documents, rather than drop the attempt silently, I'm flagging it here: the keyword search found nothing it could pair with a numeric value, most likely because the actual filings phrase or lay out this line differently than the keyword assumes. This needs a better keyword (or a different matching strategy) before it can be trusted.

The 6th keyword tested, PL_NET_INCOME_FRGAAP (net result of the period), is not part of schema/financial_fields.json and should be disregarded when scoring against the schema, I'm leaving it in results.json rather than removing it, since it doesn't conflict with any required field and shows working extraction logic on a field beyond the required set.

The remaining 7 required fields (PL_COGS_FRGAAP, PL_PERSONNEL_COSTS_FRGAAP, PL_EXT_SERVICES_COSTS_FRGAAP, PL_DEPRECIATION_AMORTIZATION_FRGAAP, PL_FINANCIAL_RESULTS_FRGAAP, BS_CAPITAL_EQUITY_FRGAAP, BS_CASH_CURRENT_ASSET_FRGAAP) were not attempted at all. PL_COGS_FRGAAP in particular is not a printed line, it has to be built from several purchase/inventory lines, and I did not have time to implement that composition logic within the time budget.

Even within the 4 covered fields, coverage across the 15 documents is uneven, and two documents return an empty result entirely. I checked both by hand rather than assuming it was a matching-logic failure, and they turned out to be two different kinds of issue:

-6860f28ca0138eae340c7453 — this filing doesn't follow the standard liasse line naming: several labels use different wording than the other 14 documents in scope, so the fixed keywords never match here. This is a real formatting exception in the source document, not a bug in the matching logic.
-68f0a715f28d8aaf48046416 — opening the PDF directly and using Ctrl+F for a word I could visually see on the page found nothing. This suggests the page itself may lack a proper underlying text layer matching what's rendered, which is a data-quality issue rather than something my keyword matching could work around.


## How extraction works, and why it's uneven

Each field is matched by a fixed keyword (e.g. `"TOTAL ACTIF"` for total assets), searched against the OCR text of the whole document, once a label is found the pipeline looks for a numeric value on the same page, vertically aligned with the label (within a small tolerance), and to its right, that's the reported value, with its own page and bbox.

This works well when the document phrases the label close to how the keyword expects it, it fails silently (returns nothing for that field, rather than a wrong value) when:

- the filing uses different wording than the keyword expects (e.g. an abbreviated or reworded label)
- the label and its value aren't on a horizontal line the tolerance catches (this is worse on the skewed-scan company, `820561470`)
- more than one plausible numeric candidate sits at a similar height (multi-column liasse layouts with several years side by side), the current logic picks the leftmost one, assumed to be the most recent year, but this hasn't been checked against every document

I chose to let missing fields come back empty rather than guess, in line with the brief's own framing: a pipeline that gets 4 fields right and says so is worth more than one that reports 12 with several silently wrong.


## Units (EUR / kEUR)

Each page is scanned for a small set of French phrases indicating thousand-euro reporting (`"en milliers d'euros"`, `"k€"`, etc.), if found, monetary values on that page are multiplied by 1000 before being reported as EUR. I did not verify this against every filing in scope, so it should be treated as a best-effort  rather than a confirmed correct scaling for `328024377`, the company known to report in thousands.


## Bounding boxes and skew

Bounding boxes are computed from the OCR polygon's bounding rectangle, normalized against the page's rendered pixel size at 300 dpi, the convention the brief states the shipped OCR uses, I chose to get this size by rendering the full page with `pixmap.get_pixmap(dpi=300)` rather than computing it from the PDF's raw page dimensions (`page.rect.width/height * dpi/72`). The render is more expensive, but it matches the documented 300-dpi convention even when the page carries a `/Rotate` flag — a plain dimension calculation from `rect` ignores rotation and would silently swap width and height on a rotated page. Since one of the five companies in scope has rotated, skewed scans, I preferred the slightly slower but more coherent approach over assuming the pixel count from page metadata. This was checked visually with `tools/bbox_viewer.py` and lines up correctly.

What it does **not** correct for is in-page skew (the small scan-angle tilt reported per page as `skew_angle`, distinct from PDF-level rotation). On `820561470`, whose scan has a ~0.7° skew, the axis-aligned bbox is visibly looser around the text than on a straight scan, it still fully contains the text, but with more padding than ideal, I did not implement skew correction, it would mean rotating polygon points by `skew_angle` before computing the bounding rectangle, which I judged not worth the time given the marginal effect on the score.


## Conclusion

This pipeline uses no LLM and no paid OCR: it runs entirely on the OCR shipped in the repo plus local PDF rendering, so the cost is €0 per page.

Given the 6–8 hour budget, I chose to spend the time validating the geometry pipeline (bbox conversion, unit detection) end to end on a handful of fields rather than spreading thin across all 12 with a less-verified approach, that trade-off shows up directly in the results: 4 of 12 required fields extracted reliably, one attempted but never matching (PL_REVENUE_FRGAAP), and 7 not attempted at all.

With another week, I would prioritize: (1) making keyword matching resilient to label wording variation (e.g. trying a few known synonyms per field before giving up), (2) correcting for per-page skew before computing bboxes, (3) manually reviewing the documents against the results produced so far, to check whether the extracted values are actually correct and to surface other weaknesses in the matching logic that haven't shown up yet, and (4) continuing to work on the fields that aren't a direct read, PL_COGS_FRGAAP and the other composed fields that have to be built from several lines rather than matched to one.



## How I used AI

I'm not very experienced with programming, so I used Claude mainly as a learning tool rather than a code generator I'd ship without understanding, from the very first step, I used it to understand exactly what the challenge was actually asking for, and then to get started on each function, but I didn't want to submit code I couldn't explain myself, which is also why the pipeline has a lot of comments: I wanted to be able to look back at any line and know what it does and why.

As I understood the problem better, I started proposing my own ideas on top of what Claude suggested, based on what I was learning technically. Two concrete examples: Claude's first version of the bbox conversion used the PDF's raw page dimensions (page.rect), and I pushed back because I wanted something more generic and coherent, based on actually rendering the page and counting pixels rather than assuming a dimension from PDF metadata, that's what led to using get_pixmap instead, which also turned out to handle page rotation correctly; The other example is the kEUR/EUR unit detection: once I understood the units problem the brief describes, I suggested how I thought it should be made.

## Screen recording (drive link)

https://drive.google.com/file/d/1-ZQL85b3ox9YE7DWUI1k1Ll46Mc8uIwt/view?usp=sharing