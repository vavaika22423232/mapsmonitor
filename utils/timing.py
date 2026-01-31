"""
Timing utilities.
"""
import time
from contextlib import contextmanager
from typing import Iterator


@contextmanager
def timed(label: str) -> Iterator[None]:
    """Context manager to measure execution time."""
    start = time.time()
    try:
        yield
    finally:
        elapsed = (time.time() - start) * 1000
        print(f"[TIMER] {label}: {elapsed:.2f} ms")
