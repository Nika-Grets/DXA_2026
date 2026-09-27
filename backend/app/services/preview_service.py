from io import BytesIO

from PIL import Image


def encode_preview(
    pixels,
    *,
    image_format: str = "png",
    jpeg_quality: int = 90,
    max_side: int | None = None,
) -> bytes:
    image = Image.fromarray(pixels, mode="L")
    if max_side and max(image.size) > max_side:
        image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    output = BytesIO()
    if image_format == "jpeg":
        image.save(output, format="JPEG", quality=jpeg_quality, optimize=True)
    else:
        image.save(output, format="PNG", optimize=True)
    return output.getvalue()
