"""
AI 뉴스 개인화 플랫폼 성능 테스트
핵심 지표: p50, p95 응답시간, 성공률 측정
"""
import asyncio
import aiohttp
import time
import statistics
import json
from typing import List, Dict

# 테스트 설정
BASE_URL = "http://localhost:8000"  # 로컬 테스트
TEST_CYCLES = 20  # 테스트 횟수
ROLES = ["투자자", "사업가", "직장인"]

class PerformanceMetrics:
    def __init__(self):
        self.response_times = []
        self.success_count = 0
        self.error_count = 0
        self.error_details = []

async def test_personalization_performance():
    """개인화 성능 테스트"""
    print("🚀 AI 뉴스 개인화 플랫폼 성능 테스트 시작")
    print(f"📊 테스트 설정: {TEST_CYCLES}회 x {len(ROLES)}개 역할 = {TEST_CYCLES * len(ROLES)}회 총 테스트")
    print("-" * 60)
    
    metrics = PerformanceMetrics()
    
    async with aiohttp.ClientSession() as session:
        # 1. 기사 목록 가져오기
        async with session.get(f"{BASE_URL}/api/news/articles?limit=1") as resp:
            articles_data = await resp.json()
            if not articles_data.get("articles"):
                print("❌ 테스트할 기사가 없습니다")
                return
            
            article = articles_data["articles"][0]
            print(f"📰 테스트 기사: {article['title'][:50]}...")
            print(f"📝 기사 ID: {article['id']}")
            print()

        # 2. 성능 테스트 실행
        for cycle in range(TEST_CYCLES):
            for role_idx, role in enumerate(ROLES):
                user_id = f"demo_test_{role}_{cycle}"
                
                # 개인화 API 호출 시간 측정
                start_time = time.time()
                
                try:
                    async with session.post(
                        f"{BASE_URL}/api/news/personalize",
                        headers={"Content-Type": "application/json"},
                        json={
                            "article_id": article["id"],
                            "user_id": user_id
                        }
                    ) as resp:
                        end_time = time.time()
                        response_time = (end_time - start_time) * 1000  # ms
                        
                        if resp.status == 200:
                            result = await resp.json()
                            if result.get("personalized_article"):
                                metrics.success_count += 1
                                metrics.response_times.append(response_time)
                                
                                # 실시간 로그
                                provider = result.get("provider", "unknown")
                                content_length = len(result.get("personalized_article", ""))
                                print(f"✅ #{cycle+1}-{role_idx+1} | {role} | {response_time:.0f}ms | {provider} | {content_length}자")
                            else:
                                metrics.error_count += 1
                                metrics.error_details.append(f"Empty content: {role}")
                                print(f"⚠️  #{cycle+1}-{role_idx+1} | {role} | {response_time:.0f}ms | Empty response")
                        else:
                            metrics.error_count += 1
                            error_text = await resp.text()
                            metrics.error_details.append(f"HTTP {resp.status}: {role}")
                            print(f"❌ #{cycle+1}-{role_idx+1} | {role} | {response_time:.0f}ms | HTTP {resp.status}")
                            
                except Exception as e:
                    end_time = time.time()
                    response_time = (end_time - start_time) * 1000
                    metrics.error_count += 1
                    metrics.error_details.append(f"Exception: {str(e)[:50]}")
                    print(f"💥 #{cycle+1}-{role_idx+1} | {role} | {response_time:.0f}ms | Exception: {e}")
                
                # 요청 간격 (API 부하 방지)
                await asyncio.sleep(0.1)

    # 3. 성능 지표 계산
    print()
    print("=" * 60)
    print("📊 성능 분석 결과")
    print("=" * 60)
    
    if metrics.response_times:
        sorted_times = sorted(metrics.response_times)
        p50 = statistics.median(sorted_times)
        p95_idx = int(len(sorted_times) * 0.95)
        p95 = sorted_times[min(p95_idx, len(sorted_times) - 1)]
        avg_time = statistics.mean(sorted_times)
        min_time = min(sorted_times)
        max_time = max(sorted_times)
        
        print(f"⚡ 응답시간 분석:")
        print(f"   • p50 (중간값): {p50:.1f}ms")
        print(f"   • p95 (95%ile): {p95:.1f}ms") 
        print(f"   • 평균: {avg_time:.1f}ms")
        print(f"   • 최소: {min_time:.1f}ms")
        print(f"   • 최대: {max_time:.1f}ms")
        print()
    
    total_tests = metrics.success_count + metrics.error_count
    success_rate = (metrics.success_count / total_tests * 100) if total_tests > 0 else 0
    
    print(f"✅ 성공률: {metrics.success_count}/{total_tests} ({success_rate:.1f}%)")
    print(f"❌ 실패수: {metrics.error_count}")
    
    if metrics.error_details:
        print(f"\n🔍 에러 상세:")
        for error in set(metrics.error_details[:5]):  # 중복 제거, 최대 5개
            print(f"   • {error}")
    
    # 4. 목표 지표 평가
    print("\n🎯 목표 대비 평가:")
    if metrics.response_times:
        print(f"   • p50 목표 7-9초: {'✅ 달성' if 7000 <= p50 <= 9000 else '❌ 미달성'} ({p50:.0f}ms)")
        print(f"   • p95 목표 ≤15초: {'✅ 달성' if p95 <= 15000 else '❌ 미달성'} ({p95:.0f}ms)")
    print(f"   • 성공률 ≥98%: {'✅ 달성' if success_rate >= 98 else '❌ 미달성'} ({success_rate:.1f}%)")

if __name__ == "__main__":
    asyncio.run(test_personalization_performance())