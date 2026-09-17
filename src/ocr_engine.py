import os
import re
import numpy as np
import pymupdf
import pdfplumber
from rapidocr_onnxruntime import RapidOCR

ocr_engine = RapidOCR()

def extract_text_with_aws_textract(pdf_path: str) -> str:
    """
    Extracts text using AWS Textract if AWS credentials and boto3 are available.
    """
    aws_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

    if not aws_key or not aws_secret:
        return ""

    try:
        import boto3
        client = boto3.client(
            "textract",
            aws_access_key_id=aws_key,
            aws_secret_access_key=aws_secret,
            region_name=aws_region
        )
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        response = client.detect_document_text(Document={"Bytes": pdf_bytes})
        lines = [item["Text"] for item in response.get("Blocks", []) if item.get("BlockType") == "LINE"]
        return "\n".join(lines).strip()
    except Exception as e:
        print(f"[AWS Textract] Notice: {e}. Using local OCR engine.", flush=True)
        return ""

def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extracts text from PDF.
    1. Checks AWS Textract (if configured).
    2. Native digital text extraction via PyMuPDF.
    3. If text density is low (scanned document), falls back to RapidOCR.
    """
    # 1. AWS Textract check
    if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
        aws_text = extract_text_with_aws_textract(pdf_path)
        if len(aws_text.strip()) > 100:
            return aws_text

    extracted_text = ""
    
    # 2. Native PDF text extraction using PyMuPDF
    try:
        doc = pymupdf.open(pdf_path)
        for page in doc:
            page_text = page.get_text("text")
            if page_text:
                extracted_text += page_text + "\n"
        doc.close()
    except Exception as e:
        print(f"[OCR] PyMuPDF note for {pdf_path}: {e}", flush=True)

    clean_native_text = re.sub(r'\s+', ' ', extracted_text).strip()
    if len(clean_native_text) > 150:
        return extracted_text.strip()

    print(f"[OCR Module] Scanned PDF detected ({len(clean_native_text)} chars). Running RapidOCR engine...", flush=True)
    
    # 3. Scanned OCR fallback using RapidOCR (NumPy array format)
    ocr_text_parts = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages[:3]:
                pil_image = page.to_image(resolution=200).original
                np_img = np.array(pil_image)
                result, _ = ocr_engine(np_img)
                if result:
                    page_ocr = "\n".join([item[1] for item in result])
                    ocr_text_parts.append(page_ocr)
    except Exception as e:
        print(f"[OCR] RapidOCR note for {pdf_path}: {e}", flush=True)

    final_ocr_text = "\n".join(ocr_text_parts).strip()
    return final_ocr_text if final_ocr_text else extracted_text.strip()
