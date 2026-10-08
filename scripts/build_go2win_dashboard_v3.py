"""Apply the user's approved commercial narration corrections."""
import json, sys, wave
import build_go2win_dashboard_video as video

base=video.base
OUT=base.OUT/'tableros_v3'
changes={
 0:base.SCENES[0][3].replace('propone una visión','ofrece una visión'),
 1:base.SCENES[1][3].replace('La propuesta de Go to win es reunir','Go to win reúne').replace('la jefatura puede','el jefe de campaña puede'),
 5:base.SCENES[5][3].replace('La definición del proyecto incluye','Go to win incluye').replace('Propone integrar','Integra'),
 6:base.SCENES[6][3].replace('plantea conectar','conecta'),
 8:base.SCENES[8][3].replace('La visión del proyecto es acompañar','Go to win acompaña').replace('La propuesta contempla apoyar','La plataforma apoya'),
 9:'Go to win está listo para apoyar al jefe de campaña con información integrada, prioridades claras y seguimiento de resultados. La plataforma conecta evidencia, organización y operación en un mismo tablero. Su enfoque se guía por veracidad, privacidad, seguridad de datos y cumplimiento electoral. El jefe de campaña cuenta con una visión compartida para coordinar al equipo y dar seguimiento a las decisiones.',
 10:base.SCENES[10][3].replace('una propuesta para conectar','una plataforma que conecta').replace('Conoce el recorrido y la visión de la plataforma.','Conoce los tableros de mando de Go to win.'),
}
for i,narration in changes.items():
 row=list(base.SCENES[i]);row[3]=narration
 if i==9:row[0]='DIRECCIÓN DE CAMPAÑA';row[1]='Información integrada para el jefe de campaña'
 base.SCENES[i]=tuple(row)

def prepare():
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/'narracion.json').write_text(json.dumps([s[3] for s in base.SCENES],ensure_ascii=False),encoding='utf-8')
 (OUT/'guion.txt').write_text('\n\n'.join(s[0]+'\n'+s[3] for s in base.SCENES),encoding='utf-8')

def render():
 total=0;number=0;subs=[]
 for i,s in enumerate(base.SCENES):
  with wave.open(str(OUT/f'voice-{i:02}.wav')) as w:duration=w.getnframes()/w.getframerate()
  sentences=[x.strip()+'.' for x in s[3].split('.') if x.strip()]
  words=sum(len(x.split()) for x in sentences);pos=total
  for sentence in sentences:
   end=pos+duration*len(sentence.split())/words;number+=1
   subs.append(f'{number}\n{base.stamp(pos)} --> {base.stamp(end)}\n{sentence}\n');pos=end
  total+=round((duration+.8)*24)/24
 (OUT/'subtitulos.srt').write_text('\n'.join(subs),encoding='utf-8')
 text=(OUT/'guion.txt').read_text(encoding='utf-8').lower()
 assert 'jefe de campaña' in text
 assert not any(x in text for x in ['jefatura','en desarrollo','no garantiza','no asegura','en evolución'])
 base.OUT=OUT;video.OUT=OUT;video.FINAL_NAME='Go2Win_Tablero_de_Mando_v3.mp4'
 video.main()

if __name__=='__main__':
 prepare() if '--prepare' in sys.argv else render()
