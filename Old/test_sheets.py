import gspread
from google.oauth2.service_account import Credentials

GSHEET_CREDS_FILE = "gsheets_creds.json"
GOOGLE_SHEET_NAME = "Boat Counter Logs"

try:
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials = Credentials.from_service_account_file(GSHEET_CREDS_FILE, scopes=scopes)
    client = gspread.authorize(credentials)
    sheet = client.open(GOOGLE_SHEET_NAME).sheet1
    print("[✅] Connected to Google Sheets successfully.")
    print(f"[📝] Sheet title: {sheet.title}, Rows: {sheet.row_count}, Cols: {sheet.col_count}")
except Exception as e:
    print(f"[❌ ERROR] Google Sheets setup failed:\n{e}")
