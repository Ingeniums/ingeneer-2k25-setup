#!/usr/bin/python3

import csv
import requests
import yaml
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
CTFD_URL = os.getenv("CTFD_URL")
AUTH_TOKEN = os.getenv("AUTH_TOKEN") # Token for CTFd API authorization
INFO_FILE_PATH = "../challenges.csv" # Path to the challenge information CSV

# --- Validate Configuration ---
if not CTFD_URL:
    print("Error: CTFD_URL environment variable not set or empty.")
    exit(1)
if not AUTH_TOKEN:
    print("Error: AUTH_TOKEN environment variable not set or empty.")
    exit(1)
# --- End Configuration ---

def load_challenge_info(file_path):
    """
    Loads challenge information from the CSV file.
    Returns a dictionary mapping challenge names to their IDs.
    """
    name_to_id_map = {}
    try:
        with open(file_path, mode='r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            # Ensure 'id' and 'name' columns exist
            if reader.fieldnames is None or not ('id' in reader.fieldnames and 'name' in reader.fieldnames):
                print(f"Error: CSV file '{file_path}' must contain 'id' and 'name' columns.")
                return None

            for row in reader:
                challenge_name = row.get('name')
                challenge_id = row.get('id')
                if challenge_name and challenge_id:
                    name_to_id_map[challenge_name.strip()] = int(challenge_id.strip())
                else:
                    print(f"Warning: Skipping row due to missing name or id: {row}")
    except FileNotFoundError:
        print(f"Error: Info file not found at '{file_path}'")
        return None
    except Exception as e:
        print(f"Error reading CSV file '{file_path}': {e}")
        return None
    return name_to_id_map

def get_unsolved_challenges_from_ctfd(ctfd_base_url, token):
    """
    Fetches visible challenges from the CTFd API and filters for those with no solves.
    Requires an authorization token.
    Returns a list of names of unsolved challenges.
    """
    challenges_api_url = f"{ctfd_base_url.rstrip('/')}/api/v1/challenges"
    unsolved_challenge_names = []
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        # Make the GET request with the authorization header
        response = requests.get(challenges_api_url, headers=headers, timeout=10) # 10 second timeout
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        
        data = response.json()
        if data.get("success"):
            for challenge in data.get("data", []):
                # The /api/v1/challenges endpoint (with auth) returns visible challenges.
                # We filter for those with 0 solves.
                # CTFd challenge state 'visible' means it's accessible.
                # 'hidden' means it's not. The API should only return visible ones by default
                # or based on user permissions tied to the token.
                if challenge.get("solves") == 0: # Check if the challenge has no solves
                    challenge_name = challenge.get("name")
                    if challenge_name:
                        unsolved_challenge_names.append(challenge_name.strip())
            return unsolved_challenge_names
        else:
            print(f"Error: CTFd API request was not successful. Response: {data}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"Error fetching challenges from CTFd API ({challenges_api_url}): {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response text: {e.response.text}")
        return None
    except ValueError: # Includes JSONDecodeError
        print(f"Error: Could not decode JSON response from CTFd API ({challenges_api_url}).")
        return None

def main():
    """
    Main function to orchestrate the script.
    """
    print(f"Starting script for CTFd instance: {CTFD_URL}")
    print(f"Using challenge info file: {INFO_FILE_PATH}")

    challenge_info_map = load_challenge_info(INFO_FILE_PATH)
    if not challenge_info_map:
        print("Exiting due to errors loading challenge info.")
        return

    print(f"Successfully loaded {len(challenge_info_map)} challenges from info file.")

    # Pass the AUTH_TOKEN to the function
    unsolved_ctfd_challenge_names = get_unsolved_challenges_from_ctfd(CTFD_URL, AUTH_TOKEN)
    
    if unsolved_ctfd_challenge_names is None:
        print("Exiting due to errors fetching challenges from CTFd or no challenges found.")
        return

    if not unsolved_ctfd_challenge_names:
        print("No unsolved (and visible) challenges found on the CTFd instance or API error during processing.")
        print(yaml.dump([], default_flow_style=False)) # Output empty YAML list
        return
        
    print(f"Found {len(unsolved_ctfd_challenge_names)} unsolved (and visible) challenges on CTFd: {unsolved_ctfd_challenge_names}")

    unsolved_ids_from_file = []
    # found_names_in_file = set() # This set was not used for output, can be removed if not needed for other logic

    for unsolved_name in unsolved_ctfd_challenge_names:
        if unsolved_name in challenge_info_map:
            unsolved_ids_from_file.append(challenge_info_map[unsolved_name])
        else:
            print(f"Warning: Unsolved CTFd challenge '{unsolved_name}' not found in the info file ('{INFO_FILE_PATH}').")

    out = {
        "unsolved": unsolved_ids_from_file
    }
    with open("./out/unsolved.yaml", "w") as unsolved_file:
        unsolved_file.write(yaml.dump(out))

if __name__ == "__main__":
    main()

