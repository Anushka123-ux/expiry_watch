import os
import re
import json
from io import BytesIO
from datetime import datetime
from PIL import Image, ImageOps
import pytesseract
from pypdf import PdfReader
from groq import Groq
from dotenv import load_dotenv
import pypdfium2 as pdfium

# Load .env variables so os.getenv("GROQ_API_KEY") works
load_dotenv()

SUPPORTED_TYPES = ["Driving License", "Passport", "Insurance", "Certificate", "Invoice", "Contract"]

MONTH_MAP = {
    "jan": "01", "january": "01",
    "feb": "02", "february": "02",
    "mar": "03", "march": "03",
    "apr": "04", "april": "04",
    "may": "05",
    "jun": "06", "june": "06",
    "jul": "07", "july": "07",
    "aug": "08", "august": "08",
    "sep": "09", "september": "09",
    "oct": "10", "october": "10",
    "nov": "11", "november": "11",
    "dec": "12", "december": "12",
}

def classify_document(text: str) -> str:
    """Classifies document by scanning for domain keywords."""
    lower_text = text.lower()
    
    # Priority: Identity & travel documents
    if any(k in lower_text for k in ["passport", "pasaporte", "passeport", "united states of america", "p<usa"]):
        return "Passport"
    if any(k in lower_text for k in ["driver license", "driving licence", "union driving license", "motor vehicle", "validity"]):
        return "Driving License"
    if any(k in lower_text for k in ["national id", "identity card", "aadhar", "ssn"]):
        return "National ID"
    if any(k in lower_text for k in ["rx", "capsule", "tablet", "mfg date", "exp date", "mg", "ml"]):
        return "Medication"
    if any(k in lower_text for k in ["insurance", "policy number", "coverage", "premium"]):
        return "Insurance"
    if any(k in lower_text for k in ["certify", "certificate", "degree", "diploma"]):
        return "Certificate"
    if any(k in lower_text for k in ["tax invoice", "gst tax invoice", "invoice no", "bill to", "retail invoice"]):
        return "Invoice / Receipt"
    if any(k in lower_text for k in ["agreement", "contract", "parties", "hereby", "terms and conditions"]):
        return "Contract"
        
    return "General Document"

def validate_and_format_date(year: str | int, month: str | int, day: str | int) -> str | None:
    """Validates real calendar boundaries (e.g. rejects day > 31 or invalid months)."""
    try:
        y, m, d = int(year), int(month), int(day)
        dt = datetime(year=y, month=m, day=d)
        return dt.strftime("%Y-%m-%d")
    except (ValueError, OverflowError):
        return None

def extract_dates_with_regex(text: str) -> str | None:
    """Extracts dates strictly near expiration-related keywords."""
    textual_pattern = re.compile(
        r'\b(\d{1,2})[\s\-\/\.](jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)[\s\-\/\.](\d{4})\b',
        re.IGNORECASE
    )
    
    textual_prefix_pattern = re.compile(
        r'\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)[\s\-\/\.](\d{1,2})[\,\s\-\/\.]+(\d{4})\b',
        re.IGNORECASE
    )
    
    numeric_iso = re.compile(r'\b(\d{4})[\-\/\.](\d{1,2})[\-\/\.](\d{1,2})\b')
    numeric_standard = re.compile(r'\b(\d{1,2})[\-\/\.](\d{1,2})[\-\/\.](\d{4})\b')

    # Look specifically for lines indicating expiration
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        if any(term in line.lower() for term in ["expir", "exp.", "exp date", "valid until", "expiration", "caducidad"]):
            # Check current line + next line (labels often sit right above the date)
            context = line + " " + (lines[idx + 1] if idx + 1 < len(lines) else "")
            
            match = textual_pattern.search(context)
            if match:
                day, month_name, year = match.groups()
                month = MONTH_MAP[month_name.lower()]
                validated = validate_and_format_date(year, month, day)
                if validated:
                    return validated

            match_prefix = textual_prefix_pattern.search(context)
            if match_prefix:
                month_name, day, year = match_prefix.groups()
                month = MONTH_MAP[month_name.lower()]
                validated = validate_and_format_date(year, month, day)
                if validated:
                    return validated

            match_iso = numeric_iso.search(context)
            if match_iso:
                year, month, day = match_iso.groups()
                validated = validate_and_format_date(year, month, day)
                if validated:
                    return validated

            match_std = numeric_standard.search(context)
            if match_std:
                day, month, year = match_std.groups()
                validated = validate_and_format_date(year, month, day)
                if validated:
                    return validated

    # Do NOT guess random dates from the rest of the text; delegate to Groq LLM instead
    return None

def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    """Safely extracts raw text from PDF or image without crashing on malformed files."""
    text = ""
    filename_lower = filename.lower()
    
    # Check if the file is genuinely a PDF by examining the header magic bytes
    is_real_pdf = file_bytes.startswith(b"%PDF-") or filename_lower.endswith(".pdf")
    
    if is_real_pdf and file_bytes.startswith(b"%PDF-"):
        # Step 1: Attempt digital PDF text extraction
        try:
            from pypdf import PdfReader
            pdf_file = BytesIO(file_bytes)
            reader = PdfReader(pdf_file)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
        except Exception as e:
            print(f"[PDF Extract Warning] Direct digital extraction failed: {e}")

        # Step 2: If no digital text, render pages via pypdfium2 for OCR
        if not text.strip():
            try:
                import pypdfium2 as pdfium
                # Pass raw file_bytes directly to pypdfium2
                pdf = pdfium.PdfDocument(file_bytes)
                first_page = pdf[0]
                image = first_page.render(scale=2).to_pil().convert("L")
                text = pytesseract.image_to_string(image, config="--psm 11")
                pdf.close()
            except Exception as e:
                print(f"[OCR Warning] pypdfium2 rendering failed: {e}")

    # Step 3: Image processing (runs for images OR for files renamed to .pdf that failed above)
    if not text.strip():
        try:
            image = Image.open(BytesIO(file_bytes))
            gray = image.convert("L")
            text = pytesseract.image_to_string(gray, config="--psm 11")
        except Exception as e:
            print(f"[Image Read Error] Pillow OCR failed: {e}")

    return text

def layer1_regex_extraction(ocr_text: str):
    """Deterministic extraction using modular classification and date parsers."""
    detected_type = classify_document(ocr_text)
    detected_date = extract_dates_with_regex(ocr_text)
    return detected_type, detected_date

def layer2_groq_fallback(ocr_text: str):
    """Structured extraction via Groq LLM with robust error handling."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("[Groq Warning] GROQ_API_KEY is not set or not loaded from .env")
        return None, None

    client = Groq(api_key=api_key)
    prompt = f"""
    Analyze the following OCR text from an uploaded document.
    Extract the Document Type (must be one of: "Driving License", "Passport", "Insurance", "Certificate", "Contract")
    and the Expiry Date (formatted strictly as YYYY-MM-DD). If no expiry date exists, return null.

    OCR TEXT:
    {ocr_text[:2000]}

    Respond ONLY with valid JSON in this exact structure:
    {{"document_type": "...", "expiry_date": "YYYY-MM-DD"}}
    """

    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="openai/gpt-oss-20b",
            response_format={"type": "json_object"},
            temperature=0.0
        )
        data = json.loads(response.choices[0].message.content)
        print(f"[Groq Response] {data}")
        return data.get("document_type"), data.get("expiry_date")
    except Exception as e:
        print(f"[Groq Fallback Error] {e}")
        return None, None

def process_document(file_bytes: bytes, filename: str):
    ocr_text = extract_text_from_file(file_bytes, filename)
    print("\n--- [DEBUG] PDF OCR EXTRACTED TEXT ---")
    print(repr(ocr_text[:500]))
    print("--------------------------------------\n")
    
    # 1. Deterministic Regex Layer
    doc_type, exp_date = layer1_regex_extraction(ocr_text)
    method_used = "regex"

    # 2. Trigger Groq if no expiry date was found OR doc_type is ambiguous
    if not exp_date or doc_type in ["General Document", "Contract", "Certificate"]:
        doc_type_llm, exp_date_llm = layer2_groq_fallback(ocr_text)
        if exp_date_llm:
            exp_date = exp_date_llm
            method_used = "groq_fallback"
        if doc_type_llm:
            doc_type = doc_type_llm

    return {
        "document_type": doc_type,
        "expiry_date": exp_date,
        "extraction_method": method_used
    }