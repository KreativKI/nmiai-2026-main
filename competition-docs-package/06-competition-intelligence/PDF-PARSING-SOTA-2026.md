# PDF Parsing SOTA — March 2026

> **Competition brief:** Written for NM i AI 2026. Prioritizes practical, ready-to-use solutions.
> **Already installed:** `pypdf` (6.7.5), `PyPDF2` (3.0.1). Nothing else pre-installed.

---

## TL;DR Decision Tree

```
Is the PDF text-based (not scanned)?
  YES → pypdf (instant, already installed) or Docling (install needed)
  NO  → Is it scanned/handwritten?
    YES → Mistral OCR 3 API ($2/1k pages) OR PaddleOCR-VL (local, GPU needed)
    MIXED → Docling (best local all-rounder) or MinerU 2.5

Need structured JSON output from tables/forms?
  → Docling (TableFormer) or Mistral OCR 3 (HTML tables in markdown)

No GPU available?
  → Docling (CPU OK, slow), pypdf+LLM hybrid, or cloud API

Need speed + no setup?
  → Mistral OCR 3 API or LlamaParse API
```

---

## Benchmark Leaderboard (OmniDocBench, March 2026)

Source: codesota.com, independently verified, 1,355 images

| Rank | Model | OmniDocBench | olmOCR | Type | License |
|------|-------|-------------|--------|------|---------|
| 1 | **PaddleOCR-VL 7B** (Baidu) | **92.86** | 80.0 | Local | Apache 2.0 |
| 2 | PaddleOCR-VL 0.9B (Baidu) | 92.56 | — | Local | Apache 2.0 |
| 3 | **MinerU 2.5** (OpenDataLab) | **90.67** | 75.2 | Local | AGPL-3.0 |
| 4 | GLM-OCR (0.9B) | 94.62* | — | Local/API | Apache 2.0 |
| 5 | **MonkeyOCR-pro-3B** | 88.85 | — | Local | Apache 2.0/MIT |
| 6 | dots.ocr 3B (RedNote) | 88.41 | 79.1 | Local | Apache 2.0 |
| 7 | Qwen2.5-VL | 87.02 | — | Local | Apache 2.0 |
| 8 | **Marker 1.10.x** | — | 76.5 | Local | Apache 2.0 |
| 9 | GPT-4o | — | 69.9 | API | Commercial |
| 10 | Gemini Flash 2 | — | 63.8 | API | Commercial |

*GLM-OCR score from OmniDocBench v1.5 (slightly different benchmark version).

**For pure text extraction:** GPT-4o wins (0.02 edit distance — best in class).
**For document parsing (tables + layout):** PaddleOCR-VL 7B wins.
**Best lightweight local:** PaddleOCR-VL 0.9B (near-SOTA, tiny footprint).

---

## Open Source Tools — Detailed

### 1. Docling (IBM Research) ⭐ Recommended for competition

- **What it is:** End-to-end document converter, 37k+ GitHub stars, donated to Linux Foundation (AAIF)
- **Key models:** TableFormer (table cell mapping), Heron layout model (Dec 2025, faster), Granite-Docling-258M (VLM, Apache 2.0, released early 2026)
- **Output formats:** Markdown, JSON, HTML, DocTags (unified DoclingDocument format)
- **Accuracy on complex layouts:** Good. Handles multi-level headers, merged cells, multi-column. Missed 2/5 tables in one benchmark test — not perfect.
- **Speed:** CPU OK (slow on large docs), GPU recommended. Heron model is significantly faster than prior versions.
- **Cost:** Free, local
- **Python install:**
  ```bash
  pip install docling
  ```
- **Quick usage:**
  ```python
  from docling.document_converter import DocumentConverter
  
  converter = DocumentConverter()
  result = converter.convert("path/to/document.pdf")
  
  # Get markdown
  markdown = result.document.export_to_markdown()
  
  # Get tables as DataFrames
  for i, table in enumerate(result.document.tables):
      df = table.export_to_dataframe(doc=result.document)
      print(f"Table {i+1}: {df.shape}")
  
  # Get JSON
  json_data = result.document.export_to_dict()
  ```
- **Strengths:** Best all-rounder for local use, active development, RAG-ready chunking, good for structured data extraction pipelines
- **Weaknesses:** Can miss tables on complex PDFs, slower than cloud APIs without GPU

---

### 2. Marker (Vik Paruchuri)

- **What it is:** Vision-transformer pipeline using Surya OCR under the hood
- **Current version:** 1.10.1 (olmOCR benchmark: 76.5)
- **Accuracy:** Good on simple-to-medium tables. Struggles with highly complex merged cells or multi-column layouts. Accuracy "depends heavily on visual complexity."
- **Speed:** GPU recommended, runs locally
- **Cost:** Free, local
- **License:** Apache 2.0/MIT
- **Python install:**
  ```bash
  pip install marker-pdf
  ```
- **Quick usage:**
  ```python
  from marker.convert import convert_single_pdf
  from marker.models import load_all_models
  
  models = load_all_models()
  full_text, images, metadata = convert_single_pdf("document.pdf", models)
  # full_text is markdown
  ```
- **Strengths:** Extracts images, tables, formulas; good for research papers
- **Weaknesses:** Surya OCR layer adds complexity; less accurate than Docling on complex tables; lower benchmark scores

---

### 3. MinerU 2.5 (OpenDataLab / Shanghai AI Lab)

- **What it is:** 1.2B parameter VLM for PDF parsing. Two-stage: global structure at 1036x1036px, then fragment crops at native resolution
- **Benchmark:** 90.67 OmniDocBench (3rd overall), 2.12 pages/sec on A100 (4x faster than MonkeyOCR-pro-3B)
- **Architecture:** NaViT encoder (675M, init from Qwen2-VL) + Qwen2-Instruct decoder (0.5B)
- **License:** AGPL-3.0
- **GPU requirement:** A100 or similar for speed; will run on lesser hardware
- **Python install:**
  ```bash
  pip install magic-pdf[full]
  # or: pip install mineru
  ```
- **Quick usage:**
  ```python
  from magic_pdf.data.data_reader_writer import FileBasedDataWriter
  from magic_pdf.pipe.UNIPipe import UNIPipe
  from magic_pdf.rw.DiskReaderWriter import DiskReaderWriter
  
  # Simple one-liner approach
  import subprocess
  subprocess.run(["magic-pdf", "-p", "document.pdf", "-o", "output/"])
  ```
- **Strengths:** Excellent accuracy, handles scanned PDFs well, very fast on A100
- **Weaknesses:** AGPL license (copyleft), needs GPU for competition-speed, heavier setup

---

### 4. PaddleOCR-VL (Baidu)

- **What it is:** Current SOTA on OmniDocBench. VL model that bridges images/PDFs to structured data for LLMs
- **Versions:** 7B (best accuracy: 92.86) and 0.9B (near-SOTA: 92.56, lightweight)
- **Features:** 100+ languages, handles skewed/warped scans, lighting variations, tables, formulas, charts
- **License:** Apache 2.0
- **Python install:**
  ```bash
  pip install paddlepaddle paddleocr
  ```
- **Quick usage:**
  ```python
  from paddleocr import PaddleOCR
  
  ocr = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=True)
  result = ocr.ocr('document.pdf', cls=True)
  for line in result:
      print(line)
  
  # For VL model (structured output):
  from paddleocr import PPStructure
  table_engine = PPStructure(show_log=True)
  result = table_engine('document_page.png')
  ```
- **Strengths:** SOTA accuracy, handles distortions, 100+ languages, small 0.9B variant available
- **Weaknesses:** Baidu ecosystem, setup can be complex; best results need GPU

---

### 5. olmOCR (Allen AI)

- **What it is:** Distributed pipeline for large-scale PDF conversion using VLMs. "Unlocking trillions of tokens in PDFs"
- **Version:** v0.4.0 (82.4 on olmOCR benchmark)
- **License:** Apache 2.0
- **Architecture:** Distributed worker architecture, designed for scale
- **Python install:**
  ```bash
  pip install olmocr
  ```
- **Strengths:** Designed for bulk processing, open weights, good for building pipelines
- **Weaknesses:** Overkill for single documents; designed for scale not per-document use

---

### 6. Surya (Vik Paruchuri)

- **What it is:** The OCR/layout model powering Marker. Can be used standalone.
- **Features:** Line-level OCR, layout detection, reading order detection, table recognition
- **Python install:**
  ```bash
  pip install surya-ocr
  ```
- **Quick usage:**
  ```python
  from surya.ocr import run_ocr
  from surya.model.detection.model import load_model, load_processor
  
  model, processor = load_model(), load_processor()
  # predictions = run_ocr(images, [["en"]], det_model, det_processor, model, processor)
  ```

---

### 7. Unstructured

- **What it is:** General document parsing (PDF, Word, HTML, email, etc.)
- **Approach:** Combines PDFMiner, Tesseract, and model-based layout detection
- **Python install:**
  ```bash
  pip install unstructured[pdf]
  ```
- **Quick usage:**
  ```python
  from unstructured.partition.pdf import partition_pdf
  
  elements = partition_pdf("document.pdf", strategy="hi_res")
  for element in elements:
      print(type(element).__name__, element.text[:100])
  ```
- **Strengths:** Handles many document types uniformly, good for mixed pipelines
- **Weaknesses:** Lower accuracy than specialized tools on complex tables; slower

---

## Cloud APIs

### Mistral OCR 3 ⭐ Best cloud option for handwriting/scanned docs

- **Released:** January 2026
- **Key improvement:** 74% win rate over OCR 2 in internal benchmarks (real customer workflows). Significantly better on forms, handwriting, table-heavy documents.
- **Output:** Markdown with HTML table tags (`<rowspan>`, `<colspan>`) — preserves layout semantics
- **Scanned doc accuracy:** 98.96% on scanned documents
- **Handwriting:** Handles cursive notes, annotations, checkboxes, mixed entries
- **Resilience:** Handles skew, compression artifacts, low resolution, background noise
- **Cost:** $2/1,000 pages | $1/1,000 pages (Batch API)
- **Model ID:** `mistral-ocr-2512`
- **Python usage:**
  ```python
  from mistralai import Mistral
  import base64
  
  client = Mistral(api_key="YOUR_KEY")
  
  # For PDF URL
  result = client.ocr.process(
      model="mistral-ocr-latest",
      document={"type": "document_url", "document_url": "https://..."}
  )
  
  # For local file
  with open("document.pdf", "rb") as f:
      pdf_data = base64.b64encode(f.read()).decode()
  
  result = client.ocr.process(
      model="mistral-ocr-latest",
      document={"type": "document_url", "document_url": f"data:application/pdf;base64,{pdf_data}"}
  )
  print(result.pages[0].markdown)
  ```
- **Practical:** Best for competition — no GPU needed, handles anything, cheap, fast

---

### LlamaParse (LlamaIndex)

- **What it is:** Cloud API, LLM-guided extraction preserving text/tables/images relationships
- **Best for:** RAG pipelines, preserving document structure for retrieval
- **Cost:** Free tier available; paid plans
- **Python usage:**
  ```python
  from llama_parse import LlamaParse
  
  parser = LlamaParse(api_key="YOUR_KEY", result_type="markdown")
  documents = parser.load_data("document.pdf")
  ```
- **Strengths:** Easy, no GPU, handles mixed content well, maintains image-text relationships

---

### Azure Document Intelligence

- **Latest API:** 2024-11-30 (GA); positioned for stability over rapid new features
- **Best approach (Microsoft recommended):** Layout model → Markdown → GPT-4o
- **Pricing:** ~$10/1,000 pages (prebuilt) | ~$30/1,000 pages (custom)
- **Strengths:** Enterprise-grade, confidence scores, bounding boxes, JSON output, good on structured business docs (invoices, contracts)
- **Python usage:**
  ```python
  from azure.ai.documentintelligence import DocumentIntelligenceClient
  from azure.core.credentials import AzureKeyCredential
  
  client = DocumentIntelligenceClient(endpoint, AzureKeyCredential(key))
  with open("document.pdf", "rb") as f:
      poller = client.begin_analyze_document("prebuilt-layout", f)
  result = poller.result()
  ```

---

### Google Document AI

- **Features:** Pre-trained processors for invoices, forms, contracts; custom model training
- **Strengths:** Best enterprise option for Google Cloud teams; strong accuracy on structured docs
- **Python:** `google-cloud-documentai` package

---

### AWS Textract

- **Features:** Tables, forms, queries (targeted field extraction), Expense/Identity document analysis
- **Best for:** AWS-native pipelines; good at forms
- **Python:** `boto3` with `textract` client

---

### Firecrawl PDF Parser v2 (March 2026)

- **New:** Rust-based parser, 3x faster than previous
- **Modes:** `fast` (Rust text extraction) | `auto` (tries fast, falls back to OCR) | `ocr` (full OCR)
- **Best for:** Web-hosted PDFs in AI pipelines
- **Python usage:**
  ```python
  from firecrawl import Firecrawl
  
  firecrawl = Firecrawl(api_key='fc-YOUR_API_KEY')
  result = firecrawl.scrape(
      url='https://example.com/document.pdf',
      formats=['markdown'],
      parsePDF='auto'  # or 'fast' or 'ocr'
  )
  ```

---

## Vision Model Approaches (VLM-as-Parser)

For when the PDF pages are converted to images and fed directly to a multimodal LLM:

### GPT-4o (OpenAI)
- **Best for:** Pure text extraction (0.02 edit distance — best in class)
- **Cost:** ~$0.05–0.07/page as images
- **Usage pattern:** `pdf2image` → base64 encode → GPT-4o with structured output
  ```python
  from pdf2image import convert_from_path
  import base64, io
  from openai import OpenAI
  
  client = OpenAI()
  images = convert_from_path("document.pdf", dpi=200)
  
  for i, img in enumerate(images):
      buffered = io.BytesIO()
      img.save(buffered, format="PNG")
      img_b64 = base64.b64encode(buffered.getvalue()).decode()
      
      response = client.chat.completions.create(
          model="gpt-4o",
          messages=[{
              "role": "user",
              "content": [
                  {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                  {"type": "text", "text": "Extract all text and tables from this PDF page. Return as structured markdown."}
              ]
          }]
      )
      print(response.choices[0].message.content)
  ```

### Gemini 2.5 Pro (Google)
- **Best for:** Chinese documents (62.2% OCRBench v2 Chinese); native PDF ingestion
- **Native PDF support:** Can send PDF bytes directly (no image conversion needed)
  ```python
  import google.generativeai as genai
  
  genai.configure(api_key="YOUR_KEY")
  model = genai.GenerativeModel("gemini-2.5-pro")
  
  with open("document.pdf", "rb") as f:
      pdf_bytes = f.read()
  
  response = model.generate_content([
      {"mime_type": "application/pdf", "data": pdf_bytes},
      "Extract all tables and structured data from this PDF."
  ])
  ```

### Claude 3.5 Sonnet / Opus (Anthropic)
- **Best for:** Reasoning about document structure, entity extraction
- **Usage:** Same pattern as GPT-4o (images via base64) or use `anthropic-sdk` with vision

---

## Hybrid Approach (Best Practice 2026)

The most reliable production pattern for complex PDFs:

```
Step 1: Extract text layer with pypdf/pdfplumber (instant, free)
  → If good text quality: feed to LLM for structure extraction
  → If poor/no text: proceed to Step 2

Step 2: Convert pages to images (pdf2image, 200-300 DPI)

Step 3: Run through specialized parser:
  - Local + GPU: PaddleOCR-VL or MinerU 2.5
  - Local + CPU: Docling
  - Cloud: Mistral OCR 3 (best for handwriting) or LlamaParse

Step 4: LLM pass for semantic understanding:
  - Feed structured markdown to Claude/GPT-4o
  - Extract specific fields with structured outputs (JSON mode)
```

**Microsoft's recommended hybrid:**
```
Azure Document Intelligence (Layout) → Markdown → GPT-4o → JSON
```

**Best local hybrid:**
```
Docling (layout + tables) → Markdown → any LLM → JSON
```

---

## Competition Quick-Start (< 5 minutes to working)

### Option A: Already works (no install)
```python
import pypdf

reader = pypdf.PdfReader("document.pdf")
text = ""
for page in reader.pages:
    text += page.extract_text() + "\n\n"
print(text)
# Then feed 'text' to Claude/GPT for structured extraction
```

### Option B: Install Docling (~2 min, handles complex layouts)
```bash
pip install docling
```
```python
from docling.document_converter import DocumentConverter
result = DocumentConverter().convert("document.pdf")
print(result.document.export_to_markdown())
```

### Option C: Mistral OCR 3 (best for scanned/handwritten, needs API key)
```bash
pip install mistralai
```
```python
from mistralai import Mistral
client = Mistral(api_key="YOUR_KEY")
result = client.ocr.process(
    model="mistral-ocr-latest",
    document={"type": "document_url", "document_url": "file:///path/to/doc.pdf"}
)
for page in result.pages:
    print(page.markdown)
```

### Option D: pdfplumber (better than pypdf for tables, no setup)
```bash
pip install pdfplumber
```
```python
import pdfplumber

with pdfplumber.open("document.pdf") as pdf:
    for page in pdf.pages:
        print(page.extract_text())
        for table in page.extract_tables():
            print(table)  # list of rows
```

---

## New Entrants (Last 3 Months)

| Tool | Released | Key Feature | Status |
|------|----------|-------------|--------|
| **Granite-Docling-258M** | Early 2026 | IBM VLM for document conversion, Apache 2.0 | Production |
| **GLM-OCR 0.9B** | 2025-2026 | 94.62 OmniDocBench v1.5 (SOTA), 1.86 pages/sec | Available |
| **Mistral OCR 3** | Jan 2026 | 74% better than OCR 2, 98.96% scanned accuracy | Production |
| **Docling Heron layout** | Dec 2025 | Faster layout detection in Docling pipeline | Merged to main |
| **PaddleOCR-VL-1.5** | Late 2025 | 0.9B model, SOTA accuracy | Production |
| **Firecrawl PDF Parser v2** | Mar 2026 | 3x faster Rust parser, auto mode | Production |
| **DeepSeek-OCR-2** | Jan 2026 | 3B, 10x token compression, 200k pages/day A100 | Available |
| **olmOCR v0.4.0** | Late 2025 | Allen AI, Apache 2.0, distributed scale | Production |

---

## Scanned / Handwritten PDFs — Special Notes

This is the hardest case. Best options ranked:

1. **Mistral OCR 3** (cloud): 98.96% accuracy on scanned docs. Handles cursive, forms, low-res, noise. Best pick if API key available.
2. **GPT-4o vision** (cloud): Best handwriting per olmOCR benchmark. More expensive ($0.05-0.07/page).
3. **PaddleOCR-VL** (local): Handles skewed/warped scans, lighting variations. Needs GPU.
4. **MinerU 2.5** (local): Good for selection marks, checkboxes, scanned matrices. AGPL.
5. **Docling** (local): CPU-capable but slower; less specialized for scanned content.
6. **Tesseract** (local): Legacy but reliable for simple clean scans; no GPU needed.

For competition: **Mistral OCR 3 API is the pragmatic choice** — no GPU needed, cheapest cloud option, handles everything.

---

## Cost Comparison (per 1,000 pages)

| Tool | Cost | Notes |
|------|------|-------|
| pypdf / pdfplumber | Free | Text-only PDFs, no layout |
| Docling / Marker / MinerU | Free | Local compute only |
| Mistral OCR 3 | $2 ($1 batch) | Best value cloud |
| LlamaParse | $3+ | Cloud, RAG-optimized |
| Azure Document Intelligence | $10–30 | Enterprise, bounding boxes |
| Google Document AI | $5–65 | Varies by processor |
| AWS Textract | $1.50–15 | Forms/tables extra |
| GPT-4o (images) | $50–70 | ~$0.05-0.07/page |

---

## Recommended Stack for NM i AI 2026

**Tier 1 (install now, no API key needed):**
- `pypdf` — already there, use for clean text PDFs
- `pdfplumber` — install for table extraction from text PDFs
- `docling` — install as main heavy-lifter

**Tier 2 (if APIs available):**
- Mistral OCR 3 — for scanned/handwritten
- Gemini 2.5 Pro — PDF-native, good reasoner

**Tier 3 (if GPU available):**
- MinerU 2.5 (AGPL) or PaddleOCR-VL (Apache 2.0)

```bash
# Install the essentials right now:
pip install pdfplumber docling
```

---

*Last updated: 2026-03-19 | Sources: codesota.com benchmarks, InfoQ, neurohive.io, codecut.ai, regolo.ai*
