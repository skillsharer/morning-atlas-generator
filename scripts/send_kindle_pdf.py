#!/usr/bin/env python3
"""Email a locally available Morning Atlas PDF to Amazon Kindle via Gmail SMTP."""
import argparse
import os
import re
import smtplib
import ssl
from datetime import date
from email.message import EmailMessage
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pdf', required=True, type=Path)
    args = parser.parse_args()
    path = args.pdf.resolve()
    if not path.is_file() or path.stat().st_size < 1000:
        raise SystemExit(f'PDF missing or too small: {path}')
    if not re.fullmatch(r'Morning_Atlas_\d{4}-\d{2}-\d{2}\.pdf', path.name):
        raise SystemExit('Unexpected PDF filename; expected Morning_Atlas_YYYY-MM-DD.pdf')
    edition_date = path.stem.removeprefix('Morning_Atlas_')
    date.fromisoformat(edition_date)
    with path.open('rb') as handle:
        if handle.read(5) != b'%PDF-':
            raise SystemExit('File does not have a PDF header')
    sender = os.environ['GMAIL_ADDRESS'].strip()
    recipient = os.environ['KINDLE_EMAIL'].strip()
    app_password = os.environ['GMAIL_APP_PASSWORD'].replace(' ', '')
    if not sender or not recipient or not app_password:
        raise SystemExit('Missing Gmail/Kindle configuration')
    message = EmailMessage()
    message['From'] = sender
    message['To'] = recipient
    message['Subject'] = f'The Morning Atlas — {edition_date}'
    message.set_content(f'The Morning Atlas newspaper for {edition_date}. PDF attached.')
    message.add_attachment(path.read_bytes(), maintype='application', subtype='pdf', filename=path.name)
    with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=ssl.create_default_context(), timeout=30) as smtp:
        smtp.login(sender, app_password)
        smtp.send_message(message)
    print(f'Gmail SMTP accepted PDF: {path.name} ({path.stat().st_size} bytes)')
    print('Note: Amazon Kindle delivery is not confirmed by SMTP acceptance.')

if __name__ == '__main__':
    main()
