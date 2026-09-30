"""Genera un dictamen de viabilidad de Felipe Fernando Macías con la estructura Cecilia."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from generate_dictamen_felifer_macias import (
    BLUE,
    GOLD,
    LIGHT,
    MID,
    NAVY,
    TEAL,
    box,
    callout,
    header_footer,
    p,
    standard_table,
    styles,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "Dictamen_Viabilidad_Electoral_Felipe_Fernando_Macias_Queretaro_2027.pdf"

IEEQ_2024 = "https://ieeq.mx/comunicacion/boletines/3094"
IEEQ_RESULTS = "https://ieeq.mx/contenido/elecciones/2023_2024/resultados/"
IEEQ_2021 = "https://ieeq.mx/contenido/ieeq/informes/proceso/2020_2021.pdf"
MUNICIPAL_ROLE = "https://municipiodequeretaro.gob.mx/municipio/repositorios/gacetas-2024-2027/Gaceta-No.38.pdf"
PMD = "https://municipiodequeretaro.gob.mx/municipio/repositorios/transparencia/a66/2T25/scul/PLANDEDESARROLLOMUNICIPAL20242027.pdf"
REPORT_2026 = "https://municipiodequeretaro.gob.mx/con-dos-anos-emparejando-la-cancha-en-queretaro-felifer-macias-destaca-logros-ineditos-durante-su-administracion/"
EL_PAIS = "https://elpais.com/mexico/2026-09-19/defensores-de-la-patria-el-pan-copia-la-estrategia-de-morena-en-un-intento-de-mantener-el-pulso-de-2027.html"
INEGI = "https://www.inegi.org.mx/contenidos/saladeprensa/boletines/2021/EstSociodemo/ResultCenso2020_Qro.pdf"
CE_RESEARCH = "https://ceonline.com.mx/wp-content/uploads/2026/03/11-Destino-27-QUERETARO-2-Marzo-2026.pdf"
METAMETRICS = "https://metametrics.org/rumbo-a-las-elecciones-2027-en-queretaro-4-de-septiembre-2026/"
POLIGRAMA = "https://www.publimetro.com.mx/queretaro/2026/09/16/felifer-macias-encabeza-preferencias-en-queretaro-poligrama/"


def final_header_footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(MID)
    canvas.setLineWidth(0.6)
    canvas.line(0.62 * inch, 0.52 * inch, 7.88 * inch, 0.52 * inch)
    canvas.setFont("Go2Win", 7)
    canvas.setFillColor(colors.HexColor("#526273"))
    canvas.drawString(0.62 * inch, 0.34 * inch, "GO2WIN | Dictamen de viabilidad electoral - Querétaro 2027")
    canvas.drawRightString(7.88 * inch, 0.34 * inch, f"Página {doc.page}")
    canvas.restoreState()


def build() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    st = styles()
    doc = SimpleDocTemplate(
        str(OUTPUT), pagesize=letter, leftMargin=0.62 * inch, rightMargin=0.62 * inch,
        topMargin=0.58 * inch, bottomMargin=0.72 * inch,
        title="Dictamen de viabilidad electoral - Felipe Fernando Macías - Querétaro 2027",
        author="Go2Win",
    )
    s = []

    # 1. Portada y dictamen ejecutivo
    cover = Table([
        [p("GO2WIN", st["cover_small"])],
        [p("DICTAMEN DE VIABILIDAD<br/>ELECTORAL", st["title"])],
        [p("Felipe Fernando Macías Olvera<br/>Posible candidatura del PAN a la Gubernatura de Querétaro - Proceso 2027", st["subtitle"])],
        [Spacer(1, 0.20 * inch)],
        [p("ANÁLISIS ESTRATÉGICO - CORTE: 27 DE SEPTIEMBRE DE 2026", st["cover_small"])],
    ], colWidths=[7.26 * inch], rowHeights=[0.36 * inch, 1.13 * inch, 0.75 * inch, 0.22 * inch, 0.30 * inch])
    cover.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY), ("LEFTPADDING", (0, 0), (-1, -1), 25),
        ("RIGHTPADDING", (0, 0), (-1, -1), 25), ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    s += [Spacer(1, 0.35 * inch), cover, Spacer(1, 0.27 * inch), p("DICTAMEN EJECUTIVO", st["h1"])]
    s += [p("Felipe Fernando Macías reúne condiciones objetivas para ser considerado en la definición del PAN para la gubernatura de Querétaro en 2027: preside el municipio de mayor peso electoral, ganó la capital en 2024 y dispone de una base territorial-estatal ya incorporada a Go2Win. El IEEQ declaró válida su elección como candidato de PAN-PRI-PRD.", st["body"])]
    s += [p("La viabilidad de postulación es <b>favorable pero abierta</b>. La viabilidad para la elección constitucional es <b>competitiva y condicionada</b>. El índice actualizado de <b>66/100</b> incorpora tres fuentes publicadas con ficha técnica, sin promediarlas: coinciden en que Macías es competitivo dentro del PAN, pero difieren en el careo general y la selección interna. No es probabilidad de triunfo ni sustituto de un tracking propio.", st["body"])]
    s += [Table([[box("66/100", "Índice actualizado", st), box('<font size="14">FAVORABLE</font>', "Definición interna", st), box('<font size="12">COMPETITIVA</font>', "Elección general", st), box("18 / 18", "Municipios en la base", st)]], colWidths=[1.78 * inch] * 4)]
    s += [Spacer(1, 0.16 * inch), callout("Conclusión", "La ventaja de Felipe Macías está en la combinación de capital, resultado reciente y visibilidad de gestión. El reto es probar capacidad estatal fuera de la zona metropolitana sin depender de una candidatura, alianza o encuesta todavía no confirmada.", st, GOLD), PageBreak()]

    # 2. Método
    s += [p("1. Objeto, alcance y metodología", st["h1"])]
    s += [p("El dictamen separa tres decisiones: elegibilidad y definición partidista; capacidad de competir en la elección constitucional; y condiciones para convertir una base municipal en una plataforma estatal. Integra resultados electorales, territorio, indicadores socioeconómicos, trayectoria, gestión pública, competencia y riesgos.", st["body"])]
    s += [standard_table([
        ["Categoría", "Qué contiene", "Cómo se usa"],
        ["Dato observado", "Resultado electoral, cargo, plan o documento público con fuente identificable.", "Base factual del diagnóstico."],
        ["Indicador estratégico", "Lectura de fortaleza, brecha o riesgo territorial.", "Ordena prioridades; no reemplaza encuesta."],
        ["Escenario", "Supuesto de candidatura, coalición o comportamiento electoral.", "Permite preparar decisiones contingentes."],
        ["Pendiente", "Información sin fuente, corte o método comparable.", "No recibe puntaje ni se usa para pronóstico."],
    ], [1.30 * inch, 3.30 * inch, 2.10 * inch], st)]
    s += [p("<b>Reglas de evidencia.</b> El documento no iguala aprobación de gobierno con intención de voto; no transfiere automáticamente votos municipales a una gubernatura; y no promedia encuestas que utilicen preguntas o metodologías distintas. Las encuestas se reportan por separado con fecha, universo, modo y pregunta; sirven como fotografía, no como pronóstico.", st["body"])]
    s += [p("<b>Limitaciones.</b> La selección del PAN, candidaturas rivales, coaliciones y reglas finales pueden cambiar. La estructura territorial no ha sido auditada. Los resultados de gestión provienen principalmente de reportes institucionales y deben contrastarse con indicadores, presupuesto, evidencia geográfica y percepción ciudadana.", st["body"]), PageBreak()]

    # 3. Perfil
    s += [p("2. Perfil político y plataforma de salida", st["h1"])]
    s += [p("Felipe Fernando Macías Olvera es Presidente Municipal de Querétaro en el periodo 2024-2027. De acuerdo con su perfil público del IEEQ y del Sistema de Información Legislativa, fue regidor del Ayuntamiento de Querétaro de 2015 a 2018 y diputado federal entre 2018 y 2024. En 2024 encabezó la candidatura común de PAN-PRI-PRD a la presidencia municipal de Querétaro.", st["body"])]
    s += [standard_table([
        ["Activo", "Evidencia / lectura", "Efecto electoral"],
        ["Incumbencia", "Preside el municipio de Querétaro 2024-2027.", "Visibilidad cotidiana y capacidad de demostrar resultados."],
        ["Mandato 2024", "El IEEQ otorgó constancia a la planilla PAN-PRI-PRD encabezada por Macías.", "Base electoral reciente y medible en la capital."],
        ["Trayectoria", "Regiduría y dos periodos federales previos.", "Experiencia legislativa y redes institucionales."],
        ["Escala estatal", "La base de 18 municipios está disponible, pero no equivale a estructura propia.", "Brecha principal a demostrar fuera de la capital."],
    ], [1.20 * inch, 2.85 * inch, 2.65 * inch], st)]
    s += [callout("Fortaleza central", "No inicia desde una candidatura abierta sin base: combina mandato vigente, experiencia y una victoria reciente en el mayor mercado municipal del estado. La debilidad central es la falta de prueba equivalente en el resto de Querétaro.", st), PageBreak()]

    # 4. 2024
    s += [p("3. Punto de partida electoral: ayuntamiento de Querétaro 2024", st["h1"])]
    s += [p("En el municipio de Querétaro, la candidatura PAN-PRI-PRD encabezada por Macías obtuvo 252,293 votos. El bloque Morena-PT-PVEM sumó 205,254 votos; Movimiento Ciudadano, 29,998. El total de votos fue 512,243, con lista nominal de 847,093 y participación de 60.47%. La diferencia entre los dos primeros bloques fue de 47,039 votos.", st["body"])]
    s += [standard_table([
        ["Opción municipal 2024", "Votos", "% sobre total", "Lectura"],
        ["PAN-PRI-PRD", "252,293", "49.25%", "Mayoría y base de salida."],
        ["Morena-PT-PVEM", "205,254", "40.07%", "Rival competitivo en la capital."],
        ["Movimiento Ciudadano", "29,998", "5.86%", "Voto relevante en un escenario fragmentado."],
        ["Otras opciones y nulos", "24,698", "4.82%", "No transferibles automáticamente."],
        ["Ventaja PAN-PRI-PRD", "47,039", "9.18 pp", "Margen municipal, no pronóstico estatal."],
    ], [2.05 * inch, 1.10 * inch, 1.20 * inch, 2.35 * inch], st)]
    s += [p("El dato robustece la plataforma de Macías para competir desde la capital, pero no permite estimar una gubernatura. Una elección estatal agrega municipios, candidatos, coaliciones, participación y dinámicas distintas. Este resultado debe leerse como activo de origen, no como meta automática.", st["body"]), PageBreak()]

    # 5. opinion
    s += [p("4. Posicionamiento y clima de opinión", st["h1"])]
    s += [p("El expediente incorpora tres fuentes públicas con ficha técnica. No se promedian, porque emplean fechas, tamaños muestrales y preguntas distintas. En conjunto permiten una lectura prudente: Macías es competitivo en la interna panista y el careo general sigue abierto y sensible al diseño de la pregunta.", st["body"])]
    s += [standard_table([
        ["Fuente y campo", "Resultado que aporta", "Alcance y cautela"],
        ["CE Research · 1 mar. 2026", "Interna PAN: Macías 39%, Nava 31%, Dorantes 16%. Careo sin PAN-MC: Macías 30%, Santiago Nieto 39%.", "400 entrevistas robóticas a teléfono fijo; ±4.9 pp. Fotografía temprana."],
        ["MetaMetrics · 1-4 sep. 2026", "Interna PAN: Nava 27.1%, Macías 26.9%, Dorantes 16.8%. Partido: PAN 41.5%, Morena-PT-PVEM 34.1%.", "1,500 entrevistas digitales; ±3.4 pp. Empate técnico interno."],
        ["Poligrama · 9 sep. 2026", "Careo: Macías 44.9%, Santiago Nieto 29.9%. Interna PAN: Macías 27.8%, Nava 20.0%, Dorantes 14.1%.", "1,000 encuestas telefónicas; ±3.1 pp. Resultado de un solo día."],
    ], [2.20 * inch, 2.35 * inch, 2.15 * inch], st)]
    s += [callout("Lectura responsable", "Las fuentes coinciden en que Macías es un perfil central del PAN. No coinciden en quién domina la interna ni en un resultado estatal definitivo. Se necesita un tracking propio, con la misma pregunta y metodología, para medir tendencia.", st, GOLD), PageBreak()]

    # 6 model
    s += [p("5. Modelo de viabilidad electoral", st["h1"])]
    s += [p("Se emplea un modelo de ocho dimensiones semejante al utilizado en el dictamen de Cecilia Patrón. El índice de 66/100 sintetiza condiciones observables y brechas. No representa una probabilidad matemática de triunfo. La puntuación de opinión mejora al existir fuentes verificables, pero conserva prudencia por la diferencia entre mediciones y la ausencia de tracking homogéneo.", st["body"])]
    s += [standard_table([
        ["Variable", "Peso", "Score", "Aporte", "Lectura"],
        ["Resultado electoral previo", "16%", "85", "13.6", "Victoria municipal 2024 en la capital; no transferible por sí sola al estado."],
        ["Conocimiento y opinión", "15%", "68", "10.2", "Tres fuentes públicas: competitivo en PAN, con careos y posiciones internas no homogéneas."],
        ["Estructura y nominación", "12%", "60", "7.2", "Cargo y perfil público; proceso PAN abierto y estructura sin auditoría."],
        ["Gestión y resultados", "16%", "70", "11.2", "PMD e informes disponibles; falta contraste territorial y ciudadano."],
        ["Cobertura territorial", "12%", "60", "7.2", "Base de 18 municipios disponible; cobertura operativa aún no validada."],
        ["Coalición y alianzas", "9%", "50", "4.5", "Configuración formal de 2027 pendiente."],
        ["Entorno político", "10%", "65", "6.5", "PAN gobierna el estado; competencia principal abierta."],
        ["Riesgo reputacional", "10%", "60", "6.0", "Sin ruptura documentada; requiere monitoreo sistemático."],
        ["TOTAL", "100%", "", "66.4", "Índice actualizado: 66/100."],
    ], [1.42 * inch, 0.52 * inch, 0.52 * inch, 0.55 * inch, 3.69 * inch], st)]
    s += [p("<b>Resultado del modelo: 66/100, viable con condiciones.</b> La ponderación reconoce una base inicial relevante y evidencia pública de posicionamiento, pero evita elevar el índice mediante supuestos sobre estructura o alianzas. Los tres componentes que más pueden modificarlo son: tracking homogéneo de opinión, definición panista y cobertura territorial auditada.", st["body"]), PageBreak()]

    # 7 competitors
    s += [p("6. Competidores y arquitectura de coalición", st["h1"])]
    s += [p("Al corte del dictamen no existen candidaturas formalmente registradas. Los perfiles siguientes se observan por referencias públicas; no deben presentarse como postulaciones definitivas.", st["body"])]
    s += [standard_table([
        ["Perfil", "Fuerza / condición", "Activo", "Lectura"],
        ["Luis Bernardo Nava Guerrero", "PAN - competencia interna observada", "Experiencia como exalcalde de la capital y presencia estatal.", "La definición interna requiere comparar aceptación, estructura y unidad."],
        ["Agustín Dorantes Lámbarri", "PAN - competencia interna observada", "Senador y trayectoria partidista.", "Perfil competitivo; se requiere lectura territorial homogénea."],
        ["Santiago Nieto Castillo", "Morena - perfil observado", "Alto conocimiento nacional y referencia pública para el bloque opositor.", "Debe validarse candidatura, alianza y fortaleza territorial real."],
    ], [1.30 * inch, 1.55 * inch, 1.80 * inch, 2.05 * inch], st)]
    s += [p("La elección de 2027 podría variar de forma material según cuatro definiciones: método interno del PAN, candidato de Morena, participación de PRI/MC y reglas de alianzas. Ninguna transferencia de voto puede asumirse antes de que esas definiciones se formalicen.", st["body"]), PageBreak()]

    # 8 geography
    s += [p("7. Geografía electoral de Querétaro", st["h1"])]
    s += [p("La base de Go2Win agrupa 18 municipios, resultados de ayuntamientos 2021 y 2024, 15 distritos locales, secciones e indicadores INEGI. Para planeación se propone una lectura funcional, no una regionalización legal: zona metropolitana, corredor San Juan del Río, semidesierto y Sierra-Golfo.", st["body"])]
    s += [standard_table([
        ["Zona funcional", "Condición inicial", "Riesgo", "Prueba necesaria"],
        ["Zona metropolitana: Querétaro, Corregidora, El Marqués, Huimilpan", "Mayor concentración de electorado; ventaja PAN-PRI-PRD en 2024 en los tres municipios principales.", "Confiar sólo en la capital o dar por consolidado el voto metropolitano.", "Voto por sección, participación y responsables."],
        ["Corredor San Juan del Río", "Segundo mercado municipal; PAN-PRI-PRD obtuvo ventaja local en 2024.", "Margen menor y competencia municipal distinta.", "Diagnóstico de secciones y red local."],
        ["Semidesierto", "Municipios con resultados divididos y participación alta.", "Cambios de alianza y candidaturas locales alteran el mapa.", "Lectura municipio por municipio."],
        ["Sierra-Golfo", "Menor volumen, relevancia para cobertura estatal y narrativa de cercanía.", "Dispersión territorial y menor evidencia organizativa.", "Cobertura, servicios y estructura verificable."],
    ], [1.35 * inch, 2.00 * inch, 1.65 * inch, 1.70 * inch], st)]
    s += [callout("Dato territorial", "En 2024, PAN-PRI-PRD y Morena-PT-PVEM tuvieron ventaja municipal en 9 municipios cada uno. La paridad territorial aconseja trabajar con prioridades y brechas, no con un mapa binario de municipios ganados o perdidos.", st), PageBreak()]

    # 9 management
    s += [p("8. Gestión municipal como activo y prueba", st["h1"])]
    s += [p("El Plan Municipal de Desarrollo 2024-2027 ordena seis ejes: Querétaro preventivo y justo; moderno e innovador; ordenado; amigable con el medio ambiente; familiar y social; y ciudadano. El segundo informe municipal reporta acciones en seguridad, movilidad, espacios públicos, áreas de conservación y atención social. Son activos potenciales de evaluación, no logros electorales automáticos.", st["body"])]
    s += [standard_table([
        ["Frente", "Activo reportado", "Pregunta crítica", "Prueba requerida"],
        ["Seguridad", "Coordinación institucional y resultados comunicados en segundo informe.", "¿El resultado se percibe y se sostiene por zona?", "Indicadores oficiales, percepción y mapa de incidencias."],
        ["Movilidad", "Transporte comunitario y eléctrico gratuito reportados.", "¿Cobertura, uso y calidad alcanzan a quienes lo necesitan?", "Rutas, viajes, usuarios y evaluación territorial."],
        ["Orden urbano", "Plan Orden y regulación del crecimiento.", "¿Hay certeza, servicios y aceptación en expansión urbana?", "Expedientes, tiempos de respuesta y zonas críticas."],
        ["Espacio público y ambiente", "Recuperación de espacios y acciones de conservación reportadas.", "¿Qué cobertura y permanencia tienen?", "Inventario georreferenciado y mantenimiento."],
    ], [1.20 * inch, 1.85 * inch, 1.75 * inch, 1.90 * inch], st)]
    s += [p("La regla del dictamen es convertir cada afirmación de gobierno en problema, acción, cobertura, resultado verificable y percepción ciudadana. Sólo entonces puede contribuir de forma sólida al modelo de viabilidad.", st["body"]), PageBreak()]

    # 10 agenda
    s += [p("9. Agenda territorial y credibilidad temática", st["h1"])]
    s += [p("Querétaro combina expansión urbana, dinamismo metropolitano y municipios con realidades rurales y serranas. INEGI reportó para el estado 2.37 millones de habitantes en 2020, crecimiento de viviendas y mejoras en conectividad, pero estas condiciones no sustituyen el diagnóstico local de servicios, seguridad y costo de vida.", st["body"])]
    s += [standard_table([
        ["Tema", "Reto territorial", "Oferta pública comprobable", "Indicador a vigilar"],
        ["Seguridad y justicia cívica", "Percepción y hechos por colonia, comunidad y municipio.", "Coordinación y capacidad de respuesta con evidencia.", "Incidencia, tiempos y percepción."],
        ["Movilidad y crecimiento", "Expansión urbana, traslados y servicios en periferias.", "Cobertura y calidad de transporte / infraestructura.", "Viajes, tiempos y cobertura."],
        ["Agua, ambiente y orden", "Presión de desarrollo y desigualdad en servicios.", "Planeación, conservación y respuesta pública.", "Disponibilidad, atención y cobertura."],
        ["Economía familiar", "Empleo, costo de vida y acceso a oportunidades.", "Programas con población, costo y resultado medible.", "Beneficiarios y evaluación."],
    ], [1.35 * inch, 1.85 * inch, 2.00 * inch, 1.50 * inch], st)]
    s += [callout("Advertencia", "La agenda no debe definirse sólo desde el informe de gobierno. Requiere encuestas, escucha ciudadana y evidencia de campo para distinguir logro comunicado, problema persistente y prioridad electoral.", st, GOLD), PageBreak()]

    # 11 FODA
    s += [p("10. FODA y matriz de riesgos", st["h1"])]
    s += [standard_table([
        ["FORTALEZAS", "OPORTUNIDADES"],
        ["Victoria municipal reciente; cargo vigente; visibilidad en capital; trayectoria legislativa; base territorial-electoral cargada.", "Convertir resultados verificables de gestión en plataforma estatal; ampliar evidencia fuera de la capital; profesionalizar seguimiento por municipio y sección."],
        ["DEBILIDADES", "AMENAZAS"],
        ["Sin encuesta comparable propia; estructura no auditada; traslado estatal no demostrado; modelo sin puntuación completa.", "Definición interna adversa; rival opositor competitivo; fragmentación o alianza distinta; crisis de servicios, seguridad u orden urbano; actos anticipados y conflicto interno."],
    ], [3.35 * inch, 3.35 * inch], st)]
    s += [p("<b>Riesgo dominante.</b> La fuerza de la capital puede convertirse en una falsa sensación de cobertura estatal. El riesgo no es sólo perder municipios; es no saber qué secciones, distritos y liderazgos hacen competitiva cada zona antes de fijar metas.", st["body"]), PageBreak()]

    # 12 scenarios
    s += [p("11. Escenarios electorales 2027", st["h1"])]
    s += [standard_table([
        ["Escenario", "Configuración", "Evaluación", "Condición decisiva"],
        ["A. Plataforma consolidada", "Macías obtiene postulación; PAN cohesionado; evidencia territorial y gestión verificable.", "Favorable", "Capital se amplía a regiones y se reduce incertidumbre."],
        ["B. Elección competitiva", "Nominación definida; rival opositor conocido; coalición abierta.", "Abierta", "Tracking y estructura municipal determinan la capacidad de cierre."],
        ["C. Ventaja comprimida", "Competencia interna prolongada o agenda de servicios se deteriora.", "Riesgo alto", "Unidad, respuesta pública y control de daños."],
        ["D. Fragmentación", "Alianzas no coinciden; MC o PRI reordenan el mercado.", "Incierta", "Transferencia real de voto, no supuesta."],
        ["E. Choque externo", "Seguridad, agua, movilidad o crisis económica dominan agenda.", "Incierta", "Capacidad de respuesta verificable y territorial."],
    ], [1.30 * inch, 2.18 * inch, 1.00 * inch, 2.25 * inch], st)]
    s += [p("Los escenarios no son predicciones. Son hipótesis de planeación que deberán alimentarse con datos de candidatura, encuestas comparables, elecciones históricas, estructura y conversación pública.", st["body"]), PageBreak()]

    # 13 roadmap
    s += [p("12. Ruta estratégica y tablero de control", st["h1"])]
    s += [standard_table([
        ["Fase", "Objetivo", "Producto verificable"],
        ["0-30 días", "Homologar expediente y línea base.", "Inventario de fuentes, resultados y mapa de vacíos."],
        ["31-60 días", "Cerrar brechas de conocimiento territorial.", "Matriz de 18 municipios, 15 distritos y secciones prioritarias."],
        ["61-90 días", "Medir opinión y competencia.", "Tracking con ficha técnica y careos homogéneos."],
        ["Definición interna", "Acreditar nominación, unidad y legalidad.", "Estatus formal, escenarios y protocolo de riesgos."],
        ["Precampaña / campaña", "Convertir evidencia en seguimiento operativo.", "Metas, responsables, acciones y tablero periódico."],
    ], [1.35 * inch, 2.50 * inch, 2.85 * inch], st)]
    s += [p("<b>Tablero mínimo semanal.</b> Opinión: conocimiento, favorabilidad, preferencia e indecisos. Territorio: participación, voto histórico, cobertura y responsable. Gestión: problema, acción, evidencia y percepción. Riesgo: temas negativos, medios, legalidad y respuesta. Operación: metas, actividades, cumplimiento y pendientes.", st["body"]), PageBreak()]

    # 14 control
    s += [p("13. Control de consistencia y fuentes", st["h1"])]
    s += [standard_table([
        ["Tema", "Hallazgo robusto", "Dato variable", "Criterio"],
        ["Cargo", "Presidente Municipal de Querétaro 2024-2027.", "Ninguno relevante.", "Hecho oficial."],
        ["Resultado 2024", "252,293 votos para la candidatura PAN-PRI-PRD en capital.", "Alianzas y candidaturas 2027.", "Base municipal, no pronóstico."],
        ["Territorio", "18 municipios y resultados locales en Go2Win.", "Estructura propia por municipio / sección.", "Cobertura de datos no es cobertura política."],
        ["Gestión", "PMD e informes públicos disponibles.", "Impacto y percepción por zona.", "Requiere validación independiente."],
        ["Opinión", "Tres encuestas públicas con fichas técnicas disponibles.", "Tendencia homogénea y negativos por región.", "Comparar por pregunta, fecha y metodología; no promediar."],
        ["Competencia", "PAN y Morena con perfiles públicos observados.", "Registros, alianzas y método.", "Actualizar permanentemente."],
    ], [1.00 * inch, 2.05 * inch, 1.75 * inch, 1.90 * inch], st)]
    source_rows = [["Fuente", "Uso"]]
    for name, use in [
        ("IEEQ 2024", "Validez de elección, resultado municipal y base histórica."),
        ("IEEQ 2021", "Contexto electoral estatal histórico."),
        ("Municipio de Querétaro", "Cargo vigente, PMD e informes de gobierno."),
        ("INEGI", "Contexto sociodemográfico y territorial."),
        ("CE Research, MetaMetrics y Poligrama", "Posicionamiento e interna; cada medición se conserva separada."),
        ("El País", "Contexto de definición política 2027; no prueba candidatura."),
    ]:
        source_rows.append([name, use])
    s += [Spacer(1, 0.10 * inch), standard_table(source_rows, [2.0 * inch, 4.7 * inch], st), PageBreak()]

    # 15 final
    s += [p("14. Dictamen final", st["h1"])]
    s += [Table([[box("66/100", "Índice actualizado", st), box('<font size="14">FAVORABLE</font>', "Nominación", st), box('<font size="12">COMPETITIVA</font>', "Elección general", st), box('<font size="13">PRIORITARIO</font>', "Siguiente paso", st)]], colWidths=[1.78 * inch] * 4)]
    s += [Spacer(1, 0.16 * inch), p("<b>Conclusión.</b> Felipe Fernando Macías cuenta con condiciones objetivas para entrar a la definición panista por la gubernatura de Querétaro desde una posición competitiva: mandato municipal vigente, victoria comprobada en el municipio de mayor escala electoral, experiencia previa y una plataforma territorial de información ya disponible.", st["body"])]
    s += [p("El índice actualizado de <b>66/100</b> significa viabilidad con condiciones: reconoce la plataforma existente y la evidencia pública de posicionamiento, sin convertirla en pronóstico. La capital es un activo relevante, pero la competencia estatal exige acreditar cobertura fuera de la zona metropolitana, resolver la definición interna, medir opinión con metodología homogénea y validar la estructura por municipio, distrito y sección.", st["body"])]
    s += [p("<b>Dictamen:</b> viable para avanzar a la etapa de validación completa. No se recomienda convertir este resultado en una declaración de candidatura, preferencia definitiva o triunfo. La siguiente actualización debe incorporar tracking base, método partidista definido, escenarios de coalición y evidencia territorial auditada.", st["body"])]
    s += [callout("Alcance", "Go2Win ya permite centralizar estas fuentes, ubicar el mercado electoral, cruzarlo con INEGI y dar seguimiento a las condiciones que faltan. El dictamen se vuelve más fuerte cada vez que una hipótesis se transforma en evidencia verificable.", st, TEAL)]
    s += [Spacer(1, 0.25 * inch), p("Referencias web utilizadas", st["h2"])]
    refs = [
        ("IEEQ 2024", IEEQ_2024), ("Resultados IEEQ 2024", IEEQ_RESULTS), ("Informe IEEQ 2021", IEEQ_2021),
        ("Municipio de Querétaro", MUNICIPAL_ROLE), ("PMD 2024-2027", PMD), ("Segundo Informe 2026", REPORT_2026),
        ("INEGI", INEGI), ("CE Research · marzo 2026", CE_RESEARCH), ("MetaMetrics · septiembre 2026", METAMETRICS),
        ("Poligrama · septiembre 2026", POLIGRAMA), ("Contexto político 2027", EL_PAIS),
    ]
    s += [standard_table([["Fuente", "Liga"]] + [[name, url] for name, url in refs], [1.75 * inch, 4.95 * inch], st)]
    s += [Spacer(1, 0.10 * inch), p("Nota: las referencias institucionales de gestión se tratan como información reportada por la administración. Para fines de evaluación electoral deberán contrastarse con indicadores oficiales, evidencia geográfica, gasto y percepción ciudadana.", st["small"])]

    doc.build(s, onFirstPage=final_header_footer, onLaterPages=final_header_footer)
    print(OUTPUT)


if __name__ == "__main__":
    build()
