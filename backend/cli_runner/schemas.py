"""Execution wire schema shared by a runner and its lifecycle controller."""
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class Completion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    protocol: Literal[1]
    provider: Literal["codex_cli", "claude_code", "antigravity_cli"]
    prompt: str = Field(max_length=4_000_000)
    system: str = Field(max_length=1_000_000)
    model: str = Field(max_length=200)
    max_tokens: int = Field(gt=0, le=1_000_000)
    effort: str = Field(default="", max_length=20)
    account_id: UUID | None = None
    claude_token: SecretStr = SecretStr("")
