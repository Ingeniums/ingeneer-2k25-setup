import csv
import requests
import random
import string
from dotenv import load_dotenv
import os

load_dotenv()

CTFD_URL = "https://private.ingeneer.ingeniums.club/api/v1"
ADMIN_KEY = os.getenv("ADMIN_KEY")
CSV_FILE = "users.csv"
USERS_FILE = "users.json"
TEAMS_FILE = "teams.json"
USER_CREDS_FILE = "./out/user-creds.csv"
TEAM_CREDS_FILE = "./out/team-creds.csv"
USERNAME_FIELD = "Username"
EMAIL_FIELD = "Email Address"
TEAM_FIELD = "Team name (exactly 4 members)"

def generate_password(length=20):
    characters = string.ascii_letters + string.digits + string.punctuation
    return ''.join(random.choice(characters) for _ in range(length))

def create_user(username, email, password, hidden=False):
    endpoint = f"{CTFD_URL}/users"
    headers = {"Authorization": f"Bearer {ADMIN_KEY}"}
    data = {"name": username, "email": email, "password": password, "hidden": int(hidden)}
    response = None
    try:
        response = requests.post(endpoint, headers=headers, json=data)
        response.raise_for_status()
        print(f"    Created User {username}")
        return response.json()["data"]["id"]
    except requests.exceptions.RequestException:
        if response is not None:
            print(response.json())
        return None

def get_user(user_id):
    endpoint = f"{CTFD_URL}/users/{user_id}"
    headers = {"Authorization": f"Bearer {ADMIN_KEY}"}
    try:
        response = requests.get(endpoint, headers=headers)
        response.raise_for_status()
        return response.json()["data"]
    except requests.exceptions.RequestException:
        return None

def create_team(team_name, email, password, hidden=False):
    endpoint = f"{CTFD_URL}/teams"
    headers = {"Authorization": f"Bearer {ADMIN_KEY}"}
    data = {"name": team_name, "email": email, "password": password, "hidden": int(hidden)}
    response = None
    try:
        response = requests.post(endpoint, headers=headers, json=data)
        response.raise_for_status()
        print(f"Created Team {team_name}")
        return response.json()["data"]["id"]
    except requests.exceptions.RequestException:
        print(response)
        if response is not None:
            print(response.json())
        return None

def get_team(team_id):
    endpoint = f"{CTFD_URL}/teams/{team_id}"
    headers = {"Authorization": f"Bearer {ADMIN_KEY}"}
    try:
        response = requests.get(endpoint, headers=headers)
        response.raise_for_status()
        return response.json()["data"]
    except requests.exceptions.RequestException:
        return None

def add_user_to_team(user_id, team_id):
    endpoint = f"{CTFD_URL}/teams/{team_id}/members"
    headers = {"Authorization": f"Bearer {ADMIN_KEY}"}
    data = {"user_id": user_id}
    try:
        response = requests.post(endpoint, headers=headers, json=data)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException:
        return False

def set_team_captain(team_id, user_id):
    endpoint = f"{CTFD_URL}/teams/{team_id}"
    headers = {"Authorization": f"Bearer {ADMIN_KEY}"}
    data = {"captain_id": user_id}
    try:
        response = requests.patch(endpoint, headers=headers, json=data)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException:
        return False

def validate(teams: dict[str, list[dict]]):
    correct = True
    for team, users in teams.items():
        if len(users) != 4:
            print(f"Team {team} has less than required number {len(users)}")
            correct = False
            for user in users:
                print(f"  User: {user}")

    return correct

def process_csv(csv_file):
    team_user_map = {}
    user_credentials = []
    team_credentials = []

    try:
        with open(csv_file, "r") as file:
            reader = csv.DictReader(file)
            if not reader.fieldnames or not all(field in reader.fieldnames for field in [USERNAME_FIELD, EMAIL_FIELD, TEAM_FIELD]):
                raise ValueError(f"CSV file must contain '{USERNAME_FIELD}', '{EMAIL_FIELD}', and '{TEAM_FIELD}' columns.")

            for row in reader:
                username = row[USERNAME_FIELD].strip()
                email = row[EMAIL_FIELD].strip()
                team = row[TEAM_FIELD].strip()

                if team not in team_user_map:
                    team_user_map[team] = []
                team_user_map[team].append({"username": username, "email": email})

        if not validate(team_user_map):
            print("Improper input...")
            exit()

        for team_name, users in team_user_map.items():
            team_password = generate_password()
            team_email = users[0]["email"]
            team_id = create_team(team_name, team_email, team_password)
            if team_id:
                team_credentials.append({
                    "id": team_id,
                    "team_name": team_name,
                    "team_email": team_email,
                    "team_password": team_password,
                })
            first_user_id = None
            first_user_name = None
            for user_data in users:
                username = user_data["username"]
                email = user_data["email"]
                user_password = generate_password()
                user_id = create_user(username, email, user_password)
                if user_id:
                    user_credentials.append({
                        "id": user_id,
                        "username": username,
                        "team_id": team_id,
                        "email": email,
                        "user_password": user_password,
                    })
                    if first_user_id is None:
                        first_user_id = user_id
                        first_user_name = username
                    
                    if team_id and add_user_to_team(user_id, team_id):
                        print(f"    Added {username} to {team_name}")
            if team_id and first_user_id:
                if set_team_captain(team_id, first_user_id):
                    print(f"    Set {first_user_name} as Captain in {team_name}")
        with open(TEAM_CREDS_FILE, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["id", "team_name", "team_email", "team_password"])
            for team in team_credentials:
                writer.writerow([team["id"], team["team_name"], team["team_email"], team["team_password"]])

        with open(USER_CREDS_FILE, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["id", "username", "team_id", "email", "password"])
            for user in user_credentials:
                writer.writerow([user["id"], user["username"], user["team_id"], user["email"], user["user_password"]])


    except FileNotFoundError:
        print(f"Error: CSV file '{csv_file}' not found.")
    except ValueError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    process_csv(CSV_FILE)
