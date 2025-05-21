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
                    name_to_id_map[challenge_name.strip()] = challenge_id.strip()
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
        "Authorization": f"Bearer {token}", # Standard token authentication for CTFd
        "User-Agent": "CTFd Unsolved Challenge Script" # Adding a User-Agent
    }
    
    response = None # Initialize response to None

    try:
        # Make the GET request with the authorization header
        print(f"DEBUG: Attempting to GET: {challenges_api_url}")
        print(f"DEBUG: Headers: {headers}")
        response = requests.get(challenges_api_url, headers=headers, timeout=15) # Increased timeout slightly
        
        # --- Enhanced Debugging ---
        print(f"DEBUG: Response Status Code: {response.status_code}")
        print(f"DEBUG: Response Headers: {response.headers}")
        # Print first 500 characters of the response text to see what we got
        # Use try-except for response.text in case it's a non-text response or error during access
        try:
            response_text_snippet = response.text[:500] if response.text else "N/A or Empty"
            print(f"DEBUG: Response Text (first 500 chars): {response_text_snippet}")
        except Exception as te:
            print(f"DEBUG: Error accessing response.text: {te}")
        # --- End Enhanced Debugging ---

        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        
        # If raise_for_status() didn't raise an error, we expect JSON
        data = response.json() # This is where the original error likely occurs
        
        if data.get("success"):
            for challenge in data.get("data", []):
                if challenge.get("solves") == 0: 
                    challenge_name = challenge.get("name")
                    if challenge_name:
                        unsolved_challenge_names.append(challenge_name.strip())
            return unsolved_challenge_names
        else:
            print(f"Error: CTFd API request was successful (status 2xx) but API indicated failure. Response: {data}")
            return None
            
    except requests.exceptions.HTTPError as e_http:
        # This catches errors raised by response.raise_for_status() (4xx, 5xx)
        print(f"HTTP Error fetching challenges from CTFd API ({challenges_api_url}): {e_http}")
        if response is not None:
            print(f"HTTP Error - Response status: {response.status_code}")
            # response.text should be available here
            try:
                print(f"HTTP Error - Response text: {response.text}")
            except Exception as te:
                print(f"HTTP Error - Error accessing response.text: {te}")
        return None
    except requests.exceptions.RequestException as e_req:
        # This catches other network errors (DNS failure, connection refused, timeout etc.)
        print(f"Network/Request Error fetching challenges from CTFd API ({challenges_api_url}): {e_req}")
        if response is not None and hasattr(response, 'status_code'): # Check if response object exists and has status_code
             print(f"Network/Request Error - Response status (if available): {response.status_code}")
        return None
    except ValueError as e_json: # Includes JSONDecodeError
        print(f"JSON Decode Error: Could not decode JSON response from CTFd API ({challenges_api_url}). Error: {e_json}")
        if response is not None:
            print(f"JSON Decode Error - Response Status Code that led to this error: {response.status_code}")
            try:
                print(f"JSON Decode Error - Response Text that failed to parse (first 500 chars): {response.text[:500] if response.text else 'N/A or Empty'}")
            except Exception as te:
                 print(f"JSON Decode Error - Error accessing response.text: {te}")
        else:
            print("JSON Decode Error - 'response' object was not available to show text (request might have failed earlier).")
        return None
    except Exception as e_general:
        # Catch any other unexpected errors
        print(f"An unexpected error occurred in get_unsolved_challenges_from_ctfd: {e_general}")
        if response is not None and hasattr(response, 'status_code'):
             print(f"Unexpected Error - Response status (if available): {response.status_code}")
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
        print("Exiting: Failed to fetch or process challenges from CTFd.")
        return

    if not unsolved_ctfd_challenge_names:
        print("No unsolved (and visible) challenges found on the CTFd instance, or no challenges matched after API processing.")
        print(yaml.dump([], default_flow_style=False)) # Output empty YAML list
        return
        
    print(f"Found {len(unsolved_ctfd_challenge_names)} unsolved (and visible) challenges on CTFd: {unsolved_ctfd_challenge_names}")

    unsolved_ids_from_file = []

    for unsolved_name in unsolved_ctfd_challenge_names:
        if unsolved_name in challenge_info_map:
            unsolved_ids_from_file.append(challenge_info_map[unsolved_name])
        else:
            print(f"Warning: Unsolved CTFd challenge '{unsolved_name}' not found in the info file ('{INFO_FILE_PATH}').")

    if not unsolved_ids_from_file:
        print(f"No matching unsolved challenges (from the {len(unsolved_ctfd_challenge_names)} found on CTFd) were present in the info file.")
    else:
        print("\n--- IDs of Unsolved Challenges (matched from info file) ---")
    
    print(yaml.dump(unsolved_ids_from_file, default_flow_style=False))

if __name__ == "__main__":
    main()
