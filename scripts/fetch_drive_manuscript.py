#!/usr/bin/env python3
"""Download and validate a Morning Atlas manuscript from a shared Google Doc."""
import argparse
import json
import os
from datetime import date
from pathlib import Path

from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    date.fromisoformat(args.date)

    info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    credentials = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    document_id = os.environ["MORNING_ATLAS_DOC_ID"].strip()
    response = AuthorizedSession(credentials).get(
        f"https://www.googleapis.com/drive/v3/files/{document_id}/export",
        params={"mimeType": "text/plain"},
        timeout=60,
    )
    response.raise_for_status()
    manuscript = json.loads(response.content.decode("utf-8-sig").strip())
    if manuscript.get("date") != args.date:
        raise ValueError(f"Wrong edition date: {manuscript.get('date')} (expected {args.date})")
    if not isinstance(manuscript.get("articles"), list) or not manuscript["articles"]:
        raise ValueError("Missing articles")
    for article in manuscript["articles"]:
        if not article.get("headline") or not article.get("paragraphs"):
            raise ValueError("Article missing headline or paragraphs")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manuscript, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Fetched {len(manuscript['articles'])} articles for {args.date}")


if __name__ == "__main__":
    main()
