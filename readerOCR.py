import json  # JSON file reading
import glob  # reading files in folders
import os  # file path handling
import pymupdf  # PDF reader

from extracaoinfo import extrair_campo_direto


DOCUMENTS_IN_SCOPE = [
    {"siren": "820561470", "deposit_date": "2023-06-05", "doc_id": "6493e4372f502414800f8164"},
    {"siren": "820561470", "deposit_date": "2023-06-13", "doc_id": "6543d3fd08093cdace058668"},
    {"siren": "820561470", "deposit_date": "2024-01-15", "doc_id": "67458f18cea78a70070fa226"},
    {"siren": "328024377", "deposit_date": "2020-12-24", "doc_id": "63e8ebbb54febda17c19ee7c"},
    {"siren": "328024377", "deposit_date": "2021-12-17", "doc_id": "63e8ebbb54febda17c19ee7d"},
    {"siren": "328024377", "deposit_date": "2022-12-13", "doc_id": "63e8ebbb54febda17c19ee7e"},
    {"siren": "445070311", "deposit_date": "2022-02-14", "doc_id": "63e2481c916269756a09542b"},
    {"siren": "445070311", "deposit_date": "2023-11-21", "doc_id": "65a4095d5fd178b16b09b860"},
    {"siren": "445070311", "deposit_date": "2025-05-15", "doc_id": "6860f28ca0138eae340c7453"},
    {"siren": "504304205", "deposit_date": "2017-05-31", "doc_id": "63e13943526e1f30cd100db5"},
    {"siren": "504304205", "deposit_date": "2018-10-24", "doc_id": "63e13943526e1f30cd100db6"},
    {"siren": "504304205", "deposit_date": "2024-08-06", "doc_id": "66cd893cedec9b09d50191e8"},
    {"siren": "401009741", "deposit_date": "2022-11-30", "doc_id": "63e881158be6eb9f9d1ff975"},
    {"siren": "401009741", "deposit_date": "2023-11-20", "doc_id": "65784e5da67d84faf4042736"},
    {"siren": "401009741", "deposit_date": "2025-10-03", "doc_id": "68f0a715f28d8aaf48046416"}
]


## Renders the PDF page as an image and returns its dimensions in pixels
def page_dimensions_px(pdf_path, page_number, dpi=300):

    doc = pymupdf.open(pdf_path)
    page = doc[page_number - 1]  # pages are 0-indexed internally, so we subtract 1
    pixmap = page.get_pixmap(dpi=dpi)  # page rotation is handled automatically by PyMuPDF, so we don't need to worry about it here
    width_px = pixmap.width
    height_px = pixmap.height
    doc.close()
    return width_px, height_px  # returns the page dimensions in pixels


## Converts the polygon in pixels to normalized coordinates (0-1) based on the page dimensions
def normalize_bbox(polygon, width_px, height_px):

    xs = [point[0] for point in polygon]  # polygon in 0 to 300 dpi
    ys = [point[1] for point in polygon]  # polygon in 0 to 300 dpi
    x0 = min(xs) / width_px
    x1 = max(xs) / width_px
    y0 = min(ys) / height_px
    y1 = max(ys) / height_px
    return [x0, y0, x1, y1]


## Loads every page_00X.json file from an OCR folder and returns a list of dictionaries,
## one per text line, already with normalized bbox and page number.
def load_document(ocr_folder, pdf_path):

    lines = []
    page_files = sorted(glob.glob(os.path.join(ocr_folder, "page_*.json")))  # sorts the JSON files in the right order

    for path in page_files:
        with open(path, "r", encoding="utf-8") as f:  # r -> read, encoding="utf-8" -> file encoding (accents, ç, etc.)
            data = json.load(f)  # loads the JSON file content into a Python dictionary

        page_number = data["page"]
        width_px, height_px = page_dimensions_px(pdf_path, page_number)

        for item in data["ocr"]:  # organizes each OCR item into a text line with normalized bbox
            bbox_norm = normalize_bbox(item["polygon"], width_px, height_px)
            lines.append({
                "page": page_number,
                "text": item["text"],
                "bbox": bbox_norm,
                "score": item["score"],
            })

    return lines


## Searches for a keyword across all text lines
## Finds where the financial fields appear in the text
def search_keyword(lines, keyword):

    keyword = keyword.lower()
    return [line for line in lines if keyword in line["text"].lower()]  # returns a list of lines containing the keyword, case-insensitive


if __name__ == "__main__":
    import time

    start_time = time.time()    
    total_pages = 0

    # The fields you defined to test
    direct_fields = [
        # 1. Total Assets (BS)
        {"field_key": "BS_TOTAL_ASSETS_FRGAAP", "keyword": "TOTAL ACTIF", "unit": "EUR"},
        # 2. Total Equity (BS)
        {"field_key": "BS_TOTAL_EQUITY_FRGAAP", "keyword": "Total des capitaux propres", "unit": "EUR"},
        # 3. Corporate Income Tax (PL)
        {"field_key": "PL_INCOME_TAX_FRGAAP", "keyword": "Impôts sur les bénéfices", "unit": "EUR"},
        # 4. Net Revenue (PL)
        {"field_key": "PL_REVENUE_FRGAAP", "keyword": "Chiffre d'affaires net", "unit": "EUR"},
        # 5. Net Income for the Period (PL)
        {"field_key": "PL_NET_INCOME_FRGAAP", "keyword": "RESULTAT DE L'EXERCICE", "unit": "EUR"},
        # 6. Average Number of Employees (META)
        {"field_key": "META_AVG_WORKFORCE_FRGAAP", "keyword": "Effectif moyen", "unit": None},
    ]

    final_results = {}

    # Goes through each of the 15 documents
    for doc in DOCUMENTS_IN_SCOPE:
        siren = doc["siren"]
        deposit_date = doc["deposit_date"]
        doc_id = doc["doc_id"]

        ocr_folder = f"data/{siren}/bilans/ocr/{doc_id}"
        pdf_path = f"data/{siren}/bilans/pdf/bilan_{deposit_date}_{doc_id}.pdf"

        if not os.path.exists(ocr_folder) or not os.path.exists(pdf_path):
            print(f" Not found: {doc_id}")
            continue

        # Uses your functions to load and extract
        lines = load_document(ocr_folder, pdf_path)

        # Counts the number of pages in the document
        num_pages = len(set(l["page"] for l in lines))
        total_pages += num_pages

        doc_extractions = {}
        for field in direct_fields:
            res = extrair_campo_direto(lines, field["keyword"], field["unit"])
            if res is not None:
                doc_extractions[field["field_key"]] = res

        final_results[doc_id] = doc_extractions

    run_time = time.time() - start_time
    seconds_per_page = round(run_time / max(1, total_pages), 4)

    # Builds the final structure required by the challenge
    output_schema = {
        "results": final_results,
        "run": {
            "cost_per_page_eur": 0.0,
            "seconds_per_page": seconds_per_page
        }
    }

    # Saves the JSON at the project root
    with open("results.json", "w", encoding="utf-8") as f:
        json.dump(output_schema, f, indent=2, ensure_ascii=False)

    print(f"\nDone! {total_pages} pages processed in {round(run_time, 2)}s.")
    print(f"Average per page: {seconds_per_page}s")
    print("File 'results.json' generated at the project root!")