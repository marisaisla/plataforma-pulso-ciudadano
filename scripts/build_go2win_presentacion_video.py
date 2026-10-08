"""Narrated video using the eight approved executive presentation slides."""
from pathlib import Path
import json, math, subprocess, sys, wave
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/videos/presentacion_ejecutiva'
SLIDES = ROOT / 'output/html/go2win_ejecutiva'
NARRATION = [
    'Dirigir una campaña exige conocer lo que ocurre y dar seguimiento a cada decisión. Go to win ofrece al jefe de campaña una visión integral para coordinar a su equipo y evaluar resultados. Conecta la información de la candidatura con el análisis, la estrategia y la operación diaria. El tablero de mando electoral es el centro de esta visión.',
    'La información de una campaña suele estar repartida entre archivos de Excel, mensajes, encuestas y reportes. Las distintas versiones dificultan identificar qué está actualizado, quién debe actuar y qué sigue pendiente. Go to win conecta esa información para trabajar con responsabilidades claras y seguimiento oportuno. Así, el equipo cuenta con una base compartida para tomar decisiones.',
    'El modelo de Go to win comienza con un paso cero: el expediente y la viabilidad electoral, que se integran al inicio. A partir de ahí, el trabajo es continuo. El tablero de mando se conecta con la inteligencia artificial, la estrategia y la planeación. El CRM territorial móvil y el CRM de comunicación omnicanal llevan las decisiones a la operación y devuelven información para evaluar los avances.',
    'El expediente y la viabilidad electoral establecen el punto de partida. Se registra la candidatura, el tipo de elección y la delimitación territorial, junto con la evaluación legal, financiera y política. Esta base común permite interpretar la información dentro de su contexto. La vista territorial de Go to win ayuda a ubicar ese contexto y a relacionarlo con la información electoral.',
    'El tablero de mando electoral responde tres preguntas del jefe de campaña. ¿Qué está funcionando? ¿Qué requiere atención? ¿Qué debemos ajustar? Conecta objetivos, responsables, avances y resultados para dar seguimiento a la estrategia y evaluar su ejecución. La vista ilustrativa muestra cómo reunir el avance de actividades, los pendientes y las decisiones que requieren atención en una misma visión de dirección.',
    'La inteligencia artificial investiga, analiza y propone. Parte del expediente e integra datos electorales, información del INEGI e información complementaria que investiga. Cruza variables, identifica relaciones y analiza el contexto para proponer escenarios. Con la priorización territorial y los escenarios analizados, propone estrategias territoriales, de comunicación y planes de acción. El equipo de campaña evalúa estas propuestas y decide cómo llevarlas a la práctica.',
    'La estrategia se lleva a la operación mediante dos herramientas conectadas. El CRM territorial móvil utiliza Telegram para coordinar tareas, recibir reportes y capturar evidencias por responsable y territorio. Integra encuestas y registros con consentimiento. El CRM de comunicación omnicanal coordina mensajes, canales y responsables conforme a la estrategia, y da seguimiento a interacciones y solicitudes. La información de ambos retroalimenta el tablero de mando.',
    'El valor de Go to win está en conectar lo que la campaña sabe, lo que decide y lo que hace. Información integrada para compartir el contexto. Decisiones con sustento para evaluar escenarios. Ejecución coordinada con responsables y seguimiento. Y evaluación continua para revisar avances y ajustar las acciones. Go to win, inteligencia para dirigir la campaña.'
]

def run(args):
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-loglevel', 'error', '-y', *args], check=True)

def stamp(sec):
    n=round(sec*1000); h,n=divmod(n,3600000); m,n=divmod(n,60000); s,ms=divmod(n,1000)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'

def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'narracion.json').write_text(json.dumps(NARRATION, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUT/'Guion_Go2Win_Presentacion_Ejecutiva.txt').write_text('\n\n'.join(f'LÁMINA {i+1}\n{t}' for i,t in enumerate(NARRATION)),encoding='utf-8')

def render():
    total=0; subs=[]; details=[]
    for i,t in enumerate(NARRATION):
        audio=OUT/f'voice-{i:02}.wav'
        with wave.open(str(audio)) as wav:
            voice=wav.getnframes()/wav.getframerate()
            assert voice>5, f'Audio vacío: {audio}'
        duration=math.ceil((voice+0.6+(2.2 if i==7 else 0.8))*24)/24
        run(['-loop','1','-framerate','24','-i',str(SLIDES/f'slide-{i+1}.png'),'-i',str(audio),
             '-map','0:v','-map','1:a','-vf','scale=1280:720,setsar=1,format=yuv420p',
             '-af','adelay=600:all=1,apad,alimiter=limit=0.95',
             '-t',str(duration),'-c:v','libx264','-tune','stillimage','-preset','fast','-crf','19',
             '-c:a','aac','-ar','48000','-b:a','160k',str(OUT/f'clip-{i:02}.mp4')])
        sentences=[a.strip()+'.' for a in t.split('.') if a.strip()]
        words=sum(len(a.split()) for a in sentences); pos=total+0.6
        for sentence in sentences:
            end=pos+voice*len(sentence.split())/words
            subs.append(f'{len(subs)+1}\n{stamp(pos)} --> {stamp(end)}\n{sentence}\n');pos=end
        details.append({'slide':i+1,'start_seconds':total,'duration_seconds':duration,'voice_seconds':voice})
        total+=duration
        print(f'Lámina {i+1}/8 lista',flush=True)
    (OUT/'subtitulos.srt').write_text('\n'.join(subs),encoding='utf-8')
    (OUT/'concat.txt').write_text('\n'.join(f"file 'clip-{i:02}.mp4'" for i in range(8)),encoding='utf-8')
    final=OUT/'Go2Win_Presentacion_Ejecutiva.mp4'
    run(['-f','concat','-safe','0','-i',str(OUT/'concat.txt'),'-i',str(OUT/'subtitulos.srt'),
         '-map','0:v','-map','0:a','-map','1:0','-c','copy','-c:s','mov_text','-metadata:s:a:0','language=spa',
         '-metadata:s:s:0','language=spa','-metadata','title=Go2Win - Presentación ejecutiva','-movflags','+faststart',str(final)])
    run(['-i',str(final),'-map','0:v','-map','0:a','-f','null','-'])
    for i in [0,4,7]:
        run(['-ss',str(details[i]['start_seconds']+1),'-i',str(final),'-frames:v','1',str(OUT/f'check-{i+1}.png')])
    (OUT/'verificacion.json').write_text(json.dumps({'duration_seconds':total,'resolution':'1280x720','fps':24,'full_decode':'passed','scenes':details},indent=2),encoding='utf-8')
    print(json.dumps({'file':str(final),'seconds':total,'bytes':final.stat().st_size}),flush=True)

if __name__=='__main__':
    prepare() if '--prepare' in sys.argv else render()
