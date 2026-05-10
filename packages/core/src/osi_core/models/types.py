from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Dialect(Enum):
    ANSI_SQL = "ANSI_SQL"
    SNOWFLAKE = "SNOWFLAKE"
    MDX = "MDX"
    TABLEAU = "TABLEAU"
    DATABRICKS = "DATABRICKS"
    MAQL = "MAQL"


class Vendor(Enum):
    COMMON = "COMMON"
    SNOWFLAKE = "SNOWFLAKE"
    SALESFORCE = "SALESFORCE"
    DBT = "DBT"
    DATABRICKS = "DATABRICKS"
    GOODDATA = "GOODDATA"


class DialectExpr(BaseModel):
    dialect: Dialect
    expression: str


class DialectExpression(BaseModel):
    dialects: List[DialectExpr] = Field(default_factory=list)


class Dimension(BaseModel):
    is_time: bool = False


class CustomExtension(BaseModel):
    vendor_name: Vendor
    data: str


class AIContext(BaseModel):
    instructions: Optional[str] = None
    synonyms: List[str] = Field(default_factory=list)
    examples: List[str] = Field(default_factory=list)


@dataclass
class ParseResult:
    raw: dict
    source_format: str
    source_version: str
    custom_extensions: List[CustomExtension] = field(default_factory=list)
    osi_spec_version: str = "0.1.1"