import os
import re
import sys
import base64
import shutil
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from src.store import init_db, is_url_processed, get_processed_count, record_processed_doc, get_summary_by_category
from src.ocr_engine import extract_text_from_pdf
from src.classifier import classify_document

load_dotenv()

DOCS_PER_SECTION_LIMIT = int(os.getenv("DOCS_PER_SECTION_LIMIT", 35))
TOTAL_MAX_LIMIT = int(os.getenv("TOTAL_MAX_LIMIT", 100))

STORAGE_DIR = "storage"
CATEGORIES = ["Act", "Rules", "Notification", "Circular", "Amendment", "Order", "Ordinance", "Other"]

JS_EXTRACT_PAGE_DOCS = """
() => {
    const docs = [];
    const rows = document.querySelectorAll('table tbody tr');
    for (const row of rows) {
        const link = row.querySelector('a.dmslink, a[val]');
        if (!link) continue;
        const val = link.getAttribute('val');
        if (!val) continue;
        const category = link.getAttribute('data-doccategory') || '';
        const title = link.innerText.trim();
        const cells = Array.from(row.querySelectorAll('td')).map(td => td.innerText.trim());
        const dateText = cells.length >= 3 ? cells[2] : '';
        docs.push({
            val: val.trim(),
            category: category.trim(),
            title: title,
            date: dateText
        });
    }
    return docs;
}
"""

JS_FETCH_PDF_BASE64 = """
async (url) => {
    try {
        const res = await fetch(url);
        if (!res.ok) return null;
        const blob = await res.blob();
        return new Promise((resolve) => {
            const reader = new FileReader();
            reader.onloadend = () => {
                const base64data = reader.result.split(',')[1];
                resolve(base64data);
            };
            reader.readAsDataURL(blob);
        });
    } catch (e) {
        return null;
    }
}
"""

def setup_storage():
    os.makedirs("temp_downloads", exist_ok=True)
    for cat in CATEGORIES:
        os.makedirs(os.path.join(STORAGE_DIR, cat), exist_ok=True)

def select_companies_act_filter(page):
    """
    Selects 'The Companies Act, 2013' in the dropdown filter and triggers the search.
    """
    try:
        page.select_option("#DropDown_Act", label="The Companies Act, 2013")
        page.evaluate("""() => {
            const goBtn = document.querySelector('#clickGo');
            if (goBtn) goBtn.click();
        }""")
        page.wait_for_timeout(2500)
        print("  [Filter] Selected 'The Companies Act, 2013'", flush=True)
    except Exception as e:
        print(f"  [Filter] Note applying Companies Act filter: {e}", flush=True)

def set_results_per_page(page, target_size: str = "50"):
    """
    Increases results shown per page to minimize pagination overhead.
    """
    try:
        length_select = page.locator("select[name*='length'], select.total-pages").first
        if length_select.is_visible():
            options = length_select.locator("option").all_inner_texts()
            val = target_size if target_size in options else ("25" if "25" in options else options[-1])
            length_select.select_option(val)
            page.wait_for_timeout(2000)
            print(f"  [Table] Results per page: {val}", flush=True)
    except Exception as e:
        print(f"  [Table] Note: {e}", flush=True)

def download_pdf(page, url: str, output_path: str) -> int:
    """
    Downloads PDF binary stream via in-page FileReader base64 encoding.
    """
    try:
        b64_data = page.evaluate(JS_FETCH_PDF_BASE64, url)
        if b64_data and len(b64_data) > 100:
            pdf_bytes = base64.b64decode(b64_data)
            if len(pdf_bytes) > 500:
                with open(output_path, "wb") as f:
                    f.write(pdf_bytes)
                return len(pdf_bytes)
    except Exception as fetch_err:
        print(f"  [Downloader] Fetch error: {fetch_err}", flush=True)
    return 0

def navigate_to_next_page(page) -> bool:
    """
    Clicks the Next button on pagination bar if available.
    """
    try:
        next_btn = page.locator(".dataTables_paginate .next:not(.disabled) a, a.paginate_button.next:not(.disabled), a:has-text('Next')").first
        if next_btn.is_visible() and "disabled" not in (next_btn.get_attribute("class") or ""):
            print("\n[Pagination] Moving to next page...", flush=True)
            next_btn.evaluate("el => el.click()")
            page.wait_for_timeout(2500)
            return True
    except Exception as e:
        print(f"[Pagination] Note: {e}", flush=True)
    return False

def run_mca_agent():
    init_db()
    setup_storage()

    current_count = get_processed_count()
    print("\n" + "=" * 65, flush=True)
    print("  MCA Companies Act, 2013 Document Automation Pipeline", flush=True)
    print(f"  Current in DB: {current_count} | Target limit: {TOTAL_MAX_LIMIT}", flush=True)
    print(f"  Limit per section: {DOCS_PER_SECTION_LIMIT}", flush=True)
    print("=" * 65 + "\n", flush=True)

    if current_count >= TOTAL_MAX_LIMIT:
        print(f"Target limit of {TOTAL_MAX_LIMIT} documents already completed.", flush=True)
        summary = get_summary_by_category()
        print("Category Breakdown:", summary, flush=True)
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1400, "height": 900}
        )
        page = context.new_page()

        def route_handler(route):
            req_url = route.request.url.lower()
            if "clientlib-devtool" in req_url or "restrinewtab" in req_url:
                route.abort()
            else:
                route.continue_()

        page.route("**/*", route_handler)
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.navigator.chrome = { runtime: {} };
        """)

        sections = [
            ("Notifications", "https://www.mca.gov.in/content/mca/global/en/acts-rules/ebooks/notifications.html", "Notifications"),
            ("Circulars", "https://www.mca.gov.in/content/mca/global/en/acts-rules/ebooks/circulars.html", "Circulars"),
            ("Other documents", "https://www.mca.gov.in/content/mca/global/en/acts-rules/ebooks/others.html", "Others")
        ]

        for section_name, section_url, dms_cat in sections:
            if get_processed_count() >= TOTAL_MAX_LIMIT:
                print(f"\nTarget limit of {TOTAL_MAX_LIMIT} documents reached.", flush=True)
                break

            print("\n" + "=" * 65, flush=True)
            print(f" Navigating to section: '{section_name}'", flush=True)
            print("=" * 65, flush=True)

            section_download_count = 0

            try:
                page.goto(section_url, wait_until="domcontentloaded")
                page.wait_for_timeout(2500)

                select_companies_act_filter(page)
                set_results_per_page(page, "50")

                page_num = 1
                while page_num <= 20 and get_processed_count() < TOTAL_MAX_LIMIT and section_download_count < DOCS_PER_SECTION_LIMIT:
                    doc_items = page.evaluate(JS_EXTRACT_PAGE_DOCS)
                    print(f"\n[{section_name} | Page {page_num}] {len(doc_items)} documents listed. (Downloaded: {section_download_count}/{DOCS_PER_SECTION_LIMIT})", flush=True)

                    if not doc_items:
                        print("No documents found on page.", flush=True)
                        break

                    for item in doc_items:
                        if get_processed_count() >= TOTAL_MAX_LIMIT or section_download_count >= DOCS_PER_SECTION_LIMIT:
                            break

                        val = item.get("val")
                        title = item.get("title", "")
                        cat_hint = item.get("category") or dms_cat

                        if not val or not title:
                            continue

                        b64_val = base64.b64encode(val.strip().encode()).decode()
                        real_pdf_url = f"https://www.mca.gov.in/bin/ebook/dms/getdocument?doc={b64_val}&docCategory={cat_hint}"

                        if is_url_processed(real_pdf_url):
                            continue

                        clean_title = re.sub(r'[^a-zA-Z0-9_\-]', '_', title)[:60].strip('_')
                        if not clean_title:
                            clean_title = f"doc_{val}"
                        filename = f"{clean_title}.pdf"
                        temp_path = os.path.join("temp_downloads", filename)

                        curr_total = get_processed_count() + 1
                        safe_title = title.encode('ascii', 'replace').decode('ascii')
                        print(f"\n" + "-" * 65, flush=True)
                        print(f" [{curr_total}/{TOTAL_MAX_LIMIT}] {safe_title}", flush=True)
                        print(f"  Section: '{section_name}' | DocID: {val}", flush=True)
                        print("-" * 65, flush=True)

                        file_size = download_pdf(page, real_pdf_url, temp_path)
                        if file_size == 0 or not os.path.exists(temp_path):
                            print("  [Downloader] Skipping un-downloadable document.", flush=True)
                            continue

                        print(f"  [Downloader] Fetched ({file_size:,} bytes)", flush=True)

                        text_content = extract_text_from_pdf(temp_path)
                        print(f"  [OCR] Extracted {len(text_content):,} characters", flush=True)

                        category = classify_document(filename, text_content, hint=section_name)
                        print(f"  [Classifier] Category: {category} -> /storage/{category}/{filename}", flush=True)

                        dest_dir = os.path.join(STORAGE_DIR, category)
                        os.makedirs(dest_dir, exist_ok=True)
                        dest_path = os.path.join(dest_dir, filename)
                        shutil.move(temp_path, dest_path)

                        record_processed_doc(
                            url=real_pdf_url,
                            filename=filename,
                            category=category,
                            source_tab=section_name,
                            text_preview=text_content,
                            file_size_bytes=file_size
                        )
                        section_download_count += 1

                    if section_download_count >= DOCS_PER_SECTION_LIMIT:
                        print(f"\n[{section_name}] Section limit of {DOCS_PER_SECTION_LIMIT} reached.", flush=True)
                        break

                    if navigate_to_next_page(page):
                        page_num += 1
                    else:
                        print(f"No further pages in section '{section_name}'.", flush=True)
                        break

            except Exception as sec_err:
                print(f"Section '{section_name}' error: {sec_err}", flush=True)

        browser.close()

    summary = get_summary_by_category()
    print("\n" + "=" * 65, flush=True)
    print(f"  Pipeline Run Complete. Total Stored Documents: {get_processed_count()}/{TOTAL_MAX_LIMIT}", flush=True)
    print("  Category Breakdown:", summary, flush=True)
    print("=" * 65 + "\n", flush=True)
