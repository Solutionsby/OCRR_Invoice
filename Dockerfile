FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    INVOICES_BASE_PATH=/data

# System deps: OCR (tesseract + polski pakiet językowy), pdf2image (poppler),
# oraz unixodbc + Microsoft ODBC Driver 18 dla pyodbc/database_manager.py —
# ten sterownik dziś jest instalowany ręcznie na Macu/Windowsie użytkownika,
# w kontenerze trzeba go dograć jawnie. Driver 18 (nie 17) — 17 ma niepełne
# paczki arm64 dla Debiana 12/bookworm, co wywala apt na Apple Silicon.
# Nazwa sterownika jest configurowalna przez DB_DRIVER (docker-compose.yml
# ustawia "ODBC Driver 18 for SQL Server" dla kontenera, .env na hoście
# zostaje przy 17 dla CLI) — patrz utils/database_manager.py.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl gnupg2 ca-certificates \
        tesseract-ocr tesseract-ocr-pol \
        poppler-utils \
        unixodbc unixodbc-dev \
    && curl -sSL https://packages.microsoft.com/keys/microsoft.asc \
        | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl -sSL https://packages.microsoft.com/config/debian/12/prod.list \
        | sed 's#\[arch=amd64,armhf,arm64\]#[arch=amd64,armhf,arm64 signed-by=/usr/share/keyrings/microsoft-prod.gpg]#' \
        > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
