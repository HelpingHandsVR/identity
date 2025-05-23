
"""
Generates the country flag variant of the logo

Requires FFmpeg
"""

import abc
import dataclasses
import functools
import io
import pathlib
import subprocess

import cairosvg
import requests
from PIL import Image, ImageDraw, ImageEnhance


CWD = pathlib.Path(__file__).parent
ROOT = CWD.parent.parent
LOGO_FOLDER = ROOT / 'logo'
OUTPUT_SIZE: int = 256


class BackgroundSource(abc.ABC):
    def get_image(self) -> Image.Image:
        raise NotImplementedError

    @property
    def brightness(self) -> float:
        return 1.0

    @functools.cached_property
    def logo_image(self) -> Image.Image:
        size = OUTPUT_SIZE

        background_image = self.get_image().resize((size, size), Image.Resampling.BICUBIC)
        enhancer = ImageEnhance.Brightness(background_image)
        background_image = enhancer.enhance(self.brightness)
        canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))

        with Image.new('L', (size, size), 0) as mask:
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, size, size), fill=255)

            canvas.paste(im=background_image, mask=mask)

        with Image.open(LOGO_FOLDER / 'hands_only.png') as hands:
            hands = hands.convert('RGBA').resize((size, size), Image.Resampling.BICUBIC)
            canvas.paste(im=hands, mask=hands)

        return canvas


@dataclasses.dataclass
class ImageBackgroundSource(BackgroundSource):
    path: pathlib.Path

    def get_image(self) -> Image.Image:
        return Image.open(self.path)


@dataclasses.dataclass
class TwemojiFlagBackgroundSource(BackgroundSource):
    id: str
    x_shift: float = 0.5
    height_scale: float = 0.72

    @property
    def brightness(self) -> float:
        return 0.8

    @property
    def regional(self) -> str:
        return ''.join(
            chr(
                ord(character.lower()) +
                (ord("\N{REGIONAL INDICATOR SYMBOL LETTER A}") - ord("a"))
            ) for character in self.id
        )

    @property
    def url(self) -> str:
        return (
            "https://github.com/twitter/twemoji/raw/d94f4cf793e6d5ca592aa00f58a88f6a4229ad43/assets/svg/"
            + '-'.join(f'{ord(character):x}' for character in self.regional)
            + ".svg"
        )

    @functools.cached_property
    def svg_content(self) -> str:
        print(f"Fetching {self.url} ...")
        response = requests.get(
            self.url,
            timeout=30
        )
        response.raise_for_status()

        return response.content

    def get_image(self) -> Image.Image:
        size = 4096
        render_scale = int(size / self.height_scale)

        output = cairosvg.svg2png(
            bytestring=self.svg_content,
            output_height=render_scale,
            output_width=render_scale,
        )

        top_trim = int((render_scale - size) / 2)
        right_trim = int((render_scale - size) * self.x_shift)

        image = Image.open(io.BytesIO(output))

        return image.crop((right_trim, top_trim, right_trim + size, top_trim + size))


# Represented by the regional indicator codes in Unicode
variant_list: list[BackgroundSource] = [
    ImageBackgroundSource(LOGO_FOLDER / 'background_unclipped.png'),
    TwemojiFlagBackgroundSource('us', x_shift=0.5),
    TwemojiFlagBackgroundSource('gb', x_shift=0.5),
    TwemojiFlagBackgroundSource('fr', x_shift=0.5),
    TwemojiFlagBackgroundSource('jp', x_shift=0.5),
    TwemojiFlagBackgroundSource('kr', x_shift=0.5),
    TwemojiFlagBackgroundSource('de', x_shift=0.5),
    TwemojiFlagBackgroundSource('nl', x_shift=0.5),
    TwemojiFlagBackgroundSource('ca', x_shift=0.5),
    TwemojiFlagBackgroundSource('es', x_shift=0.5),
    TwemojiFlagBackgroundSource('it', x_shift=0.5),
    TwemojiFlagBackgroundSource('pl', x_shift=0.5),
]

variant_image_bytes = [
    variant.logo_image.tobytes() for variant in variant_list
]

# Generate a palette
process = subprocess.Popen([
    'ffmpeg',
    '-r', '2', '-f', 'rawvideo', '-pixel_format', 'rgba', '-video_size', f'{OUTPUT_SIZE}x{OUTPUT_SIZE}',
    '-i', 'pipe:0',
    '-lavfi',
    'fps=2,palettegen',
    '-y',
    str(CWD / 'palette.png')
], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

for variant_content in variant_image_bytes:
    process.stdin.write(variant_content)

stdout, _ = process.communicate()

# Write the GIF by sequencing the frames together
process = subprocess.Popen([
    'ffmpeg',
    '-r', '2', '-f', 'rawvideo', '-pixel_format', 'rgba', '-video_size', f'{OUTPUT_SIZE}x{OUTPUT_SIZE}',
    '-i', 'pipe:0',
    '-i', str(CWD / 'palette.png'),
    '-lavfi', 'fps=2,paletteuse',
    '-f', 'gif',
    '-y',
    str(CWD / 'logo.gif')
], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

for variant_content in variant_image_bytes:
    process.stdin.write(variant_content)

stdout, _ = process.communicate()
