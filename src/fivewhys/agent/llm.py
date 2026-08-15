"""LLM 클라이언트 추상화.

에이전트 루프는 LLMClient 프로토콜에만 의존한다. 덕분에

- AnthropicLLM : Claude API (실전)
- ScriptedLLM  : 결정적 휴리스틱 엔진 (오프라인 데모 / 테스트 / 평가 베이스라인)

을 같은 루프에 끼울 수 있고, 에이전트 로직을 API 키 없이 테스트할 수 있다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class TextBlock:
    text: str
    type: str = "text"


@dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict
    type: str = "tool_use"


@dataclass
class LLMResponse:
    content: list[Any]
    stop_reason: str
    model: str = ""


class LLMClient(Protocol):
    def create(
        self, *, system: str, messages: list[dict], tools: list[dict]
    ) -> LLMResponse: ...


@dataclass
class AnthropicLLM:
    """Claude API 클라이언트 (Messages API + tool use 수동 루프용).

    - 모델 기본값은 claude-opus-5. 해당 모델은 adaptive thinking이 기본
      활성화되어 있어 thinking 파라미터를 넘기지 않는다.
    - 온도 등 샘플링 파라미터는 최신 모델에서 제거되었으므로 사용하지 않는다.
    - stop_reason == "refusal"은 안전 분류기 거절이므로 명시적으로 처리한다.
    """

    model: str = field(
        default_factory=lambda: os.environ.get("FIVEWHYS_MODEL", "claude-opus-5")
    )
    max_tokens: int = 8192
    _client: Any = None

    def __post_init__(self) -> None:
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic()

    def create(
        self, *, system: str, messages: list[dict], tools: list[dict]
    ) -> LLMResponse:
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=messages,
            tools=tools,
        )
        if resp.stop_reason == "refusal":
            detail = getattr(resp, "stop_details", None)
            raise RuntimeError(
                f"모델이 요청을 거절했습니다 (safety refusal): {detail}"
            )
        return LLMResponse(
            content=list(resp.content), stop_reason=resp.stop_reason, model=resp.model
        )
