# Corpus Format

This project now supports a small but explicit source model for building a
Connecticut divorce knowledge base. The goal is to keep primary law,
court-issued guidance, and personal case files separated so retrieval can
prefer the strongest authority.

## Source types

- `statute`: Connecticut General Statutes, usually Title 46b sections.
- `practice_book`: Connecticut Practice Book rules.
- `case`: Connecticut appellate case law.
- `court_form`: Connecticut Judicial Branch forms.
- `court_guide`: Connecticut Judicial Branch public-facing guides and FAQs.
- `law_library_guide`: Connecticut Judicial Branch Law Library research guides.
- `case_file`: personal case materials, pleadings, affidavits, orders, notes.

Each document also carries an `authority_level`:

- `primary`: statutes and case law
- `court_rule`: Practice Book rules
- `court_published`: official court forms and public guidance
- `secondary`: research guides and other explanatory materials
- `personal`: the user's own case documents

## Recommended raw file names

The ingest pipeline infers metadata from file names when possible:

- `cgs-46b-82.txt`
- `pb-25-26.txt`
- `case-oconnell-v-oconnell.txt`
- `form-jd-fm-159.md`
- `guide-divorce-options.md`
- `lawlib-dissolution-of-marriage.md`

If the filename is not enough, add frontmatter at the top of the file.

## Frontmatter

Supported frontmatter keys:

- `source_type`
- `authority_level`
- `citation`
- `title`
- `section`
- `subsection`
- `date`
- `jurisdiction`
- `issuing_body`
- `topic`
- `stage`
- `document_id`

Example for an official Judicial Branch guide:

```text
---
source_type: court_guide
authority_level: court_published
citation: Divorce Options in Connecticut
title: Divorce Options in Connecticut
issuing_body: Connecticut Judicial Branch
jurisdiction: Connecticut
topic: divorce-process
stage: pre-filing
document_id: FM-274
---
```

Example for a CT statute dump that contains multiple sections:

```text
---
source_type: statute
authority_level: primary
issuing_body: Connecticut General Assembly
jurisdiction: Connecticut
topic: family-law
---
Sec. 46b-81. Assignment of property and transfer of title.
(a) At the time of entering a decree ...
```

## Chunking behavior

For `statute` and `practice_book` sources, ingestion is citation-aware:

1. Split on repeated `Sec. ...` headings when a file contains multiple sections.
2. Within each section, split on top-level subsections like `(a)`, `(b)`, `(c)`.
3. Use recursive character chunking only inside each logical block.

This keeps chunks aligned with legal citations like:

- `Conn. Gen. Stat. § 46b-82`
- `Conn. Gen. Stat. § 46b-82(a)`
- `Conn. Practice Book § 25-26`

For forms, guides, law-library materials, and case files, the pipeline uses
general text chunking while preserving the document metadata.

## Practical CT divorce corpus plan

Start with four buckets:

1. `statute`: `46b-40`, `46b-44`, `46b-45`, `46b-56`, `46b-67`, `46b-81`,
   `46b-82`, `46b-83`, `46b-84`, `46b-86`
2. `practice_book`: Chapter 25 family procedure rules
3. `court_guide` / `court_form`: divorce options, pathways, FAQs, key forms
4. `case`: a hand-picked set of Connecticut appellate decisions on alimony,
   property division, custody, and postjudgment modification

To bootstrap the public corpus, run:

```bash
python -m ingest.main fetch-public
python -m ingest.main data/raw/public --dry-run
python -m ingest.main data/raw/public
```

Use `python -m ingest.main data/raw --dry-run` before a full ingest so you can
inspect chunk counts and metadata categories.
