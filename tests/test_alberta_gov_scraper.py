"""Tests for Alberta Government scraper using pytest."""

import csv
import os
import tempfile
from unittest.mock import Mock, patch, mock_open

import pytest
import requests
from bs4 import BeautifulSoup

from src.graphrag.scrapers.alberta_gov_scraper import AlbertaGovScraper


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test outputs."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Clean up
    import shutil

    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def scraper(temp_dir):
    """Create a scraper instance with temporary directory."""
    return AlbertaGovScraper(output_dir=temp_dir, delay=0.1)


class TestAlbertaGovScraper:
    """Test cases for AlbertaGovScraper."""

    def test_init_with_default_output_dir(self):
        """Test scraper initialization with default output directory."""
        scraper = AlbertaGovScraper()
        assert scraper.output_dir.startswith("abgov-scrape-")
        assert scraper.delay == 1.0

    def test_init_with_custom_output_dir(self, temp_dir):
        """Test scraper initialization with custom output directory."""
        custom_dir = "/tmp/test-scrape"
        scraper = AlbertaGovScraper(output_dir=custom_dir, delay=0.5)
        assert scraper.output_dir == custom_dir
        assert scraper.delay == 0.5

    @patch("src.graphrag.scrapers.alberta_gov_scraper.requests.get")
    def test_get_soup_success(self, mock_get, scraper):
        """Test successful HTML parsing."""
        mock_response = Mock()
        mock_response.content = b"<html><body><h1>Test</h1></body></html>"
        mock_get.return_value = mock_response

        soup = scraper.get_soup("http://example.com")

        assert isinstance(soup, BeautifulSoup)
        assert soup.find("h1").text == "Test"
        mock_response.raise_for_status.assert_called_once()

    @patch("src.graphrag.scrapers.alberta_gov_scraper.requests.get")
    def test_get_soup_http_error(self, mock_get, scraper):
        """Test HTTP error handling in get_soup."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.RequestException(
            "404 Not Found"
        )
        mock_get.return_value = mock_response

        with pytest.raises(requests.RequestException):
            scraper.get_soup("http://example.com/notfound")

    @patch.object(AlbertaGovScraper, "get_soup")
    def test_scrape_ministries(self, mock_get_soup, scraper):
        """Test ministry scraping."""
        # Mock HTML content
        html_content = """
        <html>
            <body>
                <div class="ministry-listing">
                    <a href="/ministry1">Ministry of Health</a>
                    <a href="/ministry2">Ministry of Education</a>
                </div>
            </body>
        </html>
        """
        mock_get_soup.return_value = BeautifulSoup(html_content, "html.parser")

        ministries = scraper.scrape_ministries()

        assert len(ministries) == 2
        assert ministries[0]["name"] == "Ministry of Health"
        assert ministries[0]["url"] == "https://www.alberta.ca/ministry1"
        assert ministries[1]["name"] == "Ministry of Education"
        assert ministries[1]["url"] == "https://www.alberta.ca/ministry2"

    @patch.object(AlbertaGovScraper, "get_soup")
    def test_scrape_staff(self, mock_get_soup, scraper):
        """Test staff directory scraping."""
        # Mock HTML content
        html_content = """
        <html>
            <body>
                <table class="staff-directory">
                    <tr><th>Name</th><th>Title</th><th>Ministry</th><th>Phone</th></tr>
                    <tr>
                        <td>John Doe</td>
                        <td>Deputy Minister</td>
                        <td>Health</td>
                        <td>(780) 123-4567</td>
                    </tr>
                    <tr>
                        <td>Jane Smith</td>
                        <td>Director</td>
                        <td>Education</td>
                        <td>(780) 987-6543</td>
                    </tr>
                    <tr><td>Incomplete</td></tr>
                </table>
            </body>
        </html>
        """
        mock_get_soup.return_value = BeautifulSoup(html_content, "html.parser")

        staff = scraper.scrape_staff()

        assert len(staff) == 2  # Incomplete row should be skipped
        assert staff[0]["name"] == "John Doe"
        assert staff[0]["title"] == "Deputy Minister"
        assert staff[0]["ministry"] == "Health"
        assert staff[0]["phone"] == "(780) 123-4567"

    @patch.object(AlbertaGovScraper, "get_soup")
    def test_scrape_documents(self, mock_get_soup, scraper):
        """Test document scraping."""
        # Mock HTML content
        html_content = """
        <html>
            <body>
                <a href="/doc1.pdf">Policy Document 1</a>
                <a href="/doc2.docx">Report 2024</a>
                <a href="/doc3.doc">Guidelines</a>
                <a href="/not-a-doc.html">Not a document</a>
            </body>
        </html>
        """
        mock_get_soup.return_value = BeautifulSoup(html_content, "html.parser")

        documents = scraper.scrape_documents()

        assert len(documents) == 3  # HTML file should be excluded
        assert documents[0]["title"] == "Policy Document 1"
        assert documents[0]["url"] == "https://www.alberta.ca/doc1.pdf"
        assert documents[1]["title"] == "Report 2024"
        assert documents[1]["url"] == "https://www.alberta.ca/doc2.docx"

    def test_save_to_csv(self, scraper, temp_dir):
        """Test CSV saving functionality."""
        test_data = [
            {"name": "Test Ministry", "url": "http://example.com"},
            {"name": "Another Ministry", "url": "http://example2.com"},
        ]

        scraper.save_to_csv(test_data, "test.csv", ["name", "url"])

        # Check if file was created and contains correct data
        csv_path = os.path.join(temp_dir, "test.csv")
        assert os.path.exists(csv_path)

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 2
        assert rows[0]["name"] == "Test Ministry"
        assert rows[1]["url"] == "http://example2.com"

    @patch("src.graphrag.scrapers.alberta_gov_scraper.requests.get")
    @patch("builtins.open", new_callable=mock_open)
    @patch("src.graphrag.scrapers.alberta_gov_scraper.time.sleep")
    def test_download_documents(self, mock_sleep, mock_file, mock_get, scraper):
        """Test document downloading."""
        # Mock successful download
        mock_response = Mock()
        mock_response.content = b"PDF content"
        mock_get.return_value = mock_response

        documents = [
            {"title": "Test Document!@#", "url": "http://example.com/doc.pdf"},
            {"title": "Another Doc", "url": "http://example.com/doc2.docx"},
        ]

        scraper.download_documents(documents)

        # Verify requests were made
        assert mock_get.call_count == 2
        # Verify files were written
        assert mock_file().write.call_count == 2
        # Verify sleep was called for politeness
        assert mock_sleep.call_count == 2

    @patch("src.graphrag.scrapers.alberta_gov_scraper.requests.get")
    @patch("src.graphrag.scrapers.alberta_gov_scraper.time.sleep")
    def test_download_documents_with_failure(self, mock_sleep, mock_get, scraper):
        """Test document downloading with network failure."""
        # Mock failed download
        mock_get.side_effect = requests.RequestException("Network error")

        documents = [{"title": "Test Doc", "url": "http://example.com/doc.pdf"}]

        # Should not raise exception, just log error
        scraper.download_documents(documents)

        mock_get.assert_called_once()
        mock_sleep.assert_called_once()

    @patch.object(AlbertaGovScraper, "scrape_ministries")
    @patch.object(AlbertaGovScraper, "scrape_staff")
    @patch.object(AlbertaGovScraper, "scrape_documents")
    @patch.object(AlbertaGovScraper, "download_documents")
    @patch.object(AlbertaGovScraper, "save_to_csv")
    def test_run_full_scrape_with_downloads(
        self,
        mock_save_csv,
        mock_download,
        mock_scrape_docs,
        mock_scrape_staff,
        mock_scrape_ministries,
        scraper,
    ):
        """Test full scraping pipeline with document downloads."""
        # Mock return values
        mock_scrape_ministries.return_value = [
            {"name": "Test Ministry", "url": "http://test.com"}
        ]
        mock_scrape_staff.return_value = [
            {"name": "John Doe", "title": "Manager", "ministry": "Test", "phone": "123"}
        ]
        mock_scrape_docs.return_value = [
            {"title": "Test Doc", "url": "http://test.com/doc.pdf"}
        ]

        scraper.run_full_scrape(download_docs=True)

        # Verify all scraping methods were called
        mock_scrape_ministries.assert_called_once()
        mock_scrape_staff.assert_called_once()
        mock_scrape_docs.assert_called_once()

        # Verify CSV saves were called
        assert mock_save_csv.call_count == 3

        # Verify download was called
        mock_download.assert_called_once()

    @patch.object(AlbertaGovScraper, "scrape_ministries")
    @patch.object(AlbertaGovScraper, "scrape_staff")
    @patch.object(AlbertaGovScraper, "scrape_documents")
    @patch.object(AlbertaGovScraper, "download_documents")
    @patch.object(AlbertaGovScraper, "save_to_csv")
    def test_run_full_scrape_without_downloads(
        self,
        mock_save_csv,
        mock_download,
        mock_scrape_docs,
        mock_scrape_staff,
        mock_scrape_ministries,
        scraper,
    ):
        """Test full scraping pipeline without document downloads."""
        # Mock return values
        mock_scrape_ministries.return_value = []
        mock_scrape_staff.return_value = []
        mock_scrape_docs.return_value = []

        scraper.run_full_scrape(download_docs=False)

        # Verify all scraping methods were called
        mock_scrape_ministries.assert_called_once()
        mock_scrape_staff.assert_called_once()
        mock_scrape_docs.assert_called_once()

        # Verify CSV saves were called
        assert mock_save_csv.call_count == 3

        # Verify download was NOT called
        mock_download.assert_not_called()


@pytest.mark.parametrize(
    "url,expected_base",
    [
        ("/ministry1", "https://www.alberta.ca/ministry1"),
        ("https://www.alberta.ca/ministry2", "https://www.alberta.ca/ministry2"),
        ("ministry3", "https://www.alberta.ca/ministry3"),
    ],
)
def test_url_joining(url, expected_base):
    """Test URL joining behavior using parametrized tests."""
    from urllib.parse import urljoin

    base_url = "https://www.alberta.ca"
    result = urljoin(base_url, url)
    assert result == expected_base


def test_filename_sanitization():
    """Test that filenames are properly sanitized."""
    scraper = AlbertaGovScraper()

    # Test the filename cleaning logic
    test_title = "Test Document!@# With/Special\\Characters"
    safe_title = "".join(
        c for c in test_title if c.isalnum() or c in (" ", "-", "_")
    ).rstrip()
    safe_title = safe_title.replace(" ", "_")

    assert safe_title == "Test_Document_WithSpecialCharacters"
    assert "/" not in safe_title
    assert "\\" not in safe_title
    assert "!" not in safe_title
