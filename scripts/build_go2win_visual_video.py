"""Add illustrations and archived Go2Win screens to the approved narration."""
import json
import shutil
import subprocess
import wave
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps
import build_movilizacion_explainer as base

ROOT = base.ROOT
OUT = base.OUT
WORK = OUT / 'visual_v9'
SCREENS = ROOT / 'output/videos/pantallas_go2win'
ART = ROOT / 'assets/go2win_video'
FF = base.imageio_ffmpeg.get_ffmpeg_exe()
# Historical screen references support the narrated topic; they are not live data.
VISUALS = {
    2: ('04-tablero.png', ['integral_06.jpg', 'integral_15.jpg']),
    4: ('01-diagnostico.png', ['integral_02.jpg', 'fuente2_01.jpg']),
    6: ('03-operacion.png', ['integral_06.jpg', 'integral_14.jpg']),
    7: ('01-diagnostico.png', ['integral_01.jpg', 'fuente2_01.jpg']),
    8: ('01-diagnostico.png', ['integral_06.jpg', 'integral_10.jpg']),
    9: ('02-escucha.png', ['integral_04.jpg', 'integral_11.jpg']),
    10: ('01-diagnostico.png', ['integral_10.jpg', 'integral_12.jpg']),
    11: ('01-diagnostico.png', ['integral_06.jpg', 'integral_10.jpg']),
    12: ('01-diagnostico.png', ['integral_13.jpg', 'integral_14.jpg']),
    13: ('03-operacion.png', ['integral_14.jpg', 'integral_15.jpg']),
    14: ('04-tablero.png', ['integral_05.jpg', 'integral_03.jpg']),
    15: ('02-escucha.png', ['integral_02.jpg', 'integral_03.jpg']),
    23: ('01-diagnostico.png', ['fuente2_01.jpg', 'integral_03.jpg']),
    24: ('02-escucha.png', ['fuente2_01.jpg', 'integral_11.jpg']),
    25: ('01-diagnostico.png', ['integral_12.jpg', 'integral_13.jpg']),
    26: ('03-operacion.png', ['integral_14.jpg', 'integral_05.jpg']),
    27: ('04-tablero.png', ['integral_15.jpg', 'integral_03.jpg']),
    28: ('04-tablero.png', ['integral_06.jpg', 'integral_14.jpg']),
}

def run(args):
    subprocess.run([FF, '-y', '-loglevel', 'error', *args], check=True)

def artwork(index, name):
    scene = base.SCENES[index]
    im = ImageOps.fit(Image.open(ART / name).convert('RGB'), (1280,720))
    shade = Image.new('RGBA', im.size)
    draw = ImageDraw.Draw(shade)
    for x in range(1280):
        draw.line((x,0,x,720), fill=(5,22,39,int(230 * max(0,1-x/1100))))
    im = Image.alpha_composite(im.convert('RGBA'), shade)
    d = ImageDraw.Draw(im)
    d.text((54,44),'Go2Win',font=base.font(34,True),fill='white')
    d.text((54,133),scene[0],font=base.font(19,True),fill='#4ce2d3')
    title=scene[1]
    # Long lines are wrapped for the image-led layout.
    import textwrap
    title='\n'.join(textwrap.fill(line, 25) for line in title.splitlines())
    d.multiline_text((50,194),title,font=base.font(45,True),fill='white',spacing=12)
    for j,line in enumerate(scene[2][:3]):
        d.text((56,445+j*44),line,font=base.font(21),fill='white')
    d.text((54,678),'Imagen conceptual · Go2Win',font=base.font(16),fill='#d5e4ec')
    path=WORK/f'art-{index:02}.png'
    im.convert('RGB').save(path)
    return path

def screen(index, number, name):
    im=Image.new('RGB',(1280,720),'#061b2d')
    src=ImageOps.contain(Image.open(SCREENS/name).convert('RGB'),(1280,632))
    im.paste(src,((1280-src.width)//2,44+(632-src.height)//2))
    d=ImageDraw.Draw(im)
    d.text((24,13),base.SCENES[index][0],font=base.font(19,True),fill='#4ce2d3')
    d.text((24,691),'Go2Win · Grabación de una versión anterior · Datos de ejemplo de la grabación',font=base.font(15),fill='#d5e4ec')
    path=WORK/f'screen-{index:02}-{number}.png';im.save(path)
    return path

def main():
    WORK.mkdir(parents=True,exist_ok=True)
    manifest=[]
    for i,scene in enumerate(base.SCENES):
        with wave.open(str(OUT/f'voice-{i:02}.wav')) as w:
            duration=w.getnframes()/w.getframerate()+0.9
        # Reuse approved full-slide scenes, including both opening slides and Telegram.
        if i not in VISUALS:
            shutil.copy2(OUT/f'clip-{i:02}.mp4',WORK/f'clip-{i:02}.mp4')
            continue
        art,names=VISUALS[i]
        frames=[artwork(i,art)]+[screen(i,j,n) for j,n in enumerate(names)]
        lengths=[round(duration*.34*24)/24,round(duration*.33*24)/24]
        lengths.append(duration-sum(lengths))
        parts=[]
        for j,(frame,seconds) in enumerate(zip(frames,lengths)):
            part=WORK/f'part-{i:02}-{j}.mp4';parts.append(part)
            vf='fps=24'
            if j==0:
                # Gentle push-in on conceptual art; UI screenshots remain uncropped.
                vf="scale=1920:1080,zoompan=z='min(zoom+0.00009,1.025)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s=1280x720:fps=24"
            vf+=f',fade=t=in:st=0:d=0.25,fade=t=out:st={max(0,seconds-.25)}:d=0.25'
            run(['-loop','1','-framerate','24','-i',str(frame),'-vf',vf,'-t',str(seconds),'-an','-c:v','libx264','-preset','ultrafast','-crf','21','-pix_fmt','yuv420p',str(part)])
        listing=WORK/f'parts-{i:02}.txt'
        listing.write_text('\n'.join(f"file '{p.name}'" for p in parts),encoding='utf-8')
        run(['-f','concat','-safe','0','-i',str(listing),'-i',str(OUT/f'voice-{i:02}.wav'),'-map','0:v','-map','1:a','-c:v','copy','-af','apad=pad_dur=0.9','-c:a','aac','-b:a','160k','-t',str(duration),str(WORK/f'clip-{i:02}.mp4')])
        manifest.append({'scene':i,'title':scene[1],'illustration':art,'historical_screens':names})
        print(f'Escena ilustrada {i+1}/{len(base.SCENES)}',flush=True)
    listing=WORK/'concat.txt'
    listing.write_text('\n'.join(f"file 'clip-{i:02}.mp4'" for i in range(len(base.SCENES))),encoding='utf-8')
    final=OUT/'Go2Win_ilustrado_pantallas_v9.mp4'
    run(['-f','concat','-safe','0','-i',str(listing),'-i',str(OUT/'subtitulos.srt'),'-map','0:v','-map','0:a','-map','1:0','-c','copy','-c:s','mov_text','-metadata:s:a:0','language=spa','-metadata:s:s:0','language=spa','-movflags','+faststart',str(final)])
    (WORK/'fuentes.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    run(['-i',str(final),'-map','0:v','-map','0:a','-f','null','-'])
    shutil.copy2(final,OUT/'Go2Win_movilizacion_electoral_con_voz.mp4')
    print(final,flush=True)

if __name__=='__main__':
    main()
