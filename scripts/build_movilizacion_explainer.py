"""Video narrado del HTML: gráficos originales, audio Windows y exportación H.264."""
from pathlib import Path
import json
import subprocess
import wave
import sys
from PIL import Image, ImageDraw, ImageFont, ImageOps
import imageio_ffmpeg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.storage import files_root

ROOT = files_root()
OUT = ROOT / 'output/videos/movilizacion_html'
SCENES = [
('DEL ANÁLISIS A LA EJECUCIÓN', 'Sistema de\nmovilización electoral', ['Evidencia', 'Territorio', 'Seguimiento'], 'Go to win presenta un sistema de inteligencia, movilización y control territorial. Su propuesta conecta evidencia, territorio, objetivos y seguimiento. Este recorrido explica el contenido del diagrama: ocho etapas relacionadas, desde el expediente de candidatura hasta el tablero de control.'),
('UN CICLO CONECTADO', 'Ocho etapas.\nUn mismo proceso.', ['Configurar · Explorar · Entender · Proyectar', 'Enfocar · Decidir · Ejecutar · Aprender'], 'El sistema se organiza como un ciclo. El expediente y los visores alimentan el análisis. Los escenarios se convierten en metas, prioridades y planes. La operación devuelve evidencia al tablero, para revisar decisiones y ajustar el trabajo. Las etapas se conectan entre sí.'),
('ETAPA 01 · CONFIGURAR', 'Expediente de\ncandidatura', ['Perfil y elección', 'Dictamen de viabilidad', 'Fuentes y territorios'], 'La primera etapa reúne el perfil, la elección, el dictamen de viabilidad, las variables y las fuentes documentales. Su propósito es establecer con qué información validada inicia el equipo y qué vacíos debe completar. El resultado es un expediente ordenado y auditable.'),
('ETAPA 02 · EXPLORAR', 'Visores\ngeográficos', ['Municipio', 'Distrito', 'Sección'], 'Los visores geográficos presentan la cartografía y los resultados electorales junto con indicadores territoriales. Permiten explorar municipios, distritos y secciones, y localizar diferencias relevantes. Así, los datos adquieren una ubicación y un contexto para su consulta.'),
('ETAPA 03 · ENTENDER', 'Análisis\nterritorial', ['Mercado electoral', 'Participación y competencia', 'Contexto INEGI + INE'], 'El análisis territorial relaciona el mercado electoral, la participación, la competencia y el contexto social. Integra el diagnóstico, los mapas de oportunidad y el cruce de información del INEGI y del INE. Estas comparaciones ayudan a formular hipótesis, sin confundir contexto con causalidad.'),
('ETAPA 04 · PROYECTAR', 'Escenarios\ny metas', ['Resultados históricos', 'Supuestos explícitos', 'Metas por territorio'], 'Los escenarios expresan una hipótesis electoral mediante supuestos visibles y revisables. Los resultados históricos, la lista nominal y la participación esperada sirven de insumo para construir metas. La meta general se distribuye por territorio y conserva la trazabilidad de sus supuestos.'),
('ETAPA 05 · ENFOCAR', 'Priorización\nterritorial', ['Peso electoral', 'Brecha de participación', 'Competitividad y contexto'], 'La priorización ordena los territorios según los criterios que el equipo decide aplicar. Considera el peso electoral, la brecha de participación, la competitividad, la fuerza histórica y el contexto. Su salida es una cartera de prioridades que alimenta el plan de acción.'),
('ETAPA 06 · DECIDIR', 'Estrategia\ny plan de acción', ['Objetivos y actividades', 'Responsables', 'Fechas y seguimiento'], 'La estrategia convierte las prioridades y las metas en objetivos, líneas de trabajo y actividades. Cada acción debe relacionarse con un territorio, un responsable y un periodo. El plan documenta qué se hará y cómo se dará seguimiento a su contribución a la meta.'),
('ETAPA 07 · EJECUTAR', 'Operación\nterritorial', ['Actividades programadas', 'Cobertura y avances', 'Hallazgos y evidencia'], 'La operación territorial lleva el plan al trabajo cotidiano. Registra las actividades realizadas, la cobertura alcanzada y los hallazgos de campo. Las evidencias y la retroalimentación permiten identificar pendientes y mantener la ejecución vinculada con la estrategia.'),
('ETAPA 08 · APRENDER', 'Tablero de evidencia\ny control', ['Avances', 'Alertas', 'Correcciones'], 'El tablero reúne avances, alertas y evidencia para revisar el plan. Permite observar qué cambió, qué riesgo surgió y qué acción necesita corregirse. Cuando corresponde, incorpora el seguimiento de los planes de desarrollo. El aprendizaje devuelve información al inicio del ciclo.'),
('INFORMACIÓN TRANSVERSAL', 'La evidencia alimenta\ntodo el ciclo', ['INE e institutos locales · INEGI', 'Medios y digital · Cartografía', 'Campo y encuestas · Planeación y PMD'], 'Todo el ciclo se alimenta de información electoral, indicadores del INEGI, medios, conversación pública, cartografía, encuestas y trabajo de campo. También incorpora planeación, metas y evidencia de gestión. El enfoque utiliza datos agregados y verificables; no sustituye el criterio político ni infiere preferencias individuales.'),
('DEL TERRITORIO A LA DECISIÓN', 'Una estrategia documentada.\nUn plan con seguimiento.', ['Defender · Recuperar · Competir · Corregir', 'Municipio → distrito → sección → localidad'], 'La propuesta de Go2Win conecta la lectura territorial con decisiones operativas: defender, recuperar, competir y corregir. El resultado buscado es una estrategia documentada, una meta medible y un plan con seguimiento. Los mapas y porcentajes del documento son ilustrativos. Go to win: inteligencia electoral y territorial.'),
]
SCENES[0] = ('DEL ANÁLISIS A LA EJECUCIÓN', 'Sistema de\nmovilización electoral', ['Información integrada', 'Operación territorial', 'Control con evidencia'], 'Go to win conecta información, análisis, decisión, operación y seguimiento. En esta presentación recorreremos su oferta de valor, el esquema conceptual, la integración con Telegram y las ocho etapas del ciclo. También veremos los entregables que la inteligencia artificial prepara para revisión del equipo.')
SCENES[1:1] = [
('OFERTA DE VALOR', 'Oferta de valor estratégica', [], 'La oferta de valor reúne seis elementos: viabilidad electoral, integración de información, visibilidad de la campaña, eficiencia, precisión territorial y optimización del presupuesto. La propuesta busca que el equipo trabaje con una visión común de la evidencia, los recursos y las decisiones. Esta imagen resume ese valor estratégico.'),
('ESQUEMA CONCEPTUAL', 'Ciclo de gestión electoral', [], 'El esquema conceptual inicia con el dictamen de viabilidad y la configuración electoral. Conecta el motor de inteligencia y análisis con la captura territorial, la planeación y la comunicación. Es una visión del modelo de trabajo: la información alimenta decisiones, la operación produce evidencia y el seguimiento permite ajustar el ciclo.'),
('COMUNICACIÓN CON CAMPO', 'Integración\ncon Telegram', ['Actividades y evidencia', 'Encuestas y territorio', 'Simpatizantes y consentimiento'], 'Go2Win presenta a Telegram como canal de campo para tres flujos: actividades territoriales, levantamiento de encuestas y registro de simpatizantes con consentimiento. La arquitectura contempla responsables, cuestionarios, respuestas y evidencias. Go to win concentra el seguimiento para el equipo autorizado, con identidad, roles, controles y auditoría.'),
]
SCENES[-1:-1] = [
('INTELIGENCIA ARTIFICIAL ASISTIDA', 'La IA prepara.\nEl equipo autoriza.', ['Organiza, resume y clasifica', 'Prepara propuestas explicadas', 'Validación y autorización humana'], 'La inteligencia artificial funciona como una capa de análisis asistido. Open AI organiza documentos, resume evidencia y clasifica sentimiento, temas y urgencia en contenido público. Prepara propuestas para revisión. No sustituye las fuentes, no infiere preferencias individuales y no activa decisiones ni trabajo de campo sin autorización humana.'),
('ENTREGABLES DE IA · 01', 'Diagnostica\ny contextualiza', ['Dictamen y fichas municipales', 'Síntesis de medios y conversación', 'Borradores de cuestionarios'], 'El primer grupo de entregables organiza el punto de partida. Incluye borradores de dictámenes de viabilidad, fichas municipales, síntesis de medios y conversación, y cuestionarios. Reúne fortalezas, riesgos, evidencia y faltantes, para que el equipo complete la información y valide las fuentes antes de utilizarla.'),
('ENTREGABLES DE IA · 02', 'Proyecta\ny prioriza', ['Escenarios electorales', 'Prioridades territoriales', 'Borradores de estrategia'], 'El segundo grupo prepara alternativas para decidir. Incluye escenarios con participación prevista, metas de votos, brechas y supuestos; propuestas de priorización territorial; y borradores de estrategia con objetivos y criterios de éxito. El equipo revisa estas propuestas y autoriza la ruta de trabajo.'),
('ENTREGABLES DE IA · 03', 'Organiza\ny activa', ['Planes de acción', 'Propuestas de actividades', 'Tablero de mando'], 'El tercer grupo traduce la estrategia autorizada en trabajo verificable. La inteligencia artificial estructura planes, propone actividades y consolida información para el tablero de mando. Cada propuesta identifica territorio, objetivo, responsable, calendario y evidencia esperada. La activación de las actividades corresponde a las personas autorizadas.'),
('ENTREGABLES DE IA · 04', 'Monitorea\ny aprende', ['Reportes semanales', 'Minutas, alertas y resúmenes', 'Cierre y aprendizaje'], 'El cuarto grupo prepara reportes semanales, minutas, alertas, resúmenes ejecutivos y reportes de cierre. Contrasta metas, cobertura e incidencias, señala pendientes y documenta el aprendizaje. La regla es clara: la inteligencia artificial puede detectar, investigar, calcular y preparar; el equipo valida, aprueba y decide los ajustes.'),
]
SCENES.insert(2, ('OFERTA DE VALOR · APORTE DE LA IA', 'La IA investiga,\nanaliza y propone', ['Investiga fuentes y reúne evidencia', 'Analiza contexto, riesgos y oportunidades', 'Propone escenarios, planes y acciones'], 'La inteligencia artificial amplía la oferta de valor de Go to win: investiga, analiza y propone. Investiga fuentes y reúne evidencia para completar la información. Analiza el contexto, los resultados, los riesgos y las oportunidades. Propone escenarios, prioridades, planes y acciones con sustento en esa evidencia. Su aporte es conectar la investigación con el análisis y las propuestas para decidir. El equipo valida las fuentes, revisa las propuestas, autoriza su ejecución y conserva la decisión final.'))
SCENES[0:0] = [
('TABLERO DE MANDO', 'Visualiza. Coordina.\nDa seguimiento.', [], 'Go to win: tablero de mando electoral. Visualiza la brecha, coordina al equipo y da seguimiento. Una visión compartida del territorio, las metas y la evidencia permite entender dónde estamos y qué decisiones requieren atención. Todo comienza con un reto: reunir la información para trabajar con claridad.'),
('EL RETO DE LA CAMPAÑA', 'Información dispersa.\nDecisiones pendientes.', [], 'En una campaña, la información suele estar dispersa: archivos de Excel, documentos, encuestas y mensajes en distintos celulares. ¿Cuál es la versión más reciente? ¿Dónde está la información oficial? ¿Quién está revisando los datos? Integrar secciones, casillas, resultados y reportes consume tiempo, mientras la operación continúa. Go to win propone conectar esa información en un mismo ciclo de análisis, decisión y seguimiento.'),
]
IMAGE_SCENES = {0: 'intro_tablero.jpg', 1: 'intro_problematica.png', 3: 'Oferta de Valor Estratégica.jpg', 5: 'Go2Win EsquemaConceptual.jpg'}
TELEGRAM_NARRATION = [
    ('Arquitectura de integración con Telegram', 'Veamos ahora la arquitectura de integración con Telegram. La presentación conecta actividades de campo, encuestas y registro de simpatizantes dentro de un mismo ciclo operativo. El principio es claro: Telegram conecta al equipo con campo; Go to win valida, conserva el historial y concentra la decisión.'),
    ('Comunicación con campo', 'La arquitectura reúne tres flujos. En actividades de campo, el personal consulta tareas, confirma recepción y reporta avances. En encuestas, el canal guía cuestionarios y vincula las respuestas con territorio, fecha y responsable. El registro de simpatizantes incorpora consentimiento, datos autorizados y seguimiento. La presentación describe además evidencia multimedia, notificaciones, alertas y una arquitectura escalable con recepción de eventos y cola de mensajería.'),
    ('Identidad, roles y alcance territorial', 'Cada acción se valida con la identidad del usuario y el contexto de la tarea. El administrador registra a la persona, su rol, equipo y alcances. Un código único vincula su cuenta con un chat privado de Telegram. Antes de responder o guardar, Go to win comprueba que el usuario esté activo y autorizado para ese territorio. La auditoría conserva vínculos, cambios de acceso, asignaciones y revisiones. Un nombre o un equipo, por sí solos, no conceden acceso.'),
    ('Ciclo de una tarea territorial', 'El ciclo inicia cuando la coordinación crea una actividad en el plan de acción y la asigna a un trabajador elegible. La persona consulta sus tareas en Telegram y confirma la recepción. Go to win registra la fecha y conserva el evento. Confirmar que recibió una tarea no equivale a concluirla. Si cambia el responsable, se invalidan los botones anteriores y la recepción previa. Las tareas concluidas o canceladas no se pueden confirmar.'),
    ('Ciclo de un reporte de campo', 'Para reportar, el trabajador selecciona una tarea asignada, recibida y vigente. Envía el avance y Go to win lo guarda con un folio y estado por validar. La presentación establece textos de hasta cuatro mil caracteres y una captura con vigencia de treinta minutos. Una persona autorizada acepta el reporte o solicita una corrección. Después de aceptarlo, el responsable puede mantener abierta la tarea o concluirla. El folio identifica al reporte, no a la tarea.'),
    ('Controles que protegen la operación', 'La integración contempla controles de privacidad, autorización y consistencia. El bot opera en chat privado y verifica rol, territorio, asignación y estado. Los mensajes repetidos no deben crear reportes duplicados. Nadie revisa su propio reporte. El sistema guarda antes de responder, conserva las capturas pendientes durante su vigencia y deja registro de cambios de acceso, vínculos, asignaciones, recepciones y revisiones.'),
    ('Operación diaria y responsabilidades', 'Las responsabilidades se distribuyen por rol. El administrador configura personas, equipos y alcances. El coordinador asigna tareas y revisa reportes dentro de su ámbito. El personal de campo consulta, confirma y reporta por Telegram. El director consulta resultados y define prioridades en su ámbito autorizado. Go to win prepara y asigna; Telegram facilita el trabajo de campo; y Go to win conserva la evidencia y muestra el avance. Esta integración se enlaza con las ocho etapas que veremos a continuación.'),
]
TELEGRAM_NARRATION[-1] = (TELEGRAM_NARRATION[-1][0], TELEGRAM_NARRATION[-1][1].replace(
    'Esta integración se enlaza con las ocho etapas que veremos a continuación.',
    'Así, Telegram acompaña la ejecución de las ocho etapas. A continuación veremos cómo la inteligencia artificial investiga, analiza y propone, y qué entregables prepara para el equipo.'))
SCENES.pop(next(i for i, s in enumerate(SCENES) if s[0] == 'COMUNICACIÓN CON CAMPO'))
telegram_index = next(i for i, s in enumerate(SCENES) if s[0] == 'INTELIGENCIA ARTIFICIAL ASISTIDA')
SCENES[telegram_index:telegram_index] = [('TELEGRAM', title, [], voice) for title, voice in TELEGRAM_NARRATION]
PPT_SCENES = {telegram_index+i: ROOT/'output/videos/telegram_slides'/f'telegram-{i+1:02d}.png' for i in range(len(TELEGRAM_NARRATION))}
SOURCE_HTML = 'output/html/Sistema_Movilizacion_Electoral_Go2Win_version_recuperada.html'
NAVY='#0a2947'; TEAL='#14b8a6'; WHITE='#f5f9fb'
def font(size,bold=False):return ImageFont.truetype('C:/Windows/Fonts/'+('arialbd.ttf' if bold else 'arial.ttf'),size)

def slide(index,scene):
    tag,title,items,_=scene
    if index in PPT_SCENES:
        Image.open(PPT_SCENES[index]).convert('RGB').resize((1280,720),Image.Resampling.LANCZOS).save(OUT/f'scene-{index:02d}.png')
        return
    im=Image.new('RGB',(1280,720),NAVY);d=ImageDraw.Draw(im)
    if index in IMAGE_SCENES:
        source=Image.open(ROOT/'output/html/recuperada_assets'/IMAGE_SCENES[index]).convert('RGB')
        fitted=ImageOps.contain(source,(1280,646),Image.Resampling.LANCZOS)
        im.paste(fitted,((1280-fitted.width)//2,38+(646-fitted.height)//2))
        d.text((24,10),tag,font=font(18,True),fill=TEAL)
        d.text((24,690),'Go2Win · Esquema de la propuesta',font=font(16),fill=WHITE)
        im.save(OUT/f'scene-{index:02d}.png')
        return
    d.ellipse((780,-320,1510,410),fill='#103b58')
    d.rectangle((0,0,1280,9),fill=TEAL)
    d.text((64,43),'go2win',font=font(32,True),fill=WHITE)
    d.text((1070,53),'go2win.mx',font=font(19),fill='#9bb6ca')
    d.text((64,120),tag,font=font(21,True),fill=TEAL)
    d.multiline_text((60,175),title,font=font(53,True),fill=WHITE,spacing=10)
    top=365
    for j,item in enumerate(items):
        y=top+j*73
        d.rounded_rectangle((64,y,1216,y+59),radius=12,fill='#153e59')
        d.ellipse((84,y+24,96,y+36),fill=TEAL)
        d.text((114,y+14),item,font=font(25),fill=WHITE)
    d.text((64,638),'SISTEMA DE MOVILIZACIÓN ELECTORAL',font=font(16,True),fill='#9bb6ca')
    d.text((1120,636),f'{index+1:02d} / {len(SCENES)}',font=font(19),fill='#9bb6ca')
    for j in range(len(SCENES)):
        x=64+j*(1152/len(SCENES))
        d.rounded_rectangle((x,681,x+1152/len(SCENES)-8,686),radius=2,fill=TEAL if j<=index else '#24485e')
    im.save(OUT/f'scene-{index:02d}.png')

def prepare():
    OUT.mkdir(parents=True,exist_ok=True)
    for i,s in enumerate(SCENES):slide(i,s)
    (OUT/'narracion.json').write_text(json.dumps([s[3] for s in SCENES],ensure_ascii=False),encoding='utf-8')
    (OUT/'guion.txt').write_text('\n\n'.join(s[0]+'\n'+s[3] for s in SCENES),encoding='utf-8')

def stamp(seconds):
    ms=round(seconds*1000);h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);s,ms=divmod(ms,1000)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'

def render():
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe();total=0;subtitles=[];number=0
    for i,scene in enumerate(SCENES):
        wav=OUT/f'voice-{i:02d}.wav'
        with wave.open(str(wav)) as w:duration=w.getnframes()/w.getframerate()
        length=duration+0.9
        sentences=[s.strip()+'.' for s in scene[3].split('.') if s.strip()]
        words=sum(len(s.split()) for s in sentences);position=total
        for sentence in sentences:
            end=position+duration*len(sentence.split())/words;number+=1
            subtitles.append(f'{number}\n{stamp(position)} --> {stamp(end)}\n{sentence}\n');position=end
        cmd=[ffmpeg,'-y','-loglevel','error','-loop','1','-i',str(OUT/f'scene-{i:02d}.png'),'-i',str(wav),'-vf',f'fade=t=in:st=0:d=0.3,fade=t=out:st={length-0.3}:d=0.3','-af','apad=pad_dur=0.9','-t',str(length),'-r','24','-c:v','libx264','-preset','ultrafast','-crf','22','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k',str(OUT/f'clip-{i:02d}.mp4')]
        subprocess.run(cmd,check=True);total+=length
        print(f'Escena {i+1}/{len(SCENES)} lista',flush=True)
    (OUT/'subtitulos.srt').write_text('\n'.join(subtitles),encoding='utf-8')
    (OUT/'concat.txt').write_text('\n'.join(f"file 'clip-{i:02d}.mp4'" for i in range(len(SCENES))),encoding='utf-8')
    output=OUT/'Go2Win_movilizacion_electoral_actualizado_temporal.mp4'
    subprocess.run([ffmpeg,'-y','-loglevel','error','-f','concat','-safe','0','-i',str(OUT/'concat.txt'),'-i',str(OUT/'subtitulos.srt'),'-map','0:v','-map','0:a','-map','1:0','-c:v','copy','-c:a','copy','-c:s','mov_text','-metadata:s:s:0','language=spa','-metadata:s:a:0','language=spa','-movflags','+faststart',str(output)],check=True)
    (OUT/'verificacion.json').write_text(json.dumps({'duration_seconds':total,'scenes':len(SCENES),'resolution':'1280x720','voice':'Microsoft Sabina Desktop es-MX','source':SOURCE_HTML},indent=2),encoding='utf-8')
    print(output,flush=True)

if __name__=='__main__':
    prepare() if '--prepare' in sys.argv else render()
