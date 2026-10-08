"""Build the local Go2Win commercial video from approved project assets."""

import sys as _storage_sys
from pathlib import Path as _StoragePath
_storage_sys.path.insert(0, str(_StoragePath(__file__).resolve().parents[1]))
from services.storage import storage_path


from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from moviepy import AudioFileClip, ColorClip, CompositeVideoClip, ImageClip, concatenate_videoclips


BASE_DIR = Path(__file__).resolve().parents[1]
ASSETS = storage_path("assets/go2win_video")
OUTPUT = storage_path("output") / "videos" / "go2win_comercial_con_voz.mp4"
SLIDES_DIR = ASSETS / "slides"
# HD ligero: se reproduce bien en pantalla y permite una exportación ágil.
WIDTH, HEIGHT = 1280, 720

SCENES = [
    ("01-diagnostico.png", "Go2Win.mx", "El dictamen de viabilidad: el punto de partida para decidir con evidencia."),
    ("02-escucha.png", "Escucha ciudadana", "Los temas del territorio se convierten en evidencia"),
    ("03-operacion.png", "Estrategia territorial", "Escenarios, metas y acción por distrito, municipio y sección"),
    ("04-tablero.png", "Tablero de mando", "Visualiza la brecha. Coordina. Da seguimiento."),
    ("05-triunfo.png", "Go2Win.mx", "De las decisiones al triunfo."),
]


def cover_image(image: Image.Image) -> Image.Image:
    ratio = max(WIDTH / image.width, HEIGHT / image.height)
    size = (round(image.width * ratio), round(image.height * ratio))
    image = image.resize(size, Image.Resampling.LANCZOS)
    left = (image.width - WIDTH) // 2
    top = (image.height - HEIGHT) // 2
    return image.crop((left, top, left + WIDTH, top + HEIGHT)).convert("RGB")


def build_slide(image_path: Path, title: str, subtitle: str, index: int) -> Path:
    image = cover_image(Image.open(image_path))
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for y in range(HEIGHT):
        alpha = int(205 * (y / HEIGHT) ** 2)
        draw.line((0, y, WIDTH, y), fill=(3, 20, 35, alpha), width=1)
    draw.rectangle((0, 0, WIDTH, 20), fill=(14, 116, 144, 255))
    font_title = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 55)
    font_subtitle = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 28)
    font_tag = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 17)
    draw.text((72, 520), "GO2WIN · TABLERO DE MANDO ELECTORAL", font=font_tag, fill=(125, 211, 252, 255))
    draw.text((72, 560), title, font=font_title, fill=(255, 255, 255, 255))
    draw.text((74, 630), subtitle, font=font_subtitle, fill=(226, 232, 240, 255))
    result = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    output = SLIDES_DIR / f"slide-{index:02d}.jpg"
    result.save(output, quality=94)
    return output


def moving_slide(slide: Path, duration: float, index: int):
    """Apply a subtle Ken Burns pan/zoom so each scene has visual movement."""
    direction = 1 if index % 2 else -1

    def scale_at(time: float) -> float:
        return 1.025 + (0.075 * min(time / duration, 1))

    def position_at(time: float) -> tuple[float, float]:
        scale = scale_at(time)
        overflow_x = (WIDTH * scale) - WIDTH
        overflow_y = (HEIGHT * scale) - HEIGHT
        progress = min(time / duration, 1)
        x = -overflow_x * (0.22 + (0.56 * progress if direction > 0 else 0.78 - 0.56 * progress))
        y = -overflow_y * (0.38 + 0.18 * progress)
        return x, y

    background = ColorClip((WIDTH, HEIGHT), color=(3, 20, 35)).with_duration(duration)
    image = (
        ImageClip(str(slide))
        .with_duration(duration)
        .resized(scale_at)
        .with_position(position_at)
    )
    return CompositeVideoClip([background, image], size=(WIDTH, HEIGHT)).with_duration(duration)


def main() -> None:
    SLIDES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    audio = AudioFileClip(str(ASSETS / "narracion-go2win.wav"))
    duration = audio.duration / len(SCENES)
    clips = []
    for index, (source, title, subtitle) in enumerate(SCENES, start=1):
        slide = build_slide(ASSETS / source, title, subtitle, index)
        clips.append(moving_slide(slide, duration, index))
    video = concatenate_videoclips(clips, method="compose").with_audio(audio)
    video.write_videofile(
        str(OUTPUT), fps=18, codec="libx264", audio_codec="aac", preset="ultrafast", logger=None
    )
    video.close()
    audio.close()
    for clip in clips:
        clip.close()
    print(OUTPUT)


if __name__ == "__main__":
    main()
