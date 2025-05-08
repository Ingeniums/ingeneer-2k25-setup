import requests
import json
import os
import sys
import logging
import argparse

SCHEDULER_URL = os.getenv("SCHEDULER_URL", "http://localhost:8001/submit")

SETTINGS = "gAAAAABoHI0pQgyPwdtbIsCy2aDVePuFmeUy_HaFeKbJ-tHfiIKkyF0LH_NSy253_QTvg4oAM1JP2vUGFvRcwfaJfbeWB5741UEaHunnO2d3Bk4bAnbbkts="

logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Reads files, prepares payload, and sends request to scheduler."""
    parser = argparse.ArgumentParser(description='Submit code execution tasks to the scheduler service.')
    parser.add_argument('language', help='The programming language of the code.')
    parser.add_argument('code_file_path', help='The path to the file containing the code.')
    parser.add_argument('input_file_path', help='The path to the file containing the input data.')

    args = parser.parse_args()

    language = args.language
    code_file_path = args.code_file_path
    input_file_path = args.input_file_path

    try:
        with open(code_file_path, 'r', encoding='utf-8') as f:
            code = f.read()
    except FileNotFoundError:
        logger.error(f"Error: Code file not found at {code_file_path}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error reading code file {code_file_path}: {e}", exc_info=True)
        sys.exit(1)

    try:
        with open(input_file_path, 'r', encoding='utf-8') as f:
            input_data = f.read()
    except FileNotFoundError:
        logger.error(f"Error: Input data file not found at {input_file_path}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error reading input data file {input_file_path}: {e}", exc_info=True)
        sys.exit(1)

    processed_code = code.replace("{{INPUT}}", input_data)

    request_payload = {
        "code": processed_code,
        "language": language,
    }
    if SETTINGS != "":
        request_payload["settings"] = SETTINGS

    try:
        response = requests.post(SCHEDULER_URL, json=request_payload)

        try:
            response_json = response.json()
            if response.ok:
                flag = response_json.get("flag", json.dumps(response_json))
                print(flag)
            else:
                 error_detail = response_json.get("detail", "Unknown error")
                 logger.error(f"Scheduler returned an error status {response.status_code}: {error_detail}")
                 sys.exit(1)

        except json.JSONDecodeError:
            logger.error("Failed to decode JSON response from scheduler.")
            logger.error(f"Raw response: {response.text}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"An error occurred processing scheduler response: {e}", exc_info=True)
            sys.exit(1)

    except requests.exceptions.ConnectionError:
        logger.error(f"Error: Could not connect to scheduler at {SCHEDULER_URL}. Is the scheduler running?")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        logger.error(f"An error occurred during the HTTP request to scheduler: {e}", exc_info=True)
        sys.exit(1)
    except Exception as e:
        logger.error(f"An unexpected error occurred during the request process: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
