"""
Performance Test Script

This script tests the performance improvements of the API endpoints.
"""

import httpx
import time
import asyncio
from statistics import mean, median

async def test_endpoint(client: httpx.AsyncClient, url: str, name: str, iterations: int = 5):
    """Test an endpoint and return timing statistics."""
    times = []
    
    print(f"Testing {name} ({url})...")
    
    for i in range(iterations):
        start_time = time.time()
        try:
            response = await client.get(url)
            end_time = time.time()
            
            if response.status_code == 200:
                duration = (end_time - start_time) * 1000  # Convert to milliseconds
                times.append(duration)
                print(f"  Run {i+1}: {duration:.1f}ms")
            else:
                print(f"  Run {i+1}: Error {response.status_code}")
                
        except Exception as e:
            print(f"  Run {i+1}: Exception {str(e)}")
    
    if times:
        avg_time = mean(times)
        median_time = median(times)
        min_time = min(times)
        max_time = max(times)
        
        print(f"  Results: Avg={avg_time:.1f}ms, Median={median_time:.1f}ms, Min={min_time:.1f}ms, Max={max_time:.1f}ms")
        return {
            'name': name,
            'url': url,
            'avg_time': avg_time,
            'median_time': median_time,
            'min_time': min_time,
            'max_time': max_time,
            'times': times
        }
    else:
        print(f"  No successful requests for {name}")
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
        ("/recommendations/1?limit=10", "Recommendations (game_id=1)")
    ]
    
    results = []
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for url, name in endpoints:
            result = await test_endpoint(client, f"{base_url}{url}", name)
            if result:
                results.append(result)
            print()
    
    # Summary
    print("=" * 60)
    print("PERFORMANCE TEST SUMMARY")
    print("=" * 60)
    
    for result in results:
        print(f"{result['name']:25} | Avg: {result['avg_time']:6.1f}ms | Median: {result['median_time']:6.1f}ms")
    
    print("=" * 60)
    print("Expected improvements:")
    print("- Games list: Should be 50-70% faster due to optimized queries and indexes")
    print("- Mechanics: Should be 80-90% faster due to caching")
    print("- Filter options: Should be 80-90% faster due to caching")
    print("- Overall: 40-60% improvement in response times")

if __name__ == "__main__":
    asyncio.run(main()) 