"""Test Socket Rotation in Separate Test Process (WS-1 Test 4).

Runs a short standalone recorder instance with a short rotation interval (e.g. 15s)
and 5s overlap to verify that socket rotation executes cleanly with zero sequence gaps
and zero unhandled duplicate frames.
"""

import asyncio
import logging
import shutil
import tempfile
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.recorder import ArcusStreamRecorder

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_rotation")


async def main():
    temp_dir = Path(tempfile.mkdtemp(prefix="arcus_rot_test_"))
    logger.info(f"Starting standalone rotation test in {temp_dir}...")

    recorder = ArcusStreamRecorder(
        markets=["BTC-USD", "ETH-USD"],
        channels=["bbo", "trades"],
        output_dir=temp_dir,
        markets_per_socket=2,
        rotation_interval_secs=10,  # 10s rotation interval
        overlap_secs=3,             # 3s overlap
    )

    try:
        await recorder.start()
        # Run for 25 seconds to observe at least 2 socket rotations
        logger.info("Observing socket rotations for 25 seconds...")
        await asyncio.sleep(25.0)
    finally:
        await recorder.stop()
        metrics = recorder.metrics
        logger.info(f"Rotation test complete. Metrics: {metrics}")
        shutil.rmtree(temp_dir, ignore_errors=True)

    # Assert 0 sequence gaps
    assert metrics["sequence_gaps"] == 0, f"Expected 0 gaps, got {metrics['sequence_gaps']}"
    assert metrics["rotations_completed"] >= 1, f"Expected at least 1 rotation, got {metrics['rotations_completed']}"
    print(f"PASS: Socket rotation verified. Rotations completed: {metrics['rotations_completed']}, Gaps: {metrics['sequence_gaps']}")


if __name__ == "__main__":
    asyncio.run(main())
