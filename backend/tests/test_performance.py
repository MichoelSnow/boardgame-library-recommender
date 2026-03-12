"""
Performance Test Script

This script tests the performance improvements of the API endpoints.
"""

import asyncio
import logging
import time
from statistics import mean, median

import httpx


logger = logging.getLogger(__name__)


async def benchmark_endpoint(
    client: httpx.AsyncClient, url: str, name: str, iterations: int = 5
):
    """Benchmark an endpoint and return timing statistics."""
    times = []

    logger.info("Testing %s (%s)...", name, url)

    for i in range(iterations):
        start_time = time.time()
        try:
            response = await client.get(url)
            end_time = time.time()

            if response.status_code == 200:
                duration = (end_time - start_time) * 1000  # Convert to milliseconds
                times.append(duration)
                logger.info("  Run %d: %.1fms", i + 1, duration)
            else:
                logger.info("  Run %d: Error %d", i + 1, response.status_code)

        except Exception as exc:
            logger.info("  Run %d: Exception %s", i + 1, str(exc))

    if times:
        avg_time = mean(times)
        median_time = median(times)
        min_time = min(times)
        max_time = max(times)

        logger.info(
            "  Results: Avg=%.1fms, Median=%.1fms, Min=%.1fms, Max=%.1fms",
            avg_time,
            median_time,
            min_time,
            max_time,
        )
        return {
            "name": name,
            "url": url,
            "avg_time": avg_time,
            "median_time": median_time,
            "min_time": min_time,
            "max_time": max_time,
            "times": times,
        }
    else:
        logger.info("  No successful requests for %s", name)
        return None


async def main():
    """Run performance tests."""
    base_url = "http://localhost:8000"

    # Test endpoints
    endpoints = [
        ("/games/?limit=24&skip=0&sort_by=rank", "Games List (Rank)"),
        ("/games/?limit=24&skip=0&sort_by=average", "Games List (Average)"),
        ("/mechanics/", "Mechanics List"),
        ("/filter-options/", "Filter Options"),
        ("/games/1", "Single Game"),
    ]

    results = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        for url, name in endpoints:
            result = await benchmark_endpoint(client, f"{base_url}{url}", name)
            if result:
                results.append(result)
            logger.info("")

    # Summary
    logger.info("=" * 60)
    logger.info("PERFORMANCE TEST SUMMARY")
    logger.info("=" * 60)

    for result in results:
        logger.info(
            "%-25s | Avg: %6.1fms | Median: %6.1fms",
            result["name"],
            result["avg_time"],
            result["median_time"],
        )

    logger.info("=" * 60)
    logger.info("Expected improvements:")
    logger.info(
        "- Games list: Should be 50-70%% faster due to optimized queries and indexes"
    )
    logger.info("- Mechanics: Should be 80-90%% faster due to caching")
    logger.info("- Filter options: Should be 80-90%% faster due to caching")
    logger.info("- Overall: 40-60%% improvement in response times")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    asyncio.run(main())
