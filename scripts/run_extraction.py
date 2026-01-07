import argparse
import base64
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import time
import fitz  # PyMuPDF
import openai

import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))

from models.canonical import StatementDocument, InvoiceDocument


REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPTS_DIR = REPO_ROOT / "prompts"
ARTIFACTS_DIR = REPO_ROOT / "artifacts"


def load_env_var(name: str) -> str | None:
    value = os.getenv(name)
    if value:
        return value
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if not line or line.strip().startswith("#"):
            continue
        key, _, val = line.partition("=")
        if key.strip() == name:
            return val.strip()
    return None


def read_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def page_to_png_b64(page: fitz.Page, zoom: float = 2.0) -> str:
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    png_bytes = pix.tobytes("png")
    return base64.b64encode(png_bytes).decode("ascii")


def call_openai_vision(prompt: str, images_b64: List[str], api_key: str) -> str:
    """Call OpenAI vision API using the official SDK."""
    client = openai.OpenAI(api_key=api_key, timeout=600.0)
    
    content = [{"type": "text", "text": prompt}]
    for img in images_b64:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{img}", "detail": "high"},
        })

    print(f"  Sending {len(images_b64)} image(s) to GPT-4o...")
    
    for attempt in range(5):
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": content}],
                temperature=0,
                max_tokens=16000,
            )
            return response.choices[0].message.content
        except openai.RateLimitError as e:
            retry_after = 60
            print(f"  Rate limited, waiting {retry_after}s (attempt {attempt + 1}/5)...")
            time.sleep(retry_after)
        except openai.APITimeoutError:
            print(f"  Timeout, retrying (attempt {attempt + 1}/5)...")
            time.sleep(10)
    
    raise RuntimeError("Failed after 5 attempts")


def parse_json_str(raw_text: str) -> dict:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(raw_text[start:end + 1])
        raise


def categorize_pages(doc: fitz.Document, statement_keyword: str, invoice_keyword: str) -> Tuple[List[int], List[int]]:
    statement_pages = []
    invoice_pages = []
    for i in range(doc.page_count):
        text = doc.load_page(i).get_text("text").lower()
        if statement_keyword in text:
            statement_pages.append(i)
        elif invoice_keyword in text:
            invoice_pages.append(i)
    return statement_pages, invoice_pages


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def run_statement(pdf_path: Path, prompt_name: str, statement_pages: List[int], api_key: str, output_path: Path) -> None:
    prompt = read_prompt("system.txt") + "\n" + read_prompt(prompt_name)

    with fitz.open(pdf_path) as doc:
        images = [page_to_png_b64(doc.load_page(i)) for i in statement_pages]

    raw = call_openai_vision(prompt, images, api_key)
    parsed = parse_json_str(raw)

    parsed.setdefault("document_metadata", {})
    parsed["document_metadata"].update({
        "source_file": str(pdf_path),
        "page_count": len(statement_pages),
        "extracted_at": datetime.utcnow().isoformat(),
    })

    StatementDocument.model_validate(parsed)

    save_json(output_path, parsed)


def run_invoice_pages(pdf_path: Path, prompt_name: str, invoice_pages: List[int], api_key: str, output_dir: Path) -> None:
    prompt = read_prompt("system.txt") + "\n" + read_prompt(prompt_name)

    with fitz.open(pdf_path) as doc:
        for i in invoice_pages:
            images = [page_to_png_b64(doc.load_page(i))]
            raw = call_openai_vision(prompt, images, api_key)
            parsed = parse_json_str(raw)

            parsed.setdefault("document_metadata", {})
            parsed["document_metadata"].update({
                "source_file": str(pdf_path),
                "page_count": 1,
                "extracted_at": datetime.utcnow().isoformat(),
            })

            invoice = InvoiceDocument.model_validate(parsed)
            invoice_number = invoice.invoice_number or f"page_{i + 1}"
            safe_name = "".join(ch for ch in invoice_number if ch.isalnum() or ch in ("-", "_"))
            out_path = output_dir / f"{safe_name}.json"
            save_json(out_path, invoice.model_dump(mode="json", by_alias=True))


def run_extraction(bovina_pdf: Path, mesquite_pdf: Path, api_key: str) -> None:
    ensure_dir(ARTIFACTS_DIR)

    with fitz.open(bovina_pdf) as doc:
        bovina_statement_pages, bovina_invoice_pages = categorize_pages(
            doc,
            statement_keyword="statement of notes",
            invoice_keyword="feed invoice",
        )

    bovina_dir = ARTIFACTS_DIR / "bovina"
    bovina_invoices_dir = bovina_dir / "invoices"
    ensure_dir(bovina_invoices_dir)

    if bovina_statement_pages:
        run_statement(
            bovina_pdf,
            "bovina_statement_prompt.txt",
            bovina_statement_pages,
            api_key,
            bovina_dir / "statement.json",
        )

    if bovina_invoice_pages:
        run_invoice_pages(
            bovina_pdf,
            "bovina_invoice_prompt.txt",
            bovina_invoice_pages,
            api_key,
            bovina_invoices_dir,
        )

    with fitz.open(mesquite_pdf) as doc:
        mesquite_statement_pages, mesquite_invoice_pages = categorize_pages(
            doc,
            statement_keyword="statement of account",
            invoice_keyword="invoice",
        )

    mesquite_dir = ARTIFACTS_DIR / "mesquite"
    mesquite_invoices_dir = mesquite_dir / "invoices"
    ensure_dir(mesquite_invoices_dir)

    if mesquite_statement_pages:
        run_statement(
            mesquite_pdf,
            "mesquite_statement_prompt.txt",
            mesquite_statement_pages,
            api_key,
            mesquite_dir / "statement.json",
        )

    if mesquite_invoice_pages:
        mesquite_invoice_pages = [i for i in mesquite_invoice_pages if i not in mesquite_statement_pages]
        run_invoice_pages(
            mesquite_pdf,
            "mesquite_invoice_prompt.txt",
            mesquite_invoice_pages,
            api_key,
            mesquite_invoices_dir,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bovina", default=r"C:\Users\sunil\Downloads\Sunil Meetings\Prospects\Sugar Mountain\Bovina.pdf")
    parser.add_argument("--mesquite", default=r"C:\Users\sunil\Downloads\Sunil Meetings\Prospects\Sugar Mountain\Mesquite.pdf")
    args = parser.parse_args()

    api_key = load_env_var("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is not set. Add it to .env or environment.")

    run_extraction(Path(args.bovina), Path(args.mesquite), api_key)


if __name__ == "__main__":
    main()
