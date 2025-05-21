import csv
import os

# Configuration variables
TEAMS_CSV_PATH = "./out/team-creds.csv"
USERS_CSV_PATH = "./out/user-creds.csv"
EMAIL_TEMPLATE_PATH = "template.html"
OUTPUT_BASE_DIR = "./out/emails/"
DISCORD_LINK = "https://discord.gg/xjYmG8Rw"

def load_teams(csv_path):
    """Load teams data from CSV file."""
    teams = {}
    with open(csv_path, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            teams[row['id']] = {
                'team_name': row['team_name'],
                'team_email': row['team_email'],
                'team_password': row['team_password'],
                'team_drive_link': row['team_drive_link'],
                'users': []
            }
    return teams

def load_users(csv_path, teams):
    """Load users data and assign them to teams."""
    with open(csv_path, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            team_id = row['team_id']
            if team_id in teams:
                teams[team_id]['users'].append({
                    'username': row['username'],
                    'email': row['email'],
                    'password': row['password']
                })
    return teams

def read_template(template_path):
    """Read the email template file."""
    with open(template_path, 'r', encoding='utf-8') as file:
        return file.read()

def create_team_folder(team_name, output_base_dir):
    """Create a folder for the team using the specified naming convention."""
    folder_name = team_name.lower().replace(' ', '-')
    folder_path = os.path.join(output_base_dir, folder_name)
    
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    
    return folder_path

def process_template(template, team):
    """Process the template replacing placeholders with team and user data."""
    content = template
    
    # Replace team placeholders
    content = content.replace('{{team}}', team['team_name'])
    content = content.replace('{{drive}}', team['team_drive_link'])
    content = content.replace('{{discord}}', DISCORD_LINK)
    
    # Replace user placeholders
    for i, user in enumerate(team['users'], 1):
        content = content.replace(f'{{{{user{i}}}}}', user['username'])
        content = content.replace(f'{{{{pass{i}}}}}', user['password'])
    
    return content

def generate_output_files(teams, template, output_base_dir):
    """Generate output files for each team."""
    for team_id, team in teams.items():
        # Skip teams with no users
        if not team['users']:
            continue
        
        # Create team folder
        team_folder = create_team_folder(team['team_name'], output_base_dir)
        
        # Process template
        processed_content = process_template(template, team)
        
        # Write HTML file
        html_output_path = os.path.join(team_folder, 'email.html')
        with open(html_output_path, 'w', encoding='utf-8') as file:
            file.write(processed_content)
        
        # Create emails.txt file
        emails_output_path = os.path.join(team_folder, 'emails.txt')
        # Combine team email with user emails
        all_emails = [user['email'] for user in team['users']]
        with open(emails_output_path, 'w', encoding='utf-8') as file:
            file.write(';'.join(all_emails))

def main():
    # Create output directory if it doesn't exist
    if not os.path.exists(OUTPUT_BASE_DIR):
        os.makedirs(OUTPUT_BASE_DIR)
    
    # Load teams data
    teams = load_teams(TEAMS_CSV_PATH)
    
    # Load and assign users to teams
    teams = load_users(USERS_CSV_PATH, teams)
    
    # Read email template
    template = read_template(EMAIL_TEMPLATE_PATH)
    
    # Generate output files
    generate_output_files(teams, template, OUTPUT_BASE_DIR)
    
    print(f"Processing complete. Output files created in '{OUTPUT_BASE_DIR}' directory.")

if __name__ == "__main__":
    main()
