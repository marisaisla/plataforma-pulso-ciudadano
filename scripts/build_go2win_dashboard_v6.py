"""Keep the people/dashboard rhythm, add three brief UI inserts and opening-image close."""
import json, shutil, wave
from PIL import Image, ImageOps
import build_go2win_dashboard_v4 as video

base=video.base
PRIOR=base.OUT/'tableros_v5'
OUT=base.OUT/'tableros_v6'
CUTS={3:('recorrido',53),6:('recorrido',326),7:('integral',180)}

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 for i,key in enumerate(video.KEYS):
  target=OUT/f'clip-{i:02}.mp4'
  if i not in CUTS and i!=10:
   shutil.copy2(PRIOR/f'clip-{i:02}.mp4',target)
   continue
  with wave.open(str(PRIOR/f'voice-{i:02}.wav')) as w:
   length=round((w.getnframes()/w.getframerate()+.8)*24)/24
  if i in CUTS:
   initial=round(length*.36*24)/24;people=7.5;screen=3
   parts=[]
   for j in (0,1):
    p=OUT/f'part-{i:02}-{j}.mp4';shutil.copy2(PRIOR/f'part-{i:02}-{j}.mp4',p);parts.append(p)
   source,start=CUTS[i];p=OUT/f'part-{i:02}-2.mp4';parts.append(p)
   vf='[0:v]scale=1280:681:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(681-ih)/2:color=0x082336,setsar=1,fps=24[v];[v][1:v]overlay=0:0,fade=t=in:st=0:d=0.2,fade=t=out:st=2.8:d=0.2[out]'
   base.run(['-ss',str(start),'-i',str(base.VIDEOS[source]),'-i',str(PRIOR/'screen-label.png'),'-filter_complex',vf,'-map','[out]','-an','-t',str(screen),'-c:v','libx264','-preset','ultrafast','-crf','20','-pix_fmt','yuv420p',str(p)])
   p=OUT/f'part-{i:02}-3.mp4';parts.append(p)
   video.still(video.ASSETS/f'{key}.png',length-initial-people-screen,p)
  else:
   parts=[OUT/'closing-dashboard.mp4',OUT/'closing-image.mp4']
   video.still(video.ASSETS/f'{key}.png',length-7,parts[0])
   frame=OUT/'closing-image.png'
   ImageOps.pad(Image.open(base.ROOT/'output/html/recuperada_assets/intro_tablero.jpg').convert('RGB'),(1280,720),method=Image.Resampling.LANCZOS).save(frame)
   # Hold the opening image through the last frame, with no fade to black.
   base.run(['-loop','1','-framerate','24','-i',str(frame),'-vf','fade=t=in:st=0:d=0.3','-t','7','-an','-c:v','libx264','-preset','ultrafast','-crf','20','-pix_fmt','yuv420p',str(parts[1])])
  listing=OUT/f'parts-{i:02}.txt';listing.write_text('\n'.join(f"file '{p.name}'" for p in parts),encoding='utf-8')
  base.run(['-f','concat','-safe','0','-i',str(listing),'-i',str(PRIOR/f'voice-{i:02}.wav'),'-map','0:v','-map','1:a','-c:v','copy','-af','apad=pad_dur=1','-c:a','aac','-b:a','160k','-t',str(length),str(target)])
  print(f'Escena actualizada: {i+1}',flush=True)
 (OUT/'concat.txt').write_text('\n'.join(f"file 'clip-{i:02}.mp4'" for i in range(11)),encoding='utf-8')
 final=OUT/'Go2Win_Tablero_Personas_Sistema_v6.mp4'
 base.run(['-f','concat','-safe','0','-i',str(OUT/'concat.txt'),'-i',str(PRIOR/'subtitulos.srt'),'-map','0:v','-map','0:a','-map','1:0','-c','copy','-c:s','mov_text','-metadata:s:a:0','language=spa','-metadata:s:s:0','language=spa','-movflags','+faststart',str(final)])
 base.run(['-i',str(final),'-map','0:v','-map','0:a','-f','null','-'])
 (OUT/'verificacion.json').write_text(json.dumps({'source_version':'v5','system_inserts':CUTS,'system_seconds':9,'closing_image_seconds':7,'narration':'unchanged','decode':'passed'},indent=2),encoding='utf-8')
 print(final,flush=True)

if __name__=='__main__':main()
