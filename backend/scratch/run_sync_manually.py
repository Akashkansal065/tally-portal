import asyncio
import logging
import sys

# Configure logging to print to stdout
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.INFO)

# Import background task
from app.routers.sync import run_once_sync_background

async def main():
    print("Running run_once_sync_background manually...")
    try:
        await run_once_sync_background(company_id=1)
        print("Done!")
    except Exception as e:
        print("Failed with exception:", str(e))
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
