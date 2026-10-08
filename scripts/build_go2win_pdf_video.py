"""Commercial overview grounded in the supplied PDF, with recorded product UI."""
from pathlib import Path
import json, subprocess, wave, sys
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/videos/tablero_pdf'
SOURCE_PDF=Path('C:/Users/jorge/Downloads/01_Proyectos/Electoral_2027/Go2Win/Tablero de Mnado Go2Win.pdf')
VIDEOS={
 'recorrido':Path('C:/Users/jorge/OneDrive/Documentos/Presentaciones/Go2Win_Recorrido_Con_Introduccion_y_Voz_Corregido.mp4'),
 'integral':Path('C:/Users/jorge/OneDrive/Documentos/ChatGPT/New project/output/video/Go2Win_Recorrido_Integral_Con_Tablero_de_Mando_con_Voz.mp4'),
 'dictamen':Path('C:/Users/jorge/OneDrive/Documentos/ChatGPT/New project/output/video/Go2Win_Recorrido_Dictamen_de_Viabilidad_con_Voz.mp4'),
}
# Each source interval was visually reviewed; the source soundtrack is omitted.
SCENES=[
 ('Go2Win', 'Tablero de Mando Electoral', 'Información • Decisión • Seguimiento',
  'Dirigir una campaña exige entender qué ocurre, qué importa y quién debe actuar. Go to win, Tablero de Mando Electoral, propone una visión compartida de la candidatura: conecta viabilidad, territorio, comunicación y operación para convertir información en decisiones y seguimiento.', [('recorrido',48),('recorrido',145)], [1]),
 ('EL RETO', 'Conectar la información dispersa', 'Una visión común para el equipo',
  'Los reportes aislados, los archivos dispersos y las actividades sin seguimiento dificultan la dirección de una campaña. La propuesta de Go to win es reunir los elementos críticos en un mismo tablero. Así, la jefatura puede identificar qué está pasando, qué requiere atención y quién es responsable de responder.', [('integral',27),('integral',40)], [3]),
 ('VIABILIDAD', 'Entender el punto de partida', 'Perfil • Competencia • Escenarios • Riesgos',
  'El punto de partida es el dictamen de viabilidad. El modelo integra perfil, elegibilidad, encuestas, competencia, alianzas, fortalezas y riesgos. Su propósito es identificar condiciones de competitividad, vacíos de información y decisiones pendientes. El análisis ayuda a ordenar la evidencia antes de definir la ruta de trabajo.', [('dictamen',27),('recorrido',69)], [3,4]),
 ('TERRITORIO', 'Ubicar los datos y las prioridades', 'Municipios • Distritos • Secciones',
  'El territorio da contexto a los datos. Resultados electorales, cartografía e indicadores permiten consultar municipios, distritos y secciones. Las pantallas muestran cómo relacionar resultados, participación y características del territorio. Esta lectura sirve de base para revisar prioridades y decidir dónde concentrar recursos.', [('recorrido',50),('recorrido',228)], [3,4]),
 ('ESCUCHA CIUDADANA', 'Organizar necesidades y hallazgos', 'Encuestas • Solicitudes • Reportes de campo',
  'La escucha ciudadana incorpora necesidades, solicitudes, encuestas, temas recurrentes y reportes de campo. Organizar estos hallazgos permite revisar la agenda y dar seguimiento a la atención territorial. Cada registro debe conservar su contexto y su evidencia para que el equipo pueda interpretarlo y verificarlo.', [('recorrido',105),('integral',193)], [3,4]),
 ('MEDIOS Y DIGITAL', 'Llevar la conversación al análisis', 'Cobertura • Temas • Tono • Alertas',
  'La definición del proyecto incluye medios y conversación digital dentro de la mesa de decisión. Propone integrar cobertura, fuentes, temas, tono y alertas para entender el contexto comunicacional. El objetivo es conectar lo que ocurre en medios y redes con una revisión informada y una comunicación responsable.', [('integral',28),('recorrido',113)], [3,4,5]),
 ('OPERACIÓN', 'Pasar de la estrategia al seguimiento', 'Responsables • Actividades • Fechas • Evidencias',
  'La estrategia necesita responsables, actividades, fechas y evidencia de avance. Go to win plantea conectar estos elementos para dar seguimiento a la ejecución. Las vistas de estrategia, planes y reportes permiten recorrer esa cadena: qué se decidió, qué se programó y qué información regresa del trabajo de campo.', [('recorrido',316),('integral',179),('integral',191)], [3,4]),
 ('VALOR DIFERENCIAL', 'Dar seguimiento a cada hallazgo', 'Hallazgo → Decisión → Acción → Evidencia',
  'El valor diferencial está en la conexión. Un hallazgo electoral, territorial, ciudadano o comunicacional debe relacionarse con una decisión, una actividad, un responsable y un indicador de avance. El tablero ofrece una lógica común para que las distintas áreas revisen prioridades y documenten los ajustes.', [('recorrido',145),('recorrido',167)], [3,5]),
 ('VISIÓN DE CAMPAÑA', 'Acompañar el ciclo completo', 'Viabilidad • Estrategia • Operación • Evaluación',
  'La visión del proyecto es acompañar el ciclo completo: desde el dictamen y el diagnóstico hasta la operación, la preparación de la jornada electoral y la evaluación de resultados. La propuesta contempla apoyar la coordinación de movilización y defensa del voto dentro de la ley, con responsabilidades y seguimiento verificable.', [('recorrido',233),('integral',180)], [2,4,5]),
 ('DESARROLLO Y RESPONSABILIDAD', 'Una propuesta en evolución', 'Veracidad • Privacidad • Seguridad • Mejora continua',
  'Go to win se encuentra en desarrollo y validación durante dos mil veintiséis. Su evolución contempla capacidades multiestado y multiperfil, integración de fuentes y seguimiento de resultados. La propuesta se guía por veracidad, privacidad, seguridad de datos y cumplimiento electoral. Go to win no garantiza resultados electorales: busca aportar evidencia, organización y seguimiento.', [('recorrido',271),('recorrido',92)], [2,4,5]),
 ('Go2Win', 'Información para dirigir. Evidencia para ajustar.', 'Tablero de Mando Electoral',
  'Una campaña necesita prioridades claras, responsables definidos y evidencia de avance. Go to win, Tablero de Mando Electoral: una propuesta para conectar información territorial, electoral y comunicacional con estrategia, operación y seguimiento. Conoce el recorrido y la visión de la plataforma.', [('recorrido',52),('recorrido',147)], [1,5]),
]

def font(n,bold=False):
 return ImageFont.truetype('C:/Windows/Fonts/'+('arialbd.ttf' if bold else 'arial.ttf'),n)

def run(args):
 subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-loglevel','error',*args],check=True)

def prepare():
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/'narracion.json').write_text(json.dumps([s[3] for s in SCENES],ensure_ascii=False),encoding='utf-8')
 (OUT/'guion.txt').write_text('\n\n'.join(s[0]+'\n'+s[1]+'\n'+s[3] for s in SCENES),encoding='utf-8')
 for i,(tag,title,caption,*_) in enumerate(SCENES):
  im=Image.new('RGBA',(1280,720),(0,0,0,0));d=ImageDraw.Draw(im)
  d.rectangle((0,0,1280,105),fill='#082336');d.rectangle((0,659,1280,720),fill='#082336')
  d.rectangle((0,0,1280,5),fill='#23c6b6')
  d.text((30,16),tag.upper(),font=font(18,True),fill='#55ddcc')
  size=34
  while d.textbbox((0,0),title,font=font(size,True))[2]>1200:size-=1
  d.text((28,45),title,font=font(size,True),fill='white')
  d.text((30,668),caption,font=font(19,True),fill='white')
  d.text((30,698),'Pantallas de recorridos grabados · Proyecto en desarrollo y validación, 2026',font=font(13),fill='#abc5d7')
  d.text((1180,685),f'{i+1:02}/{len(SCENES):02}',font=font(19,True),fill='#55ddcc')
  im.save(OUT/f'overlay-{i:02}.png')
 (OUT/'fuentes.json').write_text(json.dumps({'pdf':str(SOURCE_PDF),'videos':{k:str(v) for k,v in VIDEOS.items()},'scenes':[{'title':s[1],'pdf_pages':s[5],'clips':s[4]} for s in SCENES]},ensure_ascii=False,indent=2),encoding='utf-8')

def stamp(sec):
 ms=round(sec*1000);h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);s,ms=divmod(ms,1000)
 return f'{h:02}:{m:02}:{s:02},{ms:03}'

def render():
 total=0;subtitles=[];n=0
 for i,s in enumerate(SCENES):
  with wave.open(str(OUT/f'voice-{i:02}.wav')) as w:voice=w.getnframes()/w.getframerate()
  duration=round((voice+.8)*24)/24
  shots=s[4];each=round(duration/len(shots)*24)/24;parts=[]
  for j,(key,start) in enumerate(shots):
   length=each if j<len(shots)-1 else duration-each*(len(shots)-1)
   part=OUT/f'shot-{i:02}-{j}.mp4';parts.append(part)
   filters=f'[0:v]scale=1280:554:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:105+(554-ih)/2:color=0x082336,setsar=1,fps=24[v];[v][1:v]overlay=0:0,fade=t=in:st=0:d=0.2,fade=t=out:st={length-.2}:d=0.2[out]'
   run(['-ss',str(start),'-i',str(VIDEOS[key]),'-i',str(OUT/f'overlay-{i:02}.png'),'-filter_complex',filters,'-map','[out]','-an','-t',str(length),'-c:v','libx264','-preset','ultrafast','-crf','20','-pix_fmt','yuv420p',str(part)])
  listing=OUT/f'parts-{i:02}.txt';listing.write_text('\n'.join(f"file '{p.name}'" for p in parts),encoding='utf-8')
  run(['-f','concat','-safe','0','-i',str(listing),'-i',str(OUT/f'voice-{i:02}.wav'),'-map','0:v','-map','1:a','-c:v','copy','-af','apad=pad_dur=1','-c:a','aac','-b:a','160k','-t',str(duration),str(OUT/f'clip-{i:02}.mp4')])
  sentences=[x.strip()+'.' for x in s[3].split('.') if x.strip()];words=sum(len(x.split()) for x in sentences);pos=total
  for sentence in sentences:
   end=pos+voice*len(sentence.split())/words;n+=1;subtitles.append(f'{n}\n{stamp(pos)} --> {stamp(end)}\n{sentence}\n');pos=end
  total+=duration;print(f'Escena {i+1}/{len(SCENES)} lista',flush=True)
 (OUT/'subtitulos.srt').write_text('\n'.join(subtitles),encoding='utf-8')
 (OUT/'concat.txt').write_text('\n'.join(f"file 'clip-{i:02}.mp4'" for i in range(len(SCENES))),encoding='utf-8')
 final=OUT/'Go2Win_Tablero_de_Mando_Electoral_2026.mp4'
 run(['-f','concat','-safe','0','-i',str(OUT/'concat.txt'),'-i',str(OUT/'subtitulos.srt'),'-map','0:v','-map','0:a','-map','1:0','-c','copy','-c:s','mov_text','-metadata:s:a:0','language=spa','-metadata:s:s:0','language=spa','-movflags','+faststart',str(final)])
 run(['-i',str(final),'-map','0:v','-map','0:a','-f','null','-'])
 (OUT/'verificacion.json').write_text(json.dumps({'duration_seconds':total,'scenes':len(SCENES),'resolution':'1280x720','decode':'passed'},indent=2))
 print(final,flush=True)

if __name__=='__main__':
 prepare() if '--prepare' in sys.argv else render()
