"""
Motor de conversión de formatos local y de ultra alta velocidad para Lime Radial Windows.
Alineado con la matriz completa de formatos soportados:
- Imágenes: JPG, PNG, WebP, HEIC, TIFF, AVIF, BMP, PDF
- Audio: MP3, M4A, WAV, FLAC, OGG, Opus, AIFF, WMA
- Video: MP4, MOV, MKV, WebM, AVI, WMV, GIF, MP3
- PDF: DOCX, PAGES, PPTX, XLSX, JPG, PNG, EPUB, TXT, MD
- Documentos: PAGES, Markdown, TXT, EPUB, PDF, HTML, JPG, PNG
- Presentaciones (Slides): PDF, JPG, PNG, TXT, MD
- Hojas de cálculo: CSV, TSV, PDF, HTML, TXT, MD
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
from typing import List, Tuple

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

DOCUMENT_EXTENSIONS = {".docx", ".doc", ".pages", ".rtf", ".odt"}
SLIDE_EXTENSIONS = {".pptx", ".ppt", ".keynote", ".odp"}
SPREADSHEET_EXTENSIONS = {".xlsx", ".xls", ".numbers", ".csv", ".tsv", ".ods"}

# Formatos según tipo de archivo (Alineado estrictamente a Supported Formats)
IMAGE_FORMATS = ["JPG", "PNG", "WebP", "HEIC", "TIFF", "AVIF", "BMP", "PDF"]
AUDIO_FORMATS = ["MP3", "M4A", "WAV", "FLAC", "OGG", "Opus", "AIFF", "WMA"]
VIDEO_FORMATS = ["MP4", "MOV", "MKV", "WebM", "AVI", "WMV", "GIF", "MP3"]
PDF_FORMATS = ["DOCX", "PAGES", "PPTX", "XLSX", "JPG", "PNG", "EPUB", "TXT", "MD"]
DOCUMENT_FORMATS = ["PAGES", "Markdown", "TXT", "EPUB", "PDF", "HTML", "JPG", "PNG"]
SLIDE_FORMATS = ["PDF", "JPG", "PNG", "TXT", "MD"]
SPREADSHEET_FORMATS = ["CSV", "TSV", "PDF", "HTML", "TXT", "MD"]


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
        return list(IMAGE_FORMATS)
    
    first_ext = Path(file_paths[0]).suffix.lower()
    
    # 1. Hojas de cálculo (Excel, Numbers, CSV, TSV)
    if first_ext in SPREADSHEET_EXTENSIONS:
        return list(SPREADSHEET_FORMATS)

    # 2. Presentaciones (PowerPoint, Keynote)
    if first_ext in SLIDE_EXTENSIONS:
        return list(SLIDE_FORMATS)

    # 3. Documentos de texto (Word, Pages, RTF)
    if first_ext in DOCUMENT_EXTENSIONS:
        return list(DOCUMENT_FORMATS)

    # 4. Videos
    if first_ext in VIDEO_EXTENSIONS:
        return list(VIDEO_FORMATS)
        
    # 5. Audios
    if first_ext in AUDIO_EXTENSIONS:
        return list(AUDIO_FORMATS)
        
    # 6. PDFs
    if first_ext == ".pdf":
        return list(PDF_FORMATS)
        
    # 7. Imágenes
    if first_ext in IMAGE_EXTENSIONS:
        curr = first_ext.lstrip(".").upper()
        if curr in ("JPEG", "JPG"):
            curr = "JPG"
        fmts = [f for f in IMAGE_FORMATS if f.upper() != curr]
        if len(file_paths) > 1 and "PDF" not in fmts:
            fmts.append("PDF")
        return fmts
        
    return list(IMAGE_FORMATS)


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


# ------------------ Conversión de Documentos de Office y Texto ------------------
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

    elif ext in (".xlsx", ".xls", ".csv", ".tsv"):
        delimiter = "\t" if ext == ".tsv" else ","
        if ext in (".csv", ".tsv"):
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.reader(f, delimiter=delimiter)
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

    elif ext in (".txt", ".md"):
        txt = path.read_text(encoding="utf-8", errors="ignore")
        plain_text.append(txt)
        md_lines.append(txt)
        html_parts.append(f"<pre>{html.escape(txt)}</pre>")

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
    """Convierte Word, Excel, PowerPoint, CSV, TSV a los formatos objetivo soportados."""
    src = Path(source_file)
    fmt = target_format.upper().replace("TO ", "").strip()
    txt, md, doc_html = extract_document_text_and_md(src)
    outputs = []

    if fmt == "TXT":
        out = get_unique_output_path(src, ".txt")
        out.write_text(txt, encoding="utf-8")
        outputs.append(out)

    elif fmt in ("MD", "MARKDOWN"):
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

    elif fmt == "CSV":
        out = get_unique_output_path(src, ".csv")
        # Si es xlsx o tsv, convertir a csv estándar
        if src.suffix.lower() in (".xlsx", ".xls") and OPENPYXL_SUPPORTED:
            wb = openpyxl.load_workbook(src, data_only=True)
            ws = wb.active
            with open(out, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                for row in ws.iter_rows(values_only=True):
                    writer.writerow([c if c is not None else "" for c in row])
        else:
            with open(out, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                for line in txt.splitlines():
                    writer.writerow(line.split("\t"))
        outputs.append(out)

    elif fmt == "TSV":
        out = get_unique_output_path(src, ".tsv")
        if src.suffix.lower() in (".xlsx", ".xls") and OPENPYXL_SUPPORTED:
            wb = openpyxl.load_workbook(src, data_only=True)
            ws = wb.active
            with open(out, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f, delimiter="\t")
                for row in ws.iter_rows(values_only=True):
                    writer.writerow([c if c is not None else "" for c in row])
        else:
            with open(out, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f, delimiter="\t")
                for line in txt.splitlines():
                    writer.writerow(line.split(","))
        outputs.append(out)

    elif fmt == "PDF":
        out_pdf = get_unique_output_path(src, ".pdf")
        if not convert_office_to_pdf_native(src, out_pdf):
            if PYMUPDF_SUPPORTED:
                doc = fitz.open()
                page = doc.new_page(width=595, height=842)  # A4
                rect = fitz.Rect(50, 50, 545, 792)
                page.insert_textbox(rect, txt[:15000], fontsize=11, fontname="helv")
                doc.save(str(out_pdf))
                doc.close()
        outputs.append(out_pdf)

    elif fmt in ("JPG", "JPEG", "PNG"):
        out_pdf = src.parent / f"_temp_{src.stem}.pdf"
        if not convert_office_to_pdf_native(src, out_pdf):
            if PYMUPDF_SUPPORTED:
                doc = fitz.open()
                page = doc.new_page(width=595, height=842)
                rect = fitz.Rect(50, 50, 545, 792)
                page.insert_textbox(rect, txt[:15000], fontsize=11, fontname="helv")
                doc.save(str(out_pdf))
                doc.close()
        
        if out_pdf.exists() and PYMUPDF_SUPPORTED:
            target_ext = ".jpg" if fmt in ("JPG", "JPEG") else ".png"
            doc = fitz.open(out_pdf)
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                pix = page.get_pixmap(dpi=200)
                if len(doc) == 1:
                    out_img = get_unique_output_path(src, target_ext)
                else:
                    out_img = get_unique_output_path(src, f"_p{page_num + 1}{target_ext}")
                pix.save(str(out_img))
                outputs.append(out_img)
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
    
    # Soporte especial para AVIF mediante FFmpeg si Pillow no tiene codec nativo
    if target_fmt == "AVIF":
        out_path = get_unique_output_path(source_path, ".avif")
        ffmpeg_exe = get_ffmpeg_exe()
        cmd = [ffmpeg_exe, "-y", "-i", str(source_path), "-c:v", "libaom-av1", "-crf", "28", "-still-picture", "1", str(out_path)]
        try:
            run_ffmpeg_command(cmd)
            return out_path
        except Exception:
            # Fallback a WebP si no tiene libaom
            target_fmt = "WEBP"

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


# ------------------ Conversión Universal de PDF ------------------
def convert_pdf(source_file: str | Path, target_format: str) -> List[Path]:
    """
    Convierte un PDF a los formatos solicitados:
    DOCX, PAGES, PPTX, XLSX, JPG, PNG, EPUB, TXT, MD.
    """
    if not PYMUPDF_SUPPORTED:
        raise RuntimeError("PyMuPDF no está disponible.")
        
    source_path = Path(source_file)
    fmt = target_format.upper().replace("TO ", "").strip()
    doc = fitz.open(source_path)
    outputs = []

    # 1. Exportar a imágenes JPG o PNG por página
    if fmt in ("JPG", "JPEG", "PNG"):
        target_ext = ".jpg" if fmt in ("JPG", "JPEG") else ".png"
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=200)
            if len(doc) == 1:
                out_file = get_unique_output_path(source_path, target_ext)
            else:
                out_file = get_unique_output_path(source_path, f"_p{page_num + 1}{target_ext}")
            pix.save(str(out_file))
            outputs.append(out_file)
        doc.close()
        return outputs

    # Extraer texto y estructura de páginas
    full_text_list = []
    html_pages = []
    for page in doc:
        full_text_list.append(page.get_text("text"))
        html_pages.append(page.get_text("html"))
    doc.close()

    full_text = "\n\n".join(full_text_list).strip()
    full_html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'><title>"
        + html.escape(source_path.stem)
        + "</title></head><body>"
        + "".join(html_pages)
        + "</body></html>"
    )

    if fmt == "TXT":
        out = get_unique_output_path(source_path, ".txt")
        out.write_text(full_text, encoding="utf-8")
        outputs.append(out)

    elif fmt in ("MD", "MARKDOWN"):
        out = get_unique_output_path(source_path, ".md")
        md_text = "\n\n".join(f"# Página {i+1}\n\n{txt.strip()}" for i, txt in enumerate(full_text_list))
        out.write_text(md_text, encoding="utf-8")
        outputs.append(out)

    elif fmt == "HTML":
        out = get_unique_output_path(source_path, ".html")
        out.write_text(full_html, encoding="utf-8")
        outputs.append(out)

    elif fmt == "EPUB":
        out = get_unique_output_path(source_path, ".epub")
        build_epub_file(source_path.stem, full_html, out)
        outputs.append(out)

    elif fmt == "PAGES":
        out = get_unique_output_path(source_path, ".pages")
        build_pages_file(source_path.stem, full_text, out)
        outputs.append(out)

    elif fmt == "DOCX" and DOCX_SUPPORTED:
        out = get_unique_output_path(source_path, ".docx")
        wdoc = docx.Document()
        for i, p_txt in enumerate(full_text_list):
            if len(full_text_list) > 1:
                wdoc.add_heading(f"Página {i+1}", level=2)
            for line in p_txt.splitlines():
                if line.strip():
                    wdoc.add_paragraph(line.strip())
        wdoc.save(str(out))
        outputs.append(out)

    elif fmt == "PPTX" and PPTX_SUPPORTED:
        out = get_unique_output_path(source_path, ".pptx")
        prs = pptx.Presentation()
        for i, p_txt in enumerate(full_text_list):
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            tb = slide.shapes.add_textbox(pptx.util.Inches(0.8), pptx.util.Inches(0.8), pptx.util.Inches(8.4), pptx.util.Inches(5.8))
            tf = tb.text_frame
            tf.text = p_txt.strip()
        prs.save(str(out))
        outputs.append(out)

    elif fmt == "XLSX" and OPENPYXL_SUPPORTED:
        out = get_unique_output_path(source_path, ".xlsx")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Página 1"
        row_idx = 1
        for i, p_txt in enumerate(full_text_list):
            if i > 0:
                ws = wb.create_sheet(title=f"Página {i+1}")
                row_idx = 1
            for line in p_txt.splitlines():
                if line.strip():
                    ws.cell(row=row_idx, column=1, value=line.strip())
                    row_idx += 1
        wb.save(str(out))
        outputs.append(out)

    else:
        # Fallback predeterminado a TXT si el formato es desconocido
        out = get_unique_output_path(source_path, ".txt")
        out.write_text(full_text, encoding="utf-8")
        outputs.append(out)

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
    fmt = target_format.upper().replace("TO ", "").strip()
    
    # 1. Formatos de Audio
    if fmt == "MP3":
        out_path = get_unique_output_path(source_path, ".mp3")
        cmd = [ffmpeg_exe, "-y", "-i", str(source_path), "-vn", "-c:a", "libmp3lame", "-q:a", "2", str(out_path)]
    elif fmt == "M4A":
        out_path = get_unique_output_path(source_path, ".m4a")
        cmd = [ffmpeg_exe, "-y", "-i", str(source_path), "-vn", "-c:a", "aac", "-b:a", "192k", str(out_path)]
    elif fmt == "WAV":
        out_path = get_unique_output_path(source_path, ".wav")
        cmd = [ffmpeg_exe, "-y", "-i", str(source_path), "-vn", "-c:a", "pcm_s16le", str(out_path)]
    elif fmt == "FLAC":
        out_path = get_unique_output_path(source_path, ".flac")
        cmd = [ffmpeg_exe, "-y", "-i", str(source_path), "-vn", "-c:a", "flac", str(out_path)]
    elif fmt == "OGG":
        out_path = get_unique_output_path(source_path, ".ogg")
        cmd = [ffmpeg_exe, "-y", "-i", str(source_path), "-vn", "-c:a", "libvorbis", "-q:a", "5", str(out_path)]
    elif fmt == "OPUS":
        out_path = get_unique_output_path(source_path, ".opus")
        cmd = [ffmpeg_exe, "-y", "-i", str(source_path), "-vn", "-c:a", "libopus", "-b:a", "128k", str(out_path)]
    elif fmt == "AIFF":
        out_path = get_unique_output_path(source_path, ".aiff")
        cmd = [ffmpeg_exe, "-y", "-i", str(source_path), "-vn", "-c:a", "pcm_s16be", str(out_path)]
    elif fmt == "WMA":
        out_path = get_unique_output_path(source_path, ".wma")
        cmd = [ffmpeg_exe, "-y", "-i", str(source_path), "-vn", "-c:a", "wmav2", "-b:a", "192k", str(out_path)]
    elif fmt == "AAC":
        out_path = get_unique_output_path(source_path, ".aac")
        cmd = [ffmpeg_exe, "-y", "-i", str(source_path), "-vn", "-c:a", "aac", "-b:a", "192k", str(out_path)]

    # 2. Formatos de Video
    elif fmt == "MP4":
        out_path = get_unique_output_path(source_path, ".mp4")
        cmd = [ffmpeg_exe, "-y", "-i", str(source_path), "-c:v", "libx264", "-preset", "fast", "-crf", "22", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out_path)]
    elif fmt == "MOV":
        out_path = get_unique_output_path(source_path, ".mov")
        cmd = [ffmpeg_exe, "-y", "-i", str(source_path), "-c:v", "libx264", "-preset", "fast", "-crf", "22", "-c:a", "aac", "-b:a", "192k", str(out_path)]
    elif fmt == "MKV":
        out_path = get_unique_output_path(source_path, ".mkv")
        cmd = [ffmpeg_exe, "-y", "-i", str(source_path), "-c:v", "libx264", "-preset", "fast", "-crf", "22", "-c:a", "aac", "-b:a", "192k", str(out_path)]
    elif fmt == "WEBM":
        out_path = get_unique_output_path(source_path, ".webm")
        cmd = [ffmpeg_exe, "-y", "-i", str(source_path), "-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0", "-c:a", "libopus", str(out_path)]
    elif fmt == "AVI":
        out_path = get_unique_output_path(source_path, ".avi")
        cmd = [ffmpeg_exe, "-y", "-i", str(source_path), "-c:v", "mpeg4", "-q:v", "4", "-c:a", "mp3", str(out_path)]
    elif fmt == "WMV":
        out_path = get_unique_output_path(source_path, ".wmv")
        cmd = [ffmpeg_exe, "-y", "-i", str(source_path), "-c:v", "wmv2", "-b:v", "2M", "-c:a", "wmav2", "-b:a", "192k", str(out_path)]
    elif fmt == "GIF":
        out_path = get_unique_output_path(source_path, ".gif")
        cmd = [ffmpeg_exe, "-y", "-i", str(source_path), "-vf", "fps=15,scale='min(480,iw)':-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse", str(out_path)]
    else:
        out_path = get_unique_output_path(source_path, f".{fmt.lower()}")
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
        if ext in SPREADSHEET_EXTENSIONS or ext in SLIDE_EXTENSIONS or ext in DOCUMENT_EXTENSIONS:
            results.extend(convert_document(p, target_format))
        elif ext in VIDEO_EXTENSIONS or ext in AUDIO_EXTENSIONS:
            results.append(convert_media(p, target_format))
        elif ext == ".pdf":
            results.extend(convert_pdf(p, target_format))
        else:
            results.append(convert_image(p, target_format))
            
    return results
