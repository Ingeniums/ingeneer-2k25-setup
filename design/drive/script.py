import os
import sys
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/drive']

def authenticate():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('drive', 'v3', credentials=creds)

def list_folders(service, parent_id):
    query = f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    return results.get('files', [])

def delete_folder(service, folder_id):
    service.files().delete(fileId=folder_id).execute()

def create_folder(service, name, parent_id):
    file_metadata = {
        'name': name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id]
    }
    file = service.files().create(body=file_metadata, fields='id').execute()
    return file.get('id')

def main():
    if len(sys.argv) != 3:
        print("Usage: python create_drive_folders.py <file_path> <parent_folder_id>")
        print("Example: python create_drive_folders.py names.txt root")
        sys.exit(1)

    file_path = sys.argv[1]
    parent_id = sys.argv[2]

    # Read names from file
    try:
        with open(file_path, 'r') as f:
            names = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        sys.exit(1)

    service = authenticate()

    try:
        existing_folders = list_folders(service, parent_id)
    except HttpError as e:
        print(f"Error listing folders: {e}")
        print("Check if the parent folder ID is valid and you have permission.")
        sys.exit(1)

    if existing_folders:
        print(f"There are {len(existing_folders)} existing folders under the parent folder.")
        print("If you choose to remove them, all their contents will also be deleted.")
        choice = input("Do you want to:\n1. Remove all existing folders and create new ones from the file.\n2. Keep the existing folders and create only the new folders from the file that don't already exist.\nEnter 1 or 2: ")
        
        if choice == '1':
            print("You chose to remove all existing folders. This action cannot be undone.")
            confirm = input("Are you sure? (yes/no): ")
            if confirm.lower() == 'yes':
                for folder in existing_folders:
                    try:
                        delete_folder(service, folder['id'])
                        print(f"Deleted folder: {folder['name']}")
                    except HttpError as e:
                        print(f"Error deleting folder {folder['name']}: {e}")
                # Create all folders from the file
                for name in names:
                    try:
                        create_folder(service, name, parent_id)
                        print(f"Created folder: {name}")
                    except HttpError as e:
                        print(f"Error creating folder {name}: {e}")
            else:
                print("Deletion cancelled.")
                sys.exit(0)
        elif choice == '2':
            existing_names = set(folder['name'] for folder in existing_folders)
            for name in names:
                if name not in existing_names:
                    try:
                        create_folder(service, name, parent_id)
                        print(f"Created folder: {name}")
                    except HttpError as e:
                        print(f"Error creating folder {name}: {e}")
                else:
                    print(f"Folder '{name}' already exists, skipping.")
        else:
            print("Invalid choice.")
            sys.exit(1)
    else:
        # No existing folders, create all from the file
        for name in names:
            try:
                create_folder(service, name, parent_id)
                print(f"Created folder: {name}")
            except HttpError as e:
                print(f"Error creating folder {name}: {e}")

if __name__ == '__main__':
    main()
