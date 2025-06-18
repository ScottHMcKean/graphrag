# Scrapers Module

This module contains web scrapers for various data sources.

## Alberta Government Scraper

The `AlbertaGovScraper` class provides functionality to recursively scrape documents and extract entities from Alberta Government ministry websites.

### Features

- Scrapes ministry information from the ministries page
- Recursively explores each ministry's pages to find documents
- Extracts documents of various types (PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX, TXT)
- Extracts entities from webpage content (dates, phone numbers, emails, URLs, money amounts, names/places)
- Downloads documents with rate limiting and organized by ministry
- Saves comprehensive data to CSV files including extracted entities
- Configurable output directory, request delays, and maximum recursion depth
- Avoids duplicate URL visits and respects rate limits

### Usage

```python
from graphrag.scrapers.alberta_gov_scraper import AlbertaGovScraper

# Basic usage with default 3-level recursion
scraper = AlbertaGovScraper()
scraper.run_full_scrape()

# Custom configuration
scraper = AlbertaGovScraper(
    output_dir="custom_output",
    delay=2.0,  # 2 second delay between requests
    max_depth=2  # Maximum recursion depth
)
scraper.run_full_scrape(download_docs=False)  # Skip document downloads
```

### Individual Methods

```python
# Scrape specific data types
ministries = scraper.scrape_ministries()

# Recursively scrape documents from a specific ministry
ministry_docs = scraper.scrape_ministry_documents_recursive(ministry)

# Extract entities from text
entities = scraper.extract_entities_from_text("Sample text with john.doe@example.com and $1,000")

# Save to CSV
scraper.save_to_csv(documents, "documents.csv", ["title", "url", "ministry"])

# Download documents
scraper.download_documents(documents)
```

### Output

The scraper creates the following files in the output directory:
- `ministries.csv` - Ministry names, URLs, and descriptions
- `documents.csv` - Comprehensive document and webpage information including:
  - Document title and URL
  - Source ministry and page
  - Context around document links
  - File type
- `entities.csv` - Extracted entities with source information:
  - Entity value
  - Source ministry
  - Source document/page
  - Source URL
- `documents/` - Folder containing downloaded document files organized by ministry

### Entity Extraction

The scraper automatically extracts the following types of entities from webpage content:
- **Dates** - Various formats (MM/DD/YYYY, Month DD, YYYY, etc.)
- **Phone Numbers** - North American format with various separators
- **Email Addresses** - Standard email format
- **URLs** - HTTP/HTTPS links
- **Money Amounts** - Dollar amounts with optional cents
- **Names/Places** - Capitalized words and phrases (filtered for relevance)

### Recursive Scraping

The scraper intelligently explores ministry websites by:
- Starting at each ministry's main page
- Following relevant links containing keywords like "document", "report", "publication", "policy", "program", "service"
- Exploring navigation links, sidebar links, and content links
- Respecting the maximum depth limit to avoid infinite loops
- Tracking visited URLs to prevent duplicate processing
- Limiting links per page to avoid excessive requests

### Rate Limiting

The scraper includes comprehensive rate limiting and politeness features:
- Configurable delay between requests (default: 1 second)
- Error handling for failed requests
- Logging of all activities
- Visited URL tracking to avoid duplicate requests
- Link limits per page to prevent excessive server load

### Error Handling

- HTTP errors are logged but don't stop the scraping process
- Failed document downloads are logged but don't affect other downloads
- Malformed HTML is handled gracefully
- Entity extraction failures don't interrupt document processing
- Recursive exploration errors are caught and logged

### Testing

Run the test suite:
```bash
python -m pytest tests/test_alberta_gov_scraper.py -v
```

For integration testing against the real website (use sparingly):
```bash
# Remove @skip decorators first
python -m pytest tests/test_integration.py -v
``` 