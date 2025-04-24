#!/usr/bin/env python3
"""
Script to read hierarchical paths from a file and create Google Drive folders.
For each path (in format parent1/parent2/.../final), it creates a nested folder structure.
Before creation, it checks for existing folders in the base parent folder and prompts for action.
"""

import os
import argparse
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pickle

# If modifying these scopes, delete the file token.pickle
SCOPES = ['https://www.googleapis.com/auth/drive']

def get_drive_service():
    """Get an authorized Google Drive API service instance."""
    creds = None
    
    # The file token.pickle stores the user's access and refresh tokens
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # If no valid credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'submissions-setup-secret.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return build('drive', 'v3', credentials=creds)

def find_folder_id(service, folder_name, parent_id=None):
    """Find a folder by name and return its ID."""
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    
    if parent_id:
        query += f" and '{parent_id}' in parents"
    
    response = service.files().list(
        q=query,
        spaces='drive',
        fields='files(id, name)'
    ).execute()
    
    files = response.get('files', [])
    return files[0]['id'] if files else None

def list_folders_in_parent(service, parent_id):
    """List all folders in the specified parent folder."""
    query = f"mimeType='application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed=false"
    
    response = service.files().list(
        q=query,
        spaces='drive',
        fields='files(id, name)'
    ).execute()
    
    return response.get('files', [])

def delete_folders(service, folder_list):
    """Delete multiple folders."""
    for folder in folder_list:
        try:
            service.files().delete(fileId=folder['id']).execute()
            print(f"Deleted folder: {folder['name']}")
        except HttpError as error:
            print(f"An error occurred deleting {folder['name']}: {error}")

def create_folder(service, folder_name, parent_id):
    """Create a folder with the specified name in the parent folder."""
    file_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id]
    }
    
    file = service.files().create(
        body=file_metadata,
        fields='id'
    ).execute()
    
    return file.get('id')

def create_folder_path(service, path, parent_id):
    """Create a folder path with the specified hierarchy under the parent folder."""
    # Split the path into components
    path_parts = path.split('/')
    current_parent_id = parent_id
    created_path = []
    
    for i, part in enumerate(path_parts):
        if not part:  # Skip empty parts
            continue
            
        # Check if this folder already exists at this level
        folder_id = find_folder_id(service, part, current_parent_id)
        
        if folder_id:
            print(f"Found existing folder: {'/'.join(created_path + [part])}")
        else:
            # Create the folder
            folder_id = create_folder(service, part, current_parent_id)
            print(f"Created folder: {'/'.join(created_path + [part])}")
        
        # Update parent ID for next iteration
        current_parent_id = folder_id
        created_path.append(part)
    
    return current_parent_id

def main():
    parser = argparse.ArgumentParser(description='Create nested folder hierarchies in Google Drive from a list of paths.')
    parser.add_argument('file', help='File containing folder paths (one per line, format: parent1/parent2/.../final)')
    # parser.add_argument('parent_path', help='Base parent folder path (e.g., /me)')
    args = parser.parse_args()
    
    try:
        service = get_drive_service()
        
        # Find or create parent folder path
        parent_id = 'root'  # Start at the root of My Drive
        
        # Handle the parent path (e.g., /me, /me/subfolder)
        holder = "2024/2025|TT|ingeneer|submissions"
        path_parts = holder.strip('/').split('|')
        for part in path_parts:
            if part:
                folder_id = find_folder_id(service, part, parent_id)
                if not folder_id:
                    print(f"Creating parent folder: {part}")
                    folder_id = create_folder(service, part, parent_id)
                parent_id = folder_id
        
        # List existing folders in parent directory
        existing_folders = list_folders_in_parent(service, parent_id)
        
        if existing_folders:
            print(f"Found {len(existing_folders)} existing folders in the target location:")
            for folder in existing_folders:
                print(f"  - {folder['name']}")
            
            choice = input("Do you want to remove these folders before creating new ones? (yes/no): ").lower()
            if choice in ['yes', 'y']:
                delete_folders(service, existing_folders)
            else:
                print("Keeping existing folders.")
        
        # Read paths from file and create folder hierarchies
        with open(args.file, 'r') as f:
            paths = [line.strip() for line in f if line.strip()]
        
        print(f"Creating {len(paths)} folder hierarchies...")
        for path in paths:
            final_id = create_folder_path(service, path, parent_id)
            print(f"Completed folder hierarchy for: {path}")
        
        print("Process completed successfully.")
        
    except HttpError as error:
        print(f"An HTTP error occurred: {error}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    main()
