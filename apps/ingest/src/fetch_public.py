from __future__ import annotations

import json
import re
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


_STATUTE_URL_2023 = "https://www.cga.ct.gov/2023/pub/chap_815j.htm"
_STATUTE_URL_2024_SUP = "https://www.cga.ct.gov/2024/sup/chap_815j.htm"

# Sections updated in the 2024 supplement — fetch from the supplement URL
# rather than the 2023 base so we get the current text.
_STATUTE_2024_SUP_OVERRIDES: frozenset[str] = frozenset({
    "46b-44a", "46b-53", "46b-56e", "46b-67",
    "46b-82a", "46b-83", "46b-84",
})

# Hand-curated topic + stage for the high-impact sections. Everything not
# in this map gets a generic "dissolution" / "trial" default in
# `_build_statute_specs` below.
_STATUTE_KNOWN_TOPICS: dict[str, tuple[str, str]] = {
    "46b-40": ("grounds-for-dissolution", "pre-filing"),
    "46b-44": ("residency-and-jurisdiction", "pre-filing"),
    "46b-44a": ("nonadversarial-dissolution", "pre-filing"),
    "46b-45": ("service-and-filing", "filing"),
    "46b-56": ("custody-and-best-interests", "temporary-orders"),
    "46b-67": ("case-timing", "after-filing"),
    "46b-81": ("property-division", "judgment"),
    "46b-82": ("alimony", "judgment"),
    "46b-82a": ("alimony-family-violence", "judgment"),
    "46b-83": ("temporary-alimony-and-support", "temporary-orders"),
    "46b-84": ("child-support", "temporary-orders"),
    "46b-86": ("postjudgment-modification", "postjudgment"),
}

# Every section that physically lives in CGS Ch. 815j (dissolution of
# marriage), as discovered from the 2023 base chapter HTML anchors.
_CH_815J_SECTIONS: tuple[str, ...] = (
    "46b-40", "46b-41", "46b-42", "46b-43",
    "46b-44", "46b-44a", "46b-44b", "46b-44c", "46b-44d",
    "46b-45", "46b-45a",
    "46b-46", "46b-47", "46b-48", "46b-49",
    "46b-50", "46b-51", "46b-52", "46b-53", "46b-53a",
    "46b-54", "46b-55",
    "46b-56", "46b-56a", "46b-56b", "46b-56c", "46b-56d", "46b-56e", "46b-56f",
    "46b-57", "46b-58", "46b-59", "46b-59a", "46b-59b",
    "46b-60", "46b-61", "46b-62", "46b-63", "46b-64", "46b-65",
    "46b-66", "46b-66a",
    "46b-67", "46b-68", "46b-69", "46b-69a", "46b-69b", "46b-69c",
    "46b-70", "46b-71", "46b-72", "46b-73", "46b-74", "46b-75",
    "46b-80", "46b-81", "46b-82", "46b-82a", "46b-83", "46b-84",
    "46b-85", "46b-86", "46b-87", "46b-87a", "46b-88", "46b-89",
)


def _build_statute_specs() -> tuple[SourceSpec, ...]:
    specs: list[SourceSpec] = []
    for section in _CH_815J_SECTIONS:
        topic, stage = _STATUTE_KNOWN_TOPICS.get(section, ("dissolution", "trial"))
        is_2024_sup = section in _STATUTE_2024_SUP_OVERRIDES
        url = _STATUTE_URL_2024_SUP if is_2024_sup else _STATUTE_URL_2023
        date = "2024 supplement" if is_2024_sup else "2023"
        specs.append(SourceSpec(
            slug=f"cgs-{section}",
            kind=_STATUTE_KIND,
            url=url,
            output_path=f"statutes/cgs-{section}.txt",
            section=section,
            metadata={
                "source_type": "statute",
                "authority_level": "primary",
                "citation": f"Conn. Gen. Stat. § {section}",
                "title": f"CGS § {section}",
                "section": section,
                "date": date,
                "jurisdiction": "Connecticut",
                "issuing_body": "Connecticut General Assembly",
                "topic": topic,
                "stage": stage,
            },
        ))
    return tuple(specs)


STATUTE_SPECS: tuple[SourceSpec, ...] = _build_statute_specs()

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
    SourceSpec(
        slug="form-jd-fm-150",
        kind=_PDF_KIND,
        url="https://www.jud.ct.gov/webforms/forms/FM150.pdf",
        output_path="forms/form-jd-fm-150.md",
        metadata={
            "source_type": "court_form",
            "authority_level": "court_published",
            "citation": "Appearance (JD-FM-150)",
            "title": "Appearance",
            "date": "2026",
            "jurisdiction": "Connecticut",
            "issuing_body": "Connecticut Judicial Branch",
            "topic": "appearance",
            "stage": "filing",
            "document_id": "JD-FM-150",
        },
    ),
    SourceSpec(
        slug="form-jd-fm-160",
        kind=_PDF_KIND,
        url="https://www.jud.ct.gov/webforms/forms/FM160.pdf",
        output_path="forms/form-jd-fm-160.md",
        metadata={
            "source_type": "court_form",
            "authority_level": "court_published",
            "citation": "Application for Waiver of Fees / Payment of Costs / Appointment of Counsel (JD-FM-160)",
            "title": "Application for Waiver of Fees",
            "date": "2026",
            "jurisdiction": "Connecticut",
            "issuing_body": "Connecticut Judicial Branch",
            "topic": "fee-waiver",
            "stage": "filing",
            "document_id": "JD-FM-160",
        },
    ),
    SourceSpec(
        slug="form-jd-fm-164",
        kind=_PDF_KIND,
        url="https://www.jud.ct.gov/webforms/forms/FM164.pdf",
        output_path="forms/form-jd-fm-164.md",
        metadata={
            "source_type": "court_form",
            "authority_level": "court_published",
            "citation": "Affidavit Concerning Children (JD-FM-164)",
            "title": "Affidavit Concerning Children",
            "date": "2026",
            "jurisdiction": "Connecticut",
            "issuing_body": "Connecticut Judicial Branch",
            "topic": "uccjea-disclosure",
            "stage": "filing",
            "document_id": "JD-FM-164",
        },
    ),
    SourceSpec(
        slug="form-jd-fm-242",
        kind=_PDF_KIND,
        url="https://www.jud.ct.gov/webforms/forms/FM242.pdf",
        output_path="forms/form-jd-fm-242.md",
        metadata={
            "source_type": "court_form",
            "authority_level": "court_published",
            "citation": "Joint Petition for Nonadversarial Divorce (JD-FM-242)",
            "title": "Joint Petition - Nonadversarial Divorce",
            "date": "2026",
            "jurisdiction": "Connecticut",
            "issuing_body": "Connecticut Judicial Branch",
            "topic": "nonadversarial-dissolution",
            "stage": "filing",
            "document_id": "JD-FM-242",
        },
    ),
    SourceSpec(
        slug="form-jd-fm-272",
        kind=_PDF_KIND,
        url="https://www.jud.ct.gov/webforms/forms/FM272.pdf",
        output_path="forms/form-jd-fm-272.md",
        metadata={
            "source_type": "court_form",
            "authority_level": "court_published",
            "citation": "Motion for Entry of Judgment upon Default of Appearance — Divorce or Legal Separation (JD-FM-272)",
            "title": "Motion for Entry of Judgment upon Default of Appearance",
            "date": "2026",
            "jurisdiction": "Connecticut",
            "issuing_body": "Connecticut Judicial Branch",
            "topic": "default-judgment",
            "stage": "judgment",
            "document_id": "JD-FM-272",
        },
    ),
    SourceSpec(
        slug="form-jd-fm-264",
        kind=_PDF_KIND,
        url="https://jud.ct.gov/Publications/FM264.pdf",
        output_path="forms/form-jd-fm-264.md",
        metadata={
            "source_type": "court_form",
            "authority_level": "court_published",
            "citation": "The Forms You Will Need to File for Divorce (JD-FM-264)",
            "title": "The Forms You Will Need to File for Divorce",
            "date": "2026",
            "jurisdiction": "Connecticut",
            "issuing_body": "Connecticut Judicial Branch",
            "topic": "divorce-process",
            "stage": "filing",
            "document_id": "JD-FM-264",
        },
    ),
)

PRACTICE_BOOK_SPECS: tuple[SourceSpec, ...] = (
    SourceSpec(
        slug="pb-2026",
        kind=_PDF_KIND,
        url="https://www.jud.ct.gov/Publications/PracticeBook/PB.pdf",
        output_path="practice_book/pb-2026.md",
        metadata={
            "source_type": "practice_book",
            "authority_level": "court_rule",
            "citation": "Conn. Practice Book (2026 Edition)",
            "title": "Connecticut Practice Book, 2026 Edition",
            "date": "2026",
            "jurisdiction": "Connecticut",
            "issuing_body": "Connecticut Judicial Branch",
            "topic": "court-rules",
            "stage": "trial",
        },
    ),
)

# Additional law-library pathfinders. Highly trial-relevant — they
# enumerate the procedural rules and key CT cases for motions and
# discovery in family matters.
EXTRA_GUIDE_SPECS: tuple[SourceSpec, ...] = (
    SourceSpec(
        slug="lawlib-family-motion-practice",
        kind=_PDF_KIND,
        url="https://www.jud.ct.gov/lawlib/Notebooks/Pathfinders/MotionPractice.pdf",
        output_path="guides/lawlib-family-motion-practice.md",
        metadata={
            "source_type": "law_library_guide",
            "authority_level": "secondary",
            "citation": "Family Motion Practice in Connecticut (Law Library Pathfinder)",
            "title": "Family Motion Practice",
            "date": "2026",
            "jurisdiction": "Connecticut",
            "issuing_body": "Connecticut Judicial Branch Law Libraries",
            "topic": "motion-practice",
            "stage": "trial",
        },
    ),
    SourceSpec(
        slug="lawlib-family-discovery",
        kind=_PDF_KIND,
        url="https://www.jud.ct.gov/lawlib/Notebooks/Pathfinders/FamilyDiscovery.pdf",
        output_path="guides/lawlib-family-discovery.md",
        metadata={
            "source_type": "law_library_guide",
            "authority_level": "secondary",
            "citation": "Discovery in Family Matters (Law Library Pathfinder)",
            "title": "Discovery in Family Matters",
            "date": "2026",
            "jurisdiction": "Connecticut",
            "issuing_body": "Connecticut Judicial Branch Law Libraries",
            "topic": "discovery",
            "stage": "after-filing",
        },
    ),
)

STARTER_SOURCES: tuple[SourceSpec, ...] = (
    STATUTE_SPECS + PRACTICE_BOOK_SPECS + GUIDE_SPECS + EXTRA_GUIDE_SPECS + FORM_SPECS
)


def fetch_public_starter(
    out_dir: Path,
    *,
    force: bool,
    include_statutes: bool,
    include_guides: bool,
    include_forms: bool,
    include_practice_book: bool,
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
    if include_practice_book:
        sources.extend(PRACTICE_BOOK_SPECS)
    if include_guides:
        sources.extend(GUIDE_SPECS)
        sources.extend(EXTRA_GUIDE_SPECS)
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
        "include_practice_book": include_practice_book,
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
        if spec.metadata.get("source_type") == "practice_book":
            text = _trim_trailing_index(text)
        return render_with_frontmatter(metadata, text, suffix=".md")

    raise ValueError(f"Unsupported source kind: {spec.kind}")


_DOTTED_LEADER_RE = re.compile(r"(?m)^.{0,80}(?:\.\s){5,}")


def _trim_trailing_index(text: str) -> str:
    """Drop the dotted-leader index/TOC that follows the last `Sec. NN-NN.`
    heading in a Practice Book PDF extraction. Without this, the chunker
    treats the final rule (e.g. Sec. 86-2) as the parent of the entire
    back-of-book index — producing tens of thousands of spurious chunks
    and ruining retrieval.

    The PB rule body is normal prose. The cross-reference index that
    follows has lines like
        `1 . . . . . . . . . . .  1-3`
    which contain dotted leaders. We find the first such line after the
    LAST real section heading and truncate there.
    """
    section_re = re.compile(r"(?m)^Sec\. [0-9A-Za-z\-]+\.")
    matches = list(section_re.finditer(text))
    if not matches:
        return text
    last_section_start = matches[-1].start()
    leader_match = _DOTTED_LEADER_RE.search(text, pos=last_section_start)
    if not leader_match:
        return text
    return text[: leader_match.start()].rstrip() + "\n"


def _download(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return response.read()
    except URLError as exc:
        reason = getattr(exc, "reason", None)
        # OpenSSL 3.x defaults to SECLEVEL=2, which rejects some legacy
        # ciphers / weak DH params still served by jud.ct.gov. When the
        # server kills the handshake, retry with SECLEVEL=0 (still
        # verifying the cert chain — just permitting weaker negotiated
        # parameters). Cert-verification errors keep their original
        # insecure-context fallback below.
        if isinstance(reason, ssl.SSLError) and "HANDSHAKE_FAILURE" in str(reason):
            relaxed = ssl.create_default_context()
            try:
                relaxed.set_ciphers("DEFAULT@SECLEVEL=0")
            except ssl.SSLError:
                pass
            with urlopen(
                request, timeout=REQUEST_TIMEOUT_SECONDS, context=relaxed,
            ) as response:
                return response.read()
        if not isinstance(reason, ssl.SSLCertVerificationError):
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
