#!/usr/bin/python3
from pathlib import Path
import csv
import yaml
import sys


CHALLENGES_CSV = "../challenges.csv"
ROOT = "../ready/"

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

def update_challenge_yml(challenge_path, root_dir, set_visible=True):
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
        
        return True # Indicates yml read was successful, state update attempted/done.
    except Exception as e:
        print(f"Error processing {full_path}: {e}")
        return False

def main():
    all_challenges_data = load_csv_challenges(CHALLENGES_CSV)
    print("\nSetting all challenges to visible initially...")
    hidden_count = 0
    for chal_data in all_challenges_data.values():
        if update_challenge_yml(chal_data['path'], ROOT, set_visible=True):
            hidden_count +=1
    print(f"{hidden_count} challenge(s) initially set to visible.")

if __name__ == "__main__":
    main()
