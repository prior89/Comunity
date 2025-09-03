# cgi.py — Python 3.13에서 제거된 cgi 모듈의 최소 대체
# feedparser가 사용하는 건 parse_header 하나뿐이라 간단 셈이면 충분합니다.

from typing import Tuple, Dict

def parse_header(line: str) -> Tuple[str, Dict[str, str]]:
    # 매우 단순한 헤더 파서: 'type/subtype; k1=v1; k2="v 2"' 형태만 처리
    parts = [p.strip() for p in (line or "").split(";")]
    value = (parts[0].strip().lower() if parts else "")
    params: Dict[str, str] = {}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            params[k.strip().lower()] = v.strip().strip('"')
    return value, params