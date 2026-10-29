"""Untrusted ingestion contracts; stored runs must be complete and internally consistent."""
import json
from datetime import datetime
from typing import Any, Literal
from uuid import UUID
from pydantic import Field, StrictBool, model_validator
from .models import Model


class Event(Model):
    name: str = Field(min_length=1, max_length=128)
    data: Any


class Trial(Model):
    case_id: str = Field(min_length=1, max_length=200, pattern=r'^[A-Za-z0-9_.:/-]+$')
    trial: int = Field(ge=0, strict=True)
    seed: int = Field(strict=True)
    passed: StrictBool
    checks: list[StrictBool] = Field(min_length=1, max_length=200)
    output: Any = None
    error: str | None = Field(default=None, max_length=200)
    duration_ms: float = Field(ge=0, allow_inf_nan=False)
    events: list[Event] = Field(default_factory=list, max_length=100)

    @model_validator(mode='after')
    def outcome_matches(self):
        if self.passed != (all(self.checks) and self.error is None):
            raise ValueError('outcome disagrees with checks/error')
        return self


class RunRecord(Model):
    id: UUID
    created_at: datetime
    suite_name: str = Field(min_length=1, max_length=200)
    suite_version: str = Field(min_length=1, max_length=100)
    suite_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    agent_ref: str = Field(min_length=1, max_length=300)
    revision: str = Field(min_length=1, max_length=200)
    repeats: int = Field(ge=1, le=1000, strict=True)
    seed: int = Field(strict=True)
    results: list[Trial] = Field(min_length=1, max_length=10000)
    source: Literal['runner', 'swebench-import', 'external'] = 'runner'
    provenance: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode='after')
    def complete(self):
        if self.created_at.tzinfo is None:
            raise ValueError('timestamp must have timezone')
        groups = {}
        counts = {}
        for row in self.results:
            key = (row.case_id, row.trial)
            if key in groups or row.seed != self.seed + row.trial or row.trial >= self.repeats:
                raise ValueError('invalid trial pairing')
            groups[key] = row
            counts[row.case_id] = counts.get(row.case_id, 0) + 1
        for count in counts.values():
            if count != self.repeats:
                raise ValueError('incomplete case trials')
        json.dumps(self.model_dump(mode='json'), allow_nan=False)
        return self


class BaselineRequest(Model):
    name: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,80}$')
    version: int = Field(ge=1, strict=True)
    run_id: UUID
    note: str = Field(default='', max_length=500)
