# Development Guide

This project uses [uv](https://docs.astral.sh/uv/) for fast Python package management.

## Setup

1. Install uv:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Install dependencies:
   ```bash
   uv sync --extra dev
   ```

## Common Commands

### Running Tests
```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_alberta_gov_scraper.py -v

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Run tests with parametrization examples
uv run pytest tests/test_alberta_gov_scraper.py::test_url_joining -v

# Skip integration tests (default behavior)
uv run pytest tests/ -v

# Run only integration tests (if you want to test against real website)
uv run pytest tests/test_integration.py -v --tb=short -m "not skip"
```

### Running the Scraper
```bash
# Run the main scraper (recommended)
uv run graphrag

# Or run as a module
uv run python -m graphrag.main

# Or run directly (for development)
uv run python src/graphrag/main.py
```

### Adding Dependencies

#### Production Dependencies
```bash
uv add requests beautifulsoup4
```

#### Development Dependencies
```bash
uv add --dev pytest pytest-cov
```

### Building the Package
```bash
uv build
```

### Installing in Editable Mode
```bash
uv pip install -e .
```

## Project Structure

```
graphrag/
├── src/
│   └── graphrag/
│       ├── __init__.py
│       ├── main.py
│       └── scrapers/
│           ├── __init__.py
│           ├── alberta_gov_scraper.py
│           └── README.md
├── tests/
│   ├── __init__.py
│   ├── test_alberta_gov_scraper.py
│   └── test_integration.py
├── pyproject.toml           # Modern dependency management
├── setup.py                 # For Databricks compatibility
└── requirements-dev.txt     # Legacy requirements (can be removed)
```

## Using with Databricks

The project still maintains `setup.py` for Databricks wheel building compatibility. The wheel can be built using:

```bash
uv run python setup.py bdist_wheel
```

## Virtual Environment

uv automatically manages the virtual environment in `.venv/`. To activate it manually:

```bash
source .venv/bin/activate  # Unix/macOS
# or
.venv\Scripts\activate     # Windows
```

## Linting and Formatting

Add these to your development workflow:

```bash
# Install linting tools
uv add --dev black isort flake8 mypy

# Format code
uv run black src tests
uv run isort src tests

# Lint code
uv run flake8 src tests
uv run mypy src
``` 