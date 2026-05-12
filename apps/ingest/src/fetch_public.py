from __future__ import annotations

import json
import ssl
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.error import URLError
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup, Tag
from rich.console import Console

try:
    from pdf2text.src.extract import extract_pdf, to_markdown
except ModuleNotFoundError as exc:
    extract_pdf = None
    to_markdown = None
    _PDF_IMPORT_ERROR = exc
else:
    _PDF_IMPORT_ERROR = None


USER_AGENT = "lawagent-corpus-fetcher/0.1"
REQUEST_TIMEOUT_SECONDS = 20
_STATUTE_KIND = "statute_html"
_HTML_KIND = "html"
_PDF_KIND = "pdf"
SourceKind = Literal["statute_html", "html", "pdf"]


@dataclass(frozen=True)
class SourceSpec:
    slug: str
    kind: SourceKind
    url: str
    output_path: str
    metadata: dict[str, str]
    section: str | None = None


STATUTE_SPECS: tuple[SourceSpec, ...] = (
    SourceSpec(
        slug="cgs-46b-40",
        kind=_STATUTE_KIND,
        url="https://www.cga.ct.gov/2023/pub/chap_815j.htm",
        output_path="statutes/cgs-46b-40.txt",
        section="46b-40",
        metadata={
            "source_type": "statute",
            "authority_level": "primary",
            "citation": "Conn. Gen. Stat. § 46b-40",
            "title": "CGS § 46b-40",
            "section": "46b-40",
            "date": "2023",
            "jurisdiction": "Connecticut",
            "issuing_body": "Connecticut General Assembly",
            "topic": "grounds-for-dissolution",
            "stage": "pre-filing",
        },
    ),
    SourceSpec(
        slug="cgs-46b-44",
        kind=_STATUTE_KIND,
        url="https://www.cga.ct.gov/2023/pub/chap_815j.htm",
        output_path="statutes/cgs-46b-44.txt",
        section="46b-44",
        metadata={
            "source_type": "statute",
            "authority_level": "primary",
            "citation": "Conn. Gen. Stat. § 46b-44",
            "title": "CGS § 46b-44",
            "section": "46b-44",
            "date": "2023",
            "jurisdiction": "Connecticut",
            "issuing_body": "Connecticut General Assembly",
            "topic": "residency-and-jurisdiction",
            "stage": "pre-filing",
        },
    ),
    SourceSpec(
        slug="cgs-46b-44a",
        kind=_STATUTE_KIND,
        url="https://www.cga.ct.gov/2024/sup/chap_815j.htm",
        output_path="statutes/cgs-46b-44a.txt",
        section="46b-44a",
        metadata={
            "source_type": "statute",
            "authority_level": "primary",
            "citation": "Conn. Gen. Stat. § 46b-44a",
            "title": "CGS § 46b-44a",
            "section": "46b-44a",
            "date": "2024 supplement",
            "jurisdiction": "Connecticut",
            "issuing_body": "Connecticut General Assembly",
            "topic": "nonadversarial-dissolution",
            "stage": "pre-filing",
        },
    ),
    SourceSpec(
        slug="cgs-46b-45",
        kind=_STATUTE_KIND,
        url="https://www.cga.ct.gov/2023/pub/chap_815j.htm",
        output_path="statutes/cgs-46b-45.txt",
        section="46b-45",
        metadata={
            "source_type": "statute",
            "authority_level": "primary",
            "citation": "Conn. Gen. Stat. § 46b-45",
            "title": "CGS § 46b-45",
            "section": "46b-45",
            "date": "2023",
            "jurisdiction": "Connecticut",
            "issuing_body": "Connecticut General Assembly",
            "topic": "service-and-filing",
            "stage": "filing",
        },
    ),
    SourceSpec(
        slug="cgs-46b-56",
        kind=_STATUTE_KIND,
        url="https://www.cga.ct.gov/2023/pub/chap_815j.htm",
        output_path="statutes/cgs-46b-56.txt",
        section="46b-56",
        metadata={
            "source_type": "statute",
            "authority_level": "primary",
            "citation": "Conn. Gen. Stat. § 46b-56",
            "title": "CGS § 46b-56",
            "section": "46b-56",
            "date": "2023",
            "jurisdiction": "Connecticut",
            "issuing_body": "Connecticut General Assembly",
            "topic": "custody-and-best-interests",
            "stage": "temporary-orders",
        },
    ),
    SourceSpec(
        slug="cgs-46b-67",
        kind=_STATUTE_KIND,
        url="https://www.cga.ct.gov/2024/sup/chap_815j.htm",
        output_path="statutes/cgs-46b-67.txt",
        section="46b-67",
        metadata={
            "source_type": "statute",
            "authority_level": "primary",
            "citation": "Conn. Gen. Stat. § 46b-67",
            "title": "CGS § 46b-67",
            "section": "46b-67",
            "date": "2024 supplement",
            "jurisdiction": "Connecticut",
            "issuing_body": "Connecticut General Assembly",
            "topic": "case-timing",
            "stage": "after-filing",
        },
    ),
    SourceSpec(
        slug="cgs-46b-81",
        kind=_STATUTE_KIND,
        url="https://www.cga.ct.gov/2023/pub/chap_815j.htm",
        output_path="statutes/cgs-46b-81.txt",
        section="46b-81",
        metadata={
            "source_type": "statute",
            "authority_level": "primary",
            "citation": "Conn. Gen. Stat. § 46b-81",
            "title": "CGS § 46b-81",
            "section": "46b-81",
            "date": "2023",
            "jurisdiction": "Connecticut",
            "issuing_body": "Connecticut General Assembly",
            "topic": "property-division",
            "stage": "judgment",
        },
    ),
    SourceSpec(
        slug="cgs-46b-82",
        kind=_STATUTE_KIND,
        url="https://www.cga.ct.gov/2023/pub/chap_815j.htm",
        output_path="statutes/cgs-46b-82.txt",
        section="46b-82",
        metadata={
            "source_type": "statute",
            "authority_level": "primary",
            "citation": "Conn. Gen. Stat. § 46b-82",
            "title": "CGS § 46b-82",
            "section": "46b-82",
            "date": "2023",
            "jurisdiction": "Connecticut",
            "issuing_body": "Connecticut General Assembly",
            "topic": "alimony",
            "stage": "judgment",
        },
    ),
    SourceSpec(
        slug="cgs-46b-82a",
        kind=_STATUTE_KIND,
        url="https://www.cga.ct.gov/2024/sup/chap_815j.htm",
        output_path="statutes/cgs-46b-82a.txt",
        section="46b-82a",
        metadata={
            "source_type": "statute",
            "authority_level": "primary",
            "citation": "Conn. Gen. Stat. § 46b-82a",
            "title": "CGS § 46b-82a",
            "section": "46b-82a",
            "date": "2024 supplement",
            "jurisdiction": "Connecticut",
            "issuing_body": "Connecticut General Assembly",
            "topic": "alimony-family-violence",
            "stage": "judgment",
        },
    ),
    SourceSpec(
        slug="cgs-46b-83",
        kind=_STATUTE_KIND,
        url="https://www.cga.ct.gov/2024/sup/chap_815j.htm",
        output_path="statutes/cgs-46b-83.txt",
        section="46b-83",
        metadata={
            "source_type": "statute",
            "authority_level": "primary",
            "citation": "Conn. Gen. Stat. § 46b-83",
            "title": "CGS § 46b-83",
            "section": "46b-83",
            "date": "2024 supplement",
            "jurisdiction": "Connecticut",
            "issuing_body": "Connecticut General Assembly",
            "topic": "temporary-alimony-and-support",
            "stage": "temporary-orders",
        },
    ),
    SourceSpec(
        slug="cgs-46b-84",
        kind=_STATUTE_KIND,
        url="https://www.cga.ct.gov/2024/sup/chap_815j.htm",
        output_path="statutes/cgs-46b-84.txt",
        section="46b-84",
        metadata={
            "source_type": "statute",
            "authority_level": "primary",
            "citation": "Conn. Gen. Stat. § 46b-84",
            "title": "CGS § 46b-84",
            "section": "46b-84",
            "date": "2024 supplement",
            "jurisdiction": "Connecticut",
            "issuing_body": "Connecticut General Assembly",
            "topic": "child-support",
            "stage": "temporary-orders",
        },
    ),
    SourceSpec(
        slug="cgs-46b-86",
        kind=_STATUTE_KIND,
        url="https://www.cga.ct.gov/2023/pub/chap_815j.htm",
        output_path="statutes/cgs-46b-86.txt",
        section="46b-86",
        metadata={
            "source_type": "statute",
            "authority_level": "primary",
            "citation": "Conn. Gen. Stat. § 46b-86",
            "title": "CGS § 46b-86",
            "section": "46b-86",
            "date": "2023",
            "jurisdiction": "Connecticut",
            "issuing_body": "Connecticut General Assembly",
            "topic": "postjudgment-modification",
            "stage": "postjudgment",
        },
    ),
)

GUIDE_SPECS: tuple[SourceSpec, ...] = (
    SourceSpec(
        slug="guide-divorce-custody-visitation",
        kind=_HTML_KIND,
        url="https://www.jud.ct.gov/forms/grouped/family/dcv.htm",
        output_path="guides/guide-divorce-custody-visitation.md",
        metadata={
            "source_type": "court_guide",
            "authority_level": "court_published",
            "citation": "Divorce, Custody and Visitation",
            "title": "Divorce, Custody and Visitation",
            "date": "2026",
            "jurisdiction": "Connecticut",
            "issuing_body": "Connecticut Judicial Branch",
            "topic": "divorce-process",
            "stage": "pre-filing",
        },
    ),
    SourceSpec(
        slug="guide-divorce-with-agreement",
        kind=_HTML_KIND,
        url="https://www.jud.ct.gov/forms/grouped/family/DivWithAgree_landing.htm",
        output_path="guides/guide-divorce-with-agreement.md",
        metadata={
            "source_type": "court_guide",
            "authority_level": "court_published",
            "citation": "Divorce with an Agreement",
            "title": "Divorce with an Agreement",
            "date": "2026",
            "jurisdiction": "Connecticut",
            "issuing_body": "Connecticut Judicial Branch",
            "topic": "uncontested-divorce",
            "stage": "filing",
        },
    ),
    SourceSpec(
        slug="guide-pathways-process",
        kind=_HTML_KIND,
        url="https://www.jud.ct.gov/family/pathwaysprocess.htm",
        output_path="guides/guide-pathways-process.md",
        metadata={
            "source_type": "court_guide",
            "authority_level": "court_published",
            "citation": "Pathways Process in Your Divorce, Custody or Visitation Case",
            "title": "Pathways Process",
            "date": "2026",
            "jurisdiction": "Connecticut",
            "issuing_body": "Connecticut Judicial Branch",
            "topic": "court-process",
            "stage": "after-filing",
        },
    ),
    SourceSpec(
        slug="guide-finishing-without-hearing",
        kind=_HTML_KIND,
        url="https://www.jud.ct.gov/family/FArequest.htm",
        output_path="guides/guide-finishing-without-hearing.md",
        metadata={
            "source_type": "court_guide",
            "authority_level": "court_published",
            "citation": "Finishing Your Family Case By Agreement Without a Court Hearing",
            "title": "Finishing Your Family Case Without a Hearing",
            "date": "2026",
            "jurisdiction": "Connecticut",
            "issuing_body": "Connecticut Judicial Branch",
            "topic": "agreement-without-hearing",
            "stage": "judgment",
        },
    ),
    SourceSpec(
        slug="lawlib-dissolution-of-marriage",
        kind=_PDF_KIND,
        url="https://jud.ct.gov/lawlib/Notebooks/Pathfinders/divorce/divorce.pdf",
        output_path="guides/lawlib-dissolution-of-marriage.md",
        metadata={
            "source_type": "law_library_guide",
            "authority_level": "secondary",
            "citation": "Dissolution of Marriage in Connecticut: A Guide to Resources in the Law Library",
            "title": "Dissolution of Marriage in Connecticut",
            "date": "2026",
            "jurisdiction": "Connecticut",
            "issuing_body": "Connecticut Judicial Branch Law Libraries",
            "topic": "research-guide",
            "stage": "research",
        },
    ),
)

FORM_SPECS: tuple[SourceSpec, ...] = (
    SourceSpec(
        slug="form-jd-fm-158",
        kind=_PDF_KIND,
        url="https://www.jud.ct.gov/webforms/forms/FM158.pdf",
        output_path="forms/form-jd-fm-158.md",
        metadata={
            "source_type": "court_form",
            "authority_level": "court_published",
            "citation": "Notice of Automatic Court Orders (JD-FM-158)",
            "title": "Notice of Automatic Court Orders",
            "date": "2026",
            "jurisdiction": "Connecticut",
            "issuing_body": "Connecticut Judicial Branch",
            "topic": "automatic-orders",
            "stage": "filing",
            "document_id": "JD-FM-158",
        },
    ),
    SourceSpec(
        slug="form-jd-fm-159",
        kind=_PDF_KIND,
        url="https://www.jud.ct.gov/webforms/forms/FM159.pdf",
        output_path="forms/form-jd-fm-159.md",
        metadata={
            "source_type": "court_form",
            "authority_level": "court_published",
            "citation": "Divorce Complaint (Dissolution of Marriage) (JD-FM-159)",
            "title": "Divorce Complaint (Dissolution of Marriage)",
            "date": "2026",
            "jurisdiction": "Connecticut",
            "issuing_body": "Connecticut Judicial Branch",
            "topic": "pleadings",
            "stage": "filing",
            "document_id": "JD-FM-159",
        },
    ),
    SourceSpec(
        slug="form-jd-fm-172",
        kind=_PDF_KIND,
        url="https://www.jud.ct.gov/webforms/forms/FM172.pdf",
        output_path="forms/form-jd-fm-172.md",
        metadata={
            "source_type": "court_form",
            "authority_level": "court_published",
            "citation": "Dissolution Agreement (JD-FM-172)",
            "title": "Dissolution Agreement",
            "date": "2026",
            "jurisdiction": "Connecticut",
            "issuing_body": "Connecticut Judicial Branch",
            "topic": "settlement-agreement",
            "stage": "judgment",
            "document_id": "JD-FM-172",
        },
    ),
    SourceSpec(
        slug="form-jd-fm-249",
        kind=_PDF_KIND,
        url="https://www.jud.ct.gov/webforms/forms/FM249.pdf",
        output_path="forms/form-jd-fm-249.md",
        metadata={
            "source_type": "court_form",
            "authority_level": "court_published",
            "citation": "Certification of Waiver of Service of Process (JD-FM-249)",
            "title": "Certification of Waiver of Service of Process",
            "date": "2026",
            "jurisdiction": "Connecticut",
            "issuing_body": "Connecticut Judicial Branch",
            "topic": "service-and-filing",
            "stage": "filing",
            "document_id": "JD-FM-249",
        },
    ),
    SourceSpec(
        slug="form-jd-fm-6",
        kind=_PDF_KIND,
        url="https://www.jud.ct.gov/webforms/forms/FM006-long.pdf",
        output_path="forms/form-jd-fm-6.md",
        metadata={
            "source_type": "court_form",
            "authority_level": "court_published",
            "citation": "Financial Affidavit (JD-FM-6)",
            "title": "Financial Affidavit",
            "date": "2026",
            "jurisdiction": "Connecticut",
            "issuing_body": "Connecticut Judicial Branch",
            "topic": "financial-disclosure",
            "stage": "temporary-orders",
            "document_id": "JD-FM-6",
        },
    ),
    SourceSpec(
        slug="form-ccsg-1",
        kind=_PDF_KIND,
        url="https://www.jud.ct.gov/webforms/forms/CCSG-1.pdf",
        output_path="forms/form-ccsg-1.md",
        metadata={
            "source_type": "court_form",
            "authority_level": "court_published",
            "citation": "Worksheet for the Connecticut Child Support and Arrearage Guidelines (CCSG-1)",
            "title": "Child Support and Arrearage Guidelines Worksheet",
            "date": "2026",
            "jurisdiction": "Connecticut",
            "issuing_body": "Connecticut Judicial Branch",
            "topic": "child-support",
            "stage": "temporary-orders",
            "document_id": "CCSG-1",
        },
    ),
)

STARTER_SOURCES: tuple[SourceSpec, ...] = STATUTE_SPECS + GUIDE_SPECS + FORM_SPECS


def fetch_public_starter(
    out_dir: Path,
    *,
    force: bool,
    include_statutes: bool,
    include_guides: bool,
    include_forms: bool,
    include_pdfs: bool,
    console: Console,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, str]] = []
    fetched_count = 0
    skipped_count = 0
    failed_count = 0

    sources: list[SourceSpec] = []
    if include_statutes:
        sources.extend(STATUTE_SPECS)
    if include_guides:
        sources.extend(GUIDE_SPECS)
    if include_forms:
        sources.extend(FORM_SPECS)

    for spec in sources:
        if spec.kind == _PDF_KIND and not include_pdfs:
            continue
        if spec.kind == _PDF_KIND and _PDF_IMPORT_ERROR is not None:
            failed_count += 1
            console.print(
                f"failed [red]{spec.slug}[/red]: PDF support is unavailable; "
                f"run fetch-public --no-pdf or install pdf2text dependencies."
            )
            records.append(
                {
                    "slug": spec.slug,
                    "url": spec.url,
                    "output_path": spec.output_path,
                    "status": "failed",
                    "error": "PDF support unavailable in current environment.",
                }
            )
            continue

        output_path = out_dir / spec.output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_path.exists() and not force:
            skipped_count += 1
            console.print(f"skipping [yellow]{spec.slug}[/yellow] (already exists)")
            records.append(
                {
                    "slug": spec.slug,
                    "url": spec.url,
                    "output_path": str(output_path.relative_to(out_dir)),
                    "status": "skipped",
                }
            )
            continue

        console.print(f"fetching [cyan]{spec.slug}[/cyan]")
        try:
            content = _fetch_one(spec)
            output_path.write_text(content, encoding="utf-8")
            fetched_count += 1
            records.append(
                {
                    "slug": spec.slug,
                    "url": spec.url,
                    "output_path": str(output_path.relative_to(out_dir)),
                    "status": "fetched",
                }
            )
        except Exception as exc:
            failed_count += 1
            console.print(f"failed [red]{spec.slug}[/red]: {exc}")
            records.append(
                {
                    "slug": spec.slug,
                    "url": spec.url,
                    "output_path": str(output_path.relative_to(out_dir)),
                    "status": "failed",
                    "error": str(exc),
                }
            )

    manifest = {
        "profile": "starter",
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "include_statutes": include_statutes,
        "include_guides": include_guides,
        "include_forms": include_forms,
        "include_pdfs": include_pdfs,
        "counts": {
            "fetched": fetched_count,
            "skipped": skipped_count,
            "failed": failed_count,
            "total": len(records),
        },
        "documents": records,
    }
    manifest_path = out_dir / "public_sources_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def _fetch_one(spec: SourceSpec) -> str:
    body = _download(spec.url)
    metadata = {**spec.metadata, "source_url": spec.url}

    if spec.kind == _STATUTE_KIND:
        html = body.decode("utf-8", errors="replace")
        text = extract_cga_section_text(html, spec.section or "")
        return render_with_frontmatter(metadata, text, suffix=".txt")

    if spec.kind == _HTML_KIND:
        html = body.decode("utf-8", errors="replace")
        text = html_to_markdownish(html)
        return render_with_frontmatter(metadata, text, suffix=".md")

    if spec.kind == _PDF_KIND:
        text = pdf_bytes_to_markdown(body)
        return render_with_frontmatter(metadata, text, suffix=".md")

    raise ValueError(f"Unsupported source kind: {spec.kind}")


def _download(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return response.read()
    except URLError as exc:
        if not isinstance(getattr(exc, "reason", None), ssl.SSLCertVerificationError):
            raise

    insecure_context = ssl._create_unverified_context()
    with urlopen(
        request,
        timeout=REQUEST_TIMEOUT_SECONDS,
        context=insecure_context,
    ) as response:
        return response.read()


def render_with_frontmatter(metadata: dict[str, str], text: str, *, suffix: str) -> str:
    lines = ["---"]
    for key, value in metadata.items():
        if value:
            lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")

    body = text.strip()
    if suffix == ".txt":
        lines.append(body)
        lines.append("")
        return "\n".join(lines)

    lines.append(body)
    lines.append("")
    return "\n".join(lines)


def extract_cga_section_text(html: str, section: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    anchor = soup.find(id=f"sec_{section.lower()}") or soup.find(id=f"sec_{section}")
    if not isinstance(anchor, Tag):
        raise ValueError(f"Could not find statute section {section!r} in source HTML.")

    start_node = anchor.find_parent("p")
    if not isinstance(start_node, Tag):
        raise ValueError(f"Could not find paragraph container for section {section!r}.")

    blocks: list[str] = []
    current: Tag | None = start_node
    while current is not None:
        if current is not start_node and _is_new_statute_section(current):
            break
        if current.name == "p":
            text = normalize_text(current.get_text(" ", strip=True))
            if text:
                blocks.append(text)
        current = current.find_next_sibling()

    return "\n\n".join(blocks).strip()


def _is_new_statute_section(node: Tag) -> bool:
    heading = node.find("span", id=True)
    if not isinstance(heading, Tag):
        return False
    heading_id = heading.get("id", "")
    return heading_id.startswith("sec_")


def html_to_markdownish(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    root = soup.body or soup
    lines: list[str] = []
    seen: set[str] = set()

    for node in root.find_all(["h1", "h2", "h3", "h4", "p", "li"], recursive=True):
        text = normalize_text(node.get_text(" ", strip=True))
        if not text or text in {"Top", "21.1.1"}:
            continue

        line = _format_html_block(node.name, text)
        if not line:
            continue

        dedupe_key = f"{node.name}:{line}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        lines.append(line)
        lines.append("")

    return "\n".join(lines).strip()


def _format_html_block(tag_name: str, text: str) -> str:
    if tag_name == "h1":
        return f"# {text}"
    if tag_name == "h2":
        return f"## {text}"
    if tag_name == "h3":
        return f"### {text}"
    if tag_name == "h4":
        return f"#### {text}"
    if tag_name == "li":
        return f"- {text}"
    return text


def normalize_text(text: str) -> str:
    return " ".join(text.split())


def pdf_bytes_to_markdown(body: bytes) -> str:
    if extract_pdf is None or to_markdown is None:
        raise RuntimeError(
            "PDF corpus fetching requires PyMuPDF/Tesseract dependencies. "
            "Either install the pdf2text dependencies or run fetch-public --no-pdf."
        ) from _PDF_IMPORT_ERROR

    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        tmp.write(body)
        tmp.flush()
        result = extract_pdf(Path(tmp.name))
    return to_markdown(result).strip()
