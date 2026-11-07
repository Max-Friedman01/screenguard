import asyncio
from pathlib import Path

import tetherto.qvac_sdk as qvac
from tetherto.qvac_sdk import Client


async def main():
    package_dir = Path(qvac.__file__).resolve().parent
    worker_path = (
        package_dir
        / "_bundle"
        / "worker"
        / "dist"
        / "src"
        / "worker"
        / "index.js"
    )

    print("Python package:", package_dir)
    print("Worker path:", worker_path)
    print("Worker exists:", worker_path.exists())
    print("Starting QVAC worker...")

    if not worker_path.exists():
        raise FileNotFoundError(worker_path)

    async with Client(
        worker_path=str(worker_path),
    ):
        print("QVAC worker connected successfully")

    print("QVAC worker closed successfully")


if __name__ == "__main__":
    asyncio.run(main())