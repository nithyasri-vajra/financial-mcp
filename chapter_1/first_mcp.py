from fastmcp import FastMCP
import os
import base64
from email.mime.text import MIMEText

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


# --------------------------------------------------
# Load environment variables
# --------------------------------------------------

load_dotenv()


# --------------------------------------------------
# MCP Server
# --------------------------------------------------

mcp = FastMCP("Meeting Follow-up")


# --------------------------------------------------
# Google API scopes
# --------------------------------------------------

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/gmail.compose",
]


# --------------------------------------------------
# Environment variables
# --------------------------------------------------

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REFRESH_TOKEN = os.getenv("GOOGLE_REFRESH_TOKEN")

TRACKER_SPREADSHEET_ID = os.getenv("TRACKER_SPREADSHEET_ID")
TRACKER_SHEET_NAME = os.getenv("TRACKER_SHEET_NAME")


# --------------------------------------------------
# Validate required environment variables
# --------------------------------------------------

required_variables = {
    "GOOGLE_CLIENT_ID": GOOGLE_CLIENT_ID,
    "GOOGLE_CLIENT_SECRET": GOOGLE_CLIENT_SECRET,
    "GOOGLE_REFRESH_TOKEN": GOOGLE_REFRESH_TOKEN,
    "TRACKER_SPREADSHEET_ID": TRACKER_SPREADSHEET_ID,
    "TRACKER_SHEET_NAME": TRACKER_SHEET_NAME,
}

missing_variables = [
    name
    for name, value in required_variables.items()
    if not value
]

if missing_variables:
    raise RuntimeError(
        "Missing environment variables: "
        + ", ".join(missing_variables)
    )


# --------------------------------------------------
# Google authentication
# --------------------------------------------------

credentials = Credentials(
    token=None,
    refresh_token=GOOGLE_REFRESH_TOKEN,
    token_uri="https://oauth2.googleapis.com/token",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    scopes=SCOPES,
)


# --------------------------------------------------
# Refresh Google access token
# --------------------------------------------------

if credentials.expired or not credentials.valid:
    credentials.refresh(Request())


# --------------------------------------------------
# Google services
# --------------------------------------------------

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


# ==================================================
# TOOL 1: Find Meeting
# ==================================================

@mcp.tool()
def find_meeting(date: str, keyword: str = ""):
    """
    Find meetings in Google Calendar for a specific date.

    The date is required.

    The keyword is optional. Use it only when the user
    explicitly provides a specific meeting name or search word.

    Do not treat words such as "my", "meeting", "meetings",
    "find", "show", or "get" as search keywords.

    If only a date is provided, return all meetings for that date.
    """

    events = calendar_service.events().list(
        calendarId="primary",
        timeMin=f"{date}T00:00:00+05:30",
        timeMax=f"{date}T23:59:59+05:30",
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    matches = []

    keyword_lower = keyword.strip().lower()

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

        if keyword_lower and keyword_lower not in search_text:
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
            "message": "No meetings found for this date"
        }

    return matches


# ==================================================
# TOOL 2: Get Gemini Notes
# ==================================================

@mcp.tool()
def get_gemini_notes(doc_id: str):
    """
    Read a Gemini meeting notes Google Doc and return
    the complete document text, including paragraphs
    and table contents.

    Table contents are important because meeting action
    items may be stored inside a table.
    """

    document = docs_service.documents().get(
        documentId=doc_id
    ).execute()

    text_parts = []

    def extract_elements(elements):
        """
        Recursively extract text from Google Docs paragraphs
        and tables.
        """

        for element in elements:

            # ------------------------------------------
            # Normal paragraph
            # ------------------------------------------

            paragraph = element.get("paragraph")

            if paragraph:

                for item in paragraph.get("elements", []):

                    text_run = item.get("textRun")

                    if text_run:
                        text_parts.append(
                            text_run.get("content", "")
                        )

            # ------------------------------------------
            # Table
            # ------------------------------------------

            table = element.get("table")

            if table:

                for row in table.get("tableRows", []):

                    for cell in row.get("tableCells", []):

                        cell_content = cell.get("content", [])

                        extract_elements(cell_content)

                        # Add separator between table cells
                        text_parts.append(" | ")

                    # Add new line after each table row
                    text_parts.append("\n")

    body_content = document.get(
        "body", {}
    ).get(
        "content", []
    )

    extract_elements(body_content)

    notes_text = "".join(text_parts).strip()
    print("\n========== RAW NOTES ==========")
    print(notes_text)
    print("================================\n")

    return {
        "doc_id": doc_id,
        "notes": notes_text
    }


# ==================================================
# MCP PROMPT: Meeting Follow-up
# ==================================================

@mcp.prompt()
def meeting_followup():
    """
    Reusable instruction for handling meeting follow-up work.
    """

    return """
    Review the meeting information and complete the meeting
    follow-up analysis.

    Carefully read the complete meeting notes, including
    information contained inside tables.

    When the notes contain sections such as:
    - Suggested Next Steps
    - Action Items
    - Follow-up Actions
    - Next Steps

    treat the rows under those sections as the actual action items.

    Preserve the exact:
    - owner
    - task
    - due date

    from the meeting notes.

    Do not say that there are no action items when action
    items are present in the notes.

    Do not invent or change owners, tasks, or due dates.

    If the user asks only to read or summarize the notes,
    provide the information from the notes without automatically
    logging items to the tracker or creating an email draft.

    Only use the tracker or Gmail tools when the user asks
    for those actions.
    """


# ==================================================
# TOOL 3: Log Action Items
# ==================================================

@mcp.tool()
def log_action_items(
    spreadsheet_id: str,
    sheet_name: str,
    items: list
):
    """
    Add meeting action items to the tracker Google Sheet.

    Each item should contain:
    owner
    task
    due_date
    meeting
    source_link
    """

    if not items:
        return {
            "message": "No action items to add"
        }

    existing_data = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"{sheet_name}!A:E"
    ).execute()

    values = existing_data.get("values", [])

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

    rows = []

    for item in items:

        rows.append([
            item.get("owner", ""),
            item.get("task", ""),
            item.get("due_date", ""),
            item.get("meeting", ""),
            item.get("source_link", "")
        ])

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


# ==================================================
# TOOL 4: Draft Follow-up Email
# ==================================================

@mcp.tool()
def draft_followup_email(
    to: str,
    subject: str,
    body: str
):
    """
    Create a Gmail draft.

    The email is never sent.
    """

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


# ==================================================
# MCP SERVER
# ==================================================

if __name__ == "__main__":

    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8000
    )