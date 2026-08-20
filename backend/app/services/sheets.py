"""Google Sheets client using a service account (server-to-server)."""

import os
from functools import lru_cache

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import get_settings

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

COLUMNS_ORDERS = [
    "Order ID",
    "name",
    "wilaya",
    "commune",
    "phone",
    "product",
    "size",
    "color",
    "price",
    "quantity",
    "delivery_method",
    "status",
]

COLUMNS_PRODUCTS = [
    "name",
    "price",
    "sizes",
    "colors",
    "image_url",
    "stock",
    "facebook post id",
    "instagram post id",
]

COLUMNS_POSTS = ["facebook post id", "instagram post id", "product name"]


@lru_cache
def _credentials():
    path = get_settings().GOOGLE_APPLICATION_CREDENTIALS
    if not path:
        raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS is not set")
    creds = service_account.Credentials.from_service_account_file(path, scopes=SCOPES)
    return creds


def _service():
    creds = _credentials()
    creds.refresh(GoogleAuthRequest())
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


class SheetsClient:
    def __init__(self):
        self.service = _service()

    def read_range(self, spreadsheet_id: str, range_name: str) -> list[list]:
        result = self.service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=range_name
        ).execute()
        return result.get("values", [])

    def read_all(self, spreadsheet_id: str, tab: str) -> list[list]:
        return self.read_range(spreadsheet_id, f"{tab}!A1:ZZ")

    def write_range(self, spreadsheet_id: str, range_name: str, values: list[list]):
        body = {"values": values}
        self.service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption="RAW",
            body=body,
        ).execute()

    def append_row(self, spreadsheet_id: str, tab: str, values: list):
        body = {"values": [values]}
        self.service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{tab}!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body=body,
        ).execute()


def sheets_rows_to_dicts(rows: list[list]) -> list[dict]:
    if not rows:
        return []
    header = [str(h).strip() if h else f"col_{i}" for i, h in enumerate(rows[0])]
    result = []
    for row in rows[1:]:
        record = {}
        for i, value in enumerate(row):
            if i < len(header):
                record[header[i]] = value
        result.append(record)
    return result