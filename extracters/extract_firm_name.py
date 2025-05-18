from firm_profile_manager import (
    get_profile_for_firm,
    update_profile,
    get_all_profiles,
    match_firm_by_alias,
    add_alias_to_profile
)

def extract_firm_name(text: str) -> str:
    lines = text.splitlines()
    found_sprzedawca = False
    candidate = None

    for line in lines:
        if not found_sprzedawca:
            if "sprzedawca" in line.lower():
                found_sprzedawca = True
            else:
                continue

        clean_line = line.strip()
        print(f"🔎 OCR fragment: '{clean_line}'")

        if clean_line:
            if "nabywca" in clean_line.lower():
                continue

            name = "".join(c for c in clean_line if c.isalnum() or c in (' ', '_', '-')).strip()

            # Naprawy OCR
            name = name.replace("0.0.", "o.o.")
            name = name.replace(" 00", " oo")
            name = name.replace(" 0", " o")
            name = name.replace("sp z oo", "Sp. z o.o.")
            name = name.replace("Sp z oo", "Sp. z o.o.")
            name = name.replace("Sp z o o", "Sp. z o.o.")

            candidate = name
            print(f"✔️ Kandydująca nazwa: '{candidate}'")
            break

    # 🔁 Sprawdź, czy alias pasuje do istniejącego profilu
    if candidate:
        print(f"DEBUG: Szukam aliasu dla '{candidate}'")
        matched = match_firm_by_alias(candidate)
        print(f"DEBUG: Wynik aliasu: {matched}")
        if matched:
            print(f"🔁 Dopasowano przez alias do firmy: '{matched}'")
            return matched

        profiles = get_all_profiles()
        normalized_profiles = {k.lower().strip(): k for k in profiles}
        if candidate.lower().strip() in normalized_profiles:
            return normalized_profiles[candidate.lower().strip()]

        # Pytanie użytkownika: czy to nowa firma czy alias
        print(f"📌 Wykryto nazwę firmy: '{candidate}' — nie znaleziono w profilach.")
        existing_names = list(profiles.keys())
        if existing_names:
            print("📚 Istniejące firmy:")
            for i, name in enumerate(existing_names):
                print(f"  {i+1}. {name}")

            selection = input("🔗 Czy ta nazwa to alias istniejącej firmy? Podaj numer lub ENTER aby dodać jako nową: ").strip()
            if selection.isdigit():
                index = int(selection) - 1
                if 0 <= index < len(existing_names):
                    chosen = existing_names[index]
                    add_alias_to_profile(chosen, candidate)
                    return chosen

        # Brak aliasu – dodaj jako nowy
        confirm = input(f"➕ Czy chcesz zapisać '{candidate}' jako nową firmę? (T/n): ").strip().lower()
        if confirm in ("t", "tak", ""):
            update_profile(candidate, {})
            print(f"💾 Zapisano nową firmę: {candidate}")
            return candidate
        else:
            corrected = input("✏️ Podaj poprawną nazwę firmy: ").strip()
            if corrected:
                update_profile(corrected, {})
                add_alias_to_profile(corrected, candidate)
                return corrected
            else:
                return "dokument"

    # Fallback – pytanie ręczne
    user_input = input("❓ Nie udało się rozpoznać firmy. Podaj nazwę ręcznie: ").strip()
    if user_input:
        update_profile(user_input, {})
        return user_input

    return "dokument"
