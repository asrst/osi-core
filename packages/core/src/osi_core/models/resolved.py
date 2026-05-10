from typing import List, Optional

from pydantic import BaseModel

from .types import (
    AIContext,
    CustomExtension,
    DialectExpression,
    Dimension,
)


class Metric(BaseModel):
    name: str
    expression: DialectExpression
    description: Optional[str] = None
    custom_extensions: List[CustomExtension] = []
    ai_context: Optional[AIContext] = None


class Field(BaseModel):
    name: str
    expression: DialectExpression
    dimension: Optional[Dimension] = None
    label: Optional[str] = None
    description: Optional[str] = None
    custom_extensions: List[CustomExtension] = []
    ai_context: Optional[AIContext] = None


class Dataset(BaseModel):
    name: str
    source: str
    primary_key: List[str] = []
    unique_keys: List[List[str]] = []
    fields: List[Field] = []
    description: Optional[str] = None
    custom_extensions: List[CustomExtension] = []
    ai_context: Optional[AIContext] = None


class Relationship(BaseModel):
    name: str
    from_dataset: str
    to_dataset: str
    from_columns: List[str] = []
    to_columns: List[str] = []
    custom_extensions: List[CustomExtension] = []
    ai_context: Optional[AIContext] = None


class SemanticModel(BaseModel):
    name: str
    description: Optional[str] = None
    datasets: List[Dataset] = []
    relationships: List[Relationship] = []
    metrics: List[Metric] = []
    custom_extensions: List[CustomExtension] = []
    ai_context: Optional[AIContext] = None


class ResolvedModel(BaseModel):
    osi_spec_version: str = "0.1.1"
    name: str
    description: Optional[str] = None
    semantic_models: List[SemanticModel] = []
    custom_extensions: List[CustomExtension] = []
    ai_context: Optional[AIContext] = None

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "ResolvedModel":
        return cls.model_validate_json(json_str)