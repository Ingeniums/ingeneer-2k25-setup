#!/usr/bin/python3
import os
import yaml
import csv

CHALLENGES_DIR="../ready"
OUTPUT_FILE="../challenges.csv"

def process_challenges(challenges_dir):
    """
    Process challenges directory to extract challenge information.
    
    Args:
        challenges_dir (str): Path to the directory containing challenge categories
        
    Returns:
        list: List of dictionaries containing challenge information
    """
    challenges_list = []
    
    # Walk through the directory structure
    i = 0
    for category in os.listdir(challenges_dir):
        category_path = os.path.join(challenges_dir, category)
        
        # Skip if not a directory or if it's the sample category
        if not os.path.isdir(category_path) or category == "sample":
            continue
        
        # Process each challenge in the category
        for challenge_name in os.listdir(category_path):
            challenge_dir = os.path.join(category_path, challenge_name)
            
            # Skip if not a directory
            if not os.path.isdir(challenge_dir):
                continue
            
            # Check if challenge.yml exists
            challenge_yaml_path = os.path.join(challenge_dir, "challenge.yml")
            if not os.path.isfile(challenge_yaml_path):
                continue
            
            try:
                # Read challenge YAML file
                with open(challenge_yaml_path, 'r') as yaml_file:
                    challenge_data = yaml.safe_load(yaml_file)
                
                difficulty = ""
                if "tags" in challenge_data and isinstance(challenge_data["tags"], list):
                    difficulty_levels = ["warmup", "easy", "medium", "hard", "tough"]
                    for tag in challenge_data["tags"]:
                        tag_str = str(tag).lower()
                        if tag_str in difficulty_levels:
                            difficulty = tag_str
                            break
                
                # Construct path
                path = f"{category}/{challenge_name}"
                
                # Extract required information
                challenge_info = {
                    "id": i,  # Using challenge name as ID
                    "name": challenge_data.get("name", ""),
                    "category": category,
                    "author": challenge_data.get("author", ""),
                    "difficulty": difficulty,
                    "path": path
                }
                
                challenges_list.append(challenge_info)
                i += 1
                
            except Exception as e:
                print(f"Error processing {challenge_yaml_path}: {e}")
    
    return challenges_list


def save_challenges_to_csv(challenges_list, output_csv_path=OUTPUT_FILE):
    """
    Save list of challenges to a CSV file.
    
    Args:
        challenges_list (list): List of dictionaries containing challenge information
        output_csv_path (str): Path to the output CSV file
    """
    if not challenges_list:
        print("No challenges found to save.")
        return
    
    # Define CSV headers based on dictionary keys
    fieldnames = ["id", "category", "author", "difficulty", "name", "path"]
    
    try:
        with open(output_csv_path, 'w', newline='') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(challenges_list)
        
        print(f"Successfully saved {len(challenges_list)} challenges to {output_csv_path}")
    
    except Exception as e:
        print(f"Error saving to CSV: {e}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Process CTF challenges and export to CSV.")
    # parser.add_argument("challenges_dir", help="Path to directory containing challenge categories")
    parser.add_argument("--output", default=OUTPUT_FILE, help="Output CSV filename (default: challenges.csv)")
    
    args = parser.parse_args()
    
    # Process challenges and save to CSV
    challenges_list = process_challenges(CHALLENGES_DIR)
    save_challenges_to_csv(challenges_list, args.output)
    
    print(f"Found {len(challenges_list)} challenges.")


if __name__ == "__main__":
    main()
