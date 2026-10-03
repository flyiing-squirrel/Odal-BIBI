import logging

from tavily import TavilyClient

from app.providers.base import SearchHit

logger = logging.getLogger(__name__)

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
            raise SearchError(f"검색 실패 ({query}): {error}") from error

        return [
            SearchHit(
                title=item.get("title") or item["url"],
                url=item["url"],
                content=(item.get("content") or "")[:MAX_CONTENT_CHARS],
            )
            for item in result.get("results", [])
            if item.get("url")
        ]
