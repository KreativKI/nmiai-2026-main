# PDF Parsing for Accounting Documents: Research (March 2026)

**Purpose:** Evaluate PDF extraction methods for the Tripletex AI accounting agent.
**Context:** The bot receives PDF attachments (invoices, receipts, expense reports) via base64 and must extract structured fields (amounts, dates, vendor names, line items) within a 120-second Cloud Run timeout on 1GB memory.
**Current approach:** Send raw PDF bytes to Gemini 2.5 Flash as multimodal input via `types.Part.from_bytes()`.

---

## 1. Multimodal LLM Approaches (Native PDF Handling)

### A. Gemini 2.5 Flash (current approach)

| Attribute | Details |
|-----------|---------|
| **Version** | gemini-2.5-flash (GA via Vertex AI) |
| **Last updated** | Continuously updated through 2025-2026 |
| **How PDFs are handled** | Native: extracts embedded text + renders each page as image. Both are fed to the model simultaneously. No separate OCR step needed. |
| **Structured output** | `response_schema` parameter with Pydantic models or JSON Schema. Guarantees valid JSON matching the schema. Set `response_mime_type="application/json"`. |
| **Page limits** | Up to 1,000 pages per request. Each page = ~258 tokens. |
| **Speed** | Fast. A 1-2 page invoice typically processes in 2-5 seconds. |
| **Runs locally?** | No. API call to Vertex AI / Google AI. |
| **Cost** | ~$0.015 per invoice (2,500 tokens). Free native text tokens in Gemini 3 models. |
| **Norwegian support** | Strong. Multilingual by design. Handles Norwegian characters (ae, oe, aa) well. Tested with 7-language prompts in current bot. |
| **Scanned invoice accuracy** | 94% (best among LLMs in Koncile benchmark). |
| **Text PDF accuracy** | 96% (competitive with GPT/Claude). |

**Key advantage for our use case:** Already integrated. Zero additional dependencies. Structured output via `response_schema` means we can define a Pydantic model for invoice fields and get guaranteed JSON back. No extra parsing step, no additional container size.

**New feature (2026):** Gemini 3 models do not charge for tokens from native PDF text, only for page image tokens. This makes text-heavy PDFs cheaper to process.

### B. Claude (Anthropic)

| Attribute | Details |
|-----------|---------|
| **Version** | Claude 4 family (Opus 4.6, Sonnet 4) |
| **Last updated** | PDF support GA since mid-2025. Files API added 2025. |
| **How PDFs are handled** | Each page is converted to an image + text extracted. Both interleaved in natural order. |
| **Structured output** | Tool use / function calling for structured extraction. No native `response_schema` like Gemini, but tool_use achieves the same result. |
| **Page limits** | 600 pages (100 for 200k context models). Max 32MB per request. |
| **Speed** | 3-8 seconds for a 1-2 page document, depending on model. Sonnet is fastest. |
| **Runs locally?** | No. API call. |
| **Cost** | ~$0.019 per invoice (Sonnet 3.5 pricing). |
| **Norwegian support** | Strong multilingual capabilities. |
| **Scanned invoice accuracy** | 90% (Koncile benchmark). |
| **Text PDF accuracy** | 97% (Koncile benchmark, slightly behind GPT). |

**Key advantage:** Excellent reasoning for complex multi-step extraction. Already used as fallback agent in our bot.
**Key disadvantage for our use case:** Slower than Gemini Flash, more expensive, requires separate API key/auth setup. Not on GCP, so adds external dependency.

### C. GPT-4o (OpenAI)

| Attribute | Details |
|-----------|---------|
| **Version** | GPT-4o, GPT-4o-mini |
| **Last updated** | Continuous updates through 2025-2026 |
| **How PDFs are handled** | Does NOT natively handle PDFs. Must convert each page to an image first, then send as base64 images. Extra preprocessing step required. |
| **Structured output** | JSON mode with schema definition. |
| **Speed** | 3-6 seconds per invoice. |
| **Runs locally?** | No. API call. |
| **Cost** | ~$0.016 per invoice (GPT-4o). ~$0.005 with GPT-4o-mini. |
| **Norwegian support** | Strong. Noted as best for "multilingual invoices" in benchmarks. |
| **Scanned invoice accuracy** | 91% (Koncile benchmark). |
| **Text PDF accuracy** | 98% (Koncile benchmark, highest). |

**Key disadvantage for our use case:** No native PDF support means extra code to convert PDF pages to images. Additional dependency (not on GCP). No benefit over Gemini for our architecture.

---

## 2. Specialized PDF Extraction Tools (Open Source, 2025-2026)

### A. Docling (IBM)

| Attribute | Details |
|-----------|---------|
| **Version** | v2.81.0 (March 20, 2026) |
| **Stars** | 56.2k GitHub stars |
| **License** | MIT (fully permissive) |
| **What it does** | Converts PDF/DOCX/PPTX/XLSX/HTML to structured JSON, Markdown, HTML, DocTags. Advanced layout analysis with reading order and table structure detection. |
| **Key model** | Granite-Docling-258M (258M params, Apache 2.0). Uses DocTags format for structured markup. TableFormer model trained on 1M+ tables. Heron layout model (Dec 2025) for faster PDF parsing. |
| **Speed** | ~0.68-6.28 seconds per page depending on document complexity and features enabled. Linear scaling with page count. |
| **Runs locally?** | Yes. CPU or GPU. |
| **Container size** | 9.74GB default Docker image. Reducible with CPU-only PyTorch wheels, but still large. |
| **Memory** | Needs several GB RAM. Too heavy for 1GB Cloud Run. |
| **Norwegian support** | OCR support via Tesseract/EasyOCR backends. Norwegian available but not specifically optimized. |
| **Install** | `pip install docling` (Python 3.10+) |

**Verdict for our use case:** Too heavy for Cloud Run with 1GB memory. The Docker image alone is ~5-10GB. Processing speed is acceptable but the resource requirements are a dealbreaker. Would be excellent for a dedicated document processing service, but overkill for our in-request extraction.

### B. MinerU (OpenDataLab)

| Attribute | Details |
|-----------|---------|
| **Version** | v2.7.6 (February 6, 2026) |
| **Stars** | 56.7k GitHub stars |
| **License** | MIT |
| **What it does** | Converts PDFs to Markdown/JSON preserving structure. Handles text, images, tables, formulas. Hybrid backend combining pipeline and VLM approaches. |
| **Key model** | MinerU 2.5 with coarse-to-fine two-stage parsing. VLM/hybrid backends score 90+ on OmniDocBench. |
| **Speed** | Varies by backend. Pipeline backend is faster but less accurate. VLM backend is slower but 90+ accuracy. |
| **Runs locally?** | Yes. Requires GPU (6-10GB VRAM). |
| **Memory** | Min 16GB RAM, 32GB recommended. Requires 20GB storage. |
| **Norwegian support** | OCR supports 109 languages. Norwegian likely included but not specifically highlighted. |
| **Install** | `pip install mineru` (Python 3.10-3.13) |

**Verdict for our use case:** Way too resource-heavy. Needs 16GB RAM minimum and GPU. Impossible on Cloud Run with 1GB memory. Best suited for batch processing pipelines, not real-time request handling.

### C. Marker (Datalab/EndlessAI)

| Attribute | Details |
|-----------|---------|
| **Version** | v1.10.1 (January 31, 2026) |
| **Stars** | 32.9k GitHub stars |
| **License** | Modified AI Pubs Open Rail-M (free for research/personal/startups under $2M). GPL code. Commercial license available. |
| **What it does** | Converts PDF/DOCX/PPTX/images to Markdown, JSON, HTML, chunks. Table/form/equation formatting. Image extraction. Structured extraction with JSON schemas (beta). |
| **Key feature** | `--use_llm` mode uses Gemini 2.0 Flash for higher accuracy (table merging across pages, form value extraction). |
| **Speed** | Up to 25 pages/second on H100 in batch mode. Benchmarks favorably vs cloud services. |
| **Runs locally?** | Yes. CPU or GPU. |
| **Memory** | Moderate. Lighter than Docling/MinerU but still needs several GB for models. |
| **Norwegian support** | Claims "all languages" for non-OCR. OCR uses Surya library which supports many languages. |
| **Install** | `pip install marker-pdf` |

**Verdict for our use case:** The `--use_llm` mode is interesting, it essentially does what we already do (send to Gemini) but with extra pre-processing. The standalone mode needs model downloads that would bloat our container. The JSON schema extraction feature (beta) could be useful but adds complexity over our current direct-to-Gemini approach.

### D. LlamaParse (LlamaIndex)

| Attribute | Details |
|-----------|---------|
| **Version** | v2 (launched 2025). Legacy package deprecated May 2026. |
| **License** | Proprietary cloud service. Free tier available. |
| **What it does** | AI-powered document processing. Four tiers: Fast, Cost Effective, Agentic, Agentic Plus. |
| **Speed** | ~6 seconds consistently regardless of page count. Very predictable. |
| **Runs locally?** | No. Cloud API only. |
| **Accuracy** | Strong numerical accuracy in simple tables. Struggles with complex formatting and ToC reconstruction. |
| **Norwegian support** | Not specifically documented. |
| **Cost** | Tier-based pricing. Free credits for testing. |

**Verdict for our use case:** External API dependency adds latency and cost. The 6-second consistent speed is nice, but we'd be adding a call to LlamaParse PLUS a call to Gemini for reasoning. Double the latency. Not worth it when Gemini handles PDFs natively.

### E. Unstructured.io

| Attribute | Details |
|-----------|---------|
| **Version** | Actively maintained, regular releases through 2026 |
| **License** | Apache 2.0 (open source library). Enterprise platform also available. |
| **What it does** | Ingests and pre-processes 64+ file types. PDF partition with layout analysis. |
| **Speed** | Slow. 51 seconds for 1 page, 141 seconds for 50 pages in benchmarks. |
| **Runs locally?** | Yes. But needs heavy dependencies. |
| **Accuracy** | 75% on complex tables (vs Docling's 97.9%). Decent for simple text. |
| **Norwegian support** | Not specifically documented. |

**Verdict for our use case:** Too slow (51 seconds for a single page). Lower accuracy than alternatives. Not suitable for real-time processing.

### F. Mistral OCR 3

| Attribute | Details |
|-----------|---------|
| **Version** | mistral-ocr-latest (OCR 3, released Dec 2025) |
| **License** | Proprietary API service |
| **What it does** | Extracts text and embedded images from documents. Structured JSON output with custom templates. Form parsing, table reconstruction, handwriting detection. |
| **Speed** | Up to 2,000 pages per minute on a single node. Very fast. |
| **Runs locally?** | No. API call to Mistral. |
| **Cost** | $2 per 1,000 pages ($1 with batch discount). Very cheap. |
| **Norwegian support** | Claims support for "thousands of scripts, fonts, and languages across all continents." Norwegian likely included. |

**Verdict for our use case:** Interesting as a preprocessing step. Very cheap and fast. However, adds an external API dependency (Mistral). The structured JSON extraction is compelling, but Gemini already does this natively with `response_schema`. Would only make sense if Gemini's PDF parsing proves insufficient for specific document types.

### G. olmOCR (Allen Institute for AI)

| Attribute | Details |
|-----------|---------|
| **Version** | olmOCR-2-7B-1025 |
| **License** | Open source (Apache 2.0) |
| **What it does** | Converts PDFs to structured plain text/Markdown. Built on Qwen2.5-VL-7B-Instruct, fine-tuned on 260K PDF pages. |
| **Speed** | Fast for batch processing. $190 per million pages (32x cheaper than GPT-4o). |
| **Runs locally?** | Yes, but needs GPU (7B parameter model). |
| **Accuracy** | 82.4 on olmOCR-bench. Strong on math, tables, complex layouts. |
| **Norwegian support** | Based on Qwen2.5-VL which supports many languages. Not Norwegian-specific. |

**Verdict for our use case:** Needs GPU, too heavy for Cloud Run. Would be great for a dedicated OCR service but doesn't fit our deployment constraints.

---

## 3. Lightweight Local Tools (for pre-processing before LLM)

### A. PyMuPDF / PyMuPDF4LLM

| Attribute | Details |
|-----------|---------|
| **Version** | PyMuPDF 1.25.x, PyMuPDF4LLM latest |
| **License** | AGPL-3.0 (PyMuPDF). Note: commercial license available. |
| **What it does** | Fast text extraction, table detection, image extraction from PDFs. PyMuPDF4LLM adds Markdown output optimized for LLM consumption. |
| **Speed** | ~0.12 seconds per document. Extremely fast. |
| **Runs locally?** | Yes. Pure Python + C extension. No GPU needed. |
| **Memory** | Minimal. 10-50MB. Perfect for Cloud Run. |
| **Container size** | ~50MB additional. Very lightweight. |
| **Norwegian support** | Text extraction works for any language. No OCR built-in (for scanned docs, would need Tesseract). |
| **Install** | `pip install pymupdf4llm` |

**Verdict for our use case:** Excellent pre-processing option. Could extract text from PDFs before sending to Gemini, reducing token count (text tokens are cheaper/free vs image tokens). Only useful for text-based PDFs, not scanned documents. The AGPL license may be a concern for commercial use.

### B. pdfplumber

| Attribute | Details |
|-----------|---------|
| **Version** | Latest stable (actively maintained) |
| **License** | MIT |
| **What it does** | Extracts text, tables, and images with precise coordinate control. Good at preserving table structure. |
| **Speed** | ~0.10 seconds per page. Very fast. |
| **Runs locally?** | Yes. Pure Python. No GPU. |
| **Memory** | Minimal. Perfect for Cloud Run. |
| **Norwegian support** | Text extraction works for any language (reads embedded fonts). |
| **Install** | `pip install pdfplumber` |

**Verdict for our use case:** MIT license (better than PyMuPDF's AGPL). Excellent for table extraction from invoices. Could pre-extract table data and pass structured text to Gemini instead of raw PDF bytes. Would reduce token usage and improve extraction accuracy for tabular invoice data.

### C. pdfminer.six

| Attribute | Details |
|-----------|---------|
| **Version** | Latest stable |
| **License** | MIT |
| **What it does** | Low-level PDF text extraction. Character-level positioning. |
| **Speed** | Slower than PyMuPDF but still sub-second for typical invoices. |
| **Runs locally?** | Yes. Pure Python. |
| **Memory** | Minimal. |
| **Norwegian support** | Text extraction works for any language. |

**Verdict for our use case:** Lower-level than pdfplumber. Less useful for our needs since pdfplumber builds on it with better table extraction.

---

## 4. GCP Document AI Services

### A. Google Cloud Document AI - Invoice Parser

| Attribute | Details |
|-----------|---------|
| **Version** | pretrained-invoice-v2.0-2023-12-06 (migrate before June 30, 2026) |
| **What it does** | Pre-trained model that extracts 46+ entities from invoices: invoice number, supplier name, amounts, tax, dates, line items. |
| **Speed** | 1-5 seconds per document. |
| **Runs on GCP?** | Yes. Same project we already use. |
| **Cost** | $0.065 per page (first 500K pages/month). Cheaper at scale. |
| **Norwegian support** | Not specifically listed. Primary support for English, with some European languages. |
| **New models (2025-2026)** | Layout parser v1.6 and Custom extractor v1.6 powered by Gemini 3 Pro LLM. Available in US and EU. |

**Verdict for our use case:** Compelling because it runs on our existing GCP project. The invoice parser extracts exactly the fields we need (invoice number, amounts, dates, vendor). However, at $0.065/page it's more expensive than direct Gemini processing. The new Gemini 3 Pro-powered models could be very accurate but are still in Preview. Worth testing if Gemini Flash's direct PDF processing is insufficient for specific invoice formats.

### B. Google Cloud Document AI - Custom Extractor

| Attribute | Details |
|-----------|---------|
| **Version** | pretrained-foundation-model-v1.6-pro-2025-12-01 |
| **What it does** | Custom document extraction powered by Gemini 3 Pro. Define your own schema and extract fields. |
| **Status** | Preview (not GA). ML processing in US and EU. |

**Verdict for our use case:** Overkill for competition. Would require setup, training, and the preview status adds risk. But worth noting for production use cases after the competition.

---

## 5. Norwegian Language Support Summary

| Tool/Method | Norwegian Support | Notes |
|-------------|-------------------|-------|
| **Gemini 2.5 Flash** | Strong | Handles ae/oe/aa natively. Tested with 7 languages in our bot. |
| **Claude** | Strong | Good multilingual. |
| **GPT-4o** | Strong | Noted as best for multilingual invoices. |
| **Mistral OCR 3** | Likely good | Claims thousands of languages. |
| **Docling** | Via Tesseract/EasyOCR | Norwegian available but not optimized. |
| **MinerU** | 109 languages via OCR | Norwegian likely included. |
| **Marker** | "All languages" | Surya OCR for scanned docs. |
| **PyMuPDF/pdfplumber** | Full (text PDFs) | Reads embedded text in any language. |
| **Tesseract** | Partial | Known bug: Ae character missing from Norwegian training data. |
| **GCP Document AI** | Limited | Not specifically listed for Norwegian. |

**Bottom line for Norwegian:** Multimodal LLMs (Gemini, Claude, GPT) handle Norwegian best because they understand the language semantically, not just visually. Traditional OCR tools have gaps (Tesseract's Ae bug is a real problem for Norwegian accounting documents). Our current Gemini approach is already the best option for Norwegian.

---

## 6. Recommendations for Our Use Case

### Current approach assessment

The current approach (send raw PDF bytes to Gemini 2.5 Flash via `types.Part.from_bytes()`) is already very good:
- Fast (2-5 seconds)
- Accurate for both text and scanned PDFs
- Handles Norwegian natively
- No additional dependencies
- Fits in 1GB Cloud Run memory
- Structured output via `response_schema` is available

### Potential improvements (ranked by effort/impact)

#### 1. Add Gemini `response_schema` for structured extraction (LOW effort, HIGH impact)

Instead of asking Gemini to return free-form JSON, use the `response_schema` parameter with a Pydantic model. This guarantees valid JSON output matching the exact schema, eliminating parsing failures.

```python
from pydantic import BaseModel, Field

class InvoiceData(BaseModel):
    invoice_number: str = Field(description="Invoice number")
    date: str = Field(description="Invoice date in YYYY-MM-DD format")
    vendor_name: str = Field(description="Vendor/supplier name")
    total_amount: float = Field(description="Total amount including VAT")
    vat_amount: float = Field(description="VAT amount")
    line_items: list[LineItem] = Field(description="Line items")

# Use in generation config:
generation_config = {
    "response_mime_type": "application/json",
    "response_schema": InvoiceData,
}
```

**Why:** Eliminates JSON parsing errors. The model is forced to return valid structured data.

#### 2. Pre-extract text with pdfplumber for text-based PDFs (MEDIUM effort, MEDIUM impact)

For text-based PDFs, extract text first with pdfplumber, then send text (not images) to Gemini. This reduces token usage (text tokens are free in Gemini 3, image tokens are not) and can improve accuracy for tabular data.

```python
import pdfplumber

def extract_text_from_pdf(pdf_bytes):
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        tables = []
        text = ""
        for page in pdf.pages:
            text += page.extract_text() or ""
            page_tables = page.extract_tables()
            if page_tables:
                tables.extend(page_tables)
    return text, tables
```

**Why:** Cheaper (free text tokens vs image tokens). Better table extraction. Fallback to multimodal for scanned PDFs where text extraction returns empty.

**Tradeoff:** Adds pdfplumber as dependency (~10MB). Extra code path. Must detect scanned vs text PDFs.

#### 3. Hybrid approach: text extraction + multimodal fallback (MEDIUM effort, HIGH impact)

Combine approaches 1 and 2:
1. Try pdfplumber text extraction first
2. If text is empty or very short (scanned PDF), fall back to multimodal
3. Always use `response_schema` for structured output

This gets the best of both worlds: fast/cheap for text PDFs, accurate for scanned PDFs.

#### 4. Consider Mistral OCR 3 as preprocessing (HIGH effort, MEDIUM impact)

If Gemini struggles with specific invoice formats, Mistral OCR 3 at $1-2 per 1,000 pages could be used as a preprocessing step. Extract structured text/tables first, then pass to Gemini for field mapping.

**Only worth investigating if:** Current Gemini accuracy is insufficient for specific document types.

#### 5. GCP Document AI Invoice Parser (MEDIUM effort, MEDIUM impact)

Already on GCP. Pre-trained for invoice extraction. Could supplement Gemini for invoice-specific tasks.

**Only worth investigating if:** Invoice extraction accuracy needs improvement beyond what Gemini provides.

---

## 7. Tools NOT Recommended for Our Use Case

| Tool | Reason |
|------|--------|
| Docling | Too heavy (9GB+ Docker, needs multi-GB RAM) |
| MinerU | Needs 16GB+ RAM and GPU |
| olmOCR | Needs GPU (7B model) |
| Unstructured.io | Too slow (51s per page) |
| LlamaParse | External API, adds latency on top of Gemini |
| Marker (standalone) | Model downloads bloat container. `--use_llm` mode just calls Gemini anyway |

---

## 8. Summary: Best Path Forward

**For the competition (immediate):** Stay with current Gemini 2.5 Flash multimodal approach. It works, it's fast, it handles Norwegian, and it fits our constraints. The only quick win is adding `response_schema` for structured output.

**For production (post-competition):**
- Add pdfplumber for text pre-extraction (reduce costs, improve table accuracy)
- Use hybrid text+multimodal approach
- Consider GCP Document AI Invoice Parser for dedicated invoice processing
- Monitor Mistral OCR 3 pricing and accuracy improvements
- Evaluate Docling if you move to a beefier Cloud Run instance (4GB+ memory)

---

## Sources

- [Koncile: Claude vs GPT vs Gemini for Invoice Extraction](https://www.koncile.ai/en/ressources/claude-gpt-or-gemini-which-is-the-best-llm-for-invoice-extraction)
- [Procycons: PDF Extraction Benchmark 2025 (Docling vs Unstructured vs LlamaParse)](https://procycons.com/en/blogs/pdf-data-extraction-benchmark/)
- [Phil Schmid: From PDFs to Insights with Gemini 2.0 Structured Outputs](https://www.philschmid.de/gemini-pdf-to-data)
- [Google: Gemini Document Understanding](https://ai.google.dev/gemini-api/docs/document-processing)
- [Anthropic: Claude PDF Support](https://platform.claude.com/docs/en/build-with-claude/pdf-support)
- [Google: Gemini Structured Outputs](https://ai.google.dev/gemini-api/docs/structured-output)
- [IBM: Granite-Docling announcement](https://www.ibm.com/new/announcements/granite-docling-end-to-end-document-conversion)
- [Docling GitHub](https://github.com/docling-project/docling)
- [MinerU GitHub](https://github.com/opendatalab/MinerU)
- [Marker GitHub](https://github.com/datalab-to/marker)
- [Mistral OCR 3 announcement](https://mistral.ai/news/mistral-ocr-3)
- [olmOCR GitHub](https://github.com/allenai/olmocr)
- [Google Cloud Document AI](https://docs.cloud.google.com/document-ai/docs/release-notes)
- [PyMuPDF4LLM docs](https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/)
- [Zerox GitHub](https://github.com/getomni-ai/zerox)
- [Unstract: Python PDF to Text Libraries Evaluation 2026](https://unstract.com/blog/evaluating-python-pdf-to-text-libraries/)
- [Datastudios: Gemini 2.5 Flash File Upload and Reading](https://www.datastudios.org/post/google-gemini-2-5-flash-file-upload-and-reading-document-processing-extraction-quality-multimodal)
