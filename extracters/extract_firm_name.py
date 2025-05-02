def extract_firm_name(text: str) -> str:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if "sprzedawca" in line.lower():
            for next_line in lines[i+1:]:
                clean_line = next_line.strip()
                if clean_line:
                    name = "".join(c for c in clean_line if c.isalnum() or c in (' ', '_', '-')).strip()
                    name = name.replace(" 00", " oo").replace(" 0", " o").replace("Sp z oo", "Sp. z o.o.")
                    return name
            break
    return "dokument"