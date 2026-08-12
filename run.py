def main():
    print("📂 Które faktury chcesz wprowadzić?")
    print("  [1] Faktury z KSeF        (faktury_surowe)")
    print("  [2] Faktury spoza KSeF    (faktury_surowe/inne)")
    print("  [3] Faktury EURO          (faktury_surowe/euro)")
    choice = input("👉 Wybór: ").strip()

    if choice == "1":
        import main as main_ksef
        main_ksef.main()
    elif choice == "2":
        import main_inne
        main_inne.main()
    elif choice == "3":
        import main_euro
        main_euro.main()
    else:
        print("❌ Nieznany wybór.")


if __name__ == "__main__":
    main()
