import asyncio
import json
import os
import logging
import requests
import time
import sys
from typing import Dict, Any, Optional, List

from aio_pika import connect_robust, Message
from aio_pika.abc import AbstractChannel, AbstractIncomingMessage

# --- Configuration ---
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "0.0.0.0")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")

TASK_QUEUE = os.getenv("TASK_QUEUE", "execution_tasks")
RESULTS_QUEUE = os.getenv("RESULTS_QUEUE", "execution_results")

PISTON_URL = os.getenv("PISTON_URL", "http://192.168.100.11:2000")

DEFAULT_MEMORY_LIMIT_MB = int(os.getenv("DEFAULT_MEMORY_LIMIT", -1))
DEFAULT_COMPILE_TIMEOUT_MS = int(os.getenv("DEFAULT_COMPILE_TIMEOUT", 10000))
DEFAULT_RUN_TIMEOUT_MS = int(os.getenv("DEFAULT_RUN_TIMEOUT", 10000))

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

language_version_map: Dict[str, str] = {}

# --- RabbitMQ Connection and Channel ---
async def get_rabbitmq_connection():
    TRIES = 5
    tried = 0
    connection = None
    while tried < TRIES:
        await asyncio.sleep(2 ** tried)
        try:
            connection = await connect_robust(
                host=RABBITMQ_HOST,
                port=RABBITMQ_PORT,
                login=RABBITMQ_USER,
                password=RABBITMQ_PASSWORD,
                loop=asyncio.get_event_loop()
            )
            logger.info("Successfully connected to RabbitMQ.")
            return connection
        except Exception as e:
            logger.error(f"Attempt {tried + 1}/{TRIES}: Failed to connect to RabbitMQ at {RABBITMQ_HOST}:{RABBITMQ_PORT} - {e}")
        tried += 1
    logger.error(f"Failed to connect to RabbitMQ after {TRIES} attempts.")
    raise ConnectionError("Failed to connect to RabbitMQ")


# --- Helper to Send Result ---
async def send_result_to_queue(channel: AbstractChannel, result_payload: dict):
    try:
        await channel.declare_queue(RESULTS_QUEUE, durable=True)
        await channel.default_exchange.publish(
            Message(json.dumps(result_payload).encode('utf-8')),
            routing_key=RESULTS_QUEUE
        )
    except Exception as publish_error:
         logger.error(f"Failed to publish result for job ID {result_payload.get('job_id')}: {publish_error}")


# --- Piston Connectivity Check and Runtime Fetch ---
def fetch_piston_runtimes() -> Optional[List[Dict[str, Any]]]:
    """Fetches runtimes from the Piston API /runtimes endpoint."""
    runtimes_url = f"{PISTON_URL}/api/v2/runtimes"
    logger.info(f"Fetching Piston API runtimes from {runtimes_url}...")
    TRIES = 5
    tried = 0
    while tried < TRIES:
        try:
            response = requests.get(runtimes_url, timeout=10)
            response.raise_for_status()
            runtimes_data = response.json()
            if isinstance(runtimes_data, list):
                logger.info(f"Successfully fetched {len(runtimes_data)} runtimes from Piston API.")
                return runtimes_data
            else:
                 logger.warning("Piston API /runtimes did not return a list.")
                 return None
        except requests.exceptions.ConnectionError as ce:
            logger.error(f"Attempt {tried + 1}/{TRIES}: Piston API connection error: {ce}")
        except requests.exceptions.Timeout:
            logger.error(f"Attempt {tried + 1}/{TRIES}: Piston API connectivity check timed out.")
        except requests.exceptions.RequestException as re:
            logger.error(f"Attempt {tried + 1}/{TRIES}: Piston API request error: {re}")
        except Exception as e:
            logger.error(f"Attempt {tried + 1}/{TRIES}: Unexpected error during Piston runtime fetch: {e}", exc_info=True)
        tried += 1
        if tried < TRIES:
             time.sleep(2 ** tried)

    logger.critical(f"Failed to fetch Piston API runtimes from {PISTON_URL} after {TRIES} attempts.")
    return None


async def send_error(
    channel: AbstractChannel,
    job_id: str,
    language: str,
    message: str,
    status: str,
    version: Optional[str] = None,
    stderr: Optional[str] = None,
):
    logger.error(message)
    error_payload = {
        "job_id": job_id,
        "stdout": None,
        "stderr": stderr,
        "compile_output": None,
        "compile_stderr": None,
        "language": language,
        "version": version,
        "status": status,
        "message": message,
        "fail": True
    }
    await send_result_to_queue(channel, error_payload)
    return # Exit submit function

# --- Core Submission Logic ---
async def submit(channel: AbstractChannel, message: AbstractIncomingMessage):
    async with message.process():
        job_id = None
        language = 'unknown'
        try:
            payload = json.loads(message.body.decode('utf-8'))
            job_id = payload.get("job_id")
            code = payload.get("code")
            language = payload.get("language")

            memory_limit_mb = payload.get("memory_limit", DEFAULT_MEMORY_LIMIT_MB)
            compile_timeout_ms = payload.get("compile_timeout", DEFAULT_COMPILE_TIMEOUT_MS)
            run_timeout_ms = payload.get("run_timeout", DEFAULT_RUN_TIMEOUT_MS)

            try:
                 memory_limit_mb = int(memory_limit_mb)
            except (ValueError, TypeError):
                 memory_limit_mb = DEFAULT_MEMORY_LIMIT_MB
            try:
                 compile_timeout_ms = int(compile_timeout_ms)
            except (ValueError, TypeError):
                 compile_timeout_ms = DEFAULT_COMPILE_TIMEOUT_MS
            try:
                 run_timeout_ms = int(run_timeout_ms)
            except (ValueError, TypeError):
                 run_timeout_ms = DEFAULT_RUN_TIMEOUT_MS

            if not job_id or not code or not language:
                logger.warning(f"Received invalid message format. Missing job_id, code, or language. Payload: {payload}")
                return


            # --- Look up language version ---
            version = language_version_map.get(language.lower()) # Use lower case for lookup
            if version is None:
                return await send_error(
                    channel,
                    message=f"Unsupported language or alias '{language}' for job ID {job_id}.",
                    job_id=job_id,
                    language=language,
                    stderr=f"Unsupported language or alias: {language}",
                    version=None,
                    status="unsupported_language"
                )

            piston_request_body = {
                "language": language, # Use the original language string
                "version": version, # Include the looked-up version
                "files": [{"content": code}],
            }
            if run_timeout_ms is not None:
                piston_request_body["run_timeout"] = run_timeout_ms

            if compile_timeout_ms is not None:
                piston_request_body["compile_timeout"] = compile_timeout_ms

            if memory_limit_mb != -1:
                memory_limit_bytes = memory_limit_mb * 1024 * 1024
                piston_request_body["compile_memory_limit"] = memory_limit_bytes
                piston_request_body["run_memory_limit"] = memory_limit_bytes

            logger.info(f"Processing job ID: {job_id} for language: {language}, payload: {piston_request_body}")
            # --- Execute code using Piston API via requests ---
            piston_api_url = f"{PISTON_URL}/api/v2/execute"
            response = None
            try:
                response = await asyncio.to_thread(
                    requests.post,
                    piston_api_url,
                    json=piston_request_body,
                    timeout=(compile_timeout_ms + run_timeout_ms) / 1000.0 + 5
                )
                logger.info(f"Recieved {response.json()}")
                response.raise_for_status()

            except requests.exceptions.Timeout:
                return await send_error(
                    channel,
                    message=f"Piston API request timed out for job ID {job_id} after sending.",
                    job_id=job_id,
                    language=language,
                    stderr=f"Request timed out",
                    version=version,
                    status="piston_timeout"
                )

            except requests.exceptions.RequestException as re:
                return await send_error(
                    channel,
                    message=f"Piston API connection error for job ID {job_id}: {re}",
                    job_id=job_id,
                    language=language,
                    stderr=f"Piston API connection error: {re}",
                    version=version,
                    status="piston_connection_error"
                )

            # --- Handle HTTP Status Codes ---
            if response.status_code == 429:
                logger.warning(f"Rate Limited by Piston for job ID {job_id}. Retrying...")
                loops = 1
                while loops <= 10:
                    try:
                        await asyncio.sleep(1 * loops)
                        logger.info(f"Retrying Piston execution for job ID {job_id} (Attempt {loops + 1})...")
                        response = await asyncio.to_thread(
                            requests.post,
                            piston_api_url,
                            json=piston_request_body,
                            timeout=max(compile_timeout_ms, run_timeout_ms) / 1000.0 + 5
                        )
                        response.raise_for_status()
                        break
                    except requests.exceptions.RequestException as retry_re:
                        if retry_re.response is not None and retry_re.response.status_code == 429:
                             loops += 1
                             continue
                        else:
                            return await send_error(
                                channel,
                                message=f"Piston API error during retry for job ID {job_id}: {retry_re}",
                                job_id=job_id,
                                language=language,
                                stderr=f"Piston API Error during retry: {retry_re}",
                                version=version,
                                status="piston_api_error_retry"
                            )

                if loops > 10:
                     return await send_error(
                         channel,
                         message=f"Failed to execute job ID {job_id} after {loops} rate limit retries.",
                         job_id=job_id,
                         language=language,
                         stderr=f"Piston API Error: Too many rate limit retries.",
                         version=version,
                         status="piston_rate_limited"
                     )

            elif not response.ok:
                 return await send_error(
                     channel,
                     message=f"Piston API returned error status {response.status_code} for job ID {job_id}: {response.text}",
                     job_id=job_id,
                     language=language,
                     stderr=f"Piston API Error: Status {response.status_code}",
                     version=version,
                     status=f"piston_http_error_{response.status_code}"
                 )

            # --- Process Piston API Response (assuming 2xx status) ---
            try:
                execution_result = response.json()

                run_stage = execution_result.get("run")
                compile_stage = execution_result.get("compile")

                status_str = "success" if run_stage and run_stage.get("code") == 0 else "error"
                message_str = None
                if run_stage and run_stage.get("signal"):
                    message_str = f"Signal: {run_stage.get('signal')}"
                elif compile_stage and compile_stage.get("stderr"):
                    message_str = f"Compile Error: {compile_stage.get('stderr')}"
                elif run_stage and run_stage.get("stderr"):
                    message_str = f"Runtime Error: {run_stage.get('stderr')}"

                result_payload = {
                    "job_id": job_id,
                    "stdout": run_stage.get("stdout") if run_stage else None,
                    "stderr": run_stage.get("stderr") if run_stage else None,
                    "compile_output": compile_stage.get("output") if compile_stage else None,
                    "compile_stderr": compile_stage.get("stderr") if compile_stage else None,
                    "language": execution_result.get("language"),
                    "version": execution_result.get("version"),
                    "status": status_str,
                    "message": message_str,
                    "fail": False
                }

                await send_result_to_queue(channel, result_payload)

            except json.JSONDecodeError:
                return await send_error(
                    channel,
                    message=f"Failed to decode JSON response from Piston API for job ID {job_id}: {response.text}",
                    job_id=job_id,
                    language=language,
                    stderr="Feeder internal error: Failed to decode Piston API response.",
                    version=version,
                    status="piston_response_error"
                )

            except Exception as e:
                return await send_error(
                    channel,
                    message=f"An unexpected error occurred while processing Piston response for job ID {job_id}: {e}",
                    job_id=job_id,
                    language=language,
                    stderr=f"Feeder internal error processing Piston response: {e}",
                    version=version,
                    status="feeder_processing_error"
                )

        except json.JSONDecodeError:
            return await send_error(
                channel,
                message=f"Failed to decode JSON message: {message.body}",
                job_id=job_id or "",
                language=language,
                stderr=f"Feeder internal error: Failed to decode message.",
                version=None,
                status="feeder_error"
            )

        except Exception as e:
            return await send_error(
                channel,
                message=f"An unexpected error occurred while processing message for job ID {job_id}: {e}",
                job_id=job_id or "",
                language=language,
                stderr=f"Feeder internal error: {e}",
                version=None,
                status="feeder_error"
            )


# --- Message Processing Callback (Wrapper) ---
async def on_message(channel: AbstractChannel, message: AbstractIncomingMessage):
     await submit(channel, message)


# --- Main Consumer Function ---
async def consume_tasks():
    # --- Fetch and Map Piston Runtimes on Startup ---
    runtimes_data = fetch_piston_runtimes()
    if runtimes_data is None:
        logger.critical("Failed to fetch Piston runtimes. Cannot start feeder service.")
        sys.exit(1) # Exit if runtimes cannot be fetched

    # Populate the global language_version_map
    global language_version_map
    for runtime in runtimes_data:
        lang = runtime.get("language")
        version = runtime.get("version")
        aliases = runtime.get("aliases", [])
        if lang and version:
            # Map the main language name
            language_version_map[lang.lower()] = version
            # Map aliases
            for alias in aliases:
                language_version_map[alias.lower()] = version
    logger.info(f"Created language version map with {len(language_version_map)} entries.")


    connection = None
    try:
        connection = await get_rabbitmq_connection()
        if connection is None:
             logger.error("Failed to get RabbitMQ connection. Exiting.")
             return

        channel = await connection.channel()

        await channel.set_qos(prefetch_count=5)

        task_queue = await channel.declare_queue(TASK_QUEUE, durable=True)

        await channel.declare_queue(RESULTS_QUEUE, durable=True)

        logger.info(f"Waiting for messages on queue: {TASK_QUEUE}")

        await task_queue.consume(lambda x: on_message(channel, x))

        await asyncio.Future()

    except Exception as e:
        logger.error(f"Error in consumer setup or running: {e}", exc_info=True)
    finally:
        if connection:
            try:
                await connection.close()
                logger.info("RabbitMQ connection closed.")
            except Exception as close_error:
                logger.error(f"Error closing RabbitMQ connection: {close_error}")


if __name__ == "__main__":
    try:
        asyncio.run(consume_tasks())
    except KeyboardInterrupt:
        logger.info("Feeder service stopped by user.")
    except Exception as main_error:
        logger.error(f"An error occurred in the main execution block: {main_error}", exc_info=True)
