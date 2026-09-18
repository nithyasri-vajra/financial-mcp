from fastmcp import FastMCP
import os
from dotenv import load_dotenv

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

load_dotenv()

mcp = FastMCP("Meeting Follow-up")


# --------------------------------------------------
# Google authentication
# --------------------------------------------------

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/gmail.compose",
]

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REFRESH_TOKEN = os.getenv("GOOGLE_REFRESH_TOKEN")

if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
    raise RuntimeError(
        "GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET is missing"
    )

if not GOOGLE_REFRESH_TOKEN:
    raise RuntimeError(
        "GOOGLE_REFRESH_TOKEN is missing"
    )


credentials = Credentials(
    token=None,
    refresh_token=GOOGLE_REFRESH_TOKEN,
    token_uri="https://oauth2.googleapis.com/token",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    scopes=SCOPES,
)


calendar_service = build(
    "calendar",
    "v3",
    credentials=credentials
)

drive_service = build(
    "drive",
    "v3",
    credentials=credentials
)

docs_service = build(
    "docs",
    "v1",
    credentials=credentials
)

sheets_service = build(
    "sheets",
    "v4",
    credentials=credentials
)

gmail_service = build(
    "gmail",
    "v1",
    credentials=credentials
)


# --------------------------------------------------
# TOOL 1: Find meeting
# --------------------------------------------------

@mcp.tool()
def find_meeting(date: str, keyword: str):
    """
    Find a meeting in Google Calendar using date and keyword.
    Searches the meeting title, description, location, and attendees.
    """

    events = calendar_service.events().list(
        calendarId="primary",
        timeMin=f"{date}T00:00:00+05:30",
        timeMax=f"{date}T23:59:59+05:30",
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    matches = []

    keyword_lower = keyword.lower()

    for event in events.get("items", []):
        title = event.get("summary", "")
        description = event.get("description", "")
        location = event.get("location", "")

        attendees = [
            attendee.get("email", "")
            for attendee in event.get("attendees", [])
        ]

        search_text = " ".join([
            title,
            description,
            location,
            " ".join(attendees)
        ]).lower()

        if keyword_lower not in search_text:
            continue

        attachments = event.get("attachments", [])

        notes_doc_id = None

        for attachment in attachments:
            if attachment.get(
                "mimeType"
            ) == "application/vnd.google-apps.document":
                notes_doc_id = attachment.get("fileId")
                break

        matches.append({
            "meeting_id": event.get("id"),
            "meeting_name": title,
            "start": event.get("start"),
            "end": event.get("end"),
            "attendees": attendees,
            "gemini_notes_doc_id": notes_doc_id
        })

    if not matches:
        return {
            "message": "No matching meeting found"
        }

    return matches


# --------------------------------------------------
# TOOL 2: Get Gemini Notes
# --------------------------------------------------

@mcp.tool()
def get_gemini_notes(doc_id: str):
    """
    Read a Gemini meeting notes Google Doc and return its text.
    """

    document = docs_service.documents().get(
        documentId=doc_id
    ).execute()

    text_parts = []

    for element in document.get("body", {}).get("content", []):

        paragraph = element.get("paragraph")

        if paragraph:
            for item in paragraph.get("elements", []):

                text_run = item.get("textRun")

                if text_run:
                    text_parts.append(
                        text_run.get("content", "")
                    )

    notes_text = "".join(text_parts)

    return {
        "doc_id": doc_id,
        "notes": notes_text
    }


# --------------------------------------------------
# TOOL 3: Log Action Items
# --------------------------------------------------

@mcp.tool()
def log_action_items(
    spreadsheet_id: str,
    sheet_name: str,
    items: list
):
    """
    Add meeting action items to the tracker Google Sheet.
    Creates the header row automatically if the sheet is empty.
    """

    if not items:
        return {
            "message": "No action items to add"
        }

    # Check whether the sheet already has data
    existing_data = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"{sheet_name}!A:E"
    ).execute()

    values = existing_data.get("values", [])

    # Create header automatically if the sheet is empty
    if not values:
        sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A1:E1",
            valueInputOption="USER_ENTERED",
            body={
                "values": [[
                    "Owner",
                    "Task",
                    "Due Date",
                    "Meeting",
                    "Source Link"
                ]]
            }
        ).execute()

    # Prepare action-item rows
    rows = []

    for item in items:
        rows.append([
            item.get("owner", ""),
            item.get("task", ""),
            item.get("due_date", ""),
            item.get("meeting", ""),
            item.get("source_link", "")
        ])

    # Add action items below existing data
    sheets_service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"{sheet_name}!A:E",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={
            "values": rows
        }
    ).execute()

    return {
        "message": f"{len(rows)} action item(s) added to tracker"
    }


# --------------------------------------------------
# TOOL 4: Draft Follow-up Email
# --------------------------------------------------

@mcp.tool()
def draft_followup_email(
    to: str,
    subject: str,
    body: str
):
    """
    Create a Gmail draft. It never sends the email.
    """

    import base64
    from email.mime.text import MIMEText

    message = MIMEText(body)

    message["To"] = to
    message["Subject"] = subject

    encoded_message = base64.urlsafe_b64encode(
        message.as_bytes()
    ).decode()

    draft = gmail_service.users().drafts().create(
        userId="me",
        body={
            "message": {
                "raw": encoded_message
            }
        }
    ).execute()

    return {
        "message": "Gmail draft created successfully",
        "draft_id": draft.get("id")
    }


# --------------------------------------------------
# MCP SERVER
# --------------------------------------------------

if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8000
    )