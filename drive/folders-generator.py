#!/usr/bin/env python3
"""
Script to read a YAML configuration file with teams and challenge phases.
It prompts the user to select a phase, then generates folder paths in the format 'team/challenge'
and writes them to a folders.txt file for later use with the folder creation script.
"""

import yaml
import os
import sys
import argparse
from typing import List, Dict, Any

def load_config(config_file: str) -> Dict[str, Any]:
    """Load configuration from a YAML file."""
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        return config
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"Configuration file '{config_file}' not found.")
        sys.exit(1)

def validate_config(config: Dict[str, Any]) -> bool:
    """Validate the configuration structure."""
    if 'teams' not in config:
        print("Error: 'teams' section missing from configuration.")
        return False
    
    if 'phases' not in config:
        print("Error: 'phases' section missing from configuration.")
        return False
    
    if not isinstance(config['teams'], list):
        print("Error: 'teams' should be a list of team names.")
        return False
    
    if not isinstance(config['phases'], dict):
        print("Error: 'phases' should be a dictionary of phase names and their challenges.")
        return False
    
    # Check that each phase contains a list
    for phase, challenges in config['phases'].items():
        if not isinstance(challenges, list):
            print(f"Error: Phase '{phase}' should contain a list of challenge names.")
            return False
    
    return True

def select_phase(phases: Dict[str, List[str]]) -> str:
    """Prompt the user to select a phase."""
    phase_names = list(phases.keys())
    
    if not phase_names:
        print("Error: No phases found in configuration.")
        sys.exit(1)
    
    print("\nAvailable phases:")
    for i, phase in enumerate(phase_names, 1):
        print(f"{i}. {phase}")
    
    while True:
        try:
            choice = input("\nSelect a phase (enter the number): ")
            index = int(choice) - 1
            
            if 0 <= index < len(phase_names):
                selected_phase = phase_names[index]
                return selected_phase
            else:
                print(f"Please enter a number between 1 and {len(phase_names)}.")
        except ValueError:
            print("Please enter a valid number.")

def generate_folder_paths(teams: List[str], challenges: List[str]) -> List[str]:
    """Generate folder paths in the format 'team/challenge'."""
    paths = []
    
    for team in teams:
        for challenge in challenges:
            path = f"{team}/{challenge}"
            paths.append(path)
    
    return paths

def write_to_file(paths: List[str], output_file: str) -> None:
    """Write the folder paths to a text file."""
    try:
        with open(output_file, 'w') as f:
            for path in paths:
                f.write(f"{path}\n")
        print(f"\nSuccessfully wrote {len(paths)} folder paths to '{output_file}'")
    except IOError as e:
        print(f"Error writing to file: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='Generate folder paths from YAML configuration.')
    parser.add_argument('config', help='YAML configuration file')
    parser.add_argument('--output', '-o', default='folders.txt', 
                        help='Output file for folder paths (default: folders.txt)')
    args = parser.parse_args()
    
    print(f"Loading configuration from '{args.config}'...")
    config = load_config(args.config)
    
    if not validate_config(config):
        sys.exit(1)
    
    teams = config['teams']
    phases = config['phases']
    
    print(f"Found {len(teams)} teams and {len(phases)} phases in configuration.")
    
    selected_phase = select_phase(phases)
    challenges = phases[selected_phase]
    
    print(f"\nSelected phase: {selected_phase}")
    print(f"Found {len(challenges)} challenges in this phase.")
    
    paths = generate_folder_paths(teams, challenges)
    
    print(f"\nGenerated {len(paths)} folder paths.")
    print("Example paths:")
    for i, path in enumerate(paths[:5]):
        print(f"  {path}")
    
    if len(paths) > 5:
        print(f"  ... (and {len(paths) - 5} more)")
    
    write_to_file(paths, args.output)
    
    print(f"\nNext steps:")
    print(f"1. Review the generated paths in '{args.output}'")
    print(f"2. Use the Drive folder creator script to create these folders:")
    print(f"   python drive_folder_creator.py {args.output} /your/parent/folder")

if __name__ == '__main__':
    main()
