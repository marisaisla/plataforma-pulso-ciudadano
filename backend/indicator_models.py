from typing import Literal
from urllib.parse import urlparse
from datetime import date
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator


class Selection(BaseModel):
    model_config=ConfigDict(extra='forbid')
    import_id: int=Field(gt=0)
    mode: Literal['validated','exploratory']='validated'
    option_code: str | None=Field(default=None,pattern=r'^[A-Za-z0-9_+.-]{1,100}$')
    denominator: Literal['valid_votes','emitted_votes']='valid_votes'
    participation_proxy: StrictBool=False
    entity_code: str | None=Field(default=None,pattern=r'^[0-9]{2}$')
    unit_code: str | None=Field(default=None,pattern=r'^[0-9]{2,6}$')
    after: str=Field(default='',pattern=r'^[0-9]{0,6}$')
    limit: int=Field(default=100,ge=1,le=500)
    allow_superseded: StrictBool=False


class OptionMatch(BaseModel):
    model_config=ConfigDict(extra='forbid')
    option_a: str=Field(pattern=r'^[A-Za-z0-9_+.-]{1,100}$')
    option_b: str=Field(pattern=r'^[A-Za-z0-9_+.-]{1,100}$')
    evidence_url: str=Field(max_length=2000)
    note: str=Field(min_length=1,max_length=1000)

    @field_validator('note')
    @classmethod
    def meaningful_note(cls,value):
        if not value.strip():
            raise ValueError('Explicar la equivalencia; no basta una nota vacía.')
        return value.strip()

    @field_validator('evidence_url')
    @classmethod
    def https(cls,value):
        url=urlparse(value)
        if url.scheme!='https' or not url.hostname or url.username or url.password:
            raise ValueError('La equivalencia requiere evidencia HTTPS sin credenciales.')
        return value


class Comparison(BaseModel):
    model_config=ConfigDict(extra='forbid')
    a: Selection
    b: Selection
    coverage_mode: Literal['exact','intersection']='exact'
    option_mapping: list[OptionMatch]=Field(default_factory=list,max_length=500)

    @model_validator(mode='after')
    def unique_mapping(self):
        if len({m.option_a for m in self.option_mapping})!=len(self.option_mapping) or len({m.option_b for m in self.option_mapping})!=len(self.option_mapping):
            raise ValueError('Las equivalencias deben ser uno a uno; no redistribuir coaliciones automáticamente.')
        return self


class Metric(BaseModel):
    value: float | int | bool | None
    status: Literal['computed','proxy','unavailable','blocked','series']
    numerator: float | int | None=None
    denominator: float | int | None=None
    reason: str | None=None
    details: dict=Field(default_factory=dict)


class IndicatorDefinition(BaseModel):
    code: str
    family: Literal['IC','IP','IT']
    name: str
    definition: str
    formula: str
    unit: str
    required_inputs: str
    engine_support: Literal['single','comparison','pending_inputs']
    version: str
    geographic_levels: list[str]
    periodicity: str
    source_type: str


class CatalogOut(BaseModel):
    engine_version: str
    catalog_version: str
    items: list[IndicatorDefinition]


class DatasetOut(BaseModel):
    id: int
    election_id: int
    geography_id: int
    level: str
    vote_basis: str
    source_stage: str
    coverage_note: str
    election_name: str
    election_date: date | None
    legacy_election_year: int | None
    geography_version: str
    valid_on: date | None
    units: int
    superseded_by: int | None


class OptionOut(BaseModel):
    option_code: str
    option_name: str
    units_reported: int
    units_with_known_votes: int


class UnitIndicators(BaseModel):
    unit_code: str
    name: str
    metrics: dict[str,Metric]
    warnings: list[str]
    reported_options: list[dict]


class EvaluationOut(BaseModel):
    engine_version: str
    catalog_version: str
    request: dict
    provenance: dict
    coverage: dict
    warnings: list[str]
    summary: dict[str,Metric]
    items: list[UnitIndicators]
    next_after: str | None


class UnitComparison(BaseModel):
    unit_code: str
    name: str
    metrics: dict[str,Metric]


class ComparisonOut(BaseModel):
    engine_version: str
    catalog_version: str
    request: dict
    provenance: dict
    comparability: dict
    summary: dict[str,Metric]
    items: list[UnitComparison]
    next_after: str | None
