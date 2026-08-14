import platform
from pathlib import Path

# Importy Twoich modułów
from config import system_utils as sys_utils
from utils import ui_handler as ui
from utils import knowledge_manager as km  # bazy wiedzy o działach/kategoriach

from core.paths import source_dir_ksef, ensure_dirs
from core.ksef import analyze_ksef, finalize_ksef


def process_file(pdf_path: Path):
    try:
        print(f"\n" + "="*60 + f"\n📄 ANALIZA: {pdf_path.name}")

        data = analyze_ksef(pdf_path)

        # Część layoutów KSeF nie pokazuje "Informacja o płatności" wcale i nie
        # da się tego wywnioskować heurystyką (patrz core/ksef.py) — pytamy
        # wprost operatora, zamiast cicho przyjmować domyślną wartość.
        if data["payment_status_ambiguous"]:
            sys_utils.open_pdf(pdf_path)
            data["payment_status"] = ui.ask_payment_status_decision(
                data["firm_name"], data["invoice_number"], data["invoice_date"],
                data["payment_date"], data["payment_form"], data["brutto"],
            )
            sys_utils.close_pdf()

        confirm = ui.present_proposal(
            data["firm_name"], data["invoice_number"], data["invoice_date"],
            data["payment_date"], data["payment_status"], data["payment_form"], data["brutto"],
        )

        if confirm == 'p':
            print(f"⏭️ Pominięto fakturę: {pdf_path.name}")
            return

        if confirm in ['k', 'n', 'nie']:
            sys_utils.open_pdf(pdf_path)
            kb_data = km.load_kb()

            corrections = ui.get_manual_corrections(
                data["firm_name"], data["invoice_number"], data["invoice_date"], data["payment_date"],
                data["payment_status"], data["payment_form"], data["brutto"],
                is_quick_mode=(confirm == 'k'),
                kb_data=kb_data,
            )
            sys_utils.close_pdf()

            if corrections[0] == "SKIP":
                print(f"⏭️ Pominięto fakturę po otwarciu PDF.")
                return

            (data["firm_name"], data["invoice_number"], data["invoice_date"], data["payment_date"],
             data["kategoria"], data["payment_status"], data["payment_form"], data["brutto"]) = corrections

        result = finalize_ksef(pdf_path, data, confirm)
        print(f"✅ Plik przeniesiony do: {Path(result['target_path']).parent.name}")
        if result["saved_to_payments"]:
            print(f"📧 Dodano do bazy płatności SQL.")

    except Exception as e:
        print(f"❌ BŁĄD podczas przetwarzania {pdf_path.name}: {e}")


def main():
    ensure_dirs()

    if not Path("settings.json").exists():
        print("❌ BŁĄD: Brak pliku settings.json!")
        return

    source_dir = source_dir_ksef()
    pdf_files = list(source_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"ℹ️ Folder {source_dir} jest pusty.")
        return

    print(f"🚀 Rozpoczynam pracę na {platform.system()}. Znaleziono {len(pdf_files)} plików.")
    for pdf in pdf_files:
        process_file(pdf)

    print("\n🏁 Wszystkie zadania wykonane.")


if __name__ == "__main__":
    main()
