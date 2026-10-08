"""Replace product walkthroughs with explicitly conceptual dashboard imagery."""
import json, wave, shutil
from PIL import Image, ImageOps
import build_go2win_pdf_video as base

OUT=base.OUT/'tableros_v2'
ASSETS=OUT/'imagenes'
KEYS=['general','general','viabilidad','territorio','escucha','escucha',
      'operacion','seguimiento','general','seguimiento','general']
FINAL_NAME='Go2Win_Tablero_de_Mando_Conceptual_v2.mp4'

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 timeline=[];total=0
 for i,key in enumerate(KEYS):
  with wave.open(str(base.OUT/f'voice-{i:02}.wav')) as w:
   duration=round((w.getnframes()/w.getframerate()+.8)*24)/24
  image=Image.open(ASSETS/f'{key}.png').convert('RGB')
  image=ImageOps.pad(image,(1280,720),color='#082336',method=Image.Resampling.LANCZOS)
  frame=OUT/f'scene-{i:02}.png';image.save(frame)
  base.run(['-loop','1','-framerate','24','-i',str(frame),'-i',str(base.OUT/f'voice-{i:02}.wav'),'-vf',f'fade=t=in:st=0:d=0.35,fade=t=out:st={duration-.35}:d=0.35','-af','apad=pad_dur=1','-t',str(duration),'-c:v','libx264','-preset','ultrafast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k',str(OUT/f'clip-{i:02}.mp4')])
  timeline.append({'scene':i+1,'title':base.SCENES[i][1],'dashboard':key,'start':total,'duration':duration})
  total+=duration;print(f'Tablero {i+1}/11 listo',flush=True)
 (OUT/'concat.txt').write_text('\n'.join(f"file 'clip-{i:02}.mp4'" for i in range(len(KEYS))),encoding='utf-8')
 final=OUT/FINAL_NAME
 base.run(['-f','concat','-safe','0','-i',str(OUT/'concat.txt'),'-i',str(base.OUT/'subtitulos.srt'),'-map','0:v','-map','0:a','-map','1:0','-c','copy','-c:s','mov_text','-metadata:s:a:0','language=spa','-metadata:s:s:0','language=spa','-movflags','+faststart',str(final)])
 base.run(['-i',str(final),'-map','0:v','-map','0:a','-f','null','-'])
 (OUT/'timeline.json').write_text(json.dumps(timeline,ensure_ascii=False,indent=2),encoding='utf-8')
 print(final,flush=True)

if __name__=='__main__':main()
