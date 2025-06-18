"""Alberta Government website scraper."""

import csv
import logging
import os
import re
import time
from datetime import date
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

import html2text


class AlbertaGovScraper:
    """Scraper for Alberta Government websites."""

    BASE_URL = "https://www.alberta.ca"
    MINISTRIES_URL = f"{BASE_URL}/ministries"

    def __init__(
        self,
        output_dir: Optional[str] = None,
        delay: float = 1.0,
        max_depth: int = 3,
        file_types: Optional[List[str]] = None,
        save_markdown: bool = True,
    ):
        """
        Initialize the scraper.

        Args:
            output_dir: Directory to save scraped data. If None, creates dated folder.
            delay: Delay between requests in seconds to be polite to the server.
            max_depth: Maximum depth for recursive scraping within ministries.
            file_types: List of file extensions to scrape (e.g., ['.pdf']). If None, scrapes all common document types.
            save_markdown: Whether to save HTML content as markdown files.
        """
        self.delay = delay
        self.max_depth = max_depth
        self.save_markdown = save_markdown
        self.logger = logging.getLogger(__name__)
        self.visited_urls: Set[str] = set()

        # Set default file types if none specified
        if file_types is None:
            self.file_types = [
                ".pdf",
                ".doc",
                ".docx",
                ".xls",
                ".xlsx",
                ".ppt",
                ".pptx",
                ".txt",
            ]
        else:
            self.file_types = file_types

        if output_dir is None:
            today = str(date.today())
            self.output_dir = f"abgov-scrape-{today}"
        else:
            self.output_dir = output_dir

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        # Create markdown directory if saving markdown
        if self.save_markdown:
            self.markdown_dir = os.path.join(self.output_dir, "markdown_content")
            if not os.path.exists(self.markdown_dir):
                os.makedirs(self.markdown_dir)

        # Initialize HTML to markdown converter
        if self.save_markdown:
            self.html_converter = html2text.HTML2Text()
            self.html_converter.ignore_links = False
            self.html_converter.ignore_images = False
            self.html_converter.body_width = 0  # Don't wrap lines

    def get_soup(self, url: str) -> BeautifulSoup:
        """
        Get BeautifulSoup object from URL.

        Args:
            url: The URL to scrape

        Returns:
            BeautifulSoup object

        Raises:
            requests.RequestException: If request fails
        """
        self.logger.info(f"Fetching URL: {url}")
        resp = requests.get(url)
        resp.raise_for_status()
        return BeautifulSoup(resp.content, "html.parser")

    def scrape_ministries(self) -> List[Dict[str, str]]:
        """
        Scrape ministry information.

        Returns:
            List of dictionaries containing ministry data
        """
        self.logger.info("Scraping ministries...")
        soup = self.get_soup(self.MINISTRIES_URL)
        ministries = []

        # Updated selector based on current website structure
        for item in soup.select("div.goa-taxonomy--list-item"):
            title_elem = item.select_one("div.goa-title a")
            desc_elem = item.select_one("div.goa-text p")

            if title_elem:
                name = title_elem.get_text(strip=True)
                href = title_elem.get("href", "")
                url = urljoin(self.BASE_URL, href)
                description = desc_elem.get_text(strip=True) if desc_elem else ""

                ministries.append(
                    {"name": name, "url": url, "description": description}
                )

        self.logger.info(f"Found {len(ministries)} ministries")
        return ministries

    def extract_entities_from_text(self, text: str) -> List[str]:
        """
        Extract potential entities from text content.

        Args:
            text: Text content to analyze

        Returns:
            List of potential entities found in the text
        """
        entities = []

        # Simple entity extraction patterns (can be enhanced with NLP libraries)
        import re

        # Dates
        date_patterns = [
            r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
            r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b",
            r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b",
        ]

        for pattern in date_patterns:
            entities.extend(re.findall(pattern, text, re.IGNORECASE))

        # Phone numbers
        phone_pattern = (
            r"\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b"
        )
        entities.extend(re.findall(phone_pattern, text))

        # Email addresses
        email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        entities.extend(re.findall(email_pattern, text))

        # URLs
        url_pattern = r'https?://[^\s<>"\'()[\]{}|\\^`]+[^\s<>"\'()[\]{}|\\^`.,;:]'
        entities.extend(re.findall(url_pattern, text))

        # Money amounts
        money_pattern = r"\$[\d,]+(?:\.\d{2})?"
        entities.extend(re.findall(money_pattern, text))

        # Capitalize words (potential names/places - simple heuristic)
        capitalized_words = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text)
        # Filter out common words and add meaningful capitalized phrases
        meaningful_caps = [
            word
            for word in capitalized_words
            if len(word) > 3 and word not in ["The", "This", "That", "There"]
        ]
        entities.extend(meaningful_caps[:10])  # Limit to avoid too many false positives

        return list(set(entities))  # Remove duplicates

    def save_page_as_markdown(
        self, url: str, soup: BeautifulSoup, ministry_name: str
    ) -> str:
        """
        Save HTML content as a markdown file.

        Args:
            url: The URL of the page
            soup: BeautifulSoup object of the page
            ministry_name: Name of the ministry for organization

        Returns:
            Path to the saved markdown file
        """
        if not self.save_markdown:
            return ""

        try:
            # Clean up ministry name for filename
            safe_ministry = re.sub(r"[^\w\s-]", "", ministry_name)
            safe_ministry = re.sub(r"[-\s]+", "_", safe_ministry)

            # Create ministry subfolder
            ministry_md_dir = os.path.join(self.markdown_dir, safe_ministry)
            if not os.path.exists(ministry_md_dir):
                os.makedirs(ministry_md_dir)

            # Generate filename from URL
            parsed_url = urlparse(url)
            page_name = parsed_url.path.strip("/").replace("/", "_")
            if not page_name:
                page_name = "index"
            page_name = re.sub(r"[^\w\s-]", "", page_name)
            page_name = re.sub(r"[-\s]+", "_", page_name)

            # Ensure unique filename
            counter = 1
            base_filename = f"{page_name}.md"
            filename = base_filename
            while os.path.exists(os.path.join(ministry_md_dir, filename)):
                filename = f"{page_name}_{counter}.md"
                counter += 1

            filepath = os.path.join(ministry_md_dir, filename)

            # Convert HTML to markdown
            html_content = str(soup)
            markdown_content = self.html_converter.handle(html_content)

            # Add metadata header
            metadata = f"""---
url: {url}
ministry: {ministry_name}
scraped_at: {date.today()}
title: {soup.title.get_text() if soup.title else 'No Title'}
---

"""

            # Save markdown file
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(metadata + markdown_content)

            self.logger.debug(f"Saved markdown: {filepath}")
            return filepath

        except Exception as e:
            self.logger.warning(f"Failed to save markdown for {url}: {e}")
            return ""

    def find_documents_in_page(
        self, url: str, ministry_name: str
    ) -> List[Dict[str, str]]:
        """
        Find documents in a specific page.

        Args:
            url: URL to search for documents
            ministry_name: Name of the ministry for context

        Returns:
            List of document dictionaries
        """
        documents = []

        try:
            soup = self.get_soup(url)

            # Save page content as markdown
            markdown_path = self.save_page_as_markdown(url, soup, ministry_name)

            # Find document links using configured file types
            doc_selectors = []

            self.logger.debug(f"Looking for file types: {self.file_types}")
            for ext in self.file_types:
                doc_selectors.extend([f"a[href$='{ext}']", f"a[href*='{ext}']"])

            for selector in doc_selectors:
                for link in soup.select(selector):
                    href = link.get("href", "")
                    if href:
                        doc_url = urljoin(self.BASE_URL, href)
                        title = link.get_text(strip=True) or "Untitled Document"

                        # Extract additional context around the document link
                        parent_text = ""
                        parent = link.parent
                        if parent:
                            parent_text = parent.get_text(strip=True)[:200] + "..."

                        documents.append(
                            {
                                "title": title,
                                "url": doc_url,
                                "ministry": ministry_name,
                                "source_page": url,
                                "context": parent_text,
                                "file_type": href.split(".")[-1].lower(),
                            }
                        )

            # Also extract text content from the page for entity extraction
            page_text = soup.get_text()
            entities = self.extract_entities_from_text(page_text)

            # Add page content info
            if entities:
                page_doc = {
                    "title": f"Page Content: {soup.title.get_text() if soup.title else 'No Title'}",
                    "url": url,
                    "ministry": ministry_name,
                    "source_page": url,
                    "context": f"Entities found: {', '.join(entities[:10])}",  # First 10 entities
                    "file_type": "webpage",
                    "entities": entities,
                }
                if markdown_path:
                    page_doc["markdown_file"] = markdown_path
                documents.append(page_doc)

        except Exception as e:
            self.logger.warning(f"Error processing page {url}: {e}")

        return documents

    def find_ministry_links(self, url: str, current_depth: int = 0) -> List[str]:
        """
        Find relevant links within a ministry page for recursive exploration.

        Args:
            url: Current URL to explore
            current_depth: Current recursion depth

        Returns:
            List of URLs to explore further
        """
        if current_depth >= self.max_depth:
            return []

        links = []

        try:
            soup = self.get_soup(url)

            # Look for navigation links, document sections, etc.
            # Focus on links that are likely to contain documents or important content
            link_selectors = [
                "a[href*='document']",
                "a[href*='report']",
                "a[href*='publication']",
                "a[href*='policy']",
                "a[href*='program']",
                "a[href*='service']",
                "nav a",
                ".navigation a",
                ".sidebar a",
                ".content a",
            ]

            for selector in link_selectors:
                for link in soup.select(selector):
                    href = link.get("href", "")
                    if href:
                        full_url = urljoin(self.BASE_URL, href)
                        # Only follow links within the same domain and not already visited
                        # Exclude document files that we're not interested in
                        excluded_extensions = [
                            ext
                            for ext in [
                                ".doc",
                                ".docx",
                                ".xls",
                                ".xlsx",
                                ".ppt",
                                ".pptx",
                            ]
                            if ext not in self.file_types
                        ]
                        if self.file_types == [".pdf"]:
                            # If we're only looking for PDFs, exclude all other document types but allow PDF links
                            excluded_extensions = [
                                ".doc",
                                ".docx",
                                ".xls",
                                ".xlsx",
                                ".ppt",
                                ".pptx",
                            ]

                        if (
                            self.BASE_URL in full_url
                            and full_url not in self.visited_urls
                            and not any(ext in full_url for ext in excluded_extensions)
                        ):
                            links.append(full_url)

        except Exception as e:
            self.logger.warning(f"Error finding links in {url}: {e}")

        return links[:10]  # Limit to avoid too many requests

    def scrape_ministry_documents_recursive(
        self, ministry: Dict[str, str]
    ) -> List[Dict[str, str]]:
        """
        Recursively scrape documents from a ministry's pages.

        Args:
            ministry: Dictionary containing ministry information

        Returns:
            List of documents found in the ministry
        """
        self.logger.info(
            f"Recursively scraping documents for ministry: {ministry['name']}"
        )

        all_documents = []
        urls_to_visit = [ministry["url"]]
        current_depth = 0

        while urls_to_visit and current_depth < self.max_depth:
            next_urls = []

            for url in urls_to_visit:
                if url in self.visited_urls:
                    continue

                self.visited_urls.add(url)

                # Find documents in current page
                documents = self.find_documents_in_page(url, ministry["name"])
                all_documents.extend(documents)

                # Find more links to explore
                if current_depth < self.max_depth - 1:
                    new_links = self.find_ministry_links(url, current_depth)
                    next_urls.extend(new_links)

                time.sleep(self.delay)  # Be polite to the server

            urls_to_visit = list(set(next_urls))  # Remove duplicates
            current_depth += 1

        self.logger.info(
            f"Found {len(all_documents)} documents/pages for {ministry['name']}"
        )
        return all_documents

    def download_documents(self, documents: List[Dict[str, str]]) -> None:
        """
        Download documents from the provided list.

        Args:
            documents: List of document dictionaries with 'title' and 'url' keys
        """
        docs_folder = os.path.join(self.output_dir, "documents")
        os.makedirs(docs_folder, exist_ok=True)

        for doc in documents:
            # Skip webpage content entries
            if doc.get("file_type") == "webpage":
                continue

            # Clean filename
            safe_title = "".join(
                c for c in doc["title"] if c.isalnum() or c in (" ", "-", "_")
            ).rstrip()
            safe_title = safe_title.replace(" ", "_")

            # Add ministry prefix to organize files
            ministry_safe = "".join(
                c
                for c in doc.get("ministry", "unknown")
                if c.isalnum() or c in (" ", "-", "_")
            ).replace(" ", "_")

            filename = os.path.join(
                docs_folder,
                f"{ministry_safe}_{safe_title}{os.path.splitext(doc['url'])[1]}",
            )

            try:
                self.logger.info(f"Downloading: {doc['title']}")
                resp = requests.get(doc["url"])
                resp.raise_for_status()

                with open(filename, "wb") as f:
                    f.write(resp.content)

                self.logger.info(f"Successfully downloaded: {doc['title']}")

            except Exception as e:
                self.logger.error(f"Failed to download {doc['title']}: {e}")

            time.sleep(self.delay)  # Be polite to the server

    def save_to_csv(
        self, data: List[Dict], filename: str, fieldnames: List[str]
    ) -> None:
        """
        Save data to CSV file.

        Args:
            data: List of dictionaries to save
            filename: Name of the CSV file
            fieldnames: List of field names for the CSV header
        """
        filepath = os.path.join(self.output_dir, filename)
        self.logger.info(f"Saving {len(data)} records to {filepath}")

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(data)

    def run_full_scrape(self, download_docs: bool = True) -> None:
        """
        Run the complete scraping pipeline focusing on ministry documents.

        Args:
            download_docs: Whether to download document files
        """
        self.logger.info(
            "Starting comprehensive scrape of Alberta Government ministry documents"
        )

        # Scrape ministries
        ministries = self.scrape_ministries()
        self.save_to_csv(ministries, "ministries.csv", ["name", "url", "description"])

        # Scrape documents from each ministry recursively
        all_documents = []
        all_entities = []

        for ministry in ministries:
            self.logger.info(f"Processing ministry: {ministry['name']}")
            ministry_documents = self.scrape_ministry_documents_recursive(ministry)
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

        # Save all documents
        document_fieldnames = [
            "title",
            "url",
            "ministry",
            "source_page",
            "context",
            "file_type",
        ]
        self.save_to_csv(all_documents, "documents.csv", document_fieldnames)

        # Save extracted entities
        entity_fieldnames = ["entity", "ministry", "source_document", "source_url"]
        self.save_to_csv(all_entities, "entities.csv", entity_fieldnames)

        # Optionally download documents
        if download_docs:
            self.download_documents(all_documents)

        self.logger.info(f"Scraping complete. Data saved to {self.output_dir}")
        self.logger.info(f"Total documents found: {len(all_documents)}")
        self.logger.info(f"Total entities extracted: {len(all_entities)}")
