#!/usr/bin/env python3
"""Fetch the latest matching dated Morning Atlas JSON from a shared Drive folder."""
import argparse
import json
import os
from datetime import date
from pathlib import Path
from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--date", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    date.fromisoformat(args.date)
    folder = os.environ["MORNING_ATLAS_FOLDER_ID"].strip()
    if not folder:
        raise ValueError("MORNING_ATLAS_FOLDER_ID is empty")
    info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/drive.readonly"])
    session = AuthorizedSession(creds)
    q = f"'{folder}' in parents and trashed = false and name = 'Morning_Atlas_{args.date}.json'"
    files = []
    token = None
    while True:
        params = {"q": q, "fields": "nextPageToken,files(id,name,mimeType,modifiedTime)",
                  "page_size": 100, "orderBy": "modifiedTime desc",
                  "supportsAllDrives": "true", "includeItemsFromAllDrives": "true"}
        if token:
            params["pageToken"] = token
        resp = session.get("https://www.googleapis.com/drive/v3/files", params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        files.extend(data.get("files", []))
        token = data.get("nextPageToken")
        if not token:
            break
    if not files:
        raise ValueError(f"No dated manuscript for {args.date} in Drive folder")
    errors = []
    for item in sorted(files, key=lambda x: x.get("modifiedTime", ""), reverse=True):
        if item.get("mimeType") != "application/json":
            errors.append(f"{item['id']}: not a JSON file")
            continue
        try:
            resp = session.get(f"https://www.googleapis.com/drive/v3/files/{item['id']}",
                               params={"alt": "media", "supportsAllDrives": "true"}, timeout=60)
            resp.raise_for_status()
            manuscript = resp.json()
            if manuscript.get("date") != args.date:
                raise ValueError("Edition date mismatch")
            if not isinstance(manuscript.get("articles"), list) or not manuscript["articles"]:
                raise ValueError("Missing articles")
            for a in manuscript["articles"]:
                if not a.get("section") or not a.get("headline") or not isinstance(a.get("paragraphs"), list) or not a["paragraphs"] or not all(isinstance(x, str) and x.strip() for x in a["paragraphs"]):
                    raise ValueError("Incomplete article")
            if not manuscript.get("closing_note"):
                raise ValueError("Missing closing note")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(manuscript, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Fetched {len(manuscript['articles'])} articles from {item['id']}")
            return
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            errors.append(f"{item['id']}: {e}")
    raise ValueError("No valid dated manuscript: " + "; ".join(errors))

if __name__ == "__main__":
    main()
