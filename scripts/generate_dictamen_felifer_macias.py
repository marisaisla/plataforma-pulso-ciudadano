"""Genera el dictamen preliminar de viabilidad de Felipe Fernando Macías."""

from __future__ import annotations

import sys as _storage_sys
from pathlib import Path as _StoragePath
_storage_sys.path.insert(0, str(_StoragePath(__file__).resolve().parents[1]))
from services.storage import storage_path


from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = storage_path("output") / "pdf" / "Dictamen_Preliminar_Viabilidad_Felipe_Fernando_Macias_Queretaro_2027.pdf"

NAVY = colors.HexColor("#10243E")
BLUE = colors.HexColor("#155E99")
TEAL = colors.HexColor("#0F766E")
GOLD = colors.HexColor("#C58A19")
LIGHT = colors.HexColor("#EEF3F8")
MID = colors.HexColor("#D8E1EB")
INK = colors.HexColor("#1E293B")
MUTED = colors.HexColor("#526273")
RED = colors.HexColor("#A33B3B")

SOURCES = {
    "IEEQ 2024": "https://ieeq.mx/comunicacion/boletines/3094",
    "IEEQ resultados municipales 2024": "https://ieeq.mx/contenido/elecciones/2023_2024/resultados/",
    "IEEQ informe 2021": "https://ieeq.mx/contenido/ieeq/informes/proceso/2020_2021.pdf",
    "Municipio de Querétaro": "https://municipiodequeretaro.gob.mx/municipio/repositorios/gacetas-2024-2027/Gaceta-No.38.pdf",
    "SIL": "https://sil.gobernacion.gob.mx/Librerias/pp_PerfilLegislador.php?Referencia=9226104",
    "El País, 19 sep. 2026": "https://elpais.com/mexico/2026-09-19/defensores-de-la-patria-el-pan-copia-la-estrategia-de-morena-en-un-intento-de-mantener-el-pulso-de-2027.html",
    "MetaMetrics, 4 sep. 2026": "https://metametrics.org/rumbo-a-las-elecciones-2027-en-queretaro-4-de-septiembre-2026/",
    "Publimetro / Poligrama, 16 sep. 2026": "https://www.publimetro.com.mx/queretaro/2026/09/16/felifer-macias-encabeza-preferencias-en-queretaro-poligrama/",
}


def styles():
    font = r"C:\Windows\Fonts\arial.ttf"
    bold = r"C:\Windows\Fonts\arialbd.ttf"
    pdfmetrics.registerFont(TTFont("Go2Win", font))
    pdfmetrics.registerFont(TTFont("Go2WinBold", bold))
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=base["Title"], fontName="Go2WinBold", fontSize=28, leading=33, textColor=colors.white, alignment=TA_LEFT, spaceAfter=10),
        "subtitle": ParagraphStyle("subtitle", parent=base["Normal"], fontName="Go2Win", fontSize=12, leading=17, textColor=colors.HexColor("#D8E7F4")),
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontName="Go2WinBold", fontSize=18, leading=23, textColor=NAVY, spaceBefore=4, spaceAfter=9),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="Go2WinBold", fontSize=12, leading=16, textColor=BLUE, spaceBefore=10, spaceAfter=5),
        "body": ParagraphStyle("body", parent=base["BodyText"], fontName="Go2Win", fontSize=9.25, leading=13.7, textColor=INK, spaceAfter=6),
        "small": ParagraphStyle("small", parent=base["BodyText"], fontName="Go2Win", fontSize=7.4, leading=10.2, textColor=MUTED),
        "kpi": ParagraphStyle("kpi", parent=base["Normal"], fontName="Go2WinBold", fontSize=18, leading=21, textColor=NAVY, alignment=TA_CENTER),
        "kpi_label": ParagraphStyle("kpi_label", parent=base["Normal"], fontName="Go2WinBold", fontSize=7.4, leading=9, textColor=MUTED, alignment=TA_CENTER),
        "table": ParagraphStyle("table", parent=base["BodyText"], fontName="Go2Win", fontSize=7.4, leading=9.7, textColor=INK),
        "table_bold": ParagraphStyle("table_bold", parent=base["BodyText"], fontName="Go2WinBold", fontSize=7.4, leading=9.7, textColor=INK),
        "callout": ParagraphStyle("callout", parent=base["BodyText"], fontName="Go2Win", fontSize=9, leading=13, textColor=NAVY),
        "cover_small": ParagraphStyle("cover_small", parent=base["Normal"], fontName="Go2WinBold", fontSize=8.5, leading=10, textColor=colors.HexColor("#B7D4EC")),
    }


def p(text, style):
    return Paragraph(text, style)


def box(value, label, st):
    return Table([[p(value, st["kpi"])], [p(label, st["kpi_label"])]], colWidths=[1.48 * inch], rowHeights=[0.39 * inch, 0.34 * inch], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.6, MID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))


def standard_table(rows, widths, st, header=True, font_size=7.4):
    converted = []
    for i, row in enumerate(rows):
        converted.append([p(str(cell), st["table_bold"] if header and i == 0 else st["table"]) for cell in row])
    t = Table(converted, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, MID),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]
    for row_idx in range(1 if header else 0, len(rows)):
        if row_idx % 2 == 0:
            style.append(("BACKGROUND", (0, row_idx), (-1, row_idx), LIGHT))
    t.setStyle(TableStyle(style))
    return t


def callout(title, text, st, color=TEAL):
    table = Table([[p(f"<b>{title}</b><br/>{text}", st["callout"])]], colWidths=[6.7 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F8F7")),
        ("LINEBEFORE", (0, 0), (0, -1), 4, color),
        ("LEFTPADDING", (0, 0), (-1, -1), 11),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return table


def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(MID)
    canvas.setLineWidth(0.6)
    canvas.line(0.62 * inch, 0.52 * inch, 7.88 * inch, 0.52 * inch)
    canvas.setFont("Go2Win", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(0.62 * inch, 0.34 * inch, "GO2WIN | Dictamen preliminar de viabilidad - Querétaro 2027")
    canvas.drawRightString(7.88 * inch, 0.34 * inch, f"Página {doc.page}")
    canvas.restoreState()


def build():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    st = styles()
    doc = SimpleDocTemplate(
        str(OUTPUT), pagesize=letter, leftMargin=0.62 * inch, rightMargin=0.62 * inch,
        topMargin=0.58 * inch, bottomMargin=0.72 * inch,
        title="Dictamen preliminar de viabilidad - Felipe Fernando Macías - Querétaro 2027",
        author="Go2Win",
    )
    story = []

    # Portada
    cover = Table([[p("GO2WIN", st["cover_small"])], [p("DICTAMEN PRELIMINAR<br/>DE VIABILIDAD ELECTORAL", st["title"])], [p("Felipe Fernando Macías Olvera<br/>Posible candidatura del PAN a la Gubernatura de Querétaro - Proceso 2027", st["subtitle"])], [Spacer(1, 0.25 * inch)], [p("CORTE DE INFORMACIÓN: 27 DE SEPTIEMBRE DE 2026", st["cover_small"])]], colWidths=[7.26 * inch], rowHeights=[0.36 * inch, 1.26 * inch, 0.76 * inch, 0.24 * inch, 0.30 * inch])
    cover.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("LEFTPADDING", (0, 0), (-1, -1), 25),
        ("RIGHTPADDING", (0, 0), (-1, -1), 25),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story += [Spacer(1, 0.35 * inch), cover, Spacer(1, 0.33 * inch)]
    story += [p("Lectura ejecutiva", st["h1"])]
    story += [p("Felipe Fernando Macías cuenta con una plataforma inicial competitiva para una eventual candidatura panista a la gubernatura: ocupa la presidencia municipal de la capital, ganó la elección municipal de 2024 al frente de PAN-PRI-PRD y Go2Win dispone ya de la base territorial-electoral de los 18 municipios del estado.", st["body"])]
    story += [p("El dictamen no concluye que exista una candidatura formal ni estima un resultado de 2027. La selección interna del PAN sigue abierta y las mediciones públicas de septiembre ofrecen lecturas distintas. La conclusión responsable es: <b>viabilidad inicial alta para ser considerado en la definición interna, y viabilidad estatal competitiva pero aún no calificable numéricamente</b> hasta contar con tracking comparable, evidencia de estructura y escenario partidista definido.", st["body"])]
    story += [Spacer(1, 0.05 * inch), Table([[box("ALTA", "Plataforma inicial", st), box("ABIERTA", "Definición PAN 2027", st), box("9 / 18", "Municipios con ventaja PAN-PRI-PRD en 2024", st), box("0 / 20", "Variables calificadas", st)]], colWidths=[1.78 * inch] * 4, style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))]
    story += [Spacer(1, 0.22 * inch), callout("Conclusión ejecutiva", "El perfil debe pasar de una ventaja de capital y visibilidad pública a una prueba estatal verificable. La decisión siguiente no es asignar un pronóstico, sino completar la evidencia que permita comparar perfiles bajo el mismo método.", st, GOLD), PageBreak()]

    story += [p("1. Objeto, alcance y método", st["h1"])]
    story += [p("El documento evalúa dos preguntas diferentes: (1) si Felipe Fernando Macías cuenta con condiciones para competir en la definición del PAN y (2) si existen bases suficientes para sostener una viabilidad estatal frente a las demás fuerzas. Estas preguntas no se confunden con una candidatura formal, una encuesta ni un pronóstico.", st["body"])]
    story += [p("<b>Fuentes utilizadas.</b> Resultados oficiales de ayuntamientos del IEEQ 2021 y 2024, datos territoriales e indicadores cargados en Go2Win, documentos públicos sobre el cargo vigente y mediciones difundidas en septiembre de 2026 con metodología publicada.", st["body"])]
    story += [standard_table([
        ["Categoría", "Uso en el dictamen", "Regla"],
        ["Dato observado", "Resultados, cargo, lista nominal, participación y fuentes identificables.", "Se describe con fecha y fuente."],
        ["Indicador estratégico", "Lectura de territorio, brechas y condiciones de competencia.", "No se presenta como hecho ni pronóstico."],
        ["Pendiente", "Estructura, encuestas comparables, coaliciones, recursos y operación.", "No se transforma en puntuación."],
    ], [1.25 * inch, 3.30 * inch, 2.15 * inch], st)]
    story += [p("<b>Limitaciones decisivas.</b> El expediente no contiene una encuesta propia con serie comparable; la definición del PAN no está cerrada; los resultados municipales no sustituyen el resultado de una elección de gubernatura; y no se ha auditado la cobertura territorial, responsable por responsable. Por ello el modelo de 20 variables se conserva sin puntajes.", st["body"])]
    story += [callout("Criterio de integridad", "Una cifra de intención de voto sólo puede usarse si conserva su fecha, universo, modo de levantamiento, tamaño de muestra, margen de error y redacción exacta de la pregunta.", st), PageBreak()]

    story += [p("2. Perfil político y punto de partida", st["h1"])]
    story += [p("Felipe Fernando Macías Olvera es Presidente Municipal de Querétaro en el periodo 2024-2027. El IEEQ declaró la validez de la elección de ayuntamiento y otorgó la constancia de mayoría a la planilla encabezada por él, postulada por PAN-PRI-PRD. Su trayectoria pública también incluye regiduría en el Ayuntamiento de Querétaro y dos periodos como diputado federal.", st["body"])]
    story += [standard_table([
        ["Activo", "Evidencia", "Lectura"],
        ["Cargo vigente", "Presidencia municipal de Querétaro, 2024-2027.", "Exposición cotidiana y gestión en el municipio de mayor peso electoral."],
        ["Victoria municipal 2024", "252,293 votos para la candidatura común PAN-PRI-PRD en Querétaro municipio.", "Base observable, no transferible automáticamente a todo el estado."],
        ["Trayectoria", "Regidor 2015-2018 y diputado federal 2018-2024, según perfil público del IEEQ/SIL.", "Experiencia pública y reconocimiento acumulado."],
        ["Definición 2027", "El proceso panista permanece abierto; existen otros perfiles mencionados públicamente.", "No debe presentarse como candidatura formal."],
    ], [1.25 * inch, 2.50 * inch, 2.95 * inch], st)]
    story += [callout("Activo central", "La capital ofrece volumen, visibilidad y una victoria reciente. La prueba pendiente es demostrar que esa fortaleza se replica, compensa o al menos reduce brechas fuera de la zona metropolitana.", st), PageBreak()]

    story += [p("3. Mercado electoral y base municipal observada", st["h1"])]
    story += [p("Go2Win contiene los resultados oficiales de ayuntamientos de los 18 municipios. Para esta lectura, PAN-PRI-PRD y Morena-PT-PVEM se agrupan por las opciones de voto que integraron sus candidaturas comunes locales de 2024. Esta agregación sirve para observar mercado municipal; <b>no equivale a una elección de gubernatura ni a una estimación de 2027</b>.", st["body"])]
    story += [Table([[box("1,899,150", "Lista nominal agregada 2024", st), box("1,169,497", "Votos totales 2024", st), box("61.58%", "Participación agregada 2024", st), box("565,642", "PAN-PRI-PRD municipal", st)]], colWidths=[1.78 * inch] * 4)]
    story += [Spacer(1, 0.12 * inch)]
    story += [standard_table([
        ["Elección municipal agregada", "Lista nominal", "Votos totales", "Participación"],
        ["2021", "1,736,369", "898,713", "51.76%"],
        ["2024", "1,899,150", "1,169,497", "61.58%"],
        ["Cambio 2021-2024", "+162,781", "+270,784", "+9.82 pp"],
    ], [2.60 * inch, 1.30 * inch, 1.30 * inch, 1.40 * inch], st)]
    story += [p("La participación agregada municipal aumentó casi diez puntos porcentuales entre ambas elecciones. Para 2027, cualquier meta deberá separar tres elementos: tamaño de la lista nominal, participación esperada y porcentaje de voto válido requerido. No basta trasladar el resultado de 2024.", st["body"])]
    story += [PageBreak()]

    story += [p("4. Lectura territorial: municipios de mayor escala", st["h1"])]
    story += [p("Los cuatro municipios de mayor lista nominal concentraron 1,433,955 registros, equivalentes a 75.5% del total estatal municipal de 2024. La capital es indispensable, pero no suficiente por sí sola. Corregidora y El Marqués mostraron margen favorable al bloque PAN-PRI-PRD; San Juan del Río también fue favorable, con menor diferencia.", st["body"])]
    story += [standard_table([
        ["Municipio", "Lista nominal", "Participación", "PAN-PRI-PRD", "Morena-PT-PVEM", "Diferencia"],
        ["Querétaro", "847,093", "60.47%", "252,293", "205,254", "+47,039"],
        ["San Juan del Río", "235,505", "58.69%", "63,521", "54,120", "+9,401"],
        ["Corregidora", "175,905", "63.45%", "71,442", "29,554", "+41,888"],
        ["El Marqués", "175,452", "62.72%", "66,772", "34,297", "+32,475"],
        ["Tequisquiapan", "59,550", "68.96%", "12,003", "24,271", "-12,268"],
        ["Pedro Escobedo", "59,215", "62.61%", "15,751", "17,811", "-2,060"],
    ], [1.35 * inch, 1.00 * inch, 0.82 * inch, 1.18 * inch, 1.18 * inch, 0.88 * inch], st)]
    story += [p("En el agregado municipal de 2024, cada bloque tuvo ventaja en 9 de los 18 municipios. Esa paridad territorial obliga a evitar dos simplificaciones: asumir que la capital garantiza el resultado estatal o interpretar un municipio ganador como territorio consolidado para otra elección.", st["body"])]
    story += [callout("Lectura operativa para el dictamen", "La futura evaluación debe distinguir: base a proteger (capital y zona metropolitana), territorios competitivos y territorios de recuperación. La clasificación debe actualizarse con voto por sección, participación, estructura y encuesta, no sólo con el ganador municipal.", st), PageBreak()]

    story += [p("5. Posicionamiento público y competencia", st["h1"])]
    story += [p("Las publicaciones revisadas ofrecen fotografías de septiembre de 2026, no una serie consolidada. Por eso se presentan separadas y no se promedian.", st["body"])]
    story += [standard_table([
        ["Estudio publicado", "Fecha / método", "Hallazgo relevante", "Uso correcto"],
        ["MetaMetrics", "1-4 sep. 2026; 1,500 encuestas digitales; +/-3.4%.", "Interna PAN: Luis Nava 27.1%; Macías 26.9%. Partido: PAN 41.5%; Morena-PT-PVEM 34.1%.", "Competencia interna cerrada; no equivale a un careo individual."],
        ["Poligrama difundido por Publimetro", "9 sep. 2026; 1,000 entrevistas telefónicas; +/-3.10%.", "Careo publicado: Macías 44.9%; Santiago Nieto 29.9%; 15.8% no sabe.", "Una medición puntual, no pronóstico ni promedio."],
    ], [1.18 * inch, 1.65 * inch, 2.25 * inch, 1.65 * inch], st)]
    story += [p("La evidencia apunta a dos conclusiones compatibles: existe una competencia interna panista real y el perfil de Macías aparece competitivo en al menos un careo publicado. No permite afirmar una ventaja permanente ni cerrar la definición. Debe levantarse un tracking único que mantenga el mismo cuestionario, campo y cobertura territorial.", st["body"])]
    story += [standard_table([
        ["Campo", "Situación al corte", "Implicación"],
        ["PAN", "Felipe Macías, Luis Bernardo Nava y Agustín Dorantes son perfiles referidos públicamente en la definición interna.", "La viabilidad de candidatura depende del método partidista, unidad y aceptación interna."],
        ["Morena", "Santiago Nieto es el perfil más mencionado en las fuentes revisadas.", "La competencia debe contrastarse con un careo homogéneo y alianzas confirmadas."],
        ["Alianzas", "Sin configuración formal verificable para 2027.", "No se pueden asignar transferencias de voto ni metas de coalición."],
    ], [1.15 * inch, 3.15 * inch, 2.43 * inch], st), PageBreak()]

    story += [p("6. Modelo de 20 variables: estado real de la evidencia", st["h1"])]
    story += [p("Go2Win contiene 20 variables para ordenar el dictamen. En este caso no se les asigna un número: cinco tienen base documentada, tres están en revisión y doce permanecen pendientes. Un índice con valores estimados transmitiría una precisión que el expediente todavía no posee.", st["body"])]
    story += [standard_table([
        ["Estatus", "Variables", "Lectura"],
        ["Documentadas (5)", "Perfil, territorio, base electoral, sociodemografía, fuentes.", "Hay evidencia sobre el cargo, la base territorial y resultados históricos."],
        ["En revisión (3)", "Definición electoral, competencia, coaliciones.", "Hay información pública, pero no decisión formal ni escenario cerrado."],
        ["Pendientes (12)", "Posicionamiento, encuestas homologadas, estructura, organización, recursos, comunicación, sentimiento, temas, estrategia, plan, seguimiento y conclusión.", "Requieren carga de evidencia, no estimaciones."],
    ], [1.45 * inch, 2.80 * inch, 2.48 * inch], st)]
    story += [p("<b>Variables que definirán el dictamen final.</b> Preferencia y conocimiento con tracking comparable; probabilidad de nominación; cobertura y responsables por municipio/sección; desempeño de marca PAN; fortaleza del rival; capacidad de coalición; margen de indecisos; riesgo reputacional y viabilidad operativa.", st["body"])]
    story += [callout("Regla de puntuación", "Cada variable sólo se calificará de 0 a 100 cuando tenga una fuente, fecha de corte, responsable y nota de interpretación. Hasta entonces el tablero mostrará estado de evidencia, no una calificación artificial.", st, GOLD), PageBreak()]

    story += [p("7. Dictamen preliminar", st["h1"])]
    story += [p("<b>Viabilidad para competir en la definición panista: alta, condicionada.</b> El cargo en la capital, la victoria municipal de 2024 y la visibilidad pública constituyen una plataforma relevante. Sin embargo, la selección partidista continúa abierta y la medición interna disponible muestra una diferencia mínima con Luis Bernardo Nava en un estudio específico.", st["body"])]
    story += [p("<b>Viabilidad para ganar la gubernatura: competitiva, no calificable aún.</b> La base municipal muestra fortaleza en el corredor metropolitano y presencia relevante en San Juan del Río; también muestra municipios donde el bloque opositor quedó detrás. El contraste con un perfil de Morena y la configuración de alianzas todavía pueden modificar de manera importante el escenario.", st["body"])]
    story += [standard_table([
        ["Fortalezas observables", "Riesgos a validar", "Condiciones de cierre"],
        ["Presidencia municipal de la capital; victoria PAN-PRI-PRD 2024; zona metropolitana favorable; base territorial ya cargada.", "Definición interna no concluida; transferibilidad limitada de la capital; paridad municipal 9-9; ausencia de estructura auditada y tracking homogéneo.", "Encuesta longitudinal con ficha técnica; dictamen con 20 variables; escenarios de alianzas; responsables y cobertura territorial comprobable."],
    ], [2.25 * inch, 2.25 * inch, 2.23 * inch], st)]
    story += [p("La recomendación de este dictamen es avanzar a una fase de validación, no a una declaración de triunfo. El expediente ya permite ubicar dónde está la base, pero aún debe demostrar la capacidad de convertirla en una candidatura estatal y en una competencia verificable.", st["body"])]
    story += [PageBreak()]

    story += [p("8. Ruta para completar el dictamen", st["h1"])]
    story += [standard_table([
        ["Paso", "Entregable", "Criterio de cierre"],
        ["1. Validar candidatura", "Registro de definición interna, reglas y actores.", "Estatus formal y fuentes partidistas verificables."],
        ["2. Levantar tracking", "Serie estatal y cortes metropolitanos / regionales.", "Mismo cuestionario, universo, campo y ficha técnica."],
        ["3. Convertir territorio en evidencia", "Matriz por municipio, distrito y sección.", "Resultados, participación, INEGI, responsables y cobertura."],
        ["4. Comparar competencia", "Careos equivalentes con escenarios de alianza.", "No mezclar encuestas ni preguntas distintas."],
        ["5. Calificar 20 variables", "Modelo Go2Win con notas y fuentes.", "100% del peso evaluado con evidencia."],
        ["6. Emitir dictamen final", "Conclusión, escenarios y metas de seguimiento.", "Validación del equipo responsable y fecha de corte."],
    ], [1.15 * inch, 2.45 * inch, 3.13 * inch], st)]
    story += [Spacer(1, 0.15 * inch), callout("Resultado esperado", "Un dictamen final podrá indicar no sólo si el perfil es viable, sino bajo qué condiciones, con qué brechas territoriales, qué información respalda cada conclusión y qué debe monitorearse para actualizarla.", st)]
    story += [Spacer(1, 0.2 * inch), p("Fuentes consultadas", st["h2"])]
    source_rows = [["Fuente", "Referencia"]]
    for name, url in SOURCES.items():
        source_rows.append([name, url])
    story += [standard_table(source_rows, [2.0 * inch, 4.73 * inch], st)]
    story += [Spacer(1, 0.12 * inch), p("Nota metodológica: las cifras territoriales de 2021 y 2024 se obtuvieron de los archivos de resultados oficiales del IEEQ incorporados a Go2Win. Los porcentajes de encuestas se reportan tal como fueron publicados por sus fuentes, con sus respectivas metodologías; no son una proyección ni una garantía de resultado.", st["small"])]

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    print(OUTPUT)


if __name__ == "__main__":
    build()
