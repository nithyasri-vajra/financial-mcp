from fastmcp import FastMCP
from dotenv import load_dotenv

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

import os
import base64
from email.mime.text import MIMEText


load_dotenv()

mcp = FastMCP("Meeting Follow-up")


# ==================================================
# GOOGLE AUTHENTICATION
# ==================================================

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/gmail.compose",
]


# Get Google OAuth credentials from .env
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")


if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
    raise RuntimeError(
        "GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET is missing in .env"
    )


# Google OAuth configuration
client_config = {
    "installed": {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [
            "http://localhost"
        ]
    }
}


# First-time authorization
flow = InstalledAppFlow.from_client_config(
    client_config,
    SCOPES
)

credentials = flow.run_local_server(
    port=0
)


# ==================================================
# GOOGLE SERVICES
# ==================================================

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
# CONFIGURATION
# ==================================================

SPREADSHEET_ID = os.getenv(
    "TRACKER_SPREADSHEET_ID"
)

SHEET_NAME = os.getenv(
    "TRACKER_SHEET_NAME",
    "Sheet1"
)


# ==================================================
# TOOL 1: FIND MEETING
# ==================================================

@mcp.tool()
def find_meeting(date: str, keyword: str):
    """
    Find a meeting in Google Calendar using date
    and meeting keyword.

    Returns meeting details and the attached
    Gemini Notes document ID if available.
    """

    events = calendar_service.events().list(
        calendarId="primary",
        timeMin=f"{date}T00:00:00+05:30",
        timeMax=f"{date}T23:59:59+05:30",
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    matches = []

    for event in events.get("items", []):

        title = event.get(
            "summary",
            ""
        )

        if keyword.lower() not in title.lower():
            continue

        attendees = [
            attendee.get("email")
            for attendee in event.get(
                "attendees",
                []
            )
            if attendee.get("email")
        ]

        attachments = event.get(
            "attachments",
            []
        )

        notes_doc_id = None
        notes_link = None


        # Check Calendar attachments
        for attachment in attachments:

            if attachment.get("mimeType") == (
                "application/vnd.google-apps.document"
            ):

                notes_doc_id = attachment.get(
                    "fileId"
                )

                notes_link = attachment.get(
                    "fileUrl"
                )

                break


        # Fallback: search Google Drive
        if notes_doc_id is None:

            search_query = (
                "mimeType = "
                "'application/vnd.google-apps.document' "
                "and trashed = false "
                f"and name contains '{title}'"
            )

            drive_results = drive_service.files().list(
                q=search_query,
                spaces="drive",
                fields="files(id,name,webViewLink,mimeType)",
                pageSize=10
            ).execute()

            for file in drive_results.get(
                "files",
                []
            ):

                if "notes by gemini" in file.get(
                    "name",
                    ""
                ).lower():

                    notes_doc_id = file.get(
                        "id"
                    )

                    notes_link = file.get(
                        "webViewLink"
                    )

                    break


        matches.append({
            "meeting_id": event.get(
                "id"
            ),
            "meeting_name": title,
            "start": event.get(
                "start"
            ),
            "end": event.get(
                "end"
            ),
            "attendees": attendees,
            "gemini_notes_doc_id": notes_doc_id,
            "gemini_notes_link": notes_link
        })


    if not matches:

        return {
            "message": "No matching meeting found"
        }


    return matches


# ==================================================
# TOOL 2: GET GEMINI NOTES
# ==================================================

@mcp.tool()
def get_gemini_notes(doc_id: str):
    """
    Read a Gemini meeting notes Google Doc
    and return its text.
    """

    document = docs_service.documents().get(
        documentId=doc_id
    ).execute()

    text_parts = []

    for element in document.get(
        "body",
        {}
    ).get(
        "content",
        []
    ):

        paragraph = element.get(
            "paragraph"
        )

        if paragraph:

            for item in paragraph.get(
                "elements",
                []
            ):

                text_run = item.get(
                    "textRun"
                )

                if text_run:

                    text_parts.append(
                        text_run.get(
                            "content",
                            ""
                        )
                    )


    notes_text = "".join(
        text_parts
    )


    return {
        "doc_id": doc_id,
        "notes": notes_text
    }


# ==================================================
# TOOL 3: LOG ACTION ITEMS
# ==================================================

@mcp.tool()
def log_action_items(
    spreadsheet_id: str,
    sheet_name: str,
    items: list
):
    """
    Add meeting action items to the tracker
    Google Sheet.

    Creates the header row automatically
    if the sheet is empty.
    """

    if not items:

        return {
            "message": "No action items to add"
        }


    # Check existing sheet data
    existing_data = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"{sheet_name}!A:E"
    ).execute()

    values = existing_data.get(
        "values",
        []
    )


    # Create header automatically
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
            item.get(
                "owner",
                ""
            ),
            item.get(
                "task",
                ""
            ),
            item.get(
                "due_date",
                ""
            ),
            item.get(
                "meeting",
                ""
            ),
            item.get(
                "source_link",
                ""
            )
        ])


    # Add rows
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
        "message": (
            f"{len(rows)} action item(s) "
            "added to tracker"
        )
    }


# ==================================================
# TOOL 4: DRAFT FOLLOW-UP EMAIL
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


    encoded_message = (
        base64.urlsafe_b64encode(
            message.as_bytes()
        )
        .decode()
    )


    draft = gmail_service.users().drafts().create(
        userId="me",
        body={
            "message": {
                "raw": encoded_message
            }
        }
    ).execute()


    return {
        "message": (
            "Gmail draft created successfully"
        ),
        "draft_id": draft.get(
            "id"
        )
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