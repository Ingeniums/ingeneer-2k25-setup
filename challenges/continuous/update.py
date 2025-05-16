#!/usr/bin/python3

import os
import pathlib
import subprocess
import yaml
import argparse

CHALLENGES_PATH="../ready"
COMPILE_SCRIPT="../onetime/compile"
BASE_DIR = pathlib.Path(__file__).parent.resolve()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="Update Challenge",
        description="Updates challenges or containers",
    )

    parser.add_argument("config")
    args = parser.parse_args()
    config_path = str(args.config)
    full_path = f"{CHALLENGES_PATH}/{config_path}/challenge.yml"
    category, name = config_path.split("/")

    if not os.path.isfile(full_path):
        print("No challenge.yml file found with specified path")
        exit(1)

    with open(full_path, "r") as config:
        config = yaml.safe_load(config.read())
        state = config["state"]
        os.chdir("../onetime")
        subprocess.run(["bash", COMPILE_SCRIPT, category, name])
        os.chdir(BASE_DIR)
        print(BASE_DIR)
        if state != "hidden":
            with open(full_path, "r") as config_file:
                config = yaml.safe_load(config_file.read())
                config["state"] = "visible"
                with open(full_path, "w") as config_file:
                    config_file.write(yaml.dump(config))

            if os.path.isfile(f"{CHALLENGES_PATH}/{config_path}/compose.yaml"):
                subprocess.run([
                    "docker",
                    "compose",
                    "-f", f"{CHALLENGES_PATH}/{config_path}/compose.yaml",
                    "down",
                ])
                subprocess.run([
                    "docker",
                    "compose",
                    "-f", f"{CHALLENGES_PATH}/{config_path}/compose.yaml",
                    "up",
                    "-d",
                    "--build"
                ])

        subprocess.run(["bash", "./upload", config_path])
                
            

