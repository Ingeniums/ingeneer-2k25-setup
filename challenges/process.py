#!/usr/bin/python3
import os
import yaml
import sys

def update_yaml_with_files(yaml_file, dir_path):
    files_dir = os.path.join(dir_path, 'files')
    
    try:
        with open(yaml_file, 'r') as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        data = {}
    
    tags = list(data['tags'])
    difficulty = ""
    for tag in tags:
        if tag in ["warmup", "easy", "medium", "hard", "tough"]:
            difficulty = tag
            break
    if os.path.exists(files_dir):
        file_paths = [
            os.path.join(dir_path, 'files', f) 
            for f in os.listdir(files_dir) 
            if os.path.isfile(os.path.join(files_dir, f))
        ]
        data['files'] = file_paths

    data['type'] = "dynamic"
    data['extra'] = {
        "initial": f"{{{{{difficulty}_initial}}}}",
        "decay": f"{{{{{difficulty}_decay}}}}",
        "minimum": f"{{{{{difficulty}_minimum}}}}",
    }
    del data["value"]
    
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
