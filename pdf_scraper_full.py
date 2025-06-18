#!/usr/bin/env python3
"""
PDF Document Scraper for Alberta Government Ministries

This script performs a comprehensive scrape of all Alberta Government ministries
to build a complete table of PDF documents available across all departments.

Features:
- Scrapes ONLY PDF files (no other document types)
- Processes ALL ministries (not just a sample)
- Does NOT download the documents (builds table only)
- Saves HTML content from each page as markdown files
- Provides comprehensive logging and progress tracking
- Extracts entities from webpage content
"""

import logging
import sys
import os
from datetime import datetime

# Add src to path
sys.path.insert(0, "src")

from graphrag.scrapers.alberta_gov_scraper import AlbertaGovScraper


def setup_logging():
    """Set up comprehensive logging configuration."""
    log_filename = f'pdf_scraping_log_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(log_filename), logging.StreamHandler()],
    )

    return log_filename


def main():
    """Run the comprehensive PDF document scraping pipeline."""
    log_filename = setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("=" * 80)
    logger.info("ALBERTA GOVERNMENT PDF DOCUMENT SCRAPER")
    logger.info("=" * 80)
    logger.info("Comprehensive scrape of ALL ministries for PDF documents only")
    logger.info("Documents will NOT be downloaded - building table only")
    logger.info("=" * 80)

    # Configuration optimized for PDF-only scraping
    config = {
        "output_dir": f'alberta_pdf_catalog_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
        "delay": 1.0,  # 1 second delay between requests
        "max_depth": 3,  # Deep exploration of each ministry
        "file_types": [".pdf"],  # PDF files only
        "download_docs": False,  # No downloading - table building only
    }

    logger.info("Configuration:")
    for key, value in config.items():
        logger.info(f"  {key}: {value}")
    logger.info("")

    try:
        # Initialize the scraper with PDF-only configuration
        scraper = AlbertaGovScraper(
            output_dir=config["output_dir"],
            delay=config["delay"],
            max_depth=config["max_depth"],
            file_types=config["file_types"],
            save_markdown=True,  # Save HTML content as markdown files
        )

        logger.info("PHASE 1: Discovering Alberta Government Ministries")
        logger.info("-" * 50)

        # Get all ministries
        ministries = scraper.scrape_ministries()
        scraper.save_to_csv(
            ministries, "ministries.csv", ["name", "url", "description"]
        )

        logger.info(f"Found {len(ministries)} ministries to process")
        logger.info("")

        logger.info("PHASE 2: Comprehensive PDF Document Discovery")
        logger.info("-" * 50)

        # Track progress and statistics
        all_documents = []
        all_entities = []
        ministry_stats = []

        for i, ministry in enumerate(ministries, 1):
            logger.info(f"[{i}/{len(ministries)}] Processing: {ministry['name']}")

            # Recursively scrape PDF documents from this ministry
            start_time = datetime.now()
            ministry_documents = scraper.scrape_ministry_documents_recursive(ministry)
            end_time = datetime.now()

            # Filter out non-PDF documents (keep only actual PDF files and webpage content)
            pdf_documents = [
                doc
                for doc in ministry_documents
                if doc.get("file_type") == "pdf" or doc.get("file_type") == "webpage"
            ]

            actual_pdfs = [
                doc for doc in pdf_documents if doc.get("file_type") == "pdf"
            ]
            webpages = [
                doc for doc in pdf_documents if doc.get("file_type") == "webpage"
            ]

            all_documents.extend(pdf_documents)

            # Extract entities from documents
            entities_count = 0
            for doc in ministry_documents:
                if "entities" in doc and doc["entities"]:
                    for entity in doc["entities"]:
                        all_entities.append(
                            {
                                "entity": entity,
                                "ministry": ministry["name"],
                                "source_document": doc["title"],
                                "source_url": doc["url"],
                            }
                        )
                        entities_count += 1

            # Track statistics
            processing_time = (end_time - start_time).total_seconds()
            ministry_stats.append(
                {
                    "ministry": ministry["name"],
                    "pdf_documents": len(actual_pdfs),
                    "webpages_processed": len(webpages),
                    "entities_extracted": entities_count,
                    "processing_time_seconds": processing_time,
                }
            )

            logger.info(f"    → Found {len(actual_pdfs)} PDF documents")
            logger.info(f"    → Processed {len(webpages)} webpages")
            logger.info(f"    → Extracted {entities_count} entities")
            logger.info(f"    → Processing time: {processing_time:.1f} seconds")
            logger.info("")

        logger.info("PHASE 3: Saving Results")
        logger.info("-" * 50)

        # Save comprehensive results
        document_fieldnames = [
            "title",
            "url",
            "ministry",
            "source_page",
            "context",
            "file_type",
        ]
        scraper.save_to_csv(
            all_documents, "pdf_documents_comprehensive.csv", document_fieldnames
        )

        entity_fieldnames = ["entity", "ministry", "source_document", "source_url"]
        scraper.save_to_csv(all_entities, "entities_extracted.csv", entity_fieldnames)

        stats_fieldnames = [
            "ministry",
            "pdf_documents",
            "webpages_processed",
            "entities_extracted",
            "processing_time_seconds",
        ]
        scraper.save_to_csv(ministry_stats, "ministry_statistics.csv", stats_fieldnames)

        # Create a PDF-only summary file
        pdf_only_docs = [doc for doc in all_documents if doc.get("file_type") == "pdf"]
        scraper.save_to_csv(
            pdf_only_docs, "pdf_documents_only.csv", document_fieldnames
        )

        logger.info("SCRAPING COMPLETED SUCCESSFULLY!")
        logger.info("=" * 80)

        # Final statistics
        total_pdfs = len(pdf_only_docs)
        total_webpages = len(
            [doc for doc in all_documents if doc.get("file_type") == "webpage"]
        )
        total_entities = len(all_entities)

        logger.info("FINAL STATISTICS:")
        logger.info(f"  Ministries processed: {len(ministries)}")
        logger.info(f"  PDF documents found: {total_pdfs:,}")
        logger.info(f"  Webpages processed: {total_webpages:,}")
        logger.info(f"  Total entities extracted: {total_entities:,}")
        logger.info(f"  Results saved to: {config['output_dir']}")
        logger.info(f"  Log file: {log_filename}")

        # Show top ministries by PDF count
        ministry_stats.sort(key=lambda x: x["pdf_documents"], reverse=True)
        logger.info("")
        logger.info("TOP 10 MINISTRIES BY PDF DOCUMENT COUNT:")
        for i, stat in enumerate(ministry_stats[:10], 1):
            logger.info(f"  {i:2d}. {stat['ministry']}: {stat['pdf_documents']:,} PDFs")

        # Show output files
        logger.info("")
        logger.info("OUTPUT FILES CREATED:")
        output_files = os.listdir(config["output_dir"])
        for file in sorted(output_files):
            file_path = os.path.join(config["output_dir"], file)
            if os.path.isfile(file_path):
                size = os.path.getsize(file_path)
                logger.info(f"  {file} ({size:,} bytes)")
            else:
                logger.info(f"  {file}/ (directory)")

        logger.info("")
        logger.info("💡 TIP: Use 'pdf_documents_only.csv' for the clean PDF-only table")
        logger.info(
            "💡 TIP: Use 'pdf_documents_comprehensive.csv' for all data including webpage content"
        )
        logger.info(
            "💡 TIP: Check 'markdown_content/' folder for HTML content saved as markdown files"
        )

    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
        logger.info("Partial results may be available in the output directory")
        return 1
    except Exception as e:
        logger.error(f"Scraping failed: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    print("Alberta Government PDF Document Scraper")
    print("=" * 50)
    print("This script will:")
    print("• Scrape ALL Alberta Government ministries")
    print("• Find ONLY PDF documents (no other file types)")
    print("• Save HTML content from each page as markdown files")
    print("• Build comprehensive document tables")
    print("• Extract entities from webpage content")
    print("• NOT download any documents")
    print("")
    print("Estimated time: 30-60 minutes for complete scrape")
    print("=" * 50)
    print()

    response = input("Proceed with full PDF scrape? (y/N): ")
    if response.lower() not in ["y", "yes"]:
        print("Scraping cancelled.")
        exit(0)

    exit(main())
