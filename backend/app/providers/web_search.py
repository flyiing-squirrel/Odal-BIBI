import ipaddress
from urllib.parse import urlsplit

from tavily import TavilyClient

from app.providers.base import SearchHit

# 시험일정·응시료 등 공식 정보는 주관기관 사이트에서 먼저 찾는다
OFFICIAL_DOMAINS = [
    "q-net.or.kr",          # 한국산업인력공단 (국가기술자격)
    "dataq.or.kr",          # 한국데이터산업진흥원 (SQLD, ADsP 등)
    "license.kpc.or.kr",    # 한국생산성본부 (ERP, ITQ 등)
    "license.korcham.net",  # 대한상공회의소 (컴활, 전산회계 등)
    "historyexam.go.kr",    # 한국사능력검정시험
    "aws.amazon.com",       # AWS 자격증
]

MAX_CONTENT_CHARS = 1500


class SearchError(RuntimeError):
    """검색 API 호출 실패."""


class TavilySearchProvider:
    def __init__(self, api_key: str):
        self._client = TavilyClient(api_key=api_key)

    def search(self, query: str, *, official_only: bool = False, max_results: int = 4) -> list[SearchHit]:
        try:
            result = self._client.search(
                query,
                max_results=max_results,
                include_domains=OFFICIAL_DOMAINS if official_only else None,
            )
        except Exception as error:
            raise SearchError("Tavily 검색 실패") from error

        result_items = result.get("results", []) if isinstance(result, dict) else []
        if not isinstance(result_items, list):
            return []

        hits = []
        for item in result_items:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            if not is_safe_search_url(url):
                continue
            title = item.get("title") if isinstance(item.get("title"), str) else ""
            content = item.get("content") if isinstance(item.get("content"), str) else ""
            hits.append(SearchHit(title=title[:300] or url, url=url, content=content[:MAX_CONTENT_CHARS]))
        return hits


def is_safe_search_url(value: object) -> bool:
    if not isinstance(value, str) or len(value) > 2000 or "\\" in value:
        return False
    if any(ord(character) < 32 for character in value):
        return False
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or not hostname:
        return False
    if parsed.username is not None or parsed.password is not None or port not in {None, 80, 443}:
        return False
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        return False
    try:
        normalized_host = hostname.encode("idna").decode("ascii").lower().rstrip(".")
    except UnicodeError:
        return False
    return "." in normalized_host
