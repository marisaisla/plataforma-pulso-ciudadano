"""Contratos y validaciones de cargas históricas. Sin conexiones ni escrituras."""
import csv
import io
import re
from datetime import date, datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Level = Literal['entity', 'municipality', 'federal_district', 'local_district', 'section']
GEO_COLUMNS = ['level', 'code', 'name', 'entity_code', 'municipality_code',
               'federal_district_code', 'local_district_code']
RESULT_COLUMNS = ['unit_code', 'nominal_list', 'total_votes', 'null_votes',
                  'unregistered_votes', 'option_code', 'option_name', 'votes']


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid')

    @field_validator('*', mode='before')
    @classmethod
    def trim_metadata(cls, value, info):
        if isinstance(value, str) and '\x00' in value:
            raise ValueError('No se admiten caracteres NUL.')
        return value.strip() if isinstance(value, str) and info.field_name != 'csv_content' else value


class Source(Contract):
    authority: str = Field(min_length=1, max_length=200)
    url: str | None = Field(min_length=1, max_length=2000)
    title: str = Field(min_length=1, max_length=500)
    published_on: date | None
    retrieved_on: date
    cutoff_on: date | None
    version: str = Field(min_length=1, max_length=120)
    stage: Literal['geography', 'official_computation', 'final_judgment', 'legacy_snapshot']
    methodology: str = Field(min_length=1, max_length=4000)
    legacy_source_text: str | None = Field(default=None, max_length=4000)

    @field_validator('url')
    @classmethod
    def valid_url(cls, value):
        if value is None:
            return value
        parsed = urlparse(value)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('La fuente debe ser una URL HTTPS sin credenciales.')
        return value

    @model_validator(mode='after')
    def dates(self):
        dates = [d for d in (self.published_on, self.cutoff_on) if d is not None]
        if self.stage != 'legacy_snapshot' and (len(dates) != 2 or self.url is None):
            raise ValueError('La carga oficial requiere URL, publicación y corte; no inventar fechas faltantes.')
        if dates and max(dates) > self.retrieved_on:
            raise ValueError('La consulta no puede preceder a la publicación ni al corte.')
        if max([self.retrieved_on]+dates) > date.today():
            raise ValueError('Las fechas de la fuente no pueden estar en el futuro.')
        return self


class GeographyImport(Contract):
    version: str = Field(min_length=1, max_length=120)
    valid_on: date
    source: Source
    # No aplicar strip al CSV: el hash identifica exactamente el contenido recibido.
    csv_content: str = Field(min_length=1, max_length=5_000_000)

    @model_validator(mode='after')
    def geography_source(self):
        if self.source.stage != 'geography':
            raise ValueError('El catálogo requiere una fuente geográfica.')
        if self.valid_on > date.today():
            raise ValueError('Un catálogo histórico no puede tener vigencia futura.')
        return self


class ElectionCreate(Contract):
    code: str = Field(pattern=r'^[A-Za-z0-9_-]{1,100}$')
    name: str = Field(min_length=1, max_length=300)
    election_date: date
    jurisdiction: Literal['federal', 'local']
    office: str = Field(min_length=1, max_length=120)
    principle: Literal['MR', 'RP', 'NA']
    process: Literal['ordinary', 'extraordinary']
    entity_code: str | None = Field(default=None, pattern=r'^[0-9]{2}$')

    @model_validator(mode='after')
    def scope(self):
        if self.jurisdiction == 'local' and self.entity_code is None:
            raise ValueError('Una elección local requiere entidad.')
        if self.entity_code is not None and not 1 <= int(self.entity_code) <= 32:
            raise ValueError('Entidad fuera del rango 01–32.')
        if self.election_date > date.today():
            raise ValueError('Esta base histórica solo admite elecciones celebradas.')
        return self


class ResultImport(Contract):
    election_id: int = Field(gt=0)
    geography_id: int = Field(gt=0)
    level: Level
    vote_basis: Literal['party', 'candidacy', 'ballot_combination']
    source: Source
    coverage_note: str = Field(min_length=1, max_length=2000)
    supersedes_id: int | None = Field(default=None, gt=0)
    csv_content: str = Field(min_length=1, max_length=5_000_000)

    @model_validator(mode='after')
    def result_source(self):
        if self.source.stage not in ('official_computation', 'final_judgment'):
            raise ValueError('Se requieren cómputos oficiales o sentencia, no cartografía ni PREP.')
        return self


class GeographyOut(BaseModel):
    id: int
    version: str
    valid_on: date | None
    source: Source
    content_sha256: str
    created_at: datetime
    units: int


class GeographyDetail(BaseModel):
    id: int
    version: str
    valid_on: date | None
    source: Source
    content_sha256: str
    csv_content: str
    created_by: int
    created_at: datetime


class GeographySaved(BaseModel):
    id: int
    duplicate: bool
    units: int
    levels: dict[str, int] | None = None


class UnitOut(BaseModel):
    geography_id: int
    level: Level
    code: str
    name: str
    entity_code: str
    municipality_code: str | None
    federal_district_code: str | None
    local_district_code: str | None


class UnitPage(BaseModel):
    items: list[UnitOut]
    next_after: str | None


class ElectionOut(BaseModel):
    code: str
    name: str
    election_date: date | None
    jurisdiction: str
    office: str
    principle: str
    process: str
    entity_code: str | None
    legacy_election_year: int | None = None
    legacy_note: str | None = None
    id: int
    created_by: int
    created_at: datetime


class PreviewOut(BaseModel):
    units: int
    vote_rows: int
    content_sha256: str
    warnings: list[str]
    duplicate_id: int | None


class ImportSaved(PreviewOut):
    id: int
    duplicate: bool


class ImportOut(BaseModel):
    id: int
    election_id: int
    geography_id: int
    level: Level
    vote_basis: Literal['party', 'candidacy', 'ballot_combination', 'legacy_reported']
    source: Source
    content_sha256: str
    coverage_note: str
    supersedes_id: int | None
    superseded_by: int | None = None
    created_by: int
    created_at: datetime


class ImportDetail(ImportOut):
    fingerprint: str
    csv_content: str


class VoteOut(BaseModel):
    unit_code: str
    option_code: str
    option_name: str
    votes: int | None


class ResultOut(BaseModel):
    import_id: int
    unit_code: str
    name: str
    entity_code: str
    municipality_code: str | None
    federal_district_code: str | None
    local_district_code: str | None
    nominal_list: int | None
    total_votes: int | None
    null_votes: int | None
    unregistered_votes: int | None
    options: list[VoteOut]


class ResultPage(BaseModel):
    import_id: int
    level: Level
    vote_basis: Literal['party', 'candidacy', 'ballot_combination', 'legacy_reported']
    items: list[ResultOut]
    next_after: str | None


def read_csv(text, columns):
    if '\x00' in text:
        raise ValueError('El CSV contiene caracteres NUL.')
    reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')), strict=True)
    rows = []
    try:
        if reader.fieldnames != columns:
            raise ValueError('Encabezados y orden requeridos: ' + ','.join(columns))
        for number, row in enumerate(reader, 2):
            if number > 20001:
                raise ValueError('Máximo 20.000 filas por carga; dividir en lotes documentados.')
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f'Fila {number}: número de columnas incorrecto.')
            rows.append({k: v.strip() for k, v in row.items()})
    except csv.Error as exc:
        raise ValueError('CSV inválido: ' + str(exc)) from exc
    if not rows:
        raise ValueError('El CSV no contiene registros.')
    return rows


def code_for(level, code, entity):
    widths = {'entity': 2, 'municipality': 5, 'federal_district': 4,
              'local_district': 4, 'section': 6}
    if level not in widths or not re.fullmatch(r'[0-9]{' + str(widths[level]) + '}', code):
        raise ValueError(f'Clave inválida para {level}: {code}. Conservar ceros iniciales.')
    if not re.fullmatch(r'[0-9]{2}', entity) or not 1 <= int(entity) <= 32:
        raise ValueError('Entidad inválida; usar 01–32.')
    if not code.startswith(entity) or int(code[2:] or entity) == 0:
        raise ValueError('La clave no corresponde a la entidad o tiene componente cero.')


def parse_geography(text):
    rows = read_csv(text, GEO_COLUMNS)
    lookup = {}
    for row in rows:
        code_for(row['level'], row['code'], row['entity_code'])
        key = (row['level'], row['code'])
        if key in lookup or not row['name'] or len(row['name']) > 300:
            raise ValueError('Unidad duplicada o nombre vacío/demasiado largo: ' + row['code'])
        lookup[key] = row
    for row in rows:
        entity = row['entity_code']
        if ('entity', entity) not in lookup:
            raise ValueError('Falta la entidad padre: ' + entity)
        for field, level in [('municipality_code', 'municipality'),
                             ('federal_district_code', 'federal_district'),
                             ('local_district_code', 'local_district')]:
            value = row[field]
            if value:
                code_for(level, value, entity)
                if (level, value) not in lookup:
                    raise ValueError('Falta la unidad referenciada: ' + value)
                if row['level'] != 'section':
                    raise ValueError('Solo una sección puede declarar municipio y distritos relacionados.')
        if row['level'] == 'section' and not row['municipality_code']:
            raise ValueError('Una sección requiere municipio; los distritos desconocidos quedan vacíos.')
    return rows


def integer(value, field):
    if value == '':
        return None
    if not re.fullmatch(r'[0-9]+', value) or int(value) > 2**63 - 1:
        raise ValueError(f'{field}: usar entero no negativo sin separadores o vacío si se desconoce.')
    return int(value)


def parse_results(text):
    rows = read_csv(text, RESULT_COLUMNS)
    groups, options = {}, {}
    for row in rows:
        unit, option = row['unit_code'], row['option_code']
        if not re.fullmatch(r'[0-9]{2,6}', unit) or not re.fullmatch(r'[A-Za-z0-9_+.-]{1,100}', option) or not row['option_name'] or len(row['option_name']) > 300:
            raise ValueError('Unidad, código de opción o nombre inválido.')
        if option in options and options[option] != row['option_name']:
            raise ValueError('El mismo código de opción tiene nombres distintos.')
        options[option] = row['option_name']
        totals = {k: integer(row[k], k) for k in RESULT_COLUMNS[1:5]}
        group = groups.setdefault(unit, {'totals': totals, 'votes': {}})
        if totals != group['totals']:
            raise ValueError('Los totales repetidos de una unidad deben coincidir: ' + unit)
        if option in group['votes']:
            raise ValueError('Opción duplicada en unidad: ' + unit + '/' + option)
        group['votes'][option] = {'name': row['option_name'], 'votes': integer(row['votes'], 'votes')}
    for unit, group in groups.items():
        totals = group['totals']
        known = [v['votes'] for v in group['votes'].values() if v['votes'] is not None]
        subtotal = sum(known) + sum(totals[k] or 0 for k in ('null_votes', 'unregistered_votes'))
        total = totals['total_votes']
        if total is not None and subtotal > total:
            raise ValueError('Los componentes superan los votos totales: ' + unit)
        complete = len(known) == len(group['votes']) and all(totals[k] is not None for k in ('null_votes', 'unregistered_votes'))
        if complete and total is not None and subtotal != total:
            raise ValueError('Opciones + nulos + no registrados no concilian con el total: ' + unit)
        # No imponer votos <= lista nominal: casillas especiales/cobertura pueden diferir.
    return groups
