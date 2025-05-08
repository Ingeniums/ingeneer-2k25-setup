import os
import sys
from cryptography.hazmat.primitives import hashes, hmac
from cryptography.hazmat.backends import default_backend

# Get the signature key from environment variable
SIGNATURE_KEY = os.getenv("SIGNATURE_KEY", "")

if SIGNATURE_KEY is None:
    print("Error: SIGNATURE_KEY environment variable not set.", file=sys.stderr)
    print("Run the key generation script and set the SIGNATURE_KEY.", file=sys.stderr)
    sys.exit(1)

def generate_flag(input_string: str) -> str:
    """Generates an HMAC-SHA256 hash (flag) for the input string."""
    try:
        # Create a new HMAC instance with the signature key and SHA256
        h = hmac.HMAC(SIGNATURE_KEY.encode('utf-8'), hashes.SHA256(), backend=default_backend())
        # Update the hasher with the input string bytes
        h.update(input_string.encode('utf-8'))
        # Finalize the hash and get the hexadecimal representation
        return h.finalize().hex()
    except Exception as e:
        print(f"Error during flag generation: {e}", file=sys.stderr)
        raise # Re-raise the exception

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python generate_flag.py <string_to_hash>")
        sys.exit(1)

    string_to_hash = sys.argv[1]

    try:
        flag = generate_flag(string_to_hash)
        print(flag)
    except Exception:
        sys.exit(1)
