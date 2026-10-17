# The Morning Atlas — reusable newspaper generator

A stable, versionable **two-column A3 broadsheet PDF** generator. Both the PDF and
a ChatGPT-friendly Markdown file are derived from **one canonical JSON manuscript**.

## Install

```bash
python -m pip install -r requirements.txt
```

Requires DejaVu or Liberation TTF fonts installed on the host. No font files are bundled.

## Generate

```bash
python morning_atlas_pdf.py example_edition.json --out-dir output --verify
```

Outputs `Morning_Atlas_YYYY-MM-DD.pdf` and `Morning_Atlas_YYYY-MM-DD.md`.

## Daily workflow

1. Research and verify today's stories.
2. Save one JSON manuscript using the structure in `example_edition.json`.
3. Run the script with `--verify`.
4. Publish the generated Markdown content in ChatGPT and attach the generated PDF.
5. Do not separately rewrite or shorten either version.

The PDF uses serif fonts, a masthead, editorial rules, two columns, page numbers,
article headlines, and clickable source links.

## Important limitation

`--verify` checks for article headings, paragraph openings, closing note and links.
It is a useful automated smoke test, **not a mathematical guarantee of exact word-for-word
parity**. For production, additionally compare normalized full manuscript text to
PDF extraction and visually inspect rendered pages.

## GitHub reuse

Commit the script, requirements, README and example JSON to a public or accessible
repository. On a future run, supply the raw script URL or connect GitHub if available.
A scheduled task cannot be guaranteed to fetch an arbitrary repository on every run;
the assistant should verify repository access and disclose if reuse is unavailable.
