"""Main entry point for the GraphRAG scraping application."""

import logging
import sys
import os

# Handle imports for both direct execution and module execution
if __name__ == "__main__":
    # For direct execution, add the src directory to Python path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.dirname(current_dir)  # Go up one level to src/
    sys.path.insert(0, src_dir)
    from graphrag.scrapers.alberta_gov_scraper import AlbertaGovScraper
else:
    # For module execution, use relative imports
    from .scrapers.alberta_gov_scraper import AlbertaGovScraper


def main():
    """Main function to run the Alberta government scraping pipeline."""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    logger.info("Starting Alberta government data scraping...")

    try:
        scraper = AlbertaGovScraper()
        scraper.run_full_scrape()
        logger.info("Scraping completed successfully")
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        raise


if __name__ == "__main__":
    main()
