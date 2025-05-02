import re

def extract_invoice_number(text: str) -> str:
    prefixes = ["E-", "FS/", "F/"]
    lines = text.splitlines()

    for line in lines:
        for prefix in prefixes:
            if prefix in line:
                match = re.search(rf"{re.escape(prefix)}[\w\-/.]+", line)
                if match:
                    return match.group(0)
    return "brak-nr"