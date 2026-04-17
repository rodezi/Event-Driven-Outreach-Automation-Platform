FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

WORKDIR /app

COPY requirements-scraper.txt .
RUN pip install --no-cache-dir -r requirements-scraper.txt

COPY scraper.py email_enricher.py sheets_client.py cities.py .

CMD ["sh", "-c", "python -m http.server ${PORT:-8080} & python scraper.py --city ${SCRAPER_CITY:-CDMX} && python email_enricher.py --limit 500; wait"]
