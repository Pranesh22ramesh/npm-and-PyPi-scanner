import math
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from ..ml.schema import FEATURES

class VersionPair(BaseModel):
    model_config = ConfigDict(extra='forbid')
    previous_version: str = Field(min_length=1,max_length=200)
    current_version: str = Field(min_length=1,max_length=200)
    features: dict[str,float]

    @field_validator('features', mode='before')
    @classmethod
    def feature_schema(cls,value):
        if not isinstance(value,dict) or set(value) != set(FEATURES):
            raise ValueError('Provide exactly the 60 corrected feature names.')
        if any(isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) for v in value.values()):
            raise ValueError('Features must be finite JSON numbers.')
        return value

class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    package: str = Field(min_length=1,max_length=214)
    version_pairs: list[VersionPair] = Field(min_length=1,max_length=1000)

class ScanRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    package: str = Field(min_length=1,max_length=214)
    count: Literal[2,3,5,'all'] = 3
    versions: list[str] | None = Field(default=None,max_length=10)
