from pathlib import Path

from utils import ui_handler as ui
from config import system_utils as sys_utils

from core.paths import source_dir_inne, ensure_dirs
from core.inne import analyze_inne, finalize_inne


def process_file(pdf_path: Path):
    print(f"\n" + "=" * 60 + f"\n📄 ANALIZA: {pdf_path.name}")

    # Faktury spoza KSeF mają zbyt różnorodne layouty, żeby ufać samemu
    # odczytowi OCR — podgląd PDF-a otwiera się od razu, żeby operator
    # mógł na bieżąco porównywać z tym, co program odczytał.
    sys_utils.open_pdf(pdf_path)
    try:
        data = analyze_inne(pdf_path)

        if not data["dzial_known"]:
            dzial, kategoria = ui.ask_dzial_kategoria_inne(data["firm_name"])
            data["dzial"], data["kategoria"] = dzial, kategoria

        data["oplacona"] = ui.ask_paid_status_inne(
            data["firm_name"], data["invoice_number"], data["invoice_date"]
        )

        confirm = ui.present_proposal_inne(data)

        if confirm == 'p':
            print(f"⏭️ Pominięto fakturę: {pdf_path.name}")
            return None

        if confirm in ('n', 'nie'):
            corrected = ui.get_manual_corrections_inne(data)
            if corrected == "SKIP":
                print("⏭️ Pominięto fakturę po korekcie.")
                return None
            data.update(corrected)
    finally:
        # Zamykamy przed zmianą nazwy/przeniesieniem pliku (na Windows otwarty
        # podgląd mógłby blokować rename).
        sys_utils.close_pdf()

    result = finalize_inne(pdf_path, data, confirm)
    print(f"📁 Plik przeniesiony do: {result['target_path']}")
    if result["saved_to_kosztowe"]:
        print("💾 SQL: zapisano w FAKTURY_KOSZTOWE.")
    if result["saved_to_payments"]:
        print("📧 SQL: dodano do FAKTURY_DO_ZAPLATY.")

    return result


def main():
    ensure_dirs()

    source_dir = source_dir_inne()
    pdf_files = list(source_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"ℹ️ Folder {source_dir} jest pusty.")
        return

    print(f"🚀 Odczyt {len(pdf_files)} faktur spoza KSeF z {source_dir}.")
    accepted = []
    for pdf in pdf_files:
        try:
            data = process_file(pdf)
            if data:
                accepted.append(data)
        except Exception as e:
            print(f"❌ BŁĄD podczas przetwarzania {pdf.name}: {e}")

    print(f"\n🏁 Zakończono. Zaakceptowano i zapisano {len(accepted)}/{len(pdf_files)} faktur.")


if __name__ == "__main__":
    main()
