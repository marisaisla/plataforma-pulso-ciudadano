"""Integrate the user's recorded walkthrough with the approved voice track."""
import json
import shutil
import wave
from PIL import Image, ImageDraw
import build_go2win_visual_video as visual

base = visual.base
OUT = base.OUT
WORK = OUT / 'recorrido_v10'
SOURCE = base.Path('C:/Users/jorge/OneDrive/Documentos/Presentaciones/Go2Win_Recorrido_Con_Introduccion_y_Voz_Corregido.mp4')
# Seconds reviewed in the user's recording: maps, scenarios, diagnosis,
# prioritization and strategy. Other scenes retain their approved visuals.
SEGMENTS = {2: 48, 4: 112, 6: 224, 8: 48, 9: 91, 10: 69,
            11: 144, 12: 314, 14: 145, 15: 110, 23: 119,
            24: 93, 25: 163, 26: 326, 27: 147, 28: 228}

def main():
    WORK.mkdir(parents=True, exist_ok=True)
    manifest=[]
    for i, scene in enumerate(base.SCENES):
        target=WORK/f'clip-{i:02}.mp4'
        if i not in SEGMENTS:
            shutil.copy2(visual.WORK/f'clip-{i:02}.mp4', target)
            continue
        with wave.open(str(OUT/f'voice-{i:02}.wav')) as w:
            length=w.getnframes()/w.getframerate()+.9
        art_length=round(length*.34*24)/24
        remaining=length-art_length
        overlay=Image.new('RGBA',(1280,720),(0,0,0,0));d=ImageDraw.Draw(overlay)
        d.rectangle((0,0,1280,43),fill='#061b2d')
        d.rectangle((0,676,1280,720),fill='#061b2d')
        d.text((24,12),scene[0],font=base.font(19,True),fill='#4ce2d3')
        d.text((24,693),'Go2Win · Recorrido grabado de la plataforma',font=base.font(16),fill='#d5e4ec')
        cover=WORK/f'label-{i:02}.png';overlay.save(cover)
        segment=WORK/f'recorrido-{i:02}.mp4'
        filters=f'[0:v]scale=1280:632:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=0x061b2d,setsar=1,fps=24[v];[v][1:v]overlay=0:0,fade=t=in:st=0:d=0.25,fade=t=out:st={remaining-.25}:d=0.25[out]'
        visual.run(['-ss',str(SEGMENTS[i]),'-i',str(SOURCE),'-i',str(cover),'-filter_complex',filters,'-map','[out]','-an','-t',str(remaining),'-c:v','libx264','-preset','ultrafast','-crf','21','-pix_fmt','yuv420p',str(segment)])
        art=WORK/f'art-{i:02}.mp4';shutil.copy2(visual.WORK/f'part-{i:02}-0.mp4',art)
        listing=WORK/f'parts-{i:02}.txt';listing.write_text(f"file '{art.name}'\nfile '{segment.name}'",encoding='utf-8')
        visual.run(['-f','concat','-safe','0','-i',str(listing),'-i',str(OUT/f'voice-{i:02}.wav'),'-map','0:v','-map','1:a','-c:v','copy','-af','apad=pad_dur=0.9','-c:a','aac','-b:a','160k','-t',str(length),str(target)])
        manifest.append({'scene':i,'title':scene[1],'source_start':SEGMENTS[i],'source_duration':remaining})
        print(f'Recorrido integrado: {i+1}/29',flush=True)
    listing=WORK/'concat.txt';listing.write_text('\n'.join(f"file 'clip-{i:02}.mp4'" for i in range(len(base.SCENES))),encoding='utf-8')
    final=OUT/'Go2Win_con_recorrido_integrado_v10.mp4'
    visual.run(['-f','concat','-safe','0','-i',str(listing),'-i',str(OUT/'subtitulos.srt'),'-map','0:v','-map','0:a','-map','1:0','-c','copy','-c:s','mov_text','-metadata:s:a:0','language=spa','-metadata:s:s:0','language=spa','-movflags','+faststart',str(final)])
    visual.run(['-i',str(final),'-map','0:v','-map','0:a','-f','null','-'])
    (WORK/'fuentes.json').write_text(json.dumps({'source':str(SOURCE),'segments':manifest},ensure_ascii=False,indent=2),encoding='utf-8')
    shutil.copy2(final,OUT/'Go2Win_movilizacion_electoral_con_voz.mp4')
    print(final,flush=True)

if __name__=='__main__':
    main()
