import asyncio
from contextlib import asynccontextmanager
import json
import os
import uuid
import logging
from typing import Dict, Any, Optional

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
from aio_pika import connect_robust, Message
from aio_pika.abc import AbstractChannel, AbstractConnection

# Import cryptography libraries
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes, hmac
from cryptography.hazmat.backends import default_backend

# --- Configuration ---
# RabbitMQ connection details
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "192.168.100.11")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")

# Queue names
TASK_QUEUE = os.getenv("TASK_QUEUE", "execution_tasks")
RESULTS_QUEUE = os.getenv("RESULTS_QUEUE", "execution_results")

# Timeout for waiting for execution results (in seconds)
EXECUTION_TIMEOUT = int(os.getenv("EXECUTION_TIMEOUT", 60)) # Default to 60 seconds

# Encryption and Hashing Keys (MUST be set as environment variables)
# For Fernet, the key must be 32 url-safe base64-encoded bytes. Fernet.generate_key() can create one.
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")
# For HMAC-SHA256, the key can be any length, but a strong random key is recommended.
SIGNATURE_KEY = os.getenv("SIGNATURE_KEY", "")

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- FastAPI App ---

# --- RabbitMQ Connections and Channel ---
# Use separate connections for publishing and consuming for better isolation
rabbitmq_publish_connection: Optional[AbstractConnection] = None
rabbitmq_publish_channel: Optional[AbstractChannel] = None
rabbitmq_consume_connection: Optional[AbstractConnection] = None
rabbitmq_consume_channel: Optional[AbstractChannel] = None

# Dictionary to hold futures for pending results, keyed by job_id
pending_results: Dict[str, asyncio.Future] = {}

# --- Cryptography Instances ---
# Initialize Fernet and HMAC instances using keys from environment variables
fernet_cipher: Optional[Fernet] = None
signature_hasher: Optional[hmac.HMAC] = None

# --- RabbitMQ Connection Helper ---
async def get_rabbitmq_connection():
    """Establishes a robust connection to RabbitMQ with retries."""
    TRIES = 10 # Increased retries for startup
    tried = 0
    connection = None
    while tried < TRIES:
        await asyncio.sleep(2 ** tried) # Exponential backoff
        try:
            connection = await connect_robust(
                host=RABBITMQ_HOST,
                port=RABBITMQ_PORT,
                login=RABBITMQ_USER,
                password=RABBITMQ_PASSWORD,
                loop=asyncio.get_event_loop()
            )
            logger.info(f"Successfully connected to RabbitMQ at {RABBITMQ_HOST}:{RABBITMQ_PORT}")
            return connection
        except Exception as e:
            logger.error(f"Attempt {tried + 1}/{TRIES}: Failed to connect to RabbitMQ at {RABBITMQ_HOST}:{RABBITMQ_PORT} - {e}")
        tried += 1
    logger.error(f"Failed to connect to RabbitMQ after {TRIES} attempts.")
    # Do not raise here, allow startup to potentially continue without RabbitMQ if designed that way,
    # but the /submit endpoint will check for channel availability.
    return None


# --- Settings Processing Function ---
def process_settings(encrypted_settings_string: str) -> Dict[str, Any]:
    """
    Decrypts the settings string, parses it as JSON, and extracts
    execution parameters.
    """
    if fernet_cipher is None:
        raise ValueError("Encryption key not set or Fernet cipher not initialized.")

    try:
        # Decrypt the string (it's expected to be bytes)
        decrypted_bytes = fernet_cipher.decrypt(encrypted_settings_string.encode('utf-8'))
        # Decode bytes to string
        decrypted_string = decrypted_bytes.decode('utf-8')
        # Parse the JSON string
        settings_json = json.loads(decrypted_string)

        if not isinstance(settings_json, dict):
             raise ValueError("Decrypted settings is not a JSON object.")

        processed_params = {}
        # Extract parameters, ensuring they are of the correct type
        if 'memory_limit' in settings_json and isinstance(settings_json['memory_limit'], (int, float)):
             processed_params['memory_limit'] = int(settings_json['memory_limit'])
        if 'compile_timeout' in settings_json and isinstance(settings_json['compile_timeout'], (int, float)):
             processed_params['compile_timeout'] = int(settings_json['compile_timeout'])
        if 'run_timeout' in settings_json and isinstance(settings_json['run_timeout'], (int, float)):
             processed_params['run_timeout'] = int(settings_json['run_timeout'])
        # Add more settings processing as needed

        return processed_params

    except InvalidToken:
        logger.error("Failed to decrypt settings: Invalid token.")
        raise ValueError("Invalid encrypted settings token.")
    except json.JSONDecodeError:
        logger.error("Failed to decode decrypted settings as JSON.")
        raise ValueError("Decrypted settings is not valid JSON.")
    except Exception as e:
        logger.error(f"An unexpected error occurred during settings processing: {e}", exc_info=True)
        raise ValueError(f"Error processing settings: {e}")


# --- Feeder Response Processing Function ---
def process_feeder_response(feeder_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Processes the result received from the feeder service, hashes the output,
    and returns a flag.
    """
    if SIGNATURE_KEY is None:
         raise ValueError("Signature key not set.")

    # We will hash the stdout of the execution result
    print(feeder_result)
    output_to_hash = feeder_result.get("stdout", "")
    if output_to_hash is None: # Ensure None becomes empty string
        output_to_hash = ""

    print(output_to_hash)
    try:
        # Create a new HMAC instance for each hashing operation (recommended practice)
        h = hmac.HMAC(SIGNATURE_KEY.encode('utf-8'), hashes.SHA256(), backend=default_backend())
        h.update(output_to_hash.encode('utf-8'))
        flag = h.finalize().hex() # Get the hexadecimal representation of the hash

        return {"flag": flag}

    except Exception as e:
        logger.error(f"An error occurred during result hashing: {e}", exc_info=True)
        # Decide how to handle hashing failure - return an error flag or raise?
        # Returning an error flag for now.
        return {"flag": f"ERROR_HASHING_FAILED: {e}"}


# --- RabbitMQ Consumer Task ---
async def consume_results():
    """Consumes messages from the results queue and sets the result on pending futures."""
    global rabbitmq_consume_connection, rabbitmq_consume_channel
    try:
        rabbitmq_consume_connection = await get_rabbitmq_connection()
        if rabbitmq_consume_connection is None:
             logger.error("Consumer failed to connect to RabbitMQ. Results will not be processed.")
             return # Exit the consumer task if connection fails

        rabbitmq_consume_channel = await rabbitmq_consume_connection.channel()

        # Declare the results queue to ensure it exists
        queue = await rabbitmq_consume_channel.declare_queue(RESULTS_QUEUE, durable=True)

        logger.info(f"Scheduler consumer started, waiting for results on queue: {RESULTS_QUEUE}")

        async for message in queue.iterator():
            async with message.process():
                try:
                    result_payload = json.loads(message.body.decode('utf-8'))
                    job_id = result_payload.get("job_id")

                    if job_id in pending_results:
                        logger.info(f"Received result for job ID: {job_id}")
                        future = pending_results.pop(job_id) # Remove from pending list
                        # Set the result on the waiting future
                        # This will unblock the await in the /submit endpoint
                        future.set_result(result_payload)
                    else:
                        logger.warning(f"Received result for unknown or expired job ID: {job_id}. Skipping.")
                        # Acknowledge the message even if the job_id is not found,
                        # assuming it might be from a previous run or expired request.

                except json.JSONDecodeError:
                    logger.error(f"Failed to decode JSON message from results queue: {message.body}")
                    # Acknowledge invalid messages to remove them from the queue
                    await message.ack()
                except Exception as e:
                    logger.error(f"An error occurred while processing result message: {e}", exc_info=True)
                    # Acknowledge the message to prevent reprocessing on error
                    await message.ack()

    except Exception as e:
        logger.error(f"Error in scheduler results consumer: {e}", exc_info=True)
        # The consumer task might stop on unhandled exceptions. You might want to add logic
        # here to attempt to restart the consumer task or log a critical error.


@asynccontextmanager
async def lifespan(app: FastAPI):
    global rabbitmq_publish_connection, rabbitmq_publish_channel
    global fernet_cipher, signature_hasher

    # --- Initialize Cryptography ---
    if ENCRYPTION_KEY is None:
        logger.critical("ENCRYPTION_KEY environment variable not set. Encryption will fail.")
        # Depending on requirements, you might want to exit here
        # sys.exit(1)
    else:
        try:
            fernet_cipher = Fernet(ENCRYPTION_KEY.encode('utf-8'))
            logger.info("Fernet cipher initialized.")
        except Exception as e:
            logger.critical(f"Failed to initialize Fernet cipher with provided key: {e}")
            fernet_cipher = None # Ensure it's None if initialization fails

    if SIGNATURE_KEY is None:
        logger.critical("SIGNATURE_KEY environment variable not set. Hashing will fail.")
        # Depending on requirements, you might want to exit here
        # sys.exit(1)
    # Note: HMAC instance is created per hashing operation in process_feeder_response
    # We just need to ensure the key is available here.

    # --- Establish RabbitMQ Publisher Connection ---
    try:
        rabbitmq_publish_connection = await get_rabbitmq_connection()
        if rabbitmq_publish_connection:
            rabbitmq_publish_channel = await rabbitmq_publish_connection.channel()
            # Declare the task queue once on startup
            await rabbitmq_publish_channel.declare_queue(TASK_QUEUE, durable=True)
            logger.info(f"Scheduler publisher connected and declared queue: {TASK_QUEUE}")
        else:
             logger.error("RabbitMQ publisher connection could not be established.")
    except Exception as e:
        logger.error(f"Failed to set up RabbitMQ publisher on startup: {e}")


    # --- Start the background task for consuming results ---
    # This task will attempt to connect to RabbitMQ internally with retries
    asyncio.create_task(consume_results())
    logger.info("Results consumer background task started.")
    yield

    # Close publisher connection
    if rabbitmq_publish_connection:
        try:
            await rabbitmq_publish_connection.close()
            logger.info("RabbitMQ publisher connection closed.")
        except Exception as e:
            logger.error(f"Error closing RabbitMQ publisher connection: {e}")

    # Close consumer connection
    if rabbitmq_consume_connection:
        try:
            await rabbitmq_consume_connection.close()
            logger.info("RabbitMQ consumer connection closed.")
        except Exception as e:
            logger.error(f"Error closing RabbitMQ consumer connection: {e}")

    # Note: Pending futures are not explicitly cancelled here. Clients waiting
    # for results might time out or receive no response depending on how
    # the client handles connection closure.


app = FastAPI(lifespan=lifespan)

# --- HTTP Endpoint: /submit ---
@app.post("/submit")
async def submit_code(request: Request):
    """
    Receives code execution requests, publishes them to RabbitMQ,
    and waits asynchronously for the result.
    """
    # Check if RabbitMQ publisher is available
    if rabbitmq_publish_channel is None or rabbitmq_publish_connection is None or rabbitmq_publish_connection.is_closed:
        logger.error("RabbitMQ publisher is not available.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduler is not connected to RabbitMQ for publishing."
        )

    # Check if cryptography keys are set
    if ENCRYPTION_KEY is None or SIGNATURE_KEY is None:
         logger.error("Encryption or signature key is not set.")
         raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server is not configured with necessary security keys."
         )


    try:
        request_data = await request.json()
        code = request_data.get("code")
        language = request_data.get("language")
        encrypted_settings = request_data.get("settings") # Expecting encrypted string

        if not code or not language:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing 'code' or 'language' in request body."
            )

        job_id = str(uuid.uuid4())
        logger.info(f"Received request for job ID: {job_id}")

        # Process settings if provided and encrypted
        execution_params = {}
        if encrypted_settings is not None:
            if not isinstance(encrypted_settings, str):
                 raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Settings must be a string."
                 )
            try:
                execution_params = process_settings(encrypted_settings)
                logger.info(f"Settings processed successfully for job ID: {job_id}")
            except ValueError as ve:
                logger.error(f"Failed to process settings for job ID {job_id}: {ve}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid or unprocessable settings: {ve}"
                )
            except Exception as e:
                logger.error(f"An unexpected error occurred during settings processing for job ID {job_id}: {e}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"An unexpected error occurred during settings processing: {e}"
                )


        # Create the task payload for the feeder
        task_payload = {
            "job_id": job_id,
            "code": code,
            "language": language,
            **execution_params # Include processed settings (memory_limit, timeouts)
        }

        # Create a Future to wait for the result and store it
        future = asyncio.Future()
        pending_results[job_id] = future

        # Publish the task message to RabbitMQ
        await rabbitmq_publish_channel.default_exchange.publish(
            Message(json.dumps(task_payload).encode('utf-8')),
            routing_key=TASK_QUEUE
        )
        logger.info(f"Published task for job ID: {job_id} to {TASK_QUEUE}")

        # --- Asynchronously wait for the result ---
        try:
            # Use asyncio.wait_for to implement a timeout
            feeder_result = await asyncio.wait_for(future, timeout=EXECUTION_TIMEOUT)
            logger.info(f"Received result from feeder for job ID: {job_id}")

            # Process the result (hash the output) before returning
            final_response = process_feeder_response(feeder_result)

            return JSONResponse(content=final_response)

        except asyncio.TimeoutError:
            logger.warning(f"Execution timed out for job ID: {job_id}")
            # Clean up the pending future
            if job_id in pending_results:
                del pending_results[job_id]
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Code execution timed out after {EXECUTION_TIMEOUT} seconds."
            )
        except Exception as wait_error:
            logger.error(f"An error occurred while waiting for result for job ID {job_id}: {wait_error}", exc_info=True)
            # Clean up the pending future
            if job_id in pending_results:
                del pending_results[job_id]
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred while waiting for the execution result: {wait_error}"
            )

    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON request body."
        )
    except HTTPException:
        # Re-raise explicit HTTPExceptions
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred in /submit endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {e}"
        )
# --- Entry Point (for running with uvicorn) ---
# To run this service:
# 1. Save as scheduler_service.py
# 2. Install dependencies: pip install fastapi uvicorn aio-pika cryptography
# 3. Set environment variables ENCRYPTION_KEY and SIGNATURE_KEY (e.g., in a .env file or your shell)
# 4. Set RabbitMQ environment variables if not using defaults
# 5. Run: uvicorn scheduler_service:app --reload
# (Use --reload for development, remove for production)
