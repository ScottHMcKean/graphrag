"""Main entry point for the GraphRAG scraping application."""

import logging
from graphrag.scrapers.alberta_gov_scraper import AlbertaGovScraper


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
