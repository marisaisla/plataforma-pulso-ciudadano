"""Validación compartida de definiciones, sin acceso a datos."""
import math

def validate_definition(questions):
    if not isinstance(questions, list) or not 1 <= len(questions) <= 30:
        raise ValueError('Agrega entre 1 y 30 preguntas.')
    clean = []
    for i, q in enumerate(questions):
        label = str(q.get('label', '')).strip()
        kind, metric = q.get('type'), q.get('metric', 'none')
        if not label or len(label) > 300 or kind not in {'text', 'number', 'choice'}:
            raise ValueError(f'Revisa el título y tipo de la pregunta {i+1}.')
        if metric not in {'none', 'count', 'sum', 'average'} or (metric in {'sum', 'average'} and kind != 'number'):
            raise ValueError('Suma y promedio requieren una pregunta numérica.')
        options = [str(v).strip() for v in q.get('options', []) if str(v).strip()] if kind == 'choice' else []
        if kind == 'choice' and (not 2 <= len(options) <= 30 or len(set(options)) != len(options)
                                 or any(len(v) > 150 for v in options)):
            raise ValueError('Cada pregunta de opción necesita de 2 a 30 opciones distintas (máximo 150 caracteres).')
        minimum, maximum = q.get('min'), q.get('max')
        for value in (minimum, maximum):
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
                raise ValueError('Los límites numéricos deben ser números finitos.')
        if minimum is not None and maximum is not None and minimum > maximum:
            raise ValueError('El mínimo no puede superar el máximo.')
        metric_label = str(q.get('metric_label', '')).strip()
        if metric != 'none' and (not metric_label or len(metric_label) > 120):
            raise ValueError('Escribe el nombre del indicador (máximo 120 caracteres).')
        clean.append(dict(id=f'q{i+1}', label=label, type=kind, required=bool(q.get('required')),
                          options=options, min=minimum, max=maximum, metric=metric, metric_label=metric_label))
    return clean
