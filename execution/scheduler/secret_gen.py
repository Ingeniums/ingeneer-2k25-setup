import os
from cryptography.fernet import Fernet
import base64

def generate_fernet_key():
    """Generates a Fernet encryption key."""
    return Fernet.generate_key().decode('utf-8')

def generate_hmac_key(length=32):
    """Generates a random key for HMAC."""
    return base64.urlsafe_b64encode(os.urandom(length)).decode('utf-8')

if __name__ == "__main__":
    print("Generating new keys...")
    encryption_key = generate_fernet_key()
    signature_key = generate_hmac_key()

    print("\n--- Generated Keys ---")
    print(f"ENCRYPTION_KEY (Fernet): {encryption_key}")
    print(f"SIGNATURE_KEY (HMAC):    {signature_key}")
    print("\n----------------------")
    print("Copy these keys and set them as environment variables for your scheduler service.")
    print("For Docker Compose, add them to the environment section.")

