# MCA Companies Act, 2013 Document Downloader & Classifier Agent

An autonomous agent built in Python that periodically scrapes legal documents related to **The Companies Act, 2013** from the [Ministry of Corporate Affairs (MCA) Portal](https://www.mca.gov.in/), extracts text using OCR (PyMuPDF / RapidOCR / AWS Textract), classifies them via LLM into structured categories, and stores them in organized folders with a 100-document limit.

## Features

- **Automated MCA Scraping**: Uses Playwright with anti-bot bypass to navigate MCA sections (*Notifications*, *Circulars*, *Other documents*), apply the Companies Act 2013 filter, and download PDF documents directly from DMS endpoints.
- **OCR Text Extraction**: Native digital extraction via PyMuPDF with automatic fallback to RapidOCR (ONNX Runtime) for scanned image documents, plus optional AWS Textract support.
- **LLM-Powered Classification**: Automatically classifies documents into 8 legal taxonomy categories:
  - `Act`
  - `Rules`
  - `Notification`
  - `Circular`
  - `Amendment`
  - `Order`
  - `Ordinance`
  - `Other`
- **Categorized Storage & Deduplication**: Moves classified files to `storage/<Category>/<filename>.pdf` and tracks processed files in a SQLite database (`processed_docs.db`) to avoid duplicates.
- **Stopping Limit**: Automatically terminates once 100 documents have been downloaded and processed.
- **24-Hour Scheduler**: Built-in scheduler using `APScheduler` to run the workflow automatically every 24 hours.

## Setup

1. **Clone the repository and set up a virtual environment:**
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **Configure Environment Variables (`.env`):**
   ```env
   GROQ_API_KEY=your_groq_api_key_here
   DOCS_PER_SECTION_LIMIT=35
   TOTAL_MAX_LIMIT=100
   ```
   *(Optional for AWS Textract: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`)*

## Usage

### Run with 24-Hour Scheduler
```bash
python main.py
```

### Run Once (Immediate Execution)
```bash
python main.py --once
```

### Re-generate Technical PDF Report
```bash
python generate_pdf_report.py
```

## Documentation

For a comprehensive line-by-line architectural breakdown, flowcharts, anti-bot mechanisms, and low-level code explanations, refer to:
- **[DETAILED_ARCHITECTURE.md](DETAILED_ARCHITECTURE.md)**: Exhaustive Markdown specification.
- **`MCA_Document_Automation_Architecture_Report.pdf`**: Publication-grade technical PDF report.

## Directory Structure

```
├── main.py                     # Application entry point (scheduler & CLI)
├── clear_docs.py                 # Utility script to reset database and storage
├── requirements.txt            # Python dependencies
├── processed_docs.db           # SQLite database tracking processed documents
├── README.md                   # Project overview & quickstart guide
├── src/
│   ├── graph.py                # Main scraping, downloading & orchestration pipeline
│   ├── ocr_engine.py           # OCR text extraction engine
│   ├── classifier.py           # Groq LLM document classification
│   └── store.py                # SQLite database interface
└── storage/                    # Output folders organized by document type
    ├── Act/
    ├── Rules/
    ├── Notification/
    ├── Circular/
    ├── Amendment/
    ├── Order/
    ├── Ordinance/
    └── Other/
```

