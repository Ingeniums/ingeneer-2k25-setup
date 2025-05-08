import csv
import requests
import random
import string

CTFD_URL = "http://localhost:8000/api/v1"
ADMIN_KEY = "ctfd_62b2c76657fd24b84807e9767ae70cd7f6fc133fb30880a19dfeebdc2342b476"
CSV_FILE = "users.csv"
USERS_FILE = "users.json"
TEAMS_FILE = "teams.json"
USER_CREDS_FILE = "user-creds.csv"
TEAM_CREDS_FILE = "team-creds.csv"

def generate_password(length=12):
    characters = string.ascii_letters + string.digits + string.punctuation
    return ''.join(random.choice(characters) for _ in range(length))

def create_user(username, email, password, hidden=True):
    endpoint = f"{CTFD_URL}/users"
    headers = {"Authorization": f"Bearer {ADMIN_KEY}"}
    data = {"name": username, "email": email, "password": password, "hidden": int(hidden)}
    try:
        response = requests.post(endpoint, headers=headers, json=data)
        response.raise_for_status()
        return response.json()["data"]["id"]
    except requests.exceptions.RequestException as e:
        print(f"Error creating user {username}: {e}")
        return None

def get_user(user_id):
    endpoint = f"{CTFD_URL}/users/{user_id}"
    headers = {"Authorization": f"Bearer {ADMIN_KEY}"}
    try:
        response = requests.get(endpoint, headers=headers)
        response.raise_for_status()
        return response.json()["data"]
    except requests.exceptions.RequestException as e:
        print(f"Error getting user {user_id}: {e}")
        return None

def create_team(team_name, email, password, hidden=False):
    endpoint = f"{CTFD_URL}/teams"
    headers = {"Authorization": f"Bearer {ADMIN_KEY}"}
    data = {"name": team_name, "email": email, "password": password, "hidden": int(hidden)}
    try:
        response = requests.post(endpoint, headers=headers, json=data)
        print(response.json())
        response.raise_for_status()
        return response.json()["data"]["id"]
    except requests.exceptions.RequestException as e:
        print(f"Error creating team {team_name}: {e}")
        return None

def get_team(team_id):
    endpoint = f"{CTFD_URL}/teams/{team_id}"
    headers = {"Authorization": f"Bearer {ADMIN_KEY}"}
    try:
        response = requests.get(endpoint, headers=headers)
        response.raise_for_status()
        return response.json()["data"]
    except requests.exceptions.RequestException as e:
        print(f"Error getting team {team_id}: {e}")
        return None

def add_user_to_team(user_id, team_id):
    endpoint = f"{CTFD_URL}/teams/{team_id}/members"
    headers = {"Authorization": f"Bearer {ADMIN_KEY}"}
    data = {"user_id": user_id}
    try:
        response = requests.post(endpoint, headers=headers, json=data)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error adding user {user_id} to team {team_id}: {e}")
        return False

def set_team_captain(team_id, user_id):
    endpoint = f"{CTFD_URL}/teams/{team_id}"
    headers = {"Authorization": f"Bearer {ADMIN_KEY}"}
    data = {"captain_id": user_id}
    try:
        response = requests.patch(endpoint, headers=headers, json=data)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error setting captain for team {team_id} to user {user_id}: {e}")
        return False

def process_csv(csv_file):
    team_user_map = {}
    user_credentials = []
    team_credentials = []

    try:
        with open(csv_file, "r") as file:
            reader = csv.DictReader(file)
            if not reader.fieldnames or not all(field in reader.fieldnames for field in ["username", "email", "team"]):
                raise ValueError("CSV file must contain 'username', 'email', and 'team' columns.")

            for row in reader:
                username = row["username"]
                email = row["email"]
                team = row["team"]

                if team not in team_user_map:
                    team_user_map[team] = []
                team_user_map[team].append({"username": username, "email": email})

        for team_name, users in team_user_map.items():
            team_password = generate_password()
            team_email = users[0]["email"]
            team_id = create_team(team_name, team_email, team_password)
            if team_id:
                team_credentials.append({
                    "team_name": team_name,
                    "team_email": team_email,
                    "team_password": team_password,
                })
                first_user_id = None
                for user_data in users:
                    username = user_data["username"]
                    email = user_data["email"]
                    user_password = generate_password()
                    user_id = create_user(username, email, user_password)
                    if user_id:
                        user_credentials.append({
                            "username": username,
                            "email": email,
                            "user_password": user_password,
                        })
                        if first_user_id is None:
                            first_user_id = user_id
                        add_user_to_team(user_id, team_id)
                if first_user_id:
                    set_team_captain(team_id, first_user_id)

        with open(USER_CREDS_FILE, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["username", "email", "password"])
            for user in user_credentials:
                writer.writerow([user["username"], user["email"], user["user_password"]])

        with open(TEAM_CREDS_FILE, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["team_name", "team_email", "team_password"])
            for team in team_credentials:
                writer.writerow([team["team_name"], team["team_email"], team["team_password"]])

    except FileNotFoundError:
        print(f"Error: CSV file '{csv_file}' not found.")
    except ValueError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    process_csv(CSV_FILE)
