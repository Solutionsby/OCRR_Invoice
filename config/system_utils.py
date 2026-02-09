import os
import platform

def open_pdf(path):
    """Otwiera PDF w domyślnej aplikacji macOS/Windows."""
    if platform.system() == 'Darwin': 
        os.system(f'open "{path}"')
    elif platform.system() == 'Windows': 
        os.startfile(path)

def close_pdf():
    """Zamyka Podgląd (Preview) na macOS."""
    if platform.system() == 'Darwin':
        os.system('killall Preview 2>/dev/null')