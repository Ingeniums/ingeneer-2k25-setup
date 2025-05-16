import csv
import os
import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# --- Configuration ---
SCOPES = ['https://www.googleapis.com/auth/drive']
CLIENT_SECRET_FILE = '../secret.json'
TOKEN_FILE = './token.json'
MEMBERS_INPUT_CSV = "./users.csv"
TEAM_CREDENTIALS_CSV = "./out/team-creds.csv"

TEAM_HEADER="Team name (exactly 4 members)"
EMAIL_HEADER="Email Address"

def authenticate_google_drive():
    creds = None
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
            print("Loaded credentials from token file.")
        except Exception as e:
            print(f"Error loading credentials from {TOKEN_FILE}: {e}")
            creds = None # Ensure creds is None if loading fails

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                print("Credentials expired, attempting to refresh...")
                creds.refresh(Request())
                print("Credentials refreshed successfully.")
            except Exception as e:
                print(f"Error refreshing credentials: {e}")
                creds = None # Could not refresh
        else:
            if not os.path.exists(CLIENT_SECRET_FILE):
                print(f"ERROR: OAuth Client Secret file not found at '{CLIENT_SECRET_FILE}'.")
                print("Please download it from Google Cloud Console and place it correctly.")
                exit(1)
            try:
                print(f"No valid token found. Starting OAuth flow using {CLIENT_SECRET_FILE}...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    CLIENT_SECRET_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
                print("OAuth flow completed. User authorized.")
            except FileNotFoundError:
                print(f"ERROR: Client secret file ('{CLIENT_SECRET_FILE}') not found.")
                exit(1)
            except Exception as e:
                print(f"Error during OAuth flow: {e}")
                exit(1)
        if creds:
            try:
                with open(TOKEN_FILE, 'w') as token:
                    token.write(creds.to_json())
                print(f"Credentials saved to {TOKEN_FILE}")
            except Exception as e:
                print(f"Error saving token to {TOKEN_FILE}: {e}")

    if not creds:
        print("Failed to obtain credentials.")
        return None

    try:
        service = build('drive', 'v3', credentials=creds)
        print("Google Drive API service built successfully with user credentials.")
        return service
    except HttpError as error:
        print(f"An error occurred building the Drive service: {error}")
        exit(1)
    except Exception as e:
        print(f"An unexpected error occurred building the Drive service: {e}")
        exit(1)

def create_team_folder(service, folder_name, parent_id):
    folder_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id]
    }
    created_folder = service.files().create(
        body=folder_metadata,
        fields='id, webViewLink'
    ).execute()

    folder_id = created_folder.get('id')
    web_view_link = created_folder.get('webViewLink') # Get the webViewLink

    return folder_id, web_view_link

def create_team_folder_and_share(service, folder_name, parent_id='root', member_emails=None, access_role='writer'):
    if member_emails is None:
        member_emails = []

    try:
        folder_id, web_view_link = create_team_folder(service, folder_name, parent_id)

        if not folder_id:
            print(f"Error: Failed to create folder '{folder_name}' or retrieve its ID.")
            return None, None
        
        if member_emails:
            for email in member_emails:
                try:
                    user_permission = {
                        'type': 'user',
                        'role': access_role,
                        'emailAddress': email
                    }
                    service.permissions().create(
                        fileId=folder_id,
                        body=user_permission,
                        fields='id',
                        sendNotificationEmail=False
                    ).execute()
                except HttpError as error:
                    print(f"Warning: An error occurred while granting permission to {email} for folder ID {folder_id}: {error}")

            print(f"Access granted on folder={folder_id} to {member_emails}")
        
        return folder_id, web_view_link

    except HttpError as error:
        print(f"Error: An API error occurred during folder creation for '{folder_name}': {error}")
        return None, None
    except Exception as e:
        print(f"Error: An unexpected error occurred during folder creation for '{folder_name}': {e}")
        return None, None

def get_folder_id_from_path(service, folder_path):
    """
    Retrieves the Google Drive ID of a folder given its path.
    (This function is preserved from the original script but not directly used in the new workflow)
    """
    if not folder_path:
        print("Error: Folder path cannot be empty.")
        return None

    path_parts = [part.strip() for part in folder_path.split('|') if part.strip()]

    if not path_parts:
        print("Error: Invalid folder path format.")
        return None

    current_parent_id = 'root' 

    if path_parts[0].lower() == 'my drive':
        if len(path_parts) == 1: 
            return 'root'
        path_parts.pop(0) 

    for i, folder_name in enumerate(path_parts):
        query = (f"name = '{folder_name}' and "
                 f"mimeType = 'application/vnd.google-apps.folder' and "
                 f"'{current_parent_id}' in parents and "
                 f"trashed = false")
        try:
            results = service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)',
                pageSize=10 
            ).execute()
            items = results.get('files', [])

            if not items:
                print(f"Error: Folder '{folder_name}' not found in parent ID '{current_parent_id}'. Path: {'/'.join(path_parts[:i+1])}")
                exit(1)
            if len(items) > 1:
                print(f"Warning: Multiple folders named '{folder_name}' found in parent ID '{current_parent_id}'. Using the first one found.")
                exit(1)
            
            current_parent_id = items[0].get('id')

        except HttpError as error:
            print(f"An error occurred while searching for folder '{folder_name}': {error}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return None
    return str(current_parent_id)

def process_team_members_and_update_creds(service, members_csv_path, team_creds_csv_path):
    """
    Reads team member information from a CSV, creates Google Drive folders for each team,
    grants access, and updates another CSV (team-creds.csv) with the folder links.
    """
    # --- 1. Read and process members_csv_path ---
    teams_data = {} 
    try:
        with open(members_csv_path, mode='r', encoding='utf-8', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            
            email_header = EMAIL_HEADER
            team_name_header = TEAM_HEADER
            
            if not reader.fieldnames:
                print(f"Error: Members CSV file '{members_csv_path}' is empty or has no headers.")
                return

            for row_number, row in enumerate(reader, 1):
                try:
                    team_name = row[team_name_header].strip()
                    email = row[email_header].strip()
                    if not team_name or not email:
                        print(f"Warning: Skipping row {row_number} in '{members_csv_path}' due to missing team name or email: {row}")
                        continue
                    if team_name not in teams_data:
                        teams_data[team_name] = []
                    teams_data[team_name].append(email)
                except KeyError:
                    print(f"Warning: Skipping row {row_number} in '{members_csv_path}' due to missing expected columns. Row: {row}")
                    continue
        
        if not teams_data:
            print(f"No valid team data extracted from '{members_csv_path}'.")
            return

    except FileNotFoundError:
        print(f"Error: Members CSV file not found at '{members_csv_path}'")
        return
    except Exception as e:
        print(f"An error occurred while reading '{members_csv_path}': {e}")
        return

    try:
        team_creds_df = pd.read_csv(team_creds_csv_path)
        if 'team_name' not in team_creds_df.columns:
            print(f"Error: 'team_name' column not found in '{team_creds_csv_path}'. Cannot match teams.")
            return
    except FileNotFoundError:
        print(f"Error: Team credentials CSV file not found at '{team_creds_csv_path}'. Cannot update links.")
        return
    except Exception as e:
        print(f"An error occurred while reading '{team_creds_csv_path}': {e}")
        return

    if 'team_drive_link' not in team_creds_df.columns:
        team_creds_df['team_drive_link'] = pd.NA

    # --- 3. Iterate through teams, create folders, and update DataFrame ---
    updated_teams_count = 0
    for team_name, member_emails in teams_data.items():
        
        if team_name not in team_creds_df['team_name'].values:
            print(f"Warning: Team '{team_name}' (from '{members_csv_path}') not found in '{team_creds_csv_path}'. "
                  f"Skipping Drive folder creation and link update for this team.")
            continue

        create_team_folder(
            service,
            folder_name=team_name,
            parent_id=get_folder_id_from_path(service, "My Drive|2024/2025|TT|ingeneer|backup")
        )

        folder_id, web_view_link = create_team_folder_and_share(
            service,
            folder_name=team_name, 
            member_emails=member_emails,
            access_role='writer',
            parent_id=get_folder_id_from_path(service, "My Drive|2024/2025|TT|ingeneer|submissions")
        )

        if folder_id and web_view_link:
            team_creds_df.loc[team_creds_df['team_name'] == team_name, 'team_drive_link'] = web_view_link
            print(f"Successfully processed team '{team_name}'. Link added/updated in credentials data.")
            updated_teams_count += 1
        else:
            print(f"Failed to create folder or get link for team '{team_name}'. Link will not be updated in '{team_creds_csv_path}'.")

    if 'team_drive_link' in team_creds_df.columns: 
        try:
            team_creds_df.to_csv(team_creds_csv_path, index=False, encoding='utf-8')
            if updated_teams_count > 0:
                print(f"\nSuccessfully updated '{team_creds_csv_path}' with {updated_teams_count} team drive link(s).")
            else:
                print(f"\n'{team_creds_csv_path}' processed. 'team_drive_link' column ensured. No new links were added in this run based on input.")
        except Exception as e:
            print(f"An error occurred while writing updated data to '{team_creds_csv_path}': {e}")
    else:
        print(f"\nNo changes were applicable to '{team_creds_csv_path}'.")


if __name__ == '__main__':
    print("Attempting to authenticate with Google Drive...")
    service = authenticate_google_drive()

    if service:
        print("Authentication successful. Proceeding with script logic...")

        if not os.path.exists(MEMBERS_INPUT_CSV):
            print(f"'{MEMBERS_INPUT_CSV}' not found. Creating a dummy file for testing.")
            exit(1)
        
        if not os.path.exists(TEAM_CREDENTIALS_CSV):
            print(f"'{TEAM_CREDENTIALS_CSV}' not found. Creating a dummy file for testing.")
            exit(1)

        print(f"\nStarting processing for members in '{MEMBERS_INPUT_CSV}' and credentials in '{TEAM_CREDENTIALS_CSV}'...")
        process_team_members_and_update_creds(service, MEMBERS_INPUT_CSV, TEAM_CREDENTIALS_CSV)
        
    else:
        print("\nGoogle Drive API Service not initialized due to authentication failure.")
        print("Please check the SERVICE_ACCOUNT_FILE path and ensure the service account has Drive API enabled and necessary permissions.")
        print("Script cannot proceed without successful authentication.")

