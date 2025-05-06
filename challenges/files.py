import os
import yaml
import sys

def update_yaml_with_files(yaml_file, dir_path):
    files_dir = os.path.join(dir_path, 'files')
    
    if not os.path.exists(files_dir):
        print(f"Error: Directory {files_dir} does not exist.")
        return
    
    file_paths = [
        os.path.join(dir_path, 'files', f) 
        for f in os.listdir(files_dir) 
        if os.path.isfile(os.path.join(files_dir, f))
    ]
    
    try:
        with open(yaml_file, 'r') as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        data = {}
    
    data['files'] = file_paths
    
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
