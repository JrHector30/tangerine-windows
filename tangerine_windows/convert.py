"""
Motor de conversión de formatos local y de alta velocidad para Tangerine Windows.
Soporta Imágenes, Documentos (PDF), Audio y Video.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List

from PIL import Image, ImageOps

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIF_SUPPORTED = True
except Exception:
    HEIF_SUPPORTED = False

try:
    import pymupdf as fitz
    PYMUPDF_SUPPORTED = True
except Exception:
    PYMUPDF_SUPPORTED = False

# Extensiones reconocidas
IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", 
    ".tiff", ".tif", ".heic", ".heif", ".ico", ".avif"
}

AUDIO_EXTENSIONS = {
    ".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a", 
    ".wma", ".opus", ".aiff", ".alac"
}

VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".mov", ".webm", ".avi", ".flv", 
    ".wmv", ".m4v", ".ogv", ".3gp", ".ts", ".mts"
}

# Formatos según tipo de archivo
IMAGE_FORMATS = ["JPEG", "PNG", "WebP", "GIF", "BMP", "TIFF", "PDF", "ICO"]
if HEIF_SUPPORTED:
    IMAGE_FORMATS.insert(3, "HEIC")

PDF_FORMATS = ["PNG", "JPEG"]

AUDIO_FORMATS = [
    "To Ogg",
    "To Wav",
    "To Mp3",
    "To Aac",
]

VIDEO_FORMATS = [
    "To Mkv",
    "To Mp4",
    "To Mp4 (low quality)",
    "To Webm",
    "To Ogv",
    "To Avi",
    "To Gif",
    "To Gif (low quality)",
    "To Ogg",
    "To Wav",
    "To Mp3",
    "To Aac",
]


def get_ffmpeg_exe() -> str:
    """Obtiene la ruta del ejecutable FFmpeg."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
        
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
        
    raise RuntimeError(
        "FFmpeg no está instalado. Ejecuta: pip install imageio-ffmpeg"
    )


def get_available_formats(file_paths: List[str]) -> List[str]:
    """Retorna los formatos a los que se pueden convertir los archivos arrastrados."""
    if not file_paths:
        return IMAGE_FORMATS
    
    first_ext = Path(file_paths[0]).suffix.lower()
    
    if first_ext in VIDEO_EXTENSIONS:
        return VIDEO_FORMATS
        
    if first_ext in AUDIO_EXTENSIONS:
        return AUDIO_FORMATS
        
    if first_ext == ".pdf":
        return PDF_FORMATS
        
    if first_ext in IMAGE_EXTENSIONS:
        curr = first_ext.lstrip(".").upper()
        if curr in ("JPG", "JPEG"):
            return [f for f in IMAGE_FORMATS if f not in ("JPEG", "JPG")]
        return [f for f in IMAGE_FORMATS if f.upper() != curr]
        
    return IMAGE_FORMATS


def get_unique_output_path(source_path: Path, target_ext: str) -> Path:
    """Genera una ruta de salida en la misma carpeta sin sobrescribir."""
    target_ext = "." + target_ext.lstrip(".").lower()
    if target_ext == ".jpeg":
        target_ext = ".jpg"
        
    parent = source_path.parent
    stem = source_path.stem
    out = parent / f"{stem}{target_ext}"
    
    counter = 1
    while out.exists():
        out = parent / f"{stem} ({counter}){target_ext}"
        counter += 1
    return out


# ------------------ Conversión de Imágenes ------------------
def open_source_image(path: str | Path) -> Image.Image:
    im = Image.open(path)
    im.seek(0)
    im = ImageOps.exif_transpose(im)
    if im.mode in ("P", "LA", "PA"):
        im = im.convert("RGBA")
    elif im.mode not in ("RGB", "RGBA", "L"):
        im = im.convert("RGB")
    return im


def flatten_alpha(im: Image.Image, bg_color=(255, 255, 255)) -> Image.Image:
    if im.mode == "RGBA":
        bg = Image.new("RGB", im.size, bg_color)
        bg.paste(im, mask=im.split()[3])
        return bg
    return im.convert("RGB") if im.mode != "RGB" else im


def convert_image(source_file: str | Path, target_format: str, quality: int = 92) -> Path:
    source_path = Path(source_file)
    target_fmt = target_format.upper().replace("TO ", "").strip()
    
    pil_save_map = {
        "JPEG": "JPEG",
        "JPG": "JPEG",
        "PNG": "PNG",
        "WEBP": "WEBP",
        "GIF": "GIF",
        "BMP": "BMP",
        "TIFF": "TIFF",
        "HEIC": "HEIF",
        "ICO": "ICO",
        "PDF": "PDF",
    }
    pil_fmt = pil_save_map.get(target_fmt, "PNG")
    
    im = open_source_image(source_path)
    if target_fmt in ("JPEG", "JPG", "BMP"):
        im = flatten_alpha(im)
        
    out_ext = ".jpg" if target_fmt in ("JPEG", "JPG") else f".{target_fmt.lower()}"
    out_path = get_unique_output_path(source_path, out_ext)
    
    save_kwargs = {}
    if target_fmt in ("JPEG", "JPG", "WEBP", "HEIC"):
        save_kwargs["quality"] = quality
    if target_fmt in ("JPEG", "JPG"):
        save_kwargs["optimize"] = True
        save_kwargs["progressive"] = True
    elif target_fmt == "PNG":
        save_kwargs["optimize"] = True
    elif target_fmt == "ICO":
        side = min(256, max(im.size))
        im = ImageOps.contain(im.convert("RGBA"), (side, side))
        save_kwargs["sizes"] = [(s, s) for s in (16, 24, 32, 48, 64, 128, 256) if s <= side]
    elif target_fmt == "PDF":
        save_kwargs["resolution"] = 150.0

    im.save(out_path, format=pil_fmt, **save_kwargs)
    return out_path


# ------------------ Conversión de PDF ------------------
def convert_pdf_to_images(source_file: str | Path, target_format: str) -> List[Path]:
    if not PYMUPDF_SUPPORTED:
        raise RuntimeError("PyMuPDF no está disponible.")
        
    source_path = Path(source_file)
    target_fmt = target_format.upper().replace("TO ", "").strip()
    target_ext = ".jpg" if target_fmt in ("JPEG", "JPG") else ".png"
    
    doc = fitz.open(source_path)
    outputs = []
    
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        pix = page.get_pixmap(dpi=200)
        
        if len(doc) == 1:
            out_file = get_unique_output_path(source_path, target_ext)
        else:
            parent = source_path.parent
            stem = f"{source_path.stem}_p{page_num + 1}"
            out_file = parent / f"{stem}{target_ext}"
            counter = 1
            while out_file.exists():
                out_file = parent / f"{stem} ({counter}){target_ext}"
                counter += 1
                
        pix.save(str(out_file))
        outputs.append(out_file)
        
    doc.close()
    return outputs


# ------------------ Conversión de Audio y Video con FFmpeg ------------------
def run_ffmpeg_command(cmd_args: List[str]):
    """Ejecuta FFmpeg de forma completamente oculta sin abrir ventana CMD."""
    startupinfo = None
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
    result = subprocess.run(
        cmd_args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        startupinfo=startupinfo,
        creationflags=creationflags,
    )
    if result.returncode != 0:
        err_msg = result.stderr.decode("utf-8", errors="ignore")
        raise RuntimeError(f"FFmpeg error: {err_msg[:200]}")


def convert_media(source_file: str | Path, target_format: str) -> Path:
    ffmpeg_exe = get_ffmpeg_exe()
    source_path = Path(source_file)
    
    target_key = target_format.strip().lower()
    
    # Mapeo de argumentos de FFmpeg según formato
    if target_key == "to ogg":
        out_path = get_unique_output_path(source_path, ".ogg")
        cmd = [ffmpeg_exe, "-y", "-i", str(source_path), "-vn", "-c:a", "libvorbis", "-q:a", "5", str(out_path)]
    elif target_key == "to wav":
        out_path = get_unique_output_path(source_path, ".wav")
        cmd = [ffmpeg_exe, "-y", "-i", str(source_path), "-vn", "-c:a", "pcm_s16le", str(out_path)]
    elif target_key == "to mp3":
        out_path = get_unique_output_path(source_path, ".mp3")
        cmd = [ffmpeg_exe, "-y", "-i", str(source_path), "-vn", "-c:a", "libmp3lame", "-q:a", "2", str(out_path)]
    elif target_key == "to aac":
        out_path = get_unique_output_path(source_path, ".aac")
        cmd = [ffmpeg_exe, "-y", "-i", str(source_path), "-vn", "-c:a", "aac", "-b:a", "192k", str(out_path)]
    elif target_key == "to mkv":
        out_path = get_unique_output_path(source_path, ".mkv")
        cmd = [ffmpeg_exe, "-y", "-i", str(source_path), "-c:v", "libx264", "-preset", "fast", "-crf", "22", "-c:a", "aac", "-b:a", "192k", str(out_path)]
    elif target_key == "to mp4":
        out_path = get_unique_output_path(source_path, ".mp4")
        cmd = [ffmpeg_exe, "-y", "-i", str(source_path), "-c:v", "libx264", "-preset", "fast", "-crf", "22", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out_path)]
    elif target_key in ("to mp4 (low quality)", "to mp4 (lq)"):
        out_path = get_unique_output_path(source_path, ".mp4")
        cmd = [ffmpeg_exe, "-y", "-i", str(source_path), "-vf", "scale='min(720,iw)':-2", "-c:v", "libx264", "-preset", "fast", "-crf", "28", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(out_path)]
    elif target_key == "to webm":
        out_path = get_unique_output_path(source_path, ".webm")
        cmd = [ffmpeg_exe, "-y", "-i", str(source_path), "-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0", "-c:a", "libopus", str(out_path)]
    elif target_key == "to ogv":
        out_path = get_unique_output_path(source_path, ".ogv")
        cmd = [ffmpeg_exe, "-y", "-i", str(source_path), "-c:v", "libtheora", "-q:v", "7", "-c:a", "libvorbis", "-q:a", "4", str(out_path)]
    elif target_key == "to avi":
        out_path = get_unique_output_path(source_path, ".avi")
        cmd = [ffmpeg_exe, "-y", "-i", str(source_path), "-c:v", "mpeg4", "-q:v", "4", "-c:a", "mp3", str(out_path)]
    elif target_key == "to gif":
        out_path = get_unique_output_path(source_path, ".gif")
        cmd = [ffmpeg_exe, "-y", "-i", str(source_path), "-vf", "fps=15,scale=480:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse", str(out_path)]
    elif target_key in ("to gif (low quality)", "to gif (lq)"):
        out_path = get_unique_output_path(source_path, ".gif")
        cmd = [ffmpeg_exe, "-y", "-i", str(source_path), "-vf", "fps=10,scale=320:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=64[p];[s1][p]paletteuse", str(out_path)]
    else:
        # Fallback genérico a extensión
        fmt = target_key.replace("to ", "").split()[0]
        out_path = get_unique_output_path(source_path, f".{fmt}")
        cmd = [ffmpeg_exe, "-y", "-i", str(source_path), str(out_path)]

    run_ffmpeg_command(cmd)
    return out_path


def convert_files(file_paths: List[str], target_format: str) -> List[Path]:
    """Punto de entrada para procesar cualquier lote de archivos."""
    results = []
    for f in file_paths:
        p = Path(f)
        if not p.is_file():
            continue
            
        ext = p.suffix.lower()
        if ext in VIDEO_EXTENSIONS or ext in AUDIO_EXTENSIONS:
            results.append(convert_media(p, target_format))
        elif ext == ".pdf":
            results.extend(convert_pdf_to_images(p, target_format))
        else:
            results.append(convert_image(p, target_format))
            
    return results
