#!/usr/bin/env python3
"""
Example script demonstrating the recursive Alberta Government ministry document scraper.

This script shows how to:
1. Scrape all ministries and their documents recursively
2. Extract entities from webpage content
3. Save comprehensive data for analysis
4. Download documents organized by ministry
"""

import logging
import sys
import os
from datetime import datetime

# Add src to path
sys.path.insert(0, "src")

from graphrag.scrapers.alberta_gov_scraper import AlbertaGovScraper


def setup_logging():
    """Set up logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(
                f'scraping_log_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
            ),
            logging.StreamHandler(),
        ],
    )


def main():
    """Run the complete ministry document scraping pipeline."""
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("Alberta Government Ministry Document Scraper")
    logger.info("=" * 60)

    # Configuration
    config = {
        "output_dir": f'alberta_gov_scrape_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
        "delay": 1.0,  # 1 second delay between requests (be polite!)
        "max_depth": 3,  # How deep to recursively explore each ministry
        "download_docs": True,  # Whether to download actual documents
    }

    logger.info(f"Configuration:")
    for key, value in config.items():
        logger.info(f"  {key}: {value}")

    try:
        # Initialize the scraper
        scraper = AlbertaGovScraper(
            output_dir=config["output_dir"],
            delay=config["delay"],
            max_depth=config["max_depth"],
        )

        # Option 1: Run complete scrape of all ministries
        if len(sys.argv) > 1 and sys.argv[1] == "--full":
            logger.info("Starting FULL scrape of all ministries...")
            logger.warning(
                "This will take a significant amount of time and make many requests!"
            )
            logger.warning("Consider using --sample instead for testing.")

            # Run the full scrape
            scraper.run_full_scrape(download_docs=config["download_docs"])

        # Option 2: Sample scrape of first few ministries (default)
        else:
            logger.info("Starting SAMPLE scrape (first 3 ministries)...")
            logger.info("Use --full flag to scrape all ministries")

            # Get ministries
            ministries = scraper.scrape_ministries()
            scraper.save_to_csv(
                ministries, "ministries.csv", ["name", "url", "description"]
            )

            # Process first 3 ministries as a sample
            sample_ministries = ministries[:3]
            all_documents = []
            all_entities = []

            for ministry in sample_ministries:
                logger.info(f"Processing ministry: {ministry['name']}")

                # Recursively scrape documents
                ministry_documents = scraper.scrape_ministry_documents_recursive(
                    ministry
                )
                all_documents.extend(ministry_documents)

                # Extract entities from documents
                for doc in ministry_documents:
                    if "entities" in doc:
                        for entity in doc["entities"]:
                            all_entities.append(
                                {
                                    "entity": entity,
                                    "ministry": ministry["name"],
                                    "source_document": doc["title"],
                                    "source_url": doc["url"],
                                }
                            )

                logger.info(
                    f"Found {len(ministry_documents)} documents/pages for {ministry['name']}"
                )

            # Save results
            document_fieldnames = [
                "title",
                "url",
                "ministry",
                "source_page",
                "context",
                "file_type",
            ]
            scraper.save_to_csv(all_documents, "documents.csv", document_fieldnames)

            entity_fieldnames = ["entity", "ministry", "source_document", "source_url"]
            scraper.save_to_csv(all_entities, "entities.csv", entity_fieldnames)

            # Optionally download documents
            if config["download_docs"]:
                logger.info("Downloading documents...")
                scraper.download_documents(all_documents)

            # Summary
            logger.info(f"Sample scrape completed!")
            logger.info(f"Ministries processed: {len(sample_ministries)}")
            logger.info(f"Total documents found: {len(all_documents)}")
            logger.info(f"Total entities extracted: {len(all_entities)}")

        logger.info(f"Results saved to: {config['output_dir']}")
        logger.info("Scraping completed successfully!")

        # Show what files were created
        output_files = os.listdir(config["output_dir"])
        logger.info(f"Output files created:")
        for file in sorted(output_files):
            file_path = os.path.join(config["output_dir"], file)
            if os.path.isfile(file_path):
                size = os.path.getsize(file_path)
                logger.info(f"  {file} ({size:,} bytes)")
            else:
                logger.info(f"  {file}/ (directory)")

    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Scraping failed: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    print("Alberta Government Ministry Document Scraper")
    print("Usage:")
    print(
        "  python example_ministry_scraper.py           # Sample scrape (first 3 ministries)"
    )
    print(
        "  python example_ministry_scraper.py --full    # Full scrape (all ministries)"
    )
    print()

    exit(main())
