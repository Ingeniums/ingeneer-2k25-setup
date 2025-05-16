#!/usr/bin/env python3
import csv
import os
import subprocess
import sys
import yaml
from pathlib import Path

# --- Google Drive Imports ---
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
# from googleapiclient.http import MediaFileUpload # Kept if future use

# --- Configuration ---
CHALLENGES_CSV = "../challenges.csv"
CONFIG = "../../config.yaml"
ROOT = "../ready/"

# --- Google Drive Configuration ---
DRIVE_BASE_PATH_ON_DRIVE = "2024/2025|TT|ingeneer" # Example: "MyCTFEvent|Data"
SCOPES = ['https://www.googleapis.com/auth/drive']
CREDENTIALS_FILE = '../../secret.json'
TOKEN_FILE = 'token.json'

# --- Google Drive Helper Functions ---
def authenticate_google_drive():
    """Authenticates with Google Drive API."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as token_file:
            token_file.write(creds.to_json())

    try:
        service = build('drive', 'v3', credentials=creds)
        print("Google Drive authenticated.")
        return service
    except Exception as e:
        print(f'Google Drive authentication error: {e}')
        return None

def get_folder_id(service, parent_id, folder_name):
    query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
    if parent_id: # If parent_id is None, it implies searching in root or a shared drive context
        query += f" and '{parent_id}' in parents"

    try:
        response = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        for folder in response.get('files', []):
            return folder.get('id')
    except HttpError as error:
        print(f"Error searching for folder '{folder_name}': {error}")
    return None

def create_folder_if_not_exists(service, parent_id, folder_name):
    folder_id = get_folder_id(service, parent_id, folder_name)
    if not folder_id: # Folder doesn't exist, create it
        file_metadata = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}
        if parent_id: # If no parent_id, it will be created in the root of "My Drive"
            file_metadata['parents'] = [parent_id]
        try:
            folder = service.files().create(body=file_metadata, fields='id').execute()
            folder_id = folder.get('id')
            print(f"Created Drive folder '{folder_name}' (ID: {folder_id}) under parent {parent_id or 'root'}.")
        except HttpError as error:
            print(f"Error creating Drive folder '{folder_name}': {error}")
            return None
    return folder_id

def get_or_create_folder_id_by_path(service, path_string, root_folder_id='root'):
    parts = [part for part in path_string.split('|') if part]
    current_parent_id = root_folder_id

    if not parts: # Path string was empty or just separators
        print(f"Warning: Path string '{path_string}' is empty or invalid for get_or_create_folder_id_by_path.")
        return None # Or root_folder_id if that's desired for an empty path

    for part in parts:
        folder_id = get_folder_id(service, current_parent_id, part)
        if not folder_id:
            folder_id = create_folder_if_not_exists(service, current_parent_id, part)
            if not folder_id: # Failed to create this part of the path
                print(f"FATAL: Could not get or create Drive folder part: '{part}' in path '{path_string}'.")
                return None # Critical failure
        current_parent_id = folder_id
    return current_parent_id


def list_items_in_folder(service, folder_id, item_type='all'):
    items = []
    page_token = None
    query = f"'{folder_id}' in parents and trashed=false"
    if item_type == 'files':
        query += " and mimeType != 'application/vnd.google-apps.folder'"
    elif item_type == 'folders':
        query += " and mimeType = 'application/vnd.google-apps.folder'"

    try:
        while True:
            response = service.files().list(q=query,
                                            spaces='drive',
                                            fields='nextPageToken, files(id, name, mimeType, parents)',
                                            pageToken=page_token).execute()
            items.extend(response.get('files', []))
            page_token = response.get('nextPageToken', None)
            if page_token is None:
                break
    except HttpError as error:
        print(f'Error listing Drive items in folder {folder_id}: {error}')
    return items

def move_drive_item(service, item_id, new_parent_id):
    try:
        file_obj = service.files().get(fileId=item_id, fields='parents').execute()
        previous_parents = ",".join(file_obj.get('parents'))
        service.files().update(
            fileId=item_id,
            addParents=new_parent_id,
            removeParents=previous_parents,
            fields='id, parents'
        ).execute()
        return True
    except HttpError as error:
        print(f"Error moving Drive item {item_id} to {new_parent_id}: {error}")
        return False

def backup_team_submissions_on_drive(service, base_drive_path_str):
    print(f"\nStarting Google Drive Backup for '{base_drive_path_str}'...")
    base_folder_id = get_or_create_folder_id_by_path(service, base_drive_path_str)
    if not base_folder_id:
        print(f"Error: Base Drive folder '{base_drive_path_str}' not found/created. Backup aborted.")
        return

    submissions_folder_name = "submissions"
    submissions_folder_id = create_folder_if_not_exists(service, base_folder_id, submissions_folder_name)
    if not submissions_folder_id:
        print(f"Error: '{submissions_folder_name}' folder not found/created in '{base_drive_path_str}'. Backup aborted.")
        return # Changed from exit(1) to allow script to continue if desired

    backup_folder_name = "backup"
    backup_main_folder_id = create_folder_if_not_exists(service, base_folder_id, backup_folder_name)
    if not backup_main_folder_id:
        print(f"Error: '{backup_folder_name}' folder not found/created in '{base_drive_path_str}'. Backup aborted.")
        return # Changed from exit(1)

    team_submission_folders = list_items_in_folder(service, submissions_folder_id, item_type='folders')
    if not team_submission_folders:
        print(f"No team submission folders found in '{base_drive_path_str}|{submissions_folder_name}'.")
        return

    print(f"Found {len(team_submission_folders)} team folder(s) in submissions for backup.")
    for team_folder in team_submission_folders:
        team_name = team_folder['name']
        # team_submission_folder_id = team_folder['id'] # This is the ID of the folder named team_name
        print(f"Processing team: {team_name}")

        team_backup_folder_id = create_folder_if_not_exists(service, backup_main_folder_id, team_name)
        if not team_backup_folder_id:
            print(f"Error creating backup folder for team '{team_name}'. Skipping.")
            continue

        items_to_move = list_items_in_folder(service, team_folder['id'], item_type='all') # Use team_folder['id'] directly
        if not items_to_move:
            print(f"No items to move for team '{team_name}'.")
            continue

        moved_count = 0
        for item in items_to_move:
            # Corrected Call: Pass the target backup folder ID for this team
            if move_drive_item(service, item['id'], team_backup_folder_id):
                moved_count += 1
        print(f"  Moved {moved_count}/{len(items_to_move)} items for team '{team_name}'.")

    print("Google Drive Backup Process Completed.")

# --- Original CTF Script Functions ---
def load_yaml_phases(yaml_path):
    try:
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
            return data.get('phases', {})
    except Exception as e:
        print(f"Error loading YAML {yaml_path}: {e}")
        sys.exit(1)

def load_csv_challenges(csv_path):
    challenges = {}
    try:
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                challenges[int(row['id'])] = row
        return challenges
    except Exception as e:
        print(f"Error loading CSV {csv_path}: {e}")
        sys.exit(1)

def update_challenge_yml(challenge_path, root_dir, set_visible=True, drive_service=None, challenge_uploads_parent_folder_id=None):
    full_path = Path(root_dir) / challenge_path / "challenge.yml"
    if not full_path.exists():
        print(f"Challenge file not found: {full_path}")
        return False
    try:
        with open(full_path, 'r') as f:
            challenge_data = yaml.safe_load(f)
        
        current_state = challenge_data.get('state')
        desired_state = 'visible' if set_visible else 'hidden'
        
        if current_state != desired_state:
            challenge_data['state'] = desired_state
            with open(full_path, 'w') as f:
                yaml.dump(challenge_data, f, default_flow_style=False, sort_keys=False)
            print(f"Challenge {challenge_path}: state set to {desired_state}.")
        
        if set_visible and drive_service and challenge_uploads_parent_folder_id:
            if challenge_data.get('submit') == 'drive':
                challenge_name_for_folder = challenge_data.get('name')
                if challenge_name_for_folder:
                    print(f"  Challenge '{challenge_name_for_folder}' uses Drive submission. Ensuring folder exists...")
                    team_folders = list_items_in_folder(
                        drive_service,
                        challenge_uploads_parent_folder_id
                    )
                    for team_folder in team_folders:
                        created_id = create_folder_if_not_exists(drive_service, team_folder["id"], challenge_name_for_folder)
                        if not created_id:
                            print(f"  FAILED to create/verify Drive folder for '{challenge_name_for_folder}'.")
                else:
                    print(f"  Warning: Challenge {challenge_path} has 'submit: drive' but no 'name' field in challenge.yml. Cannot create Drive folder.")
        
        return True # Indicates yml read was successful, state update attempted/done.
    except Exception as e:
        print(f"Error processing {full_path}: {e}")
        return False

def check_and_start_containers(challenge_path, root_dir):
    challenge_dir = Path(root_dir) / challenge_path
    compose_file = challenge_dir / "compose.yml"
    if not compose_file.exists():
        compose_file = challenge_dir / "docker-compose.yml"

    if compose_file.exists():
        try:
            result = subprocess.run(
                ["docker-compose", "up", "-d"],
                cwd=str(challenge_dir),
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode == 0:
                print(f"Containers for {challenge_path}: started.")
            else:
                print(f"Failed to start containers for {challenge_path}.")
                if result.stderr.strip(): print(f"  Error: {result.stderr.strip()}")
        except FileNotFoundError:
             print("Error: docker-compose command not found. Is it installed?")
        except Exception as e:
            print(f"Error starting containers for {challenge_path}: {e}")

def process_phase(phase_name, challenge_ids, challenges, root_dir, processed_for_visibility, drive_service=None, challenge_uploads_parent_folder_id=None):
    print(f"\nProcessing phase: {phase_name}")
    for challenge_id in challenge_ids:
        if challenge_id not in challenges:
            print(f"Challenge ID {challenge_id} (phase {phase_name}) not in CSV.")
            continue

        challenge = challenges[challenge_id]
        challenge_full_path = challenge['path']

        if update_challenge_yml(challenge_full_path, root_dir, set_visible=True, drive_service=drive_service, challenge_uploads_parent_folder_id=challenge_uploads_parent_folder_id):
            check_and_start_containers(challenge_full_path, root_dir)
        processed_for_visibility.add(int(challenge_id))

def hide_other_challenges(all_challenges_data, visible_challenge_ids, root_dir):
    print("\nHiding challenges not in current phase(s)...")
    hidden_count = 0
    for chal_id, challenge_data in all_challenges_data.items():
        if chal_id not in visible_challenge_ids:
            # For hiding, we don't need to pass drive_service or parent_folder_id
            if update_challenge_yml(challenge_data['path'], root_dir, set_visible=False):
                hidden_count +=1
    if hidden_count > 0:
        print(f"{hidden_count} challenge(s) set to hidden.")

def select_phase(phases):
    print("\nAvailable phases:")
    phase_names = list(phases.keys())
    if not phase_names:
        print("No phases defined in config.")
        return None

    for i, phase_name in enumerate(phase_names, 1):
        challenge_count = len(phases[phase_name])
        print(f"{i}. {phase_name} ({challenge_count} challenges)")

    while True:
        try:
            choice = input(f"\nSelect phase (1-{len(phase_names)}), or 'a' for all: ")
            if choice.lower() == 'a':
                return "ALL_PHASES_SELECTED"
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(phase_names):
                return phase_names[choice_idx]
            else:
                print("Invalid selection.")
        except ValueError:
            print(f"Enter a number (1-{len(phase_names)}) or 'a'.")

def main():
    drive_service = None
    challenge_uploads_parent_folder_id = None # For challenge-specific submission folders

    phases_config = load_yaml_phases(CONFIG)
    all_challenges_data = load_csv_challenges(CHALLENGES_CSV)

    if not phases_config or not all_challenges_data:
        print("Missing phases in config or challenges in CSV. Exiting.")
        return

    if input("Hide all challenges before phase selection? (for clean state) [y/n]: ").lower() == 'y':
        print("\nSetting all challenges to hidden initially...")
        hidden_count = 0
        for chal_data in all_challenges_data.values():
            if update_challenge_yml(chal_data['path'], ROOT, set_visible=False): # No Drive args needed for hiding
                hidden_count +=1
        print(f"{hidden_count} challenge(s) initially set to hidden.")

    if input("Continue to phase selection and activation? [y/n]: ").lower() == 'n':
        print("Exiting.")
        exit()

    if not Path(CREDENTIALS_FILE).exists():
        print(f"Error: {CREDENTIALS_FILE} not found. Download from Google Cloud Console.")
        exit(1)
    else:
        drive_service = authenticate_google_drive()
        if drive_service:
            # Setup folder for direct challenge submissions
            base_drive_folder_id = get_or_create_folder_id_by_path(drive_service, DRIVE_BASE_PATH_ON_DRIVE)
            if base_drive_folder_id:
                challenge_uploads_parent_folder_id = create_folder_if_not_exists(drive_service, base_drive_folder_id, f"submissions")
                if not challenge_uploads_parent_folder_id:
                    print(f"Could not create/verify '{DRIVE_BASE_PATH_ON_DRIVE}|submissions'. Challenge-specific Drive folders will not be created.")
                    exit(1)
            else:
                print("Google Drive operations skipped (authentication failed).")

    if input("Perform Google Drive backup and setup? [y/n]: ").lower() == 'y':
        if not Path(CREDENTIALS_FILE).exists():
            print(f"Error: {CREDENTIALS_FILE} not found. Download from Google Cloud Console.")
        else:
            backup_team_submissions_on_drive(drive_service, DRIVE_BASE_PATH_ON_DRIVE)
    else:
        print("Google Drive operations skipped.")

    selected_phase_key = select_phase(phases_config)
    processed_ids_for_visibility = set()

    if selected_phase_key == "ALL_PHASES_SELECTED":
        print("\n--- Processing ALL Phases ---")
        for phase_name, challenge_ids_in_phase in phases_config.items():
            process_phase(phase_name, challenge_ids_in_phase, all_challenges_data, ROOT, processed_ids_for_visibility, drive_service, challenge_uploads_parent_folder_id)
    elif selected_phase_key:
        if selected_phase_key in phases_config:
            selected_phase_ids = phases_config[selected_phase_key]
            process_phase(selected_phase_key, selected_phase_ids, all_challenges_data, ROOT, processed_ids_for_visibility, drive_service, challenge_uploads_parent_folder_id)
        else:
            print(f"Error: Phase '{selected_phase_key}' not in YAML.")
    else:
        print("No phase selected for visibility.")

    if processed_ids_for_visibility:
         hide_other_challenges(all_challenges_data, processed_ids_for_visibility, ROOT)

    print("\nScript finished.")

if __name__ == "__main__":
    main()
