"""
Motor de conversión de formatos local y de alta velocidad para Tangerine Windows.
Soporta Imágenes, Documentos de Office (Word, Excel, PPT), PDF, Audio y Video.
"""
from __future__ import annotations

import csv
import html
import io
import os
import shutil
import subprocess
import sys
import zipfile
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

try:
    import docx
    DOCX_SUPPORTED = True
except Exception:
    DOCX_SUPPORTED = False

try:
    import openpyxl
    OPENPYXL_SUPPORTED = True
except Exception:
    OPENPYXL_SUPPORTED = False

try:
    import pptx
    PPTX_SUPPORTED = True
except Exception:
    PPTX_SUPPORTED = False

try:
    import win32com.client
    WIN32COM_SUPPORTED = True
except Exception:
    WIN32COM_SUPPORTED = False


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

DOCUMENT_EXTENSIONS = {
    ".docx", ".doc",
    ".xlsx", ".xls", ".csv",
    ".pptx", ".ppt"
}

# Formatos según tipo de archivo
IMAGE_FORMATS = ["JPEG", "PNG", "WebP", "GIF", "BMP", "TIFF", "PDF", "ICO"]
if HEIF_SUPPORTED:
    IMAGE_FORMATS.insert(3, "HEIC")

PDF_FORMATS = ["PNG", "JPEG", "DOCX", "TXT"]

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

# Exacto como Tangerine macOS para Word/Excel/PPT:
# Sólo JPG y PNG para imágenes, y el resto PDF, TXT, MD, HTML, EPUB, PAGES
DOCUMENT_FORMATS = ["PDF", "TXT", "MD", "HTML", "EPUB", "PAGES", "JPG", "PNG"]


def get_ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    raise RuntimeError("FFmpeg no encontrado.")


def get_available_formats(file_paths: List[str]) -> List[str]:
    """Retorna los formatos destino apropiados según el tipo de archivo arrastrado."""
    if not file_paths:
        return IMAGE_FORMATS
    
    first_ext = Path(file_paths[0]).suffix.lower()
    
    # 1. Documentos de Office (Word, Excel, PowerPoint)
    if first_ext in DOCUMENT_EXTENSIONS:
        return DOCUMENT_FORMATS

    # 2. Videos
    if first_ext in VIDEO_EXTENSIONS:
        return VIDEO_FORMATS
        
    # 3. Audios
    if first_ext in AUDIO_EXTENSIONS:
        return AUDIO_FORMATS
        
    # 4. PDFs
    if first_ext == ".pdf":
        return PDF_FORMATS
        
    # 5. Imágenes
    if first_ext in IMAGE_EXTENSIONS:
        curr = first_ext.lstrip(".").upper()
        if curr in ("JPG", "JPEG"):
            return [f for f in IMAGE_FORMATS if f not in ("JPEG", "JPG")]
        return [f for f in IMAGE_FORMATS if f.upper() != curr]
        
    return IMAGE_FORMATS


def get_unique_output_path(source_path: Path, target_ext: str) -> Path:
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


# ------------------ Conversión de Documentos (Word, Excel, PPT) ------------------
def extract_document_text_and_md(path: Path) -> Tuple[str, str, str]:
    """Extrae texto plano, Markdown y contenido HTML estructurado."""
    ext = path.suffix.lower()
    plain_text = []
    md_lines = []
    html_parts = []

    if ext in (".docx", ".doc") and DOCX_SUPPORTED:
        doc = docx.Document(path)
        for p in doc.paragraphs:
            t = p.text.strip()
            if not t:
                continue
            plain_text.append(t)
            style_name = p.style.name.lower() if p.style else ""
            if "heading 1" in style_name:
                md_lines.append(f"# {t}\n")
                html_parts.append(f"<h1>{html.escape(t)}</h1>")
            elif "heading 2" in style_name:
                md_lines.append(f"## {t}\n")
                html_parts.append(f"<h2>{html.escape(t)}</h2>")
            elif "heading 3" in style_name:
                md_lines.append(f"### {t}\n")
                html_parts.append(f"<h3>{html.escape(t)}</h3>")
            elif "bullet" in style_name or "list" in style_name:
                md_lines.append(f"- {t}")
                html_parts.append(f"<li>{html.escape(t)}</li>")
            else:
                md_lines.append(f"{t}\n")
                html_parts.append(f"<p>{html.escape(t)}</p>")

        for table in doc.tables:
            html_parts.append("<table border='1' cellspacing='0' cellpadding='5'>")
            table_md = []
            for r_idx, row in enumerate(table.rows):
                cells = [c.text.strip() for c in row.cells]
                html_parts.append("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in cells) + "</tr>")
                table_md.append("| " + " | ".join(cells) + " |")
                if r_idx == 0:
                    table_md.append("| " + " | ".join(["---"] * len(cells)) + " |")
            html_parts.append("</table>")
            md_lines.extend(table_md)
            plain_text.append("\n".join(table_md))

    elif ext in (".xlsx", ".xls", ".csv"):
        if ext == ".csv":
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.reader(f)
                for row in reader:
                    plain_text.append("\t".join(row))
                    md_lines.append("| " + " | ".join(row) + " |")
                    html_parts.append("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in row) + "</tr>")
        elif OPENPYXL_SUPPORTED:
            wb = openpyxl.load_workbook(path, data_only=True)
            for sheetname in wb.sheetnames:
                ws = wb[sheetname]
                md_lines.append(f"## Hoja: {sheetname}\n")
                html_parts.append(f"<h2>{html.escape(sheetname)}</h2><table border='1'>")
                for row in ws.iter_rows(values_only=True):
                    row_strs = [str(c) if c is not None else "" for c in row]
                    if any(row_strs):
                        plain_text.append("\t".join(row_strs))
                        md_lines.append("| " + " | ".join(row_strs) + " |")
                        html_parts.append("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in row_strs) + "</tr>")
                html_parts.append("</table>")

    elif ext in (".pptx", ".ppt") and PPTX_SUPPORTED:
        prs = pptx.Presentation(path)
        for s_idx, slide in enumerate(prs.slides):
            md_lines.append(f"# Diapositiva {s_idx + 1}\n")
            html_parts.append(f"<div style='border:1px solid #ccc; padding:15px; margin:10px 0;'><h3>Diapositiva {s_idx + 1}</h3>")
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        t = para.text.strip()
                        if t:
                            plain_text.append(t)
                            md_lines.append(f"- {t}")
                            html_parts.append(f"<p>{html.escape(t)}</p>")
            html_parts.append("</div>")

    txt_content = "\n".join(plain_text)
    md_content = "\n".join(md_lines)
    full_html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'><title>"
        + html.escape(path.stem)
        + "</title><style>body{font-family:system-ui,sans-serif;max-width:800px;margin:30px auto;line-height:1.6;}table{border-collapse:collapse;width:100%;}td,th{border:1px solid #ddd;padding:8px;}</style></head><body>"
        + "".join(html_parts)
        + "</body></html>"
    )
    return txt_content, md_content, full_html


def build_epub_file(title: str, html_body: str, out_path: Path):
    """Construye un contenedor EPUB estándar en formato zip."""
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        container_xml = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""
        zf.writestr("META-INF/container.xml", container_xml)
        content_opf = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookID" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>{html.escape(title)}</dc:title>
    <dc:language>es</dc:language>
  </metadata>
  <manifest>
    <item id="chapter1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="chapter1"/>
  </spine>
</package>"""
        zf.writestr("OEBPS/content.opf", content_opf)
        chapter_xhtml = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>{html.escape(title)}</title></head>
<body>{html_body}</body>
</html>"""
        zf.writestr("OEBPS/chapter1.xhtml", chapter_xhtml)


def build_pages_file(title: str, text_content: str, out_path: Path):
    """Genera un archivo compatible .pages (paquete estructurado de texto)."""
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        meta_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<pages-document>
  <metadata><title>{html.escape(title)}</title></metadata>
  <content><![CDATA[{text_content}]]></content>
</pages-document>"""
        zf.writestr("Document.xml", meta_xml)
        zf.writestr("preview.txt", text_content)


def convert_office_to_pdf_native(source_path: Path, out_pdf_path: Path) -> bool:
    """Intenta exportar a PDF nativo usando Microsoft Office COM si está instalado."""
    if not WIN32COM_SUPPORTED:
        return False
    ext = source_path.suffix.lower()
    src_abs = str(source_path.resolve())
    out_abs = str(out_pdf_path.resolve())
    
    try:
        if ext in (".docx", ".doc"):
            word = win32com.client.Dispatch("Word.Application")
            word.Visible = False
            doc = word.Documents.Open(src_abs)
            doc.SaveAs(out_abs, FileFormat=17)  # 17 = wdFormatPDF
            doc.Close()
            word.Quit()
            return True
        elif ext in (".xlsx", ".xls"):
            excel = win32com.client.Dispatch("Excel.Application")
            excel.Visible = False
            wb = excel.Workbooks.Open(src_abs)
            wb.ExportAsFixedFormat(0, out_abs)  # 0 = xlTypePDF
            wb.Close(False)
            excel.Quit()
            return True
        elif ext in (".pptx", ".ppt"):
            ppt = win32com.client.Dispatch("PowerPoint.Application")
            prs = ppt.Presentations.Open(src_abs, WithWindow=False)
            prs.SaveAs(out_abs, 32)  # 32 = ppSaveAsPDF
            prs.Close()
            ppt.Quit()
            return True
    except Exception:
        pass
    return False


def convert_document(source_file: str | Path, target_format: str) -> List[Path]:
    """Convierte Word, Excel o PowerPoint a PDF, TXT, MD, HTML, EPUB, PAGES, JPG o PNG."""
    src = Path(source_file)
    fmt = target_format.upper().replace("TO ", "").strip()
    txt, md, doc_html = extract_document_text_and_md(src)
    outputs = []

    if fmt == "TXT":
        out = get_unique_output_path(src, ".txt")
        out.write_text(txt, encoding="utf-8")
        outputs.append(out)

    elif fmt == "MD":
        out = get_unique_output_path(src, ".md")
        out.write_text(md, encoding="utf-8")
        outputs.append(out)

    elif fmt == "HTML":
        out = get_unique_output_path(src, ".html")
        out.write_text(doc_html, encoding="utf-8")
        outputs.append(out)

    elif fmt == "EPUB":
        out = get_unique_output_path(src, ".epub")
        build_epub_file(src.stem, doc_html, out)
        outputs.append(out)

    elif fmt == "PAGES":
        out = get_unique_output_path(src, ".pages")
        build_pages_file(src.stem, txt, out)
        outputs.append(out)

    elif fmt == "PDF":
        out_pdf = get_unique_output_path(src, ".pdf")
        if not convert_office_to_pdf_native(src, out_pdf):
            # Fallback a creación de PDF con PyMuPDF
            if PYMUPDF_SUPPORTED:
                doc = fitz.open()
                page = doc.new_page(width=595, height=842)  # A4
                rect = fitz.Rect(50, 50, 545, 792)
                page.insert_textbox(rect, txt[:15000], fontsize=11, fontname="helv")
                doc.save(str(out_pdf))
                doc.close()
        outputs.append(out_pdf)

    elif fmt in ("JPG", "JPEG", "PNG"):
        # Convertir primero a PDF temporal y luego renderizar como imagen
        out_pdf = src.parent / f"_temp_{src.stem}.pdf"
        if not convert_office_to_pdf_native(src, out_pdf):
            if PYMUPDF_SUPPORTED:
                doc = fitz.open()
                page = doc.new_page(width=595, height=842)
                page.insert_textbox(fitz.Rect(50, 50, 545, 792), txt[:15000], fontsize=11)
                doc.save(str(out_pdf))
                doc.close()

        if out_pdf.exists() and PYMUPDF_SUPPORTED:
            doc = fitz.open(out_pdf)
            target_ext = ".jpg" if fmt in ("JPG", "JPEG") else ".png"
            for p_num in range(min(len(doc), 5)):
                page = doc.load_page(p_num)
                pix = page.get_pixmap(dpi=200)
                if len(doc) == 1:
                    img_out = get_unique_output_path(src, target_ext)
                else:
                    img_out = src.parent / f"{src.stem}_p{p_num + 1}{target_ext}"
                pix.save(str(img_out))
                outputs.append(img_out)
            doc.close()
            try:
                os.remove(out_pdf)
            except Exception:
                pass

    return outputs


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
        fmt = target_key.replace("to ", "").split()[0]
        out_path = get_unique_output_path(source_path, f".{fmt}")
        cmd = [ffmpeg_exe, "-y", "-i", str(source_path), str(out_path)]

    run_ffmpeg_command(cmd)
    return out_path


def convert_files(file_paths: List[str], target_format: str) -> List[Path]:
    """Punto de entrada universal para procesar cualquier tipo de archivo."""
    results = []
    for f in file_paths:
        p = Path(f)
        if not p.is_file():
            continue
            
        ext = p.suffix.lower()
        if ext in DOCUMENT_EXTENSIONS:
            results.extend(convert_document(p, target_format))
        elif ext in VIDEO_EXTENSIONS or ext in AUDIO_EXTENSIONS:
            results.append(convert_media(p, target_format))
        elif ext == ".pdf":
            results.extend(convert_pdf_to_images(p, target_format))
        else:
            results.append(convert_image(p, target_format))
            
    return results
