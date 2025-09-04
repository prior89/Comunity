import asyncio
import aiohttp
import time
import statistics

async def test_performance():
    print("AI News Personalization Performance Test")
    print("=" * 50)
    
    BASE_URL = "http://localhost:8000"
    response_times = []
    success_count = 0
    error_count = 0
    
    async with aiohttp.ClientSession() as session:
        # Get test article
        async with session.get(f"{BASE_URL}/api/news/articles?limit=1") as resp:
            articles = await resp.json()
            if not articles.get("articles"):
                print("No articles found for testing")
                return
            article_id = articles["articles"][0]["id"]
            print(f"Test Article ID: {article_id}")
        
        # Test 10 personalization requests
        for i in range(10):
            start = time.time()
            try:
                async with session.post(
                    f"{BASE_URL}/api/news/personalize",
                    headers={"Content-Type": "application/json"},
                    json={
                        "article_id": article_id,
                        "user_id": f"demo_investor_{i}"
                    }
                ) as resp:
                    end = time.time()
                    duration = (end - start) * 1000  # ms
                    
                    if resp.status == 200:
                        result = await resp.json()
                        if result.get("personalized_article"):
                            success_count += 1
                            response_times.append(duration)
                            content_len = len(result["personalized_article"])
                            provider = result.get("provider", "unknown")
                            print(f"Test {i+1:2d}: {duration:6.0f}ms | {provider:15s} | {content_len:4d} chars | SUCCESS")
                        else:
                            error_count += 1
                            print(f"Test {i+1:2d}: {duration:6.0f}ms | Empty content | FAILED")
                    else:
                        error_count += 1
                        print(f"Test {i+1:2d}: {duration:6.0f}ms | HTTP {resp.status} | FAILED")
                        
            except Exception as e:
                end = time.time()
                duration = (end - start) * 1000
                error_count += 1
                print(f"Test {i+1:2d}: {duration:6.0f}ms | Exception: {str(e)[:30]} | FAILED")
            
            await asyncio.sleep(0.5)  # Rate limiting

    # Calculate metrics
    print("\n" + "=" * 50)
    print("PERFORMANCE RESULTS")
    print("=" * 50)
    
    if response_times:
        sorted_times = sorted(response_times)
        p50 = statistics.median(sorted_times)
        p95_idx = int(len(sorted_times) * 0.95)
        p95 = sorted_times[min(p95_idx, len(sorted_times) - 1)]
        avg = statistics.mean(sorted_times)
        
        print(f"Response Times:")
        print(f"  p50 (median): {p50:6.0f}ms")
        print(f"  p95 (95th):   {p95:6.0f}ms")  
        print(f"  Average:      {avg:6.0f}ms")
        print(f"  Min:          {min(sorted_times):6.0f}ms")
        print(f"  Max:          {max(sorted_times):6.0f}ms")
        print()
    
    total = success_count + error_count
    success_rate = (success_count / total * 100) if total > 0 else 0
    
    print(f"Success Rate: {success_count}/{total} ({success_rate:.1f}%)")
    print()
    
    # Target evaluation
    print("TARGET EVALUATION:")
    if response_times:
        print(f"  p50 target 7-9s:  {'PASS' if 7000 <= p50 <= 9000 else 'FAIL'} ({p50:.0f}ms)")
        print(f"  p95 target ≤15s: {'PASS' if p95 <= 15000 else 'FAIL'} ({p95:.0f}ms)")
    print(f"  Success ≥98%:     {'PASS' if success_rate >= 98 else 'FAIL'} ({success_rate:.1f}%)")

if __name__ == "__main__":
    asyncio.run(test_performance())