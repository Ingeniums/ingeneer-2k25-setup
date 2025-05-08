
import asyncio
import json
import os
import logging
from aio_pika import connect_robust, Message
from aio_pika.abc import AbstractChannel, AbstractIncomingMessage
from pyston import PystonClient, File
import pyston
from pyston.client import Output

# --- Configuration ---
# RabbitMQ connection details
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "0.0.0.0")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")

# Queue names
TASK_QUEUE = os.getenv("TASK_QUEUE", "execution_tasks")
RESULTS_QUEUE = os.getenv("RESULTS_QUEUE", "execution_results")

# Piston API details
# Assuming Piston is accessible via a service name in the Docker network
PISTON_URL = os.getenv("PISTON_URL", "http://192.168.100.11:2000") # Using the provided URL

# Default limits and timeouts
DEFAULT_MEMORY_LIMIT = int(os.getenv("DEFAULT_MEMORY_LIMIT", -1))  # in MB
DEFAULT_COMPILE_TIMEOUT = int(os.getenv("DEFAULT_COMPILE_TIMEOUT", 10000)) # in milliseconds
DEFAULT_RUN_TIMEOUT = int(os.getenv("DEFAULT_RUN_TIMEOUT", 10000)) # in milliseconds

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- RabbitMQ Connection and Channel ---
async def get_rabbitmq_connection():
    """Establishes a robust connection to RabbitMQ."""
    TRIES = 5
    tried = 0
    connection = None
    while tried < TRIES:
        await asyncio.sleep(2 * tried)
        try:
            connection = await connect_robust(
                host=RABBITMQ_HOST,
                port=RABBITMQ_PORT,
                login=RABBITMQ_USER,
                password=RABBITMQ_PASSWORD,
                loop=asyncio.get_event_loop()
            )
            # logger.info("Successfully connected to RabbitMQ.") # Keep connection success log
            return connection
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
        tried += 1
    raise


# --- Helper to Send Result ---
async def send_result_to_queue(channel: AbstractChannel, result_payload: dict):
    """Sends the result payload to the results queue."""
    try:
        await channel.declare_queue(RESULTS_QUEUE, durable=True)
        await channel.default_exchange.publish(
            Message(json.dumps(result_payload).encode('utf-8')),
            routing_key=RESULTS_QUEUE
        )
    except Exception as publish_error:
         logger.error(f"Failed to publish result for job ID {result_payload.get('job_id')}: {publish_error}")


async def submit(channel: AbstractChannel, client: PystonClient, message: AbstractIncomingMessage):
    # Parse the incoming message
    payload = json.loads(message.body.decode('utf-8'))
    job_id = payload.get("job_id")
    code = payload.get("code")
    language = payload.get("language")
    memory_limit = payload.get("memory_limit", DEFAULT_MEMORY_LIMIT)
    compile_timeout = payload.get("compile_timeout", DEFAULT_COMPILE_TIMEOUT)
    run_timeout = payload.get("run_timeout", DEFAULT_RUN_TIMEOUT)

    if not job_id or not code or not language:
        logger.warning(f"Received invalid message format. Missing job_id, code, or language. Payload: {payload}")
        # Acknowledge the message as unprocessable
        await message.ack()
        return

    logger.info(memory_limit)
    logger.info(run_timeout)
    logger.info(compile_timeout)
        # --- Execute code using Piston ---
    execution_result: Output = await client.execute(
        language=language,
        files=[File(code)],
        compile_timeout=compile_timeout,
        run_timeout=run_timeout,
        compile_memory_limit=memory_limit, # Using memory_limit for compile stage
        run_memory_limit=memory_limit,     # Using memory_limit for run stage
    )
    logger.info(payload)

    # --- Prepare result message using the provided structure ---
    result_payload = {
        "job_id": job_id,
        "stdout": execution_result.run_stage.stdout if execution_result.run_stage else None,
        "stderr": execution_result.run_stage.stdrr if execution_result.run_stage else None, # Corrected from stdrr to stderr
        "compile_output": execution_result.compile_stage.output if execution_result.compile_stage else None,
        "compile_stderr": execution_result.compile_stage.stdrr if execution_result.compile_stage else None, # Corrected from stdrr to stderr
        "language": language,
        "version": execution_result.version,
        "status": "success" if execution_result.run_stage and execution_result.run_stage.code == 0 else "error",
        "message": execution_result.run_stage.signal if execution_result.run_stage and execution_result.run_stage.signal else None,
        "fail": False # Set fail to False on successful execution or Piston error
    }

    logger.info(result_payload)

    # --- Send result back to results queue ---
    await send_result_to_queue(channel, result_payload)

    # Acknowledge the message only after successfully sending the result
    await message.ack()

# --- Message Processing Callback ---
async def on_message(channel: AbstractChannel, client: PystonClient, message: AbstractIncomingMessage):
    """Callback function to process incoming messages from the task queue."""
    job_id = None # Initialize job_id outside try block
    language = 'unknown' # Initialize language outside try block
    try:
        return await submit(channel, client, message)

    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON message: {message.body}", exc_info=True)
        # Send a failed result back
        error_payload = {
            "job_id": job_id, # job_id might be None here if parsing failed
            "stdout": None,
            "stderr": f"Feeder internal error: Failed to decode message.",
            "compile_output": None,
            "compile_stderr": None,
            "language": language,
            "version": None,
            "status": "feeder_error",
            "message": "Invalid message format.",
            "fail": True # Set fail to True on decoding error
        }
        await send_result_to_queue(channel, error_payload)
        await message.ack() # Acknowledge the message as unprocessable

    except pyston.exceptions.TooManyRequests:
        loops = 1
        while True:
            try:
                print(f"Rate Limited {loops}")
                await asyncio.sleep(1)
                return await submit(channel, client, message)
            except pyston.exceptions.TooManyRequests:
                loops += 1
                continue

    except Exception as pe: # Using general Exception as PystonException import is commented out
        logger.error(f"Piston API error for job ID {job_id}: {pe}", exc_info=True)
        error_payload = {
            "job_id": job_id,
            "stdout": None,
            "stderr": f"Piston API Error: {pe}",
            "compile_output": None,
            "compile_stderr": None,
            "language": language,
            "version": None,
            "status": "piston_api_error",
            "message": str(pe),
            "fail": True # Set fail to True if Piston API call fails
        }
        await send_result_to_queue(channel, error_payload)
        await message.ack() # Acknowledge the message


# --- Main Consumer Function ---
async def consume_tasks():
    """Connects to RabbitMQ and starts consuming messages from the task queue."""
    connection = None
    # Instantiate PystonClient here once and pass it to the message handler
    piston_client = PystonClient(PISTON_URL)
    try:
        await piston_client.runtimes()
        logger.info("Connected to piston")
    except Exception as e:
        logger.error(f"Failed to connect to piston: {e}")
        raise
    try:
        connection = await get_rabbitmq_connection()
        if connection is None:
            return
        async with connection:
            channel = await connection.channel()

            await channel.set_qos(prefetch_count=5) # Process up to 5 messages concurrently

            queue = await channel.declare_queue(TASK_QUEUE, durable=True)


            logger.info(f"Waiting for messages on queue: {TASK_QUEUE}")

            await queue.consume(lambda x: on_message(channel, piston_client, x))

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
        if piston_client and hasattr(piston_client, 'close'):
            await piston_client.close_session() # Uncomment if PystonClient needs explicit closing


if __name__ == "__main__":
    # Run the asyncio event loop
    try:
        asyncio.run(consume_tasks())
    except KeyboardInterrupt:
        logger.info("Feeder service stopped by user.")
    except Exception as main_error:
        logger.error(f"An error occurred in the main execution block: {main_error}", exc_info=True)
    while True:
        continue
