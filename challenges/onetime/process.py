#!/usr/bin/python3
import os
import yaml
import sys

CATEGORIES={
    "crypto": "Parseltongue",
    "design": "Charm Learning",
    "devops": "Systemic Sorcery",
    "forensics": "Auror Investigation",
    "misc": "Wizarding Whimsy",
    "problem solving": "Arithmancy",
    "web": "Horcrux Hunt",
    "networking": "Floo Network",
    "reverse": "Spell Deconstruction"
}


def update_yaml_with_files(yaml_file, dir_path):
    files_dir = os.path.join(dir_path, 'files')
    
    with open(yaml_file, 'r') as f:
        data = yaml.safe_load(f) or {}


    if os.path.exists(files_dir):
        file_paths = [
            os.path.join(dir_path, 'files', f) 
            for f in os.listdir(files_dir) 
            if os.path.isfile(os.path.join(files_dir, f))
        ]
        data['files'] = file_paths
    
    if data["category"] not in ["design"]:
        data["extra"] = {
            "initial": "{{initial}}",
            "decay": "{{decay}}",
            "minimum": "{{minimum}}",
        }
        del data["value"]
        data["type"] = "dynamic"
        # tags = []
        # for tag in list(data["tags"]):
        #     if tag not in ["warmup", "easy", "medium", "hard", "tough"]:
        #         tags.append(tag)
        #
        # data["tags"] = tags
    else:
        data["value"] = 10
        data["type"] = "standard"
    data["category"] = CATEGORIES[data["category"]]

    
    with open(yaml_file, 'w') as f:
        yaml.safe_dump(data, f, default_flow_style=False)
    
    print(f"Updated {yaml_file} with files from {files_dir}...")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python script.py <yaml_file> <dir>")
        sys.exit(1)
    
    yaml_file = sys.argv[1]
    dir_path = sys.argv[2]
    update_yaml_with_files(yaml_file, dir_path)
