from datetime import UTC, datetime, timedelta
from typing import ClassVar, Protocol

from app.providers.base import ScheduleRecord


class OfficialScheduleAdapter(Protocol):
    """Adapter contract for a certification's official schedule site."""

    def fetch(self, certification_code: str, target_period: str | None) -> list[ScheduleRecord]:
        """Parse or call the official source and return normalized schedule records."""


class UnconfiguredOfficialScheduleAdapter:
    """Return no dates until a source has verified official schedule records."""

    def fetch(self, certification_code: str, target_period: str | None) -> list[ScheduleRecord]:
        return []


class MockOfficialScheduleAdapter:
    """Example adapter with fake-but-realistically shaped schedule data.

    Replace this class with an adapter for Q-Net, AWS Training, or another official
    site. The rest of the application only depends on OfficialScheduleAdapter.
    """

    _URLS: ClassVar[dict[str, str]] = {
        "INFO_PROCESSOR_ENGINEER": "https://www.q-net.or.kr/crf005.do?id=crf00503&jmCd=1320",
        "SQLD": "https://www.dataq.or.kr/www/accept/schedule.do",
        "ADSP": "https://www.dataq.or.kr/www/accept/schedule.do",
        "BIGDATA_ENGINEER": "https://www.q-net.or.kr/crf005.do?id=crf00503&jmCd=1321",
        "AWS_SAA": "https://aws.amazon.com/certification/certified-solutions-architect-associate/",
        "SOCIETY_ANALYST_2": "https://www.q-net.or.kr/crf005.do?id=crf00503&jmCd=1740",
    }

    def fetch(self, certification_code: str, target_period: str | None) -> list[ScheduleRecord]:
        today = datetime.now(UTC).date()
        records: list[ScheduleRecord] = []
        for round_number in range(1, 4):
            exam_date = today + timedelta(days=35 + (round_number - 1) * 56)
            registration_start = exam_date - timedelta(days=42)
            registration_end = exam_date - timedelta(days=24)
            records.append(
                ScheduleRecord(
                    exam_name=f"{certification_code} 모의 연간 일정 {round_number}회",
                    registration_start=registration_start,
                    registration_end=registration_end,
                    exam_date=exam_date,
                    result_date=exam_date + timedelta(days=14),
                    status="upcoming",
                    source_name="Mock Official Schedule Adapter",
                    source_url=self._URLS.get(certification_code, "https://example.com/official"),
                    details=(
                        f"{target_period or '미정'} 목표 검토용 예시 일정입니다. 실제 서비스에서는 공식 사이트에서 "
                        "최신 공고를 조회해 교체합니다."
                    ),
                )
            )
        return records


class OfficialSiteScheduleProvider:
    """Provider facade that makes the official-site adapter swappable."""

    def __init__(self, adapter: OfficialScheduleAdapter):
        self.adapter = adapter

    def get_schedules(self, certification_code: str, target_period: str | None) -> list[ScheduleRecord]:
        return self.adapter.fetch(certification_code, target_period)

