"""Pydantic models for the Anthropic Messages API (POST /v1/messages).

Wire contract version: anthropic-version: 2023-06-01.

Usage:
    from anthropic_api import MessagesRequest, MessagesResponse, Message, Tool

    body = MessagesRequest(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        messages=[Message(role="user", content="Hello")],
    )
    raw = json.dumps(body.model_dump(exclude_none=True)).encode()
    #                              ^^^^^^^^^^^^^^^^^^ drop unset optionals so you
    #                              never send `temperature: null` etc. (400 risk)

    resp = MessagesResponse.model_validate(json.loads(urlopen(req).read()))
    resp.stop_reason          # typed
    resp.content[0]           # a discriminated block — match on .type
    resp.usage.input_tokens
"""

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

# ──────────────────────────────────────────────────────────────────────────
# Content blocks (the tagged-union pieces of a message's `content`)
# ──────────────────────────────────────────────────────────────────────────


class TextBlock(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ToolUseBlock(BaseModel):
    # Note: extra fields the API may attach (e.g. `caller`) are dropped on parse,
    # so re-sending a parsed assistant turn is clean — no invalid input fields.
    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict[str, Any]


class ToolResultBlock(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: Union[str, list[TextBlock]]
    is_error: bool = False


class ThinkingBlock(BaseModel):
    type: Literal["thinking"] = "thinking"
    thinking: str = ""
    signature: str | None = None


# One union for every block, used by both request `Message.content` and response
# `MessagesResponse.content`. (tool_result only ever shows up on the request side,
# and thinking/text/tool_use on the response side — but sharing one type means you
# can echo a response's content straight back into a request with zero casts.)
ContentBlock = Annotated[
    Union[TextBlock, ToolUseBlock, ToolResultBlock, ThinkingBlock],
    Field(discriminator="type"),
]


# ──────────────────────────────────────────────────────────────────────────
# Request
# ──────────────────────────────────────────────────────────────────────────


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: Union[str, list[ContentBlock]]


class Tool(BaseModel):
    name: str
    description: str | None = None
    input_schema: dict[str, Any]


class ToolChoiceAuto(BaseModel):
    type: Literal["auto"] = "auto"


class ToolChoiceAny(BaseModel):
    type: Literal["any"] = "any"


class ToolChoiceTool(BaseModel):
    type: Literal["tool"] = "tool"
    name: str


ToolChoice = Annotated[
    Union[ToolChoiceAuto, ToolChoiceAny, ToolChoiceTool],
    Field(discriminator="type"),
]


class ThinkingConfig(BaseModel):
    # Frontier models (opus-4-8, fable-5): only {type: "adaptive"}.
    # sonnet/haiku 4.5: {type: "enabled", budget_tokens: N} or {type: "disabled"}.
    type: Literal["adaptive", "enabled", "disabled"]
    budget_tokens: int | None = None


class MessagesRequest(BaseModel):
    # Current model IDs: claude-opus-4-8, claude-sonnet-4-6, claude-haiku-4-5,
    # claude-sonnet-4-5, claude-fable-5. (str, not a Literal, so you're never
    # blocked from using a new one.)
    model: str
    max_tokens: int
    messages: list[Message]

    system: Union[str, list[TextBlock]] | None = None
    tools: list[Tool] | None = None
    tool_choice: ToolChoice | None = None
    stop_sequences: list[str] | None = None

    # temperature/top_p/top_k are REMOVED on frontier models (sending them = 400);
    # still valid on sonnet/haiku 4.5.
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None

    thinking: ThinkingConfig | None = None
    metadata: dict[str, Any] | None = None
    stream: bool | None = None


# ──────────────────────────────────────────────────────────────────────────
# Response
# ──────────────────────────────────────────────────────────────────────────

# Known stop reasons as of 2023-06-01. Typed as `str` on the model (below) so a
# value Anthropic adds later won't raise on parse — match on it, with a default
# arm for the unknown. Use this alias in your own annotations if you want.
StopReason = Literal[
    "end_turn",
    "max_tokens",
    "stop_sequence",
    "tool_use",
    "pause_turn",
    "refusal",
]


class Usage(BaseModel):
    model_config = ConfigDict(extra="allow")  # forward-compat: keep unknown fields

    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int | None = None
    cache_read_input_tokens: int | None = None
    service_tier: str | None = None


class MessagesResponse(BaseModel):
    model_config = ConfigDict(extra="allow")  # forward-compat for new top-level fields

    id: str
    type: Literal["message"] = "message"
    role: Literal["assistant"] = "assistant"
    model: str
    content: list[ContentBlock]
    stop_reason: str | None = None  # see StopReason alias above
    stop_sequence: str | None = None
    usage: Usage
