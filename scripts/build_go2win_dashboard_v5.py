"""Balance six dashboards with existing illustrative people imagery."""
import shutil
import build_go2win_dashboard_v4 as video

prior=video.OUT
video.OUT=video.base.OUT/'tableros_v5'
video.CUT_DURATION=7.5
video.FINAL_NAME='Go2Win_Tablero_de_Mando_Personas_v5.mp4'
video.CUTS={
 2:('people','01-diagnostico.png'),
 3:('people','03-operacion.png'),
 4:('people','02-escucha.png'),
 5:('people','02-escucha.png'),
 6:('people','03-operacion.png'),
 7:('people','01-diagnostico.png'),
 8:('people','03-operacion.png'),
 9:('people','04-tablero.png'),
}
if __name__=='__main__':
 video.prepare()
 # Keep the approved Excel phrasing and all three narration corrections.
 shutil.copy2(prior/'voice-01.wav',video.OUT/'voice-01.wav')
 video.render()
