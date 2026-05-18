from typing import List, Optional

from pydantic import BaseModel

from .types import (
    AIContext,
    CustomExtension,
    DialectExpression,
    Dimension,
)


class Metric(BaseModel):
    """A computed metric defined over one or more datasets."""

    name: str
    expression: DialectExpression
    description: Optional[str] = None
    custom_extensions: List[CustomExtension] = []
    ai_context: Optional[AIContext] = None


class Field(BaseModel):
    """A column or computed field within a dataset."""

    name: str
    expression: DialectExpression
    dimension: Optional[Dimension] = None
    label: Optional[str] = None
    description: Optional[str] = None
    custom_extensions: List[CustomExtension] = []
    ai_context: Optional[AIContext] = None


class Dataset(BaseModel):
    """A logical table or view that groups related fields."""

    name: str
    source: str
    primary_key: List[str] = []
    unique_keys: List[List[str]] = []
    fields: List[Field] = []
    description: Optional[str] = None
    custom_extensions: List[CustomExtension] = []
    ai_context: Optional[AIContext] = None


class Relationship(BaseModel):
    """A join relationship between two datasets."""

    name: str
    from_dataset: str
    to_dataset: str
    from_columns: List[str] = []
    to_columns: List[str] = []
    custom_extensions: List[CustomExtension] = []
    ai_context: Optional[AIContext] = None


class SemanticModel(BaseModel):
    """A named semantic model containing datasets, relationships, and metrics."""

    name: str
    description: Optional[str] = None
    datasets: List[Dataset] = []
    relationships: List[Relationship] = []
    metrics: List[Metric] = []
    custom_extensions: List[CustomExtension] = []
    ai_context: Optional[AIContext] = None


class OsiModel(BaseModel):
    """Top-level OSI model document.

    Represents a parsed OSI specification file, containing one or more
    semantic models along with metadata such as spec version and custom extensions.
    """

    osi_spec_version: str = "0.1.1"
    name: str
    description: Optional[str] = None
    semantic_models: List[SemanticModel] = []
    custom_extensions: List[CustomExtension] = []
    ai_context: Optional[AIContext] = None

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "OsiModel":
        return cls.model_validate_json(json_str)
