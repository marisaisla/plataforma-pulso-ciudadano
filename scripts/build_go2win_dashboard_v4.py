"""Dashboard-led edit with the requested opening and brief product cutaways."""
import json, shutil, sys, wave
from PIL import Image,ImageOps,ImageDraw
import build_go2win_dashboard_v3 as previous

base=previous.base
OUT=base.OUT/'tableros_v4'
ASSETS=previous.video.ASSETS
KEYS=previous.video.KEYS
row=list(base.SCENES[1]);row[3]=row[3].replace('los archivos dispersos','los archivos de Excel dispersos');base.SCENES[1]=tuple(row)
CUTS={2:('dictamen',30),3:('recorrido',53),4:('integral',194),5:('recorrido',115),
      6:('recorrido',326),7:('recorrido',147),8:('recorrido',235),9:('integral',180)}
CUT_DURATION=4.5
FINAL_NAME='Go2Win_Tablero_de_Mando_Dinamico_v4.mp4'

def prepare():
 OUT.mkdir(parents=True,exist_ok=True)
 for i in range(len(KEYS)):shutil.copy2(previous.OUT/f'voice-{i:02}.wav',OUT/f'voice-{i:02}.wav')
 (OUT/'narracion.json').write_text(json.dumps([s[3] for s in base.SCENES],ensure_ascii=False),encoding='utf-8')
 (OUT/'guion.txt').write_text('\n\n'.join(s[0]+'\n'+s[3] for s in base.SCENES),encoding='utf-8')

def still(source,duration,target):
 frame=target.with_suffix('.png')
 ImageOps.pad(Image.open(source).convert('RGB'),(1280,720),color='#082336',method=Image.Resampling.LANCZOS).save(frame)
 base.run(['-loop','1','-framerate','24','-i',str(frame),'-vf',f'fade=t=in:st=0:d=0.2,fade=t=out:st={duration-.2}:d=0.2','-t',str(duration),'-an','-c:v','libx264','-preset','ultrafast','-crf','20','-pix_fmt','yuv420p',str(target)])

def render():
 total=0;subs=[];n=0;timeline=[];dashboard_time=0
 overlay=Image.new('RGBA',(1280,720),(0,0,0,0));d=ImageDraw.Draw(overlay)
 d.rectangle((0,681,1280,720),fill='#082336');d.text((24,690),'Go2Win · Pantalla del recorrido grabado',font=base.font(18),fill='white')
 overlay.save(OUT/'screen-label.png')
 for i,key in enumerate(KEYS):
  with wave.open(str(OUT/f'voice-{i:02}.wav')) as w:voice=w.getnframes()/w.getframerate()
  duration=round((voice+.8)*24)/24;dashboard=ASSETS/f'{key}.png';parts=[]
  if i in (0,1):
   intro=base.ROOT/'output/html/recuperada_assets'/('intro_tablero.jpg' if i==0 else 'intro_problematica.png')
   partspec=[('still',intro,8),('still',dashboard,duration-8)]
   dashboard_time+=duration-8
  elif i in CUTS:
   initial=round(duration*.36*24)/24;cut=CUT_DURATION
   partspec=[('still',dashboard,initial),('recorded',CUTS[i],cut),('still',dashboard,duration-initial-cut)]
   dashboard_time+=duration-cut
  else:partspec=[('still',dashboard,duration)];dashboard_time+=duration
  for j,(kind,source,length) in enumerate(partspec):
   part=OUT/f'part-{i:02}-{j}.mp4';parts.append(part)
   if kind=='still':still(source,length,part)
   elif source[0]=='people':
    picture=base.ROOT/'assets/go2win_video'/source[1]
    vf=f"scale=1920:1080,zoompan=z='min(zoom+0.00010,1.025)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s=1280x720:fps=24,fade=t=in:st=0:d=0.3,fade=t=out:st={length-.3}:d=0.3"
    base.run(['-loop','1','-framerate','24','-i',str(picture),'-vf',vf,'-an','-t',str(length),'-c:v','libx264','-preset','ultrafast','-crf','20','-pix_fmt','yuv420p',str(part)])
   else:
    video,start=source
    vf=f'[0:v]scale=1280:681:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(681-ih)/2:color=0x082336,setsar=1,fps=24[v];[v][1:v]overlay=0:0,fade=t=in:st=0:d=0.2,fade=t=out:st={length-.2}:d=0.2[out]'
    base.run(['-ss',str(start),'-i',str(base.VIDEOS[video]),'-i',str(OUT/'screen-label.png'),'-filter_complex',vf,'-map','[out]','-an','-t',str(length),'-c:v','libx264','-preset','ultrafast','-crf','20','-pix_fmt','yuv420p',str(part)])
  listing=OUT/f'parts-{i:02}.txt';listing.write_text('\n'.join(f"file '{p.name}'" for p in parts),encoding='utf-8')
  base.run(['-f','concat','-safe','0','-i',str(listing),'-i',str(OUT/f'voice-{i:02}.wav'),'-map','0:v','-map','1:a','-c:v','copy','-af','apad=pad_dur=1','-c:a','aac','-b:a','160k','-t',str(duration),str(OUT/f'clip-{i:02}.mp4')])
  sentences=[x.strip()+'.' for x in base.SCENES[i][3].split('.') if x.strip()];words=sum(len(x.split()) for x in sentences);pos=total
  for sentence in sentences:
   end=pos+voice*len(sentence.split())/words;n+=1;subs.append(f'{n}\n{base.stamp(pos)} --> {base.stamp(end)}\n{sentence}\n');pos=end
  timeline.append({'scene':i+1,'start':total,'duration':duration,'dashboard':key,'cutaway':CUTS.get(i)})
  total+=duration;print(f'Escena {i+1}/11 lista',flush=True)
 (OUT/'subtitulos.srt').write_text('\n'.join(subs),encoding='utf-8')
 (OUT/'concat.txt').write_text('\n'.join(f"file 'clip-{i:02}.mp4'" for i in range(len(KEYS))),encoding='utf-8')
 final=OUT/FINAL_NAME
 base.run(['-f','concat','-safe','0','-i',str(OUT/'concat.txt'),'-i',str(OUT/'subtitulos.srt'),'-map','0:v','-map','0:a','-map','1:0','-c','copy','-c:s','mov_text','-metadata:s:a:0','language=spa','-metadata:s:s:0','language=spa','-movflags','+faststart',str(final)])
 base.run(['-i',str(final),'-map','0:v','-map','0:a','-f','null','-'])
 (OUT/'verificacion.json').write_text(json.dumps({'duration':total,'dashboard_seconds':dashboard_time,'dashboard_share':dashboard_time/total,'decode':'passed','timeline':timeline},indent=2),encoding='utf-8')
 print(final,flush=True)

if __name__=='__main__':prepare() if '--prepare' in sys.argv else render()
