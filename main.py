import os
import sys
import signal
import asyncio
from dotenv import load_dotenv
from loguru import logger

from functions import create_resource_in_executable_dir, get_abspath
from manager import EtsyReger

log_folder = "logs"
os.makedirs(log_folder, exist_ok=True)
logger.add(
    os.path.join(log_folder, "file_{time}.log"),
    rotation="10 MB",
    retention="10 days",
    compression="zip",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)

settings_path = create_resource_in_executable_dir("config/settings.env")
proxies_path = create_resource_in_executable_dir("config/proxies.txt")
recaptcha_tokens_path = create_resource_in_executable_dir("config/recaptcha_tokens.json")

load_dotenv(settings_path)

# The Go binary acts as a TLS proxy, rewriting the JA3/JA4 fingerprint of each
# outgoing request to mimic a real Chrome browser and bypass Etsy's TLS inspection.
async def start_go_server() -> asyncio.subprocess.Process:
    go_binary_path = get_abspath("tls_client_app.exe")
    process = await asyncio.create_subprocess_exec(
        go_binary_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    await asyncio.sleep(2)
    return process

async def shutdown(process: asyncio.subprocess.Process):
    if process.returncode is None:
        process.terminate()
        await process.wait()
    logger.info("Go server stopped")

async def main():
    anymessage_api_key = os.getenv('ANYMESSAGE', '')
    rucaptcha_api_key = os.getenv('RUCAPTCHA', '')
    threads_num = os.getenv('THREADS_NUM', '10')

    if not anymessage_api_key or not rucaptcha_api_key:
        logger.error("Missing API keys in .env file. Please configure and restart.")
        return

    with open(proxies_path, 'r') as f:
        proxies = [line.strip() for line in f if line.strip()]

    if not proxies:
        logger.error("No proxies found in config/proxies.txt")
        return

    try:
        threads_num = int(threads_num)
    except ValueError:
        logger.error("THREADS_NUM must be an integer")
        return

    reger = EtsyReger(
        proxies=proxies,
        anymessage_api_key=anymessage_api_key,
        rucaptcha_api_key=rucaptcha_api_key,
        threads_num=threads_num,
    )

    go_process = await start_go_server()

    def signal_handler(sig, frame):
        logger.info("Received interrupt signal, shutting down...")
        asyncio.create_task(shutdown(go_process))
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        await reger.mainloop()
    except Exception as e:
        logger.error(f"Fatal error in main loop: {e}")
    finally:
        await shutdown(go_process)
        await reger.close()

if __name__ == "__main__":
    asyncio.run(main())