from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Assertion(Model):
    kind: Literal["equals", "contains", "type"]
    path: list[str | int] = Field(default_factory=list)
    expected: Any

    @model_validator(mode="after")
    def valid_type(self):
        if self.kind == "type" and self.expected not in ("string", "number", "boolean", "object", "array", "null"):
            raise ValueError("unknown JSON type")
        return self


class Case(Model):
    id: str = Field(min_length=1)
    input: dict[str, Any]
    assertions: list[Assertion] = Field(min_length=1)


class Suite(Model):
    schema_version: Literal[1] = 1
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    cases: list[Case] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_ids(self):
        if len({case.id for case in self.cases}) != len(self.cases):
            raise ValueError("case IDs must be unique")
        return self
