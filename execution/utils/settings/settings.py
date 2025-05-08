import json
import os
import sys
from cryptography.fernet import Fernet
from dotenv import load_dotenv
load_dotenv()

# Get the encryption key from environment variable
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

settings = {
    "memory_limit": 512, # In MB
    # "compile_timeout": 1500000, # In milliseconds
    # "run_timeout": 1500000, # In milliseconds
}

if ENCRYPTION_KEY is None:
    print("Error: ENCRYPTION_KEY environment variable not set.", file=sys.stderr)
    print("Run the key generation script and set the ENCRYPTION_KEY.", file=sys.stderr)
    sys.exit(1)

try:
    fernet_cipher = Fernet(ENCRYPTION_KEY.encode('utf-8'))
except Exception as e:
    print(f"Error: Failed to initialize Fernet cipher: {e}", file=sys.stderr)
    sys.exit(1)

def encrypt_settings_json(json_string: str) -> str:
    """Encrypts a JSON string using Fernet."""
    try:
        # Ensure the input is valid JSON before encrypting
        json.loads(json_string)
    except json.JSONDecodeError:
        raise ValueError("Input string is not valid JSON.")

    # Encrypt the bytes of the JSON string
    encrypted_bytes = fernet_cipher.encrypt(json_string.encode('utf-8'))
    # Return the encrypted bytes decoded as a string (Fernet produces url-safe base64)
    return encrypted_bytes.decode('utf-8')

if __name__ == "__main__":
    settings_json_string = json.dumps(settings)

    try:
        encrypted_string = encrypt_settings_json(settings_json_string)
        print(encrypted_string)
        print("Set them as value for 'settings' in submission script")
    except ValueError as ve:
        print(f"Error: {ve}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)
