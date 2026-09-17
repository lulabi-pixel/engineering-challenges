import re


# checks whether the page is in thousands of euros (kEUR) or in euros (EUR)
def detect_page_scale(page_lines):
    
    # joins all the page text in lowercase to make searching easier
    page_text = " ".join([l.get("text", "").lower() for l in page_lines])

    # common patterns in French fiscal documents
    keur_patterns = [
        r"en milliers d'euros",
        r"en milliers d’euros",
        r"en k€",
        r"en keur",
        r"k€",
        r"chiffres exprimes en milliers"
    ]

    for pattern in keur_patterns:
        if re.search(pattern, page_text):
            return "kEUR"

    return "EUR"


## Filters whether a text looks like a numeric value from a liasse fiscale, e.g. "638 962", "1 234,56" or "-93"
def is_numeric(text):
    text = text.strip()
    # Pattern to identify integers, decimals with a comma, and values with a thousand-separator space
    pattern = r"^-?\s*\(?\d[\d\s\.]*(,\d+)?\)?$"
    return bool(re.match(pattern, text))


## Converts text into a float
def text_to_number(text):
    # Removes spaces and parentheses, and swaps comma for dot (French convention)
    clean_text = (
        text.strip()
        .replace(" ", "")
        .replace("(", "-")
        .replace(")", "")
        .replace(",", ".")
    )
    try:
        val = float(clean_text)
        return int(val) if val.is_integer() else val
    except ValueError:
        return None


## Checks whether two bboxes are on the same horizontal line using the vertical center (y_center)
def same_line(bbox_a, bbox_b, tolerance=0.015):
    y_center_a = (bbox_a[1] + bbox_a[3]) / 2
    y_center_b = (bbox_b[1] + bbox_b[3]) / 2
    return abs(y_center_a - y_center_b) <= tolerance


# Finds the numeric value corresponding to the label we're looking for
def find_value_next_to(lines, label_line, tolerance=0.015):
    candidates = []

    for line in lines:
        if line["page"] != label_line["page"]:
            continue
        if line is label_line:
            continue
        if not is_numeric(line["text"]):
            continue
        if not same_line(line["bbox"], label_line["bbox"], tolerance):
            continue
        # the number needs to be to the right of the label's start
        if line["bbox"][0] < label_line["bbox"][0]:
            continue
        candidates.append(line)

    if not candidates:
        return None

    # picks the closest candidate (first column to the right)
    candidates.sort(key=lambda c: c["bbox"][0])
    return candidates[0]


## Searches for the label by keyword and finds the numeric value next to it
def extrair_campo_direto(lines, keyword, unit):
    occurrences = [line for line in lines if keyword.lower() in line["text"].lower()]

    if not occurrences:
        return None

    # tries each occurrence until one has a numeric value on the same line
    for label_line in occurrences:
        found_value = find_value_next_to(lines, label_line)
        if found_value is not None:
            num = text_to_number(found_value["text"])
            if num is not None:
                current_page = found_value["page"]

                # filters only the lines on the same page to check the scale
                page_lines = [l for l in lines if l.get("page") == current_page]
                scale = detect_page_scale(page_lines)

                # if the page is in kEUR and the field is monetary (EUR), multiply by 1,000
                if scale == "kEUR" and unit == "EUR":
                    num = num * 1000

                return {
                    "value": num,
                    "unit": unit,
                    "page": current_page,
                    "bbox": found_value["bbox"],
                }

    return None