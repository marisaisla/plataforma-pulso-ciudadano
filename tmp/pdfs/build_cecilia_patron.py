from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether
)
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.colors import HexColor
from pathlib import Path

OUT = Path(r"C:\Users\jorge\Documents\Codex\2026-09-05\Plataforma-Pulso-Ciudadano-Local\output\pdf\Dictamen_Viabilidad_Electoral_Cecilia_Patron_Laviada_Merida_2027.pdf")
OUT.parent.mkdir(parents=True, exist_ok=True)

NAVY = HexColor('#132840')
BLUE = HexColor('#24618D')
TEAL = HexColor('#208B77')
GOLD = HexColor('#D99A25')
RED = HexColor('#B74A4A')
INK = HexColor('#172333')
MUTED = HexColor('#5A6878')
PALE = HexColor('#EEF3F6')
GRID = HexColor('#C8D5DE')
WHITE = colors.white

regular = r"C:\Windows\Fonts\arial.ttf"
bold = r"C:\Windows\Fonts\arialbd.ttf"
pdfmetrics.registerFont(TTFont('Arial', regular))
pdfmetrics.registerFont(TTFont('Arial-Bold', bold))

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='H1x', fontName='Arial-Bold', fontSize=22, leading=26, textColor=NAVY, spaceAfter=8))
styles.add(ParagraphStyle(name='H2x', fontName='Arial-Bold', fontSize=13.5, leading=16, textColor=BLUE, spaceBefore=3, spaceAfter=10))
styles.add(ParagraphStyle(name='H3x', fontName='Arial-Bold', fontSize=10.3, leading=13, textColor=NAVY, spaceBefore=6, spaceAfter=4))
styles.add(ParagraphStyle(name='Bodyx', fontName='Arial', fontSize=8.9, leading=12.3, textColor=INK, spaceAfter=6))
styles.add(ParagraphStyle(name='Smallx', fontName='Arial', fontSize=7.3, leading=9.5, textColor=MUTED))
styles.add(ParagraphStyle(name='Cellx', fontName='Arial', fontSize=7.4, leading=9.4, textColor=INK))
styles.add(ParagraphStyle(name='CellBold', fontName='Arial-Bold', fontSize=7.4, leading=9.4, textColor=NAVY))
styles.add(ParagraphStyle(name='Whitex', fontName='Arial-Bold', fontSize=8.2, leading=10, textColor=WHITE))
styles.add(ParagraphStyle(name='BigScore', fontName='Arial-Bold', fontSize=18, leading=20, textColor=TEAL))
styles.add(ParagraphStyle(name='Quote', fontName='Arial-Bold', fontSize=9.4, leading=12.5, textColor=NAVY))

def P(text, style='Bodyx'):
    return Paragraph(text, styles[style])

def bullets(items):
    return [P('• ' + x) for x in items]

def table(data, widths, header=True, font=7.4, row_bgs=None):
    cooked = []
    for r, row in enumerate(data):
        cooked.append([P(str(v), 'Whitex' if header and r == 0 else ('CellBold' if (not header and r == 0) else 'Cellx')) for v in row])
    t = Table(cooked, colWidths=widths, repeatRows=1 if header else 0, hAlign='LEFT')
    commands = [
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.45, GRID),
        ('LEFTPADDING', (0,0), (-1,-1), 6), ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]
    if header:
        commands += [('BACKGROUND', (0,0), (-1,0), NAVY)]
        for r in range(1, len(data)):
            if r % 2 == 0: commands.append(('BACKGROUND', (0,r), (-1,r), PALE))
    if row_bgs:
        for r, bg in row_bgs.items(): commands.append(('BACKGROUND', (0,r), (-1,r), bg))
    t.setStyle(TableStyle(commands))
    return t

def callout(text, color=BLUE):
    t = Table([[P(text, 'Quote')]], colWidths=[170*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),PALE), ('BOX',(0,0),(-1,-1),0.8,color),
        ('LEFTPADDING',(0,0),(-1,-1),10), ('RIGHTPADDING',(0,0),(-1,-1),10),
        ('TOPPADDING',(0,0),(-1,-1),8), ('BOTTOMPADDING',(0,0),(-1,-1),8)
    ]))
    return t

def score_cards(cards):
    cells=[]
    for title, value, note, col in cards:
        cells.append([P(title,'Smallx'), Paragraph(value, ParagraphStyle('tmp',parent=styles['BigScore'],textColor=col)), P(note,'Smallx')])
    outer=[]
    for cell in cells:
        tt=Table([[cell[0]],[cell[1]],[cell[2]]], colWidths=[51*mm], rowHeights=[9*mm,16*mm,9*mm])
        tt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),PALE),('BOX',(0,0),(-1,-1),0.6,GRID),('LEFTPADDING',(0,0),(-1,-1),8)]))
        outer.append(tt)
    return Table([outer], colWidths=[56*mm]*3, hAlign='CENTER')

def header_footer(c: Canvas, doc):
    c.saveState()
    w,h=A4
    c.setFillColor(NAVY); c.rect(0,h-22*mm,w,22*mm,fill=1,stroke=0)
    c.setFont('Arial-Bold',8); c.setFillColor(WHITE)
    c.drawString(18*mm,h-13.5*mm,'DICTAMEN DE VIABILIDAD ELECTORAL | MÉRIDA 2027')
    c.setFont('Arial',7); c.setFillColor(MUTED)
    c.drawString(18*mm,9*mm,'Análisis estratégico · Corte: 25 de septiembre de 2026')
    c.drawRightString(w-18*mm,9*mm,f'Página {doc.page}')
    c.restoreState()

doc=BaseDocTemplate(str(OUT), pagesize=A4, leftMargin=18*mm, rightMargin=18*mm, topMargin=30*mm, bottomMargin=17*mm,
                    title='Dictamen de viabilidad electoral de Cecilia Patrón Laviada', author='Análisis estratégico')
frame=Frame(doc.leftMargin,doc.bottomMargin,doc.width,doc.height,id='main')
doc.addPageTemplates(PageTemplate(id='all',frames=[frame],onPage=header_footer))
S=[]

# 1
S += [Spacer(1,22*mm), P('DICTAMEN DE VIABILIDAD ELECTORAL','H2x'),
      P('Cecilia Anunciación Patrón Laviada','H1x'),
      P('Posible candidatura a la Presidencia Municipal de Mérida · Proceso 2027', 'H2x'), Spacer(1,5*mm)]
S.append(score_cards([
    ('Viabilidad global','84/100','Alta, condicionada',TEAL),
    ('Nominación PAN','FAVORABLE','Incumbencia y liderazgo',TEAL),
    ('Elección general','COMPETITIVA','Ventaja inicial, no irreversible',GOLD)]))
S += [Spacer(1,12*mm),P('DICTAMEN EJECUTIVO','H2x'),
      P('Cecilia Patrón presenta una <b>viabilidad electoral alta, aunque condicionada</b>, para buscar un segundo periodo al frente del Ayuntamiento de Mérida en 2027. Parte de cuatro activos: victoria comprobada en 2024, control de agenda municipal, reconocimiento elevado y una marca panista históricamente competitiva en la capital.'),
      P('El cómputo municipal de 2024 registró <b>258,489 votos</b> para su candidatura frente a <b>205,395</b> para la coalición Morena–PT–PVEM: una diferencia de 53,094 sufragios. En 2026, mediciones públicas la ubican entre 59.4% y 64.5% de aprobación. El entorno, sin embargo, es más exigente: Morena gobierna Yucatán, la coordinación metropolitana incide en servicios visibles y el desgaste de gestión puede comprimir la ventaja.'),
      callout('<b>DICTAMEN:</b> candidatura viable y favorita inicial. Para conservar esa posición debe transformar aprobación en preferencia electoral, sostener resultados verificables en calles, agua, alumbrado, movilidad y seguridad, y ampliar la coalición social hacia el sur, poniente y comisarías.'),
      Spacer(1,12*mm),P('Documento para presentación a la posible candidata. Las calificaciones son indicadores estratégicos, no probabilidades ni garantías de resultado.','Smallx'), PageBreak()]

# 2
S += [P('1. Objeto, alcance y metodología','H2x'),
      P('El dictamen evalúa tres decisiones distintas: elegibilidad y ruta de elección consecutiva; probabilidad de obtener la postulación; y capacidad de ganar la elección constitucional. Integra hechos oficiales, desempeño, mediciones públicas, estructura partidista, territorio y riesgos.'),
      P('Reglas de evidencia','H3x'), table([
          ['Categoría','Qué contiene','Cómo se usa'],
          ['Dato observado','Cargo, resultado electoral, cifra o norma identificable.','Base factual del diagnóstico.'],
          ['Indicador estratégico','Calificación ponderada de activos y brechas.','Ordena prioridades; no es encuesta.'],
          ['Escenario','Supuesto sobre candidatura, coalición o contexto.','Permite preparar decisiones contingentes.']], [40*mm,65*mm,65*mm]),
      P('Criterios de lectura','H3x')] + bullets([
          'Separar aprobación de gobierno, intención de voto y fortaleza partidista.',
          'No promediar encuestas con métodos, fechas o universos distintos.',
          'Distinguir resultados municipales propios de variables estatales o federales.',
          'Evaluar Mérida por zonas sociales y funcionales, no como un territorio homogéneo.',
          'Mantener abiertas las hipótesis de coalición y rival hasta su registro formal.'
      ]) + [P('Nota jurídica','H3x'), P('La Constitución de Yucatán vigente permite a presidentas y presidentes municipales ser electos por un periodo adicional, con postulación del mismo partido o de alguno de los partidos de la coalición original, salvo la excepción de renuncia o pérdida de militancia prevista. La reforma federal que prohíbe la reelección será aplicable a procesos de 2030; por ello, <b>la ruta de 2027 es jurídicamente posible</b>, sujeta a requisitos, plazos y criterios electorales aplicables.'),
      callout('La elegibilidad formal debe validarse nuevamente al inicio del proceso electoral con la normativa, lineamientos y resoluciones vigentes.',GOLD), PageBreak()]

#3
S += [P('2. Perfil político y plataforma de salida','H2x'),
      P('Cecilia Patrón ocupa la Presidencia Municipal de Mérida para el periodo 2024–2027. Antes fue diputada federal en las legislaturas LXIV y LXV; en esta última llegó por mayoría relativa en el distrito federal 4 de Yucatán. Su trayectoria combina trabajo social, operación partidista, representación legislativa y gobierno municipal.'),
      table([
          ['Activo','Evidencia / lectura','Efecto electoral'],
          ['Incumbencia','Encabeza el gobierno municipal y la agenda cotidiana.','Alta visibilidad y capacidad de demostrar resultados.'],
          ['Mandato 2024','Ganó con 258,489 votos en coalición.','Base electoral reciente y medible.'],
          ['Experiencia federal','Dos periodos como diputada federal.','Red institucional y experiencia legislativa.'],
          ['Estructura partidista','Trayectoria en el PAN y conocimiento de su organización.','Facilita nominación y movilización.'],
          ['Perfil de cercanía','Narrativa de atención territorial y servicios.','Afinidad con voto vecinal; exige presencia constante.'],
          ['Arraigo meridano','Carrera pública concentrada en Mérida y Yucatán.','Identidad local sólida; riesgo de sobreexposición.']], [37*mm,76*mm,57*mm]),
      P('Fortaleza central','H3x'), P('Su perfil encaja con una elección municipal: conocimiento, estructura y capacidad de asociar la candidatura con resultados visibles en el entorno inmediato.'),
      P('Debilidad central','H3x'), P('La misma incumbencia convierte cada falla de servicio, conflicto urbano o percepción de desigualdad territorial en una evaluación personal de la candidata.'),
      callout('La campaña no debe presentarla como una aspirante que promete empezar, sino como una presidenta que rinde cuentas, corrige y solicita continuidad con metas concretas.'), PageBreak()]

#4
S += [P('3. Punto de partida electoral: elección municipal 2024','H2x'),
      P('El acta de cómputo municipal del IEPAC reportó 514,886 votos contabilizados. La candidatura PAN–PRI–Nueva Alianza obtuvo 258,489; Morena–PT–PVEM, 205,395; Movimiento Ciudadano, 35,892; PRD, 2,689; candidaturas no registradas, 315; y votos nulos, 12,111.'),
      table([
          ['Opción','Votos','% sobre total','Lectura'],
          ['PAN–PRI–Nueva Alianza','258,489','50.20%','Mayoría; base de continuidad.'],
          ['Morena–PT–PVEM','205,395','39.89%','Rival competitivo y estructurado.'],
          ['Movimiento Ciudadano','35,892','6.97%','Bolsa decisiva si crece o se redistribuye.'],
          ['PRD','2,689','0.52%','Incidencia limitada.'],
          ['No registrados + nulos','12,426','2.41%','Señal de rechazo o error, no transferible.']], [48*mm,27*mm,29*mm,66*mm]),
      Spacer(1,6*mm), score_cards([
          ('Ventaja nominal','53,094','votos',TEAL),
          ('Margen total','10.31 pp','sobre votos emitidos',TEAL),
          ('Umbral de alerta','< 6 pp','contienda cerrada',GOLD)]),
      P('Lectura estratégica','H3x'), P('La ventaja fue relevante, pero no blindada. Una oscilación neta de aproximadamente 26,500 votos habría empatado la contienda. La prioridad no es sólo conservar el voto de 2024: es impedir que el desgaste de gobierno una a los inconformes y, simultáneamente, conquistar electores de MC, abstencionistas y votantes blandos de Morena.'),
      callout('Meta política sugerida: sostener un colchón de al menos 8 puntos en medición homogénea y una ventaja territorial visible en la mayoría de las zonas operativas.',GOLD), PageBreak()]

#5
S += [P('4. Aprobación y clima de opinión','H2x'),
      P('Las mediciones disponibles en 2026 muestran una posición favorable, pero no son directamente comparables. La aprobación mide evaluación de desempeño; no equivale a intención de voto ni asegura transferencia partidista.'),
      table([
          ['Medición / corte','Aprobación','Lectura'],
          ['LaEncuesta.mx · marzo 2026','64.5%','Nivel alto; requiere revisar ficha técnica y serie.'],
          ['MetaMetrics · agosto 2026','64.1%','Primer lugar entre capitales en su medición.'],
          ['Demoscopia Digital · agosto 2026','59.4%','Mayoría favorable, con margen de desgaste.']], [62*mm,32*mm,76*mm]),
      P('Conclusión robusta','H3x'), P('Existe una mayoría que aprueba su gestión en las mediciones citadas. La banda 59–65% es un activo político, pero la decisión electoral dependerá del rival, alianza, participación, campaña y evaluación de servicios al cierre de 2026 y primer semestre de 2027.'),
      P('Preguntas que el tracking debe responder','H3x')] + bullets([
          '¿Cuánto de la aprobación se convierte en voto por reelección?',
          '¿Dónde se concentra la desaprobación: sur, poniente, periferia, centro o comisarías?',
          '¿Qué servicio explica mejor el voto de castigo?',
          '¿Cuál es el techo propio y cuál el de la marca PAN?',
          '¿Quién puede unificar el voto opositor y con qué atributos?'
      ]) + [callout('No comunicar rankings como sustituto de resultados. La mejor defensa electoral es una serie propia, comparable y auditada.',GOLD), PageBreak()]

#6
S += [P('5. Modelo de viabilidad electoral','H2x'),
      P('El índice de 84/100 sintetiza condiciones actuales. No representa una probabilidad matemática de triunfo.'),
      table([
          ['Variable','Peso','Score','Aporte','Lectura'],
          ['Resultado electoral previo','16%','90','14.4','Ventaja comprobada en 2024.'],
          ['Aprobación y conocimiento','15%','88','13.2','Posición favorable en 2026.'],
          ['Estructura y nominación','12%','91','10.9','Incumbencia y control de red.'],
          ['Gestión y resultados','16%','80','12.8','Activos visibles; escrutinio alto.'],
          ['Cobertura territorial','12%','77','9.2','Brechas entre zonas de la ciudad.'],
          ['Coalición y alianzas','9%','74','6.7','Configuración 2027 aún abierta.'],
          ['Entorno político','10%','75','7.5','Gobierno estatal de Morena eleva competencia.'],
          ['Riesgo reputacional','10%','91','9.1','Sin ruptura dominante; requiere prevención.'],
          ['TOTAL','100%','','83.8','Redondeado: 84/100.']], [48*mm,18*mm,18*mm,20*mm,66*mm]),
      P('Semáforo','H3x'), table([
          ['Rango','Clasificación','Condición'],
          ['85–100','Muy alta','Ventaja estable y riesgos contenidos.'],
          ['75–84','Alta, condicionada','Favorita inicial; debe proteger desempeño.'],
          ['60–74','Competitiva','Elección abierta.'],
          ['<60','Baja / vulnerable','Necesita recomposición sustantiva.']], [30*mm,50*mm,90*mm]),
      callout('Resultado: 84/100. Se ubica en el límite superior de “alta, condicionada”; puede subir con evidencia de servicios y coalición definida, o caer rápidamente si la aprobación deja de convertirse en preferencia.',TEAL), PageBreak()]

#7
S += [P('6. Competidores y arquitectura de coalición','H2x'),
      P('Al corte del dictamen no existen candidaturas formalmente registradas. Los nombres siguientes son perfiles observados en encuestas, declaraciones y movimientos partidistas; deben tratarse como hipótesis competitivas y actualizarse cuando se publiquen convocatorias y registros.'),
      table([
          ['Perfil','Fuerza','Activos','Riesgos / lectura'],
          ['Rommel Pacheco Marrufo','Morena','Excandidato 2024; 205,395 votos del bloque; alto conocimiento; respaldo institucional potencial.','Principal rival observado. Carga la derrota previa y debe recomponer unidad interna.'],
          ['Jessica Saidén Quiroz','Morena','Estructura política y crecimiento en mediciones internas; posibilidad de cohesionar sectores.','Menor conocimiento municipal que Rommel; depende de nominación y transferencia.'],
          ['Verónica Camino Farjat','Morena','Senadora; candidata a Mérida en 2021; experiencia y reconocimiento.','Resultado previo y competencia interna; posicionamiento variable entre estudios.'],
          ['Óscar Brito Zapata','Morena','Diputado federal; trayectoria partidista; perfil generacional y territorial.','Conocimiento público menor; necesita ampliar estructura y atributos ejecutivos.'],
          ['Javier Osante Solís','Movimiento Ciudadano','Diputado local con licencia; opción perfilada por MC; puede captar voto joven y de rechazo.','Estructura menor y presión de voto útil; hoy altera más el margen que el liderazgo.']], [38*mm,26*mm,54*mm,52*mm]),
      P('Competencia interna y factores políticos','H3x'),
      P('<b>Elías Lixa Abimerhi</b> y <b>Álvaro Cetina Puerto</b> han sido medidos o mencionados como alternativas panistas. Si Cecilia confirma la búsqueda de elección consecutiva, su relevancia principal será la negociación de unidad, candidaturas legislativas y estructura, no la competencia constitucional. Ermilo Barrera y Benito Domínguez aparecen como opciones secundarias dentro de Morena.'),
      P('Jerarquización de amenaza','H3x'),
      table([
          ['Nivel','Perfil','Condición que eleva el riesgo'],
          ['1','Rommel Pacheco','Coalición Morena-PT-PVEM unida y transferencia del gobierno estatal.'],
          ['2','Jessica Saidén','Candidatura de consenso con estructura y posicionamiento creciente.'],
          ['3','Verónica Camino','Unificación de redes políticas y recuperación de voto urbano.'],
          ['4','Óscar Brito','Salto de conocimiento y operación territorial eficaz.'],
          ['5','Javier Osante','Crecimiento de MC suficiente para capturar voto panista blando.']], [20*mm,45*mm,105*mm]),
      callout('Amenaza principal: que Morena seleccione un perfil único, evite fracturas y convierta el respaldo estatal en una oferta municipal de cambio. A la fecha, Rommel Pacheco es el rival individual de referencia.',GOLD), PageBreak()]

#8
S += [P('7. Geografía electoral de Mérida','H2x'),
      P('Mérida tenía 995,129 habitantes en el Censo 2020, distribuidos en 166 localidades. La ciudad concentra la mayoría de la población, pero Cholul, Caucel y las comisarías obligan a una operación diferenciada. El territorio combina alta consolidación urbana, expansión periférica y contrastes de servicios.'),
      table([
          ['Zona funcional','Condición inicial','Riesgo','Prioridad'],
          ['Norte consolidado','Base favorable, mayor ingreso y evaluación exigente.','Desgaste por movilidad, densificación y orden urbano.','Calidad de servicios, seguridad vial y certeza regulatoria.'],
          ['Centro','Alta visibilidad, comercio, turismo y patrimonio.','Conflictos por movilidad, uso de vía pública y vivienda.','Orden con diálogo, limpieza y recuperación de espacios.'],
          ['Poniente–Caucel','Crecimiento, familias jóvenes y movilidad pendular.','Tráfico, drenaje pluvial, tiempos de traslado y servicios.','Conectividad, alumbrado, parques y respuesta rápida.'],
          ['Sur y suroriente','Demanda histórica de equidad urbana.','Percepción de abandono y voto opositor concentrado.','Obra básica, economía familiar y presencia territorial.'],
          ['Oriente','Alta densidad y diversidad social.','Servicios, seguridad cotidiana y deterioro vial.','Microzonificación y compromisos por colonia.'],
          ['Comisarías','Identidad propia y necesidades de agua, caminos y transporte.','Promesas urbanas poco pertinentes.','Agenda rural-periurbana, brigadas y enlaces permanentes.']], [34*mm,45*mm,45*mm,46*mm]),
      callout('La campaña debe organizarse por problemas y trayectos cotidianos, no sólo por distritos formales. Cada zona necesita una promesa verificable y un responsable territorial.'), PageBreak()]

#9
S += [P('8. Gestión municipal como activo y prueba','H2x'),
      P('La administración ha comunicado avances en bacheo, alumbrado LED, ordenamiento, parques, agua en comisarías, atención a mujeres y finanzas municipales. Estos datos son activos potenciales sólo si se documentan con línea base, ubicación, costo, cobertura y satisfacción ciudadana.'),
      table([
          ['Frente','Activo potencial','Pregunta crítica','Prueba necesaria'],
          ['Calles y bacheo','Alta actividad reportada.','¿Disminuyó reincidencia y tiempo de respuesta?','Mapa de intervención y auditoría de calidad.'],
          ['Alumbrado','Expansión de luminarias LED.','¿Mejoró percepción de seguridad y cobertura?','Inventario georreferenciado y fallas resueltas.'],
          ['Agua y comisarías','Obras y mantenimiento municipal.','¿Hay continuidad, presión y calidad?','Indicadores por sistema y coordinación metropolitana.'],
          ['Espacio público','Parques, limpieza y ordenamiento.','¿Se distribuyen con equidad territorial?','Cobertura por colonia y uso efectivo.'],
          ['Mujeres','Créditos, prevención y dispositivos de apoyo.','¿Llegan a quienes más los necesitan?','Beneficiarias, seguimiento y resultados.'],
          ['Finanzas','Calificación AAA y disciplina comunicada.','¿Se traduce en mejores servicios?','Costo unitario, avance físico y transparencia.']], [32*mm,44*mm,48*mm,46*mm]),
      P('Regla de comunicación','H3x'), P('Cada logro debe expresarse como solución ciudadana: problema inicial, acción, cobertura, resultado y siguiente meta. Evitar acumulaciones de cifras sin contexto.'),
      callout('La continuidad se vuelve creíble cuando la ciudadanía puede reconocer la mejora en su calle, parque, traslado o servicio; no sólo cuando la administración la anuncia.'), PageBreak()]

#10
S += [P('9. Agenda municipal y credibilidad temática','H2x'),
      P('Los foros metropolitanos de 2026 concentraron aportaciones en agua, movilidad y seguridad. Estas prioridades coinciden con los temas que más pueden alterar una elección municipal por su impacto cotidiano.'),
      table([
          ['Tema','Reto','Oferta creíble','Indicador 2027'],
          ['Agua','Fugas, presión, expansión urbana y comisarías.','Plan coordinado por zonas, mantenimiento y transparencia.','Continuidad, presión y fugas atendidas.'],
          ['Movilidad','Congestión, periferia, banquetas y seguridad vial.','Intersecciones críticas, movilidad barrial y coordinación.','Tiempo de traslado y siniestros.'],
          ['Calles y drenaje pluvial','Baches, lluvias y deterioro recurrente.','Mantenimiento preventivo y garantía de obra.','Reincidencia y días de respuesta.'],
          ['Seguridad','Percepción, prevención y videovigilancia.','Policía cercana, iluminación y coordinación estatal.','Incidencia y percepción por zona.'],
          ['Orden urbano','Crecimiento, permisos, vía pública y patrimonio.','Reglas claras, inspección imparcial y participación.','Trámites, cumplimiento y conflictos resueltos.'],
          ['Economía familiar','Ingreso, empleo, emprendimiento y cuidados.','Crédito, capacitación, simplificación y mercados.','Empleo formal y supervivencia de negocios.'],
          ['Medio ambiente','Calor, arbolado, residuos y expansión.','Sombra urbana, reciclaje y protección de suelo.','Cobertura arbórea y valorización de residuos.']], [31*mm,43*mm,58*mm,38*mm]),
      callout('Eje narrativo recomendado: “continuidad que corrige y llega parejo”. Reconoce lo pendiente, evita triunfalismo y convierte el segundo periodo en una etapa de consolidación medible.',TEAL), PageBreak()]

#11
S += [P('10. FODA y matriz de riesgos','H2x'),
      table([
          ['FORTALEZAS','OPORTUNIDADES'],
          ['• Victoria municipal reciente.<br/>• Aprobación mayoritaria publicada.<br/>• Incumbencia y visibilidad.<br/>• Estructura partidista y experiencia.<br/>• Capacidad de exhibir obra y servicios.','• Convertir gestión en mandato de continuidad.<br/>• Ampliar apoyo hacia jóvenes y periferias.<br/>• Liderar agenda metropolitana desde lo municipal.<br/>• Captar voto blando de MC y abstención.<br/>• Profesionalizar evidencia y respuesta ciudadana.'],
          ['DEBILIDADES','AMENAZAS'],
          ['• Desgaste inherente al gobierno.<br/>• Brechas territoriales de servicio.<br/>• Dependencia de coordinación estatal.<br/>• Sobreexposición de cifras oficiales.<br/>• Riesgo de confundir aprobación con voto.','• Morena con candidato competitivo y coalición unida.<br/>• Crisis de agua, lluvias, movilidad o seguridad.<br/>• Ruptura partidista o alianza incoherente.<br/>• Narrativa de desigualdad norte-sur.<br/>• Campaña negativa y controversias de integridad.']], [85*mm,85*mm], header=True),
      Spacer(1,6*mm), P('Matriz de riesgos prioritarios','H3x'),
      table([
          ['Riesgo','Prob.','Impacto','Señal temprana','Mitigación'],
          ['Deterioro de servicios','Media-alta','Alto','Suben reportes y desaprobación zonal.','SLA públicos, brigadas y tablero semanal.'],
          ['Rival único competitivo','Media','Alto','Morena reduce conflicto y crece en careo.','Contraste temprano por capacidad local.'],
          ['Crisis metropolitana','Media','Alto','Agua, movilidad o seguridad dominan conversación.','Protocolo conjunto y vocería basada en datos.'],
          ['Ruptura interna','Baja-media','Alto','Operadores se desmovilizan o migran.','Acuerdos verificables e inclusión territorial.'],
          ['Fatiga reputacional','Media','Medio-alto','Logros dejan de generar credibilidad.','Terceros validadores y rendición de cuentas.']], [35*mm,17*mm,19*mm,47*mm,52*mm]), PageBreak()]

#12
S += [P('11. Escenarios electorales 2027','H2x'),
      table([
          ['Escenario','Configuración','Evaluación','Condición decisiva'],
          ['A. Continuidad sólida','Patrón nominada; PAN cohesionado; alianza funcional; servicios mejoran.','Muy favorable','Aprobación se convierte en voto y margen ≥8 pp.'],
          ['B. Elección competitiva','Patrón nominada; rival de Morena conocido; gestión mixta.','Favorable / abierta','Territorio, movilización y contraste.'],
          ['C. Ventaja comprimida','Rival único; crisis de servicios; voto de cambio crece.','Riesgo alto','Corrección rápida y recuperación del sur/poniente.'],
          ['D. Fragmentación','PAN o aliados divididos; MC capta voto urbano.','Abierta','Unidad, voto útil y defensa de base.'],
          ['E. Choque externo','Evento de seguridad, agua o desastre domina agenda.','Incierta','Capacidad de respuesta y coordinación.']], [35*mm,58*mm,31*mm,46*mm]),
      P('Umbrales de decisión','H3x'),
      table([
          ['Indicador','Verde','Ámbar','Rojo'],
          ['Intención efectiva de voto','Ventaja ≥8 pp','Ventaja 4–7.9 pp','Ventaja <4 pp o desventaja'],
          ['Aprobación','≥60%','52–59%','<52%'],
          ['Servicios prioritarios','Mejora en 4 de 5','Estables / mixtos','Deterioro en 3 o más'],
          ['Unidad política','Acuerdo operativo','Negociación abierta','Ruptura / desmovilización'],
          ['Cobertura territorial','≥90% de zonas con responsable','75–89%','<75%']], [44*mm,42*mm,42*mm,42*mm]),
      callout('El objetivo no es adivinar el escenario, sino detectar temprano cuál está emergiendo y activar la respuesta predefinida.'), PageBreak()]

#13
S += [P('12. Ruta estratégica y tablero','H2x'),
      table([
          ['Fase','Objetivo','Producto verificable'],
          ['0–30 días','Homologar evidencia y línea base.','Encuesta municipal, auditoría de logros y mapa de riesgos.'],
          ['31–60 días','Cerrar brechas territoriales.','Planes por seis zonas, responsables y metas de servicio.'],
          ['61–120 días','Convertir gestión en narrativa de continuidad.','Portafolio de 20 resultados comprobables y agenda pendiente.'],
          ['Precampaña','Asegurar nominación, unidad y legalidad.','Acuerdo político, protocolo jurídico y defensa territorial.'],
          ['Campaña','Ganar contraste y movilización.','Mensaje único, microcampañas y tablero diario.']], [30*mm,58*mm,82*mm]),
      P('Tablero mínimo semanal','H3x'),
      table([
          ['Dimensión','Indicador','Frecuencia','Responsable'],
          ['Opinión','Aprobación, voto, careos y atributos.','Quincenal / mensual','Investigación'],
          ['Servicios','Reportes, solución, reincidencia y satisfacción.','Semanal','Gestión municipal'],
          ['Territorio','Contactos, cobertura, promotores y secciones.','Semanal','Operación territorial'],
          ['Digital','Conversación, sentimiento, desinformación y respuesta.','Diaria','Comunicación'],
          ['Político','Unidad, alianzas, actores y conflictos.','Semanal','Coordinación política'],
          ['Legal','Actos, propaganda, recursos y fiscalización.','Permanente','Jurídico-electoral']], [32*mm,69*mm,31*mm,38*mm]),
      P('Decisiones inmediatas','H3x')] + bullets([
          'Levantar una encuesta propia con muestra suficiente para seis zonas operativas.',
          'Construir expediente público de 20 resultados con trazabilidad y evidencia territorial.',
          'Definir cinco compromisos de segundo periodo con metas, costo y calendario.',
          'Instalar sala de respuesta para agua, movilidad, baches, alumbrado y seguridad.',
          'Abrir diálogo programático con aliados antes de negociar posiciones.'
      ]) + [PageBreak()]

#14
S += [P('13. Control de consistencia y fuentes públicas','H2x'),
      P('El dictamen distingue hechos, mediciones y supuestos. Los siguientes puntos deben actualizarse conforme avance el proceso.'),
      table([
          ['Tema','Hallazgo robusto','Dato variable','Criterio'],
          ['Cargo','Presidenta municipal 2024–2027.','Ninguno relevante.','Hecho oficial.'],
          ['Resultado 2024','258,489 vs 205,395 votos.','Alianzas de 2027.','Base electoral, no pronóstico.'],
          ['Reelección','Permitida en 2027; prohibición federal aplica desde 2030.','Lineamientos y plazos.','Validación jurídica continua.'],
          ['Aprobación','Mayoría favorable en tres mediciones.','59.4%–64.5%.','No promediar ni equiparar con voto.'],
          ['Agenda','Agua, movilidad, seguridad y servicios.','Prioridad por zona.','Medición territorial propia.'],
          ['Competencia','Morena es la principal fuerza rival.','Candidato y coalición.','Escenarios abiertos.']], [35*mm,57*mm,38*mm,40*mm]),
      P('Referencias públicas principales','H3x')] + bullets([
          'IEPAC Yucatán: acta de cómputo municipal de Mérida, elección 2024.',
          'Constitución Política del Estado de Yucatán, texto vigente consultado en septiembre de 2026.',
          'Diario Oficial de la Federación, decreto de no reelección publicado el 1 de abril de 2025 y sus transitorios.',
          'INEGI, Panorama sociodemográfico de Yucatán, Censo de Población y Vivienda 2020.',
          'Ayuntamiento de Mérida: Plan Municipal de Desarrollo 2024–2027, informes de gobierno y comunicados de resultados.',
          'Gobierno de Yucatán: foros y prioridades del Plan Bienestar Metropolitano 2026.',
          'LaEncuesta.mx, MetaMetrics y Demoscopia Digital: mediciones de aprobación publicadas en 2026.'
      ]) + [P('Advertencia metodológica','H3x'), P('Las fuentes institucionales documentan actos y cifras oficiales, pero también reflejan la comunicación de las entidades que las emiten. Las encuestas dependen de diseño, levantamiento y patrocinio. El dictamen utiliza estas piezas para orientar decisiones y recomienda verificación independiente.'),
      callout('Actualización obligatoria: al definirse candidaturas y alianzas, y después de contar con una encuesta propia homogénea.',GOLD), PageBreak()]

#15
S += [P('14. Dictamen final','H2x'), Spacer(1,3*mm),
      score_cards([
          ('Nominación','8.8/10','Favorable',TEAL),
          ('Elección general','8.0/10','Competitiva favorable',TEAL),
          ('Viabilidad global','8.4/10','Alta, condicionada',TEAL)]),
      Spacer(1,10*mm), P('Conclusión','H3x'),
      P('Cecilia Patrón Laviada reúne condiciones objetivas para competir por la Presidencia Municipal de Mérida en 2027 y comenzar el proceso como <b>favorita inicial</b>. Su triunfo de 2024, posición institucional, reconocimiento y aprobación constituyen una plataforma superior a la de una candidatura abierta.'),
      P('La ventaja no debe interpretarse como inercia suficiente. Una elección consecutiva será un referéndum sobre la experiencia cotidiana de gobierno. <b>Rommel Pacheco es el rival individual de referencia</b>; Jessica Saidén, Verónica Camino y Óscar Brito conforman la segunda línea de alternativas de Morena, mientras Javier Osante puede modificar el margen desde Movimiento Ciudadano. El principal riesgo es la convergencia entre desgaste de servicios, una candidatura opositora competitiva y una narrativa de desigualdad territorial.'),
      callout('<b>RESOLUCIÓN: VIABLE.</b> Se recomienda avanzar en la preparación política, territorial, jurídica y programática de la posible candidatura, condicionada a mantener aprobación mayoritaria, cerrar brechas de servicios, asegurar unidad y sostener una ventaja mínima de ocho puntos en medición homogénea.',TEAL),
      Spacer(1,8*mm), P('Condiciones de éxito','H3x')] + bullets([
          'Resultados verificables y cercanos en los cinco servicios prioritarios.',
          'Estrategia diferenciada para sur, poniente, oriente y comisarías.',
          'Coalición coherente, estructura unificada y defensa completa de casillas.',
          'Contraste municipal: capacidad, experiencia, cercanía y metas de continuidad.',
          'Integridad, legalidad y respuesta rápida ante controversias.'
      ]) + [Spacer(1,10*mm), P('Vigencia del dictamen','H3x'), P('Válido como evaluación estratégica al 25 de septiembre de 2026. Debe revisarse ante cambios relevantes de candidatura, coalición, aprobación, servicios o marco jurídico.'),
      Spacer(1,18*mm), P('Documento ejecutivo para presentación a la posible candidata.','Smallx')]

doc.build(S)
print(OUT)
