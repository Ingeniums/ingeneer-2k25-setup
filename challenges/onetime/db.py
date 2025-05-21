#!/usr/bin/python3
import os
import re
import yaml
import csv

# --- Configuration Constants ---
# These paths should be relative to the script's execution location or absolute.
# Adjust them if your script is located elsewhere relative to these directories/files.
CHALLENGES_DIR = "../ready"  # Directory containing processed challenge categories
CHALLENGES_SRC = "../../../challenges/"  # Source directory for challenges (for tags/difficulty)
OUTPUT_FILE = "../challenges.csv"  # Output CSV file

def load_challenges_from_csv(csv_path):
    """
    Loads challenges from an existing CSV file.

    Args:
        csv_path (str): Path to the CSV file.

    Returns:
        tuple: (challenge_name_to_data_map, max_id)
               - challenge_name_to_data_map: Dictionary mapping challenge name to its full data dictionary.
               - max_id: Highest 'id' found in the CSV, or -1 if file is empty/not found or IDs are invalid.
    """
    challenge_name_to_data_map = {}
    max_id = -1

    if not os.path.isfile(csv_path):
        print(f"Info: CSV file '{csv_path}' not found. A new file will be created.")
        return challenge_name_to_data_map, max_id

    try:
        with open(csv_path, 'r', newline='', encoding='utf-8') as csv_file:
            reader = csv.DictReader(csv_file)
            if not reader.fieldnames or "name" not in reader.fieldnames or "id" not in reader.fieldnames:
                print(f"Warning: CSV file '{csv_path}' is missing 'name' or 'id' headers, or is empty. Treating as new.")
                return challenge_name_to_data_map, max_id

            for row in reader:
                try:
                    challenge_name = row.get('name')
                    if not challenge_name:
                        print(f"Warning: Skipping row in CSV due to missing name: {row}")
                        continue
                    
                    current_id_str = row.get('id')
                    if current_id_str is None:
                        print(f"Warning: Skipping row in CSV due to missing id: {row}")
                        continue
                    
                    current_id = int(current_id_str)
                    row['id'] = current_id  # Store ID as integer

                    # Ensure all expected fields are present, fill with default if needed for consistency
                    # This helps if the CSV was manually edited and is missing columns
                    for field in ["category", "author", "difficulty", "path"]:
                        if field not in row:
                            row[field] = "" 
                            
                    challenge_name_to_data_map[challenge_name] = row
                    
                    if current_id > max_id:
                        max_id = current_id
                except ValueError:
                    print(f"Warning: Skipping row in CSV due to invalid id format: {row}")
                    continue
                except Exception as e:
                    print(f"Error processing row {row} from CSV: {e}")
                    continue
                    
    except Exception as e:
        print(f"Error reading CSV file '{csv_path}': {e}. Treating as if it were new.")
        return {}, -1  # Return empty map and -1 to signify fresh start
        
    print(f"Successfully loaded {len(challenge_name_to_data_map)} challenges from '{csv_path}'. Max ID: {max_id}")
    return challenge_name_to_data_map, max_id

def process_challenges(challenges_dir, challenges_src_global, existing_challenges_map, current_max_id):
    """
    Processes challenge directories, updates existing_challenges_map with new/modified
    challenge information, and assigns new IDs as needed.

    Args:
        challenges_dir (str): Path to the directory containing challenge categories.
        challenges_src_global (str): Path to the source challenges directory (for difficulty tags).
        existing_challenges_map (dict): Dict mapping challenge names to their data. Modified in place.
        current_max_id (int): The current maximum ID from the loaded CSV.

    Returns:
        int: The new maximum ID after processing all challenges.
    """
    next_id_to_assign = current_max_id + 1
    
    for category_name in os.listdir(challenges_dir):
        category_path = os.path.join(challenges_dir, category_name)
        
        if not os.path.isdir(category_path) or category_name == "sample":
            continue
        
        for challenge_folder_name in os.listdir(category_path):
            challenge_folder_path = os.path.join(category_path, challenge_folder_name)
            
            if not os.path.isdir(challenge_folder_path):
                continue
            
            challenge_yaml_path = os.path.join(challenge_folder_path, "challenge.yml")
            if not os.path.isfile(challenge_yaml_path):
                # print(f"Debug: No challenge.yml in {challenge_folder_path}")
                continue
            
            try:
                with open(challenge_yaml_path, 'r', encoding='utf-8') as yaml_file:
                    challenge_data = yaml.safe_load(yaml_file)

                if not challenge_data: # Handle empty YAML file
                    print(f"Warning: Empty or invalid YAML file at {challenge_yaml_path}. Skipping.")
                    continue

                yaml_challenge_name = challenge_data.get("name")
                if not yaml_challenge_name:
                    print(f"Warning: Challenge at '{challenge_yaml_path}' has no 'name' in YML. Skipping.")
                    continue

                challenge_src_yaml_path = os.path.join(challenges_src_global, category_name, challenge_folder_name, "challenge.yml")
                challenge_src_data = {}
                if os.path.isfile(challenge_src_yaml_path):
                    try:
                        with open(challenge_src_yaml_path, 'r', encoding='utf-8') as yaml_src:
                            parsed_src_content = re.sub('"{{\\w+}}"', '""', yaml_src.read())
                            parsed_src_content = re.sub("{{\\w+}}", '""', parsed_src_content)
                            challenge_src_data = yaml.safe_load(parsed_src_content)
                            if not challenge_src_data: challenge_src_data = {} # Ensure it's a dict
                    except Exception as e_src_yaml:
                         print(f"Warning: Could not parse source YAML {challenge_src_yaml_path}: {e_src_yaml}")
                # else:
                #     print(f"Debug: Source challenge YAML not found at {challenge_src_yaml_path}.")


                difficulty = ""
                src_tags = challenge_src_data.get("tags")
                if isinstance(src_tags, list):
                    difficulty_levels = ["warmup", "easy", "medium", "hard", "tough"]
                    for tag in src_tags:
                        tag_str = str(tag).lower()
                        if tag_str in difficulty_levels:
                            difficulty = tag_str
                            break
                
                current_path_in_repo = f"{category_name}/{challenge_folder_name}"
                author = challenge_data.get("author", "")

                if yaml_challenge_name in existing_challenges_map:
                    # Update existing challenge
                    challenge_entry = existing_challenges_map[yaml_challenge_name]
                    challenge_entry["category"] = category_name
                    challenge_entry["author"] = author
                    challenge_entry["difficulty"] = difficulty
                    challenge_entry["path"] = current_path_in_repo
                    # print(f"Updated challenge: {yaml_challenge_name} (ID: {challenge_entry['id']})")
                else:
                    # Insert new challenge
                    new_challenge_info = {
                        "id": next_id_to_assign,
                        "name": yaml_challenge_name,
                        "category": category_name,
                        "author": author,
                        "difficulty": difficulty,
                        "path": current_path_in_repo
                    }
                    existing_challenges_map[yaml_challenge_name] = new_challenge_info
                    # print(f"Added new challenge: {yaml_challenge_name} with ID {next_id_to_assign}")
                    next_id_to_assign += 1
            
            except yaml.YAMLError as e_yaml:
                print(f"Error parsing YAML file {challenge_yaml_path}: {e_yaml}")
            except Exception as e_general:
                print(f"Error processing challenge directory {challenge_folder_path}: {e_general}")
    
    return next_id_to_assign - 1 # The new highest ID used

def save_challenges_to_csv(challenges_list, output_csv_path=OUTPUT_FILE):
    """
    Saves a list of challenge dictionaries to a CSV file.
    The list is sorted by ID before saving.

    Args:
        challenges_list (list): List of dictionaries containing challenge information.
        output_csv_path (str): Path to the output CSV file.
    """
    if not challenges_list:
        print("No challenges processed or found to save.")
        # Create an empty CSV with headers if the file should exist
        if not os.path.exists(output_csv_path):
             try:
                with open(output_csv_path, 'w', newline='', encoding='utf-8') as csv_file:
                    fieldnames = ["id", "name", "category", "author", "difficulty", "path"]
                    writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
                    writer.writeheader()
                print(f"Created empty CSV with headers at {output_csv_path}")
             except Exception as e:
                print(f"Error creating empty CSV at {output_csv_path}: {e}")
        return
    
    # Sort by ID for consistent output. Ensure 'id' is an integer for proper sorting.
    try:
        challenges_list.sort(key=lambda x: int(x.get('id', -1)))
    except (TypeError, ValueError) as e:
        print(f"Warning: Could not sort challenges by ID due to data issues ({e}). Proceeding without sorting.")

    fieldnames = ["id", "name", "category", "author", "difficulty", "path"]
    
    try:
        with open(output_csv_path, 'w', newline='', encoding='utf-8') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(challenges_list)
        
        print(f"Successfully saved {len(challenges_list)} challenges to '{output_csv_path}'")
    
    except Exception as e:
        print(f"Error saving challenges to CSV '{output_csv_path}': {e}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Process CTF challenges from YAML files and update/insert into a CSV.")
    parser.add_argument("--output", default=OUTPUT_FILE, 
                        help=f"Output CSV filename (default: {OUTPUT_FILE})")
    parser.add_argument("--challenges-dir", default=CHALLENGES_DIR,
                        help=f"Path to directory containing processed challenge categories (default: {CHALLENGES_DIR})")
    parser.add_argument("--challenges-src", default=CHALLENGES_SRC,
                        help=f"Path to source challenges directory for metadata (default: {CHALLENGES_SRC})")
    
    args = parser.parse_args()
    
    output_csv_path = args.output
    current_challenges_dir = args.challenges_dir
    current_challenges_src = args.challenges_src

    # 1. Load existing challenges from CSV
    challenges_map, max_id_from_csv = load_challenges_from_csv(output_csv_path)
    
    # 2. Process YAMLs. This function modifies challenges_map in place
    #    and returns the new highest ID after any additions.
    #    (No need to capture returned max_id if not used further in main)
    process_challenges(
        current_challenges_dir,
        current_challenges_src,
        challenges_map,  # This map is modified by the function
        max_id_from_csv
    )
    
    # The challenges_map now contains the consolidated data (existing, updated, new).
    final_challenges_list = list(challenges_map.values())
    
    # 3. Save the consolidated list to CSV
    save_challenges_to_csv(final_challenges_list, output_csv_path)
    
    print(f"Script finished. Total challenges in '{output_csv_path}': {len(final_challenges_list)}.")

if __name__ == "__main__":
    main()
