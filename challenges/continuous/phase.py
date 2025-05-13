#!/usr/bin/env python3
import csv
import os
from os.path import exists
import subprocess
import sys
import yaml

CHALLENGES_CSV="../challenges.csv"
CONFIG="../../config.yaml"
ROOT="../ready/"

def load_yaml_phases(yaml_path):
    try:
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
            return data.get('phases', {})
    except Exception as e:
        print(f"Error loading YAML file: {e}")
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
        print(f"Error loading CSV file: {e}")
        sys.exit(1)

def update_challenge_yml(challenge_path, root_dir, set_visible=True):
    full_path = os.path.join(root_dir, challenge_path, "challenge.yml")
    
    if not os.path.exists(full_path):
        print(f"Challenge file not found: {full_path}")
        return False
    
    try:
        with open(full_path, 'r') as f:
            challenge_data = yaml.safe_load(f)
        
        state = 'visible' if set_visible else 'hidden'
        challenge_data['state'] = state
        
        with open(full_path, 'w') as f:
            yaml.dump(challenge_data, f, default_flow_style=False)
        
        print(f"Updated challenge state to {state}: {full_path}")
        return True
    except Exception as e:
        print(f"Error updating challenge file {full_path}: {e}")
        return False

def check_and_start_containers(challenge_path, root_dir):
    challenge_dir = os.path.join(root_dir, challenge_path)
    compose_file = os.path.join(challenge_dir, "compose.yml")
    
    if os.path.exists(compose_file):
        print(f"Found docker-compose.yml in {challenge_dir}")
        try:
            print(f"Starting containers for {challenge_path}...")
            result = subprocess.run(
                ["docker-compose", "up", "-d"], 
                cwd=challenge_dir,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print(f"Started containers for {challenge_path}")
                print(f"Output: {result.stdout.strip()}")
            else:
                print(f"Failed to start containers for {challenge_path}")
                print(f"Error: {result.stderr.strip()}")
        except Exception as e:
            print(f"Error starting containers: {e}")

def process_phase(phase_name, challenge_ids, challenges, root_dir):
    print(f"\nProcessing {phase_name} (IDs: {challenge_ids})")
    
    for challenge_id in challenge_ids:
        if challenge_id not in challenges:
            print(f"Challenge ID {challenge_id} not found in CSV data")
            continue
        
        challenge = challenges[challenge_id]
        print(f"Processing: {challenge['path']} (ID: {challenge_id})")
        
        if update_challenge_yml(challenge['path'], root_dir, set_visible=True):
            check_and_start_containers(challenge['path'], root_dir)

def hide_other_challenges(selected_phase_ids, challenges, phases, root_dir):
    print("\nHiding challenges not in current phase")
    
    all_challenge_ids = set(map(lambda k: int(challenges[k]["id"]), list(challenges)))
    
    challenges_to_hide = all_challenge_ids - set(selected_phase_ids)
    
    for challenge_id in challenges_to_hide:
        if challenge_id not in challenges:
            print(f"Challenge ID {challenge_id} not found in CSV data")
            continue
            
        challenge = challenges[challenge_id]
        print(f"Hiding: {challenge['path']} (ID: {challenge_id})")
        update_challenge_yml(challenge['path'], root_dir, set_visible=False)

def select_phase(phases):
    print("\nAvailable phases:")
    phase_names = list(phases.keys())
    
    for i, phase_name in enumerate(phase_names, 1):
        challenge_count = len(phases[phase_name])
        print(f"{i}. {phase_name} ({challenge_count} challenges)")
    
    while True:
        try:
            choice = input("\nSelect phase number (or 'a' for all phases): ")
            if choice.lower() == 'a':
                return None  # Process all phases
            
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(phase_names):
                return phase_names[choice_idx]
            else:
                print("Invalid selection. Please try again.")
        except ValueError:
            print("Please enter a number or 'a'.")

def main():
    print(f"Loading phases from: {CONFIG}")
    phases = load_yaml_phases(CONFIG)
    
    print(f"Loading challenge data from: {CHALLENGES_CSV}")
    challenges = load_csv_challenges(CHALLENGES_CSV)
    
    phase_to_process = select_phase(phases)
    
    if phase_to_process:
        if phase_to_process in phases:
            # Process selected phase
            selected_phase_ids = phases[phase_to_process]
            process_phase(phase_to_process, selected_phase_ids, challenges, ROOT)
            
            # Hide challenges in other phases
            hide_other_challenges(selected_phase_ids, challenges, phases, ROOT)
        else:
            print(f"Phase '{phase_to_process}' not found in YAML file")
    else:
        # Process all phases (don't hide any)
        for phase_name, challenge_ids in phases.items():
            process_phase(phase_name, challenge_ids, challenges, ROOT)

    print("\nProcessing complete!")

if __name__ == "__main__":
    main()
