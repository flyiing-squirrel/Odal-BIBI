import hashlib
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import quote, urlsplit

import requests
from google_auth_oauthlib.flow import Flow
from oauthlib.oauth2 import OAuth2Error

from app.core.config import Settings
from app.models import CertificationSchedule

CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.app.created"
GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URI = "https://oauth2.googleapis.com/revoke"
GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3"


class CalendarIntegrationError(Exception):
    pass


class CalendarReauthorizationRequired(CalendarIntegrationError):
    pass


@dataclass(frozen=True)
class ExchangedGoogleToken:
    access_token: str
    refresh_token: str | None
    scopes: tuple[str, ...]


class GoogleCalendarProvider:
    def __init__(self, settings: Settings):
        self.settings = settings

    def authorization_url(self, state: str) -> str:
        flow = self._flow([CALENDAR_SCOPE])
        authorization_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=state,
        )
        return authorization_url

    def exchange_code(self, code: str) -> ExchangedGoogleToken:
        flow = self._flow([CALENDAR_SCOPE])
        try:
            flow.fetch_token(code=code, timeout=15, allow_redirects=False)
        except (OAuth2Error, requests.RequestException, ValueError):
            raise CalendarIntegrationError("Google authorization could not be completed.") from None
        credentials = flow.credentials
        if not credentials.token:
            raise CalendarIntegrationError("Google did not return an access token.")
        return ExchangedGoogleToken(
            access_token=credentials.token,
            refresh_token=credentials.refresh_token,
            scopes=tuple(credentials.scopes or [CALENDAR_SCOPE]),
        )

    def create_calendar(self, access_token: str) -> tuple[str, str]:
        name = "Odal BIBI 자격증 일정"
        try:
            response = requests.post(
                f"{GOOGLE_CALENDAR_API}/calendars",
                headers=self._headers(access_token),
                json={"summary": name},
                timeout=10,
                allow_redirects=False,
            )
        except requests.RequestException:
            raise CalendarIntegrationError("Google Calendar is temporarily unavailable.") from None
        if response.status_code not in (200, 201):
            raise CalendarIntegrationError("A Google Calendar could not be created.")
        try:
            calendar_id = response.json()["id"]
        except (ValueError, KeyError, TypeError):
            raise CalendarIntegrationError("Google returned an invalid calendar response.") from None
        if not isinstance(calendar_id, str) or not calendar_id:
            raise CalendarIntegrationError("Google returned an invalid calendar response.")
        return calendar_id, name

    def refresh_access_token(self, refresh_token: str) -> str:
        try:
            response = requests.post(
                GOOGLE_TOKEN_URI,
                data={
                    "client_id": self.settings.google_client_id,
                    "client_secret": self.settings.google_client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
                timeout=10,
                allow_redirects=False,
            )
        except requests.RequestException:
            raise CalendarIntegrationError("Google Calendar is temporarily unavailable.") from None

        try:
            payload = response.json()
        except ValueError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        if response.status_code == 400 and payload.get("error") == "invalid_grant":
            raise CalendarReauthorizationRequired("Google Calendar authorization has expired.")
        if response.status_code != 200 or not isinstance(payload.get("access_token"), str):
            raise CalendarIntegrationError("Google Calendar authorization could not be refreshed.")
        return payload["access_token"]

    def upsert_exam_event(
        self,
        access_token: str,
        calendar_id: str,
        schedule: CertificationSchedule,
        event_id: str,
        existing_event_id: str | None = None,
    ) -> str:
        event = self._event_body(schedule, event_id)
        base_url = f"{GOOGLE_CALENDAR_API}/calendars/{quote(calendar_id, safe='')}/events"
        event_url = f"{base_url}/{quote(event_id, safe='')}"
        if existing_event_id:
            response = self._request("put", event_url, access_token, event)
            if response.status_code == 404:
                response = self._request("post", base_url, access_token, event)
                if response.status_code == 409:
                    response = self._request("put", event_url, access_token, event)
            if response.status_code not in (200, 201):
                raise CalendarIntegrationError("The Google Calendar event could not be updated.")
        else:
            response = self._request("post", base_url, access_token, event)
            if response.status_code == 409:
                response = self._request("put", event_url, access_token, event)
            if response.status_code not in (200, 201):
                raise CalendarIntegrationError("The Google Calendar event could not be created.")

        try:
            actual_event_id = response.json()["id"]
        except (ValueError, KeyError, TypeError):
            raise CalendarIntegrationError("Google returned an invalid event response.") from None
        if actual_event_id != event_id:
            raise CalendarIntegrationError("Google returned an unexpected event identifier.")
        return actual_event_id

    def revoke(self, refresh_token: str) -> bool:
        try:
            response = requests.post(
                GOOGLE_REVOKE_URI,
                data={"token": refresh_token},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10,
                allow_redirects=False,
            )
        except requests.RequestException:
            raise CalendarIntegrationError("Google authorization could not be revoked.") from None
        if response.status_code == 200:
            return True
        try:
            error = response.json().get("error")
        except (ValueError, AttributeError):
            error = None
        if response.status_code == 400 and error == "invalid_token":
            # Google reports an already expired or revoked credential this way.
            return True
        raise CalendarIntegrationError("Google authorization could not be revoked.")

    def _flow(self, scopes: list[str]) -> Flow:
        if not self.settings.google_oauth_configured:
            raise CalendarIntegrationError("Google Calendar is not configured.")
        try:
            redirect = urlsplit(self.settings.google_redirect_uri)
            redirect_host = redirect.hostname
            redirect_port = redirect.port
        except ValueError:
            raise CalendarIntegrationError("Google Calendar callback is not configured.") from None
        local_http = (
            self.settings.app_env == "local"
            and redirect.scheme == "http"
            and redirect_host in {"localhost", "127.0.0.1"}
        )
        if (
            (redirect.scheme != "https" and not local_http)
            or redirect.path != "/api/google/callback"
            or not redirect_host
            or redirect.username
            or redirect.password
            or redirect.query
            or redirect.fragment
            or (redirect.scheme == "https" and redirect_port not in (None, 443))
        ):
            raise CalendarIntegrationError("Google Calendar callback is not configured.")
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.settings.google_client_id,
                    "client_secret": self.settings.google_client_secret,
                    "auth_uri": GOOGLE_AUTH_URI,
                    "token_uri": GOOGLE_TOKEN_URI,
                    "redirect_uris": [self.settings.google_redirect_uri],
                }
            },
            scopes=scopes,
        )
        flow.redirect_uri = self.settings.google_redirect_uri
        return flow

    @staticmethod
    def event_id(session_id: int, schedule_id: int) -> str:
        digest = hashlib.sha256(f"{session_id}:{schedule_id}".encode("ascii")).hexdigest()[:48]
        # Hex characters are within Google's lowercase base32hex event ID alphabet.
        return f"od{digest}"

    @staticmethod
    def _headers(access_token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    def _request(self, method: str, url: str, token: str, body: dict) -> requests.Response:
        try:
            return requests.request(
                method,
                url,
                headers=self._headers(token),
                json=body,
                timeout=10,
                allow_redirects=False,
            )
        except requests.RequestException:
            raise CalendarIntegrationError("Google Calendar is temporarily unavailable.") from None

    @staticmethod
    def _event_body(schedule: CertificationSchedule, event_id: str) -> dict:
        description_lines = [
            f"자격증: {schedule.certification.name}",
            f"시험: {schedule.exam_name}",
            f"접수: {schedule.registration_start or '미확인'} ~ {schedule.registration_end or '미확인'}",
            f"발표: {schedule.result_date or '미확인'}",
            f"공식 출처: {schedule.source_url}",
        ]
        if schedule.details:
            description_lines.append(schedule.details[:2000])
        return {
            "id": event_id,
            "summary": f"[Odal BIBI] {schedule.certification.name} · {schedule.exam_name}"[:1024],
            "description": "\n".join(description_lines)[:8000],
            "start": {"date": schedule.exam_date.isoformat()},
            "end": {"date": (schedule.exam_date + timedelta(days=1)).isoformat()},
            "source": {"title": schedule.source_name[:255], "url": schedule.source_url},
        }
