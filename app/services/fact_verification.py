"""
자동 팩트 검증 시스템
"""
import re
from typing import Dict, List, Any
from ..models.schemas import ExtractedFacts
from ..core.logging import get_logger

logger = get_logger("fact_verification")

class FactVerifier:
    """팩트 자동 검증 시스템"""
    
    def __init__(self):
        # 검증 규칙들
        self.date_patterns = [
            r'\d{4}년\s*\d{1,2}월\s*\d{1,2}일',
            r'\d{1,2}일\(.*\)',
            r'어제|오늘|내일',
            r'\d{1,2}시\s*\d{1,2}분'
        ]
        
        self.number_patterns = [
            r'\d+[억만천]?\s*원',
            r'\d+\.?\d*%',
            r'\d+[개명건]',
            r'\d+년|월|일|시간'
        ]
        
        self.location_keywords = [
            '서울', '부산', '대구', '인천', '광주', '대전', '울산',
            '한국', '미국', '중국', '일본', '러시아', '유럽',
            '청와대', '국회', '법원', '검찰청'
        ]

    async def verify_facts(self, facts: ExtractedFacts, original_text: str) -> Dict[str, Any]:
        """팩트 자동 검증 및 신뢰도 점수 계산"""
        
        verification_result = {
            "overall_confidence": 0.0,
            "verified_facts": [],
            "warnings": [],
            "license_safe": True
        }
        
        try:
            # 1. WHO 검증 (인명/기관명)
            who_score = await self._verify_who(facts.who, original_text)
            
            # 2. WHEN 검증 (날짜/시간)  
            when_score = await self._verify_when(facts.when, original_text)
            
            # 3. WHERE 검증 (지명/장소)
            where_score = await self._verify_where(facts.where, original_text)
            
            # 4. WHAT 검증 (핵심 사건)
            what_score = await self._verify_what(facts.what, original_text)
            
            # 5. 수치 정보 검증
            numbers_score = await self._verify_numbers(facts.numbers, original_text)
            
            # 전체 신뢰도 계산
            scores = [who_score, when_score, where_score, what_score, numbers_score]
            verification_result["overall_confidence"] = sum(scores) / len(scores)
            
            # 검증된 팩트 목록
            if who_score > 0.7: verification_result["verified_facts"].extend(facts.who[:3])
            if when_score > 0.7 and facts.when: verification_result["verified_facts"].append(facts.when)
            if where_score > 0.7: verification_result["verified_facts"].extend(facts.where[:2])
            if what_score > 0.7 and facts.what: verification_result["verified_facts"].append(facts.what[:100])
            
            # 경고 생성
            if who_score < 0.5: verification_result["warnings"].append("인물/기관 정보 불확실")
            if when_score < 0.5: verification_result["warnings"].append("시간 정보 불확실")
            if verification_result["overall_confidence"] < 0.6: verification_result["warnings"].append("전체 신뢰도 낮음")
            
            logger.info("팩트 검증 완료", 
                       overall_confidence=verification_result["overall_confidence"],
                       warnings_count=len(verification_result["warnings"]))
            
        except Exception as e:
            logger.error("팩트 검증 실패", error=str(e))
            verification_result["warnings"].append(f"검증 시스템 오류: {str(e)[:100]}")
            
        return verification_result

    async def _verify_who(self, who_list: List[str], text: str) -> float:
        """WHO 검증: 인명/기관명이 원문에 있는지"""
        if not who_list:
            return 0.5
        
        found_count = 0
        for person in who_list[:5]:  # 최대 5명만 검증
            if person and len(person) > 1:
                # 원문에서 해당 인명 찾기
                if person in text or any(part in text for part in person.split() if len(part) > 1):
                    found_count += 1
        
        return min(found_count / max(len(who_list), 1), 1.0)

    async def _verify_when(self, when_info: str, text: str) -> float:
        """WHEN 검증: 시간 정보 패턴 매칭"""
        if not when_info:
            return 0.5
        
        # 원문에서 날짜 패턴 찾기
        for pattern in self.date_patterns:
            if re.search(pattern, text):
                if when_info in text or any(part in text for part in when_info.split() if len(part) > 2):
                    return 0.9
        
        return 0.3

    async def _verify_where(self, where_list: List[str], text: str) -> float:
        """WHERE 검증: 지명 정보 확인"""
        if not where_list:
            return 0.5
            
        found_count = 0
        for location in where_list[:3]:  # 최대 3곳만 검증
            if location and any(keyword in location for keyword in self.location_keywords):
                if location in text:
                    found_count += 1
        
        return min(found_count / max(len(where_list), 1), 1.0)

    async def _verify_what(self, what_info: str, text: str) -> float:
        """WHAT 검증: 핵심 사건 일치도"""
        if not what_info:
            return 0.5
        
        # 핵심 단어 추출 (3글자 이상)
        keywords = [word for word in what_info.split() if len(word) >= 3]
        found_keywords = sum(1 for keyword in keywords if keyword in text)
        
        return min(found_keywords / max(len(keywords), 1), 1.0) if keywords else 0.5

    async def _verify_numbers(self, numbers: Dict[str, str], text: str) -> float:
        """수치 정보 검증"""
        if not numbers:
            return 0.5
            
        verified_count = 0
        for key, value in numbers.items():
            if value and any(re.search(pattern, value) for pattern in self.number_patterns):
                if value in text:
                    verified_count += 1
        
        return min(verified_count / max(len(numbers), 1), 1.0)