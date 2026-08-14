from pathlib import Path

from utils import ui_handler as ui
from config import system_utils as sys_utils

from core.paths import source_dir_euro, ensure_dirs
from core.euro import analyze_euro, finalize_euro


def process_file(pdf_path: Path):
    print(f"\n" + "=" * 60 + f"\n📄 ANALIZA (EUR): {pdf_path.name}")

    sys_utils.open_pdf(pdf_path)
    try:
        data = analyze_euro(pdf_path)

        rate = ui.ask_exchange_rate(
            data["eur_netto"], data["eur_vat"], data["suggested_rate"], data["rate_date"]
        )
        data["kurs_eur"] = rate
        data["netto"] = round(data["eur_netto"] * rate, 2)
        data["vat"] = round(data["eur_vat"] * rate, 2)

        if not data["dzial_known"]:
            dzial, kategoria = ui.ask_dzial_kategoria_inne(data["firm_name"])
            data["dzial"], data["kategoria"] = dzial, kategoria

        data["oplacona"] = ui.ask_paid_status_inne(
            data["firm_name"], data["invoice_number"], data["invoice_date"]
        )
        data["brutto"] = round(data["netto"] + data["vat"], 2)

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
        sys_utils.close_pdf()

    result = finalize_euro(pdf_path, data, confirm)
    print(f"📁 Plik przeniesiony do: {result['target_path']}")
    if result["saved_to_kosztowe"]:
        print("💾 SQL: zapisano w FAKTURY_KOSZTOWE.")
    if result["saved_to_payments"]:
        print("📧 SQL: dodano do FAKTURY_DO_ZAPLATY.")

    return result


def main():
    ensure_dirs()

    source_dir = source_dir_euro()
    pdf_files = list(source_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"ℹ️ Folder {source_dir} jest pusty.")
        return

    print(f"🚀 Odczyt {len(pdf_files)} faktur EUR z {source_dir}.")
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
