FROM python:3.11-slim

# Dependencias de sistema para Playwright / Chromium
RUN apt-get update && apt-get install -y \
    wget curl gnupg ca-certificates \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 libpango-1.0-0 libpangocairo-1.0-0 \
    libgtk-3-0 libx11-xcb1 libxcb-dri3-0 \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-scraper.txt .
RUN pip install --no-cache-dir -r requirements-scraper.txt
RUN playwright install chromium

COPY scraper.py email_enricher.py sheets_client.py .

# Corre scraper primero, luego enriquece emails
# Railway ejecuta este comando según el cron configurado en el dashboard
CMD ["sh", "-c", "python scraper.py && python email_enricher.py --limit 200"]
