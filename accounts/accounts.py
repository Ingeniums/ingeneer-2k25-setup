import csv
import json
import zipfile
import secrets
from passlib.hash import bcrypt
from collections import defaultdict

def generate_ctfd_import(users_csv, output_zip, plaintext_password=None, rounds=12):
    """
    Generate a CTFd-compatible ZIP file with users and teams JSON.
    
    Args:
        users_csv (str): Path to input CSV file (username,email,team).
        output_zip (str): Path to output ZIP file.
        plaintext_password (str): Plaintext password to hash for all users (optional).
        rounds (int): Bcrypt rounds (default: 12).
    """
    # Initialize data structures
    users = []
    teams = []
    team_names = set()
    user_id_counter = 1
    team_id_counter = 1
    team_id_map = {}
    user_team_map = defaultdict(list)

    # Read CSV file
    with open(users_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, fieldnames=['username', 'email', 'team'])
        next(reader)  # Skip header
        for row in reader:
            username = row['username'].strip()
            email = row['email'].strip()
            team_name = row['team'].strip() if row['team'] else f"Team{user_id_counter}"
            team_names.add(team_name)
            user_team_map[team_name].append(user_id_counter)
            
            # Generate password (use provided or random)
            password = plaintext_password or secrets.token_urlsafe(12)
            hashed_password = bcrypt.using(rounds=rounds).hash(password)
            
            # Create user entry
            users.append({
                'id': user_id_counter,
                'name': username,
                'email': email,
                'password': hashed_password,
                'type': 'user',
                'verified': True,
                'hidden': False,
                'banned': False,
                'team_id': None  # Will be updated after teams are created
            })
            user_id_counter += 1

    # Create teams
    for team_name in team_names:
        team_id_map[team_name] = team_id_counter
        teams.append({
            'id': team_id_counter,
            'name': team_name,
            'email': f"{team_name.lower().replace(' ', '_')}@ctfd.io",
            'password': bcrypt.using(rounds=rounds).hash(secrets.token_urlsafe(12)),
            'members': user_team_map[team_name]
        })
        team_id_counter += 1

    # Assign team IDs to users
    for user in users:
        for team_name, user_ids in user_team_map.items():
            if user['id'] in user_ids:
                user['team_id'] = team_id_map[team_name]

    # Create JSON files
    export_data = {
        'users': {'count': len(users), 'data': users},
        'teams': {'count': len(teams), 'data': teams}
    }

    # Write to ZIP file
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Write users.json
        zf.writestr('db/users.json', json.dumps(export_data['users'], indent=2))
        # Write teams.json
        zf.writestr('db/teams.json', json.dumps(export_data['teams'], indent=2))

    print(f"Generated {output_zip} with {len(users)} users and {len(teams)} teams.")
    if plaintext_password:
        print(f"All users have the password: {plaintext_password}")
    else:
        print("Random passwords generated for each user.")

# Example usage
if __name__ == '__main__':
    # Input CSV file
    users_csv = 'users.csv'
    
    # Output ZIP file
    output_zip = 'setup.zip'
    
    # Plaintext password (set to None for random passwords)
    plaintext_password = 'CTF2025Password'
    
    # Generate the import file
    generate_ctfd_import(users_csv, output_zip, plaintext_password)
