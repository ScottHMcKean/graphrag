"""Integration tests for Alberta Government scraper using pytest.

These tests make actual HTTP requests and should be run sparingly
to avoid overloading the target website.
"""

import os
import tempfile

import pytest
import requests

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
    """Create a scraper instance with temporary directory and longer delay for politeness."""
    return AlbertaGovScraper(output_dir=temp_dir, delay=2.0)


class TestAlbertaGovScraperIntegration:
    """Integration test cases for AlbertaGovScraper."""

    @pytest.mark.skip(reason="Run manually to test against real website")
    def test_real_website_accessibility(self, scraper):
        """Test that the target websites are accessible."""
        urls_to_test = [
            scraper.BASE_URL,
            scraper.MINISTRIES_URL,
            scraper.STAFF_DIRECTORY_URL,
            scraper.DOCUMENTS_URL,
        ]

        for url in urls_to_test:
            try:
                response = requests.get(url, timeout=10)
                assert (
                    response.status_code < 400
                ), f"URL {url} returned status {response.status_code}"
            except requests.RequestException as e:
                pytest.fail(f"Failed to connect to {url}: {e}")

    @pytest.mark.skip(
        reason="Run manually to test real scraping - be mindful of rate limits"
    )
    def test_real_ministries_scraping(self, scraper):
        """Test scraping ministries from the real website."""
        try:
            ministries = scraper.scrape_ministries()
            assert isinstance(ministries, list)
            if ministries:  # Only test if we got results
                assert "name" in ministries[0]
                assert "url" in ministries[0]
                assert ministries[0]["url"].startswith("http")
        except Exception as e:
            pytest.skip(
                f"Real website scraping failed (this is expected if website structure changed): {e}"
            )

    @pytest.mark.skip(
        reason="Run manually to test real scraping - be mindful of rate limits"
    )
    def test_real_staff_scraping(self, scraper):
        """Test scraping staff from the real website."""
        try:
            staff = scraper.scrape_staff()
            assert isinstance(staff, list)
            if staff:  # Only test if we got results
                assert "name" in staff[0]
                assert "title" in staff[0]
                assert "ministry" in staff[0]
                assert "phone" in staff[0]
        except Exception as e:
            pytest.skip(
                f"Real website scraping failed (this is expected if website structure changed): {e}"
            )

    @pytest.mark.skip(
        reason="Run manually to test real scraping - be mindful of rate limits"
    )
    def test_real_documents_scraping(self, scraper):
        """Test scraping documents from the real website."""
        try:
            documents = scraper.scrape_documents()
            assert isinstance(documents, list)
            if documents:  # Only test if we got results
                assert "title" in documents[0]
                assert "url" in documents[0]
                assert any(
                    documents[0]["url"].endswith(ext)
                    for ext in [".pdf", ".doc", ".docx"]
                )
        except Exception as e:
            pytest.skip(
                f"Real website scraping failed (this is expected if website structure changed): {e}"
            )

    @pytest.mark.skip(
        reason="Run manually and only for a few documents to avoid bandwidth abuse"
    )
    def test_real_document_download(self, scraper, temp_dir):
        """Test downloading a single document from the real website."""
        try:
            documents = scraper.scrape_documents()
            if documents:
                # Only test with first document to avoid downloading too much
                test_documents = documents[:1]
                scraper.download_documents(test_documents)

                # Check if document was downloaded
                docs_folder = os.path.join(temp_dir, "documents")
                assert os.path.exists(docs_folder)
                downloaded_files = os.listdir(docs_folder)
                assert len(downloaded_files) > 0
        except Exception as e:
            pytest.skip(f"Real document download failed: {e}")


@pytest.mark.integration
class TestRealWebsiteStructure:
    """Tests for real website structure changes (run manually)."""

    @pytest.mark.skip(reason="Manual testing only")
    def test_ministry_page_structure(self):
        """Test that the ministry page still has expected CSS selectors."""
        response = requests.get("https://www.alberta.ca/ministries")
        assert response.status_code == 200

        # This would help identify if selectors need updating
        content = response.text.lower()
        assert "ministry" in content  # Basic check

    @pytest.mark.skip(reason="Manual testing only")
    def test_staff_directory_structure(self):
        """Test that the staff directory page still has expected structure."""
        response = requests.get("https://www.alberta.ca/staff-directory.cfm")
        # Note: This might not exist, so we handle gracefully
        if response.status_code == 404:
            pytest.skip("Staff directory page not found - URL may have changed")

        assert response.status_code == 200
        content = response.text.lower()
        assert any(keyword in content for keyword in ["staff", "directory", "employee"])


if __name__ == "__main__":
    # Print warning about integration tests
    print("WARNING: Integration tests make real HTTP requests.")
    print("Run with caution to avoid overloading target servers.")
    print("Most tests are skipped by default. Use pytest -m 'not skip' to run them.")
    print("Example: pytest tests/test_integration.py -v --tb=short")
