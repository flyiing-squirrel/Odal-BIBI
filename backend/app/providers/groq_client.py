import json

import groq
from groq import Groq


class LLMError(RuntimeError):
    """Groq 호출 실패 또는 응답 형식 오류."""


class GroqClient:
    """Groq chat completion 호출 래퍼. API key와 호출 코드는 이 클래스 안에만 둔다."""

    def __init__(self, api_key: str, model: str):
        self._client = Groq(api_key=api_key, timeout=15.0, max_retries=0)
        self.model = model

    def complete(
        self,
        messages: list[dict],
        *,
        json_mode: bool = False,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> str:
        extra = {"response_format": {"type": "json_object"}} if json_mode else {}
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **extra,
            )
        except groq.APIError as error:
            raise LLMError("Groq 호출 실패") from error
        return response.choices[0].message.content or ""

    def complete_json(self, messages: list[dict], **kwargs) -> dict:
        text = self.complete(messages, json_mode=True, **kwargs)
        try:
            return json.loads(text)
        except json.JSONDecodeError as error:
            raise LLMError("Groq JSON 응답을 읽지 못했습니다.") from error
