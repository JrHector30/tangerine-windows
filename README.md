# Tangerine for Windows 🍊

> **Drag. Hold Shift. Drop. Converted in 1 second.**  
> Recreación avanzada de la famosa app de macOS **Tangerine** ahora para **Windows 10 y Windows 11**.

![Tangerine Glass Preview](radial_glass_preview.png)

Sin abrir páginas web, sin abrir ventanas pesadas ni pulsar botones de confirmación: simplemente arrastra tus archivos con la tecla **Shift** presionada y suelta sobre el formato deseado.

---

## ✨ Novedades y Características

- 🎯 **Gesto Universal Shift + Drag Inteligente**: Funciona en cualquier parte de Windows (Escritorio, Explorador de archivos, etc.). **Protegido contra falsos positivos en juegos o navegadores**.
- 📑 **Documentos de Office (Word, Excel, PowerPoint)**:
  - Soporta `.docx`, `.doc`, `.xlsx`, `.xls`, `.csv`, `.pptx`, `.ppt`.
  - Opciones idénticas a Tangerine macOS: **PDF, TXT, MD, HTML, EPUB, PAGES, JPG, PNG**.
- 💎 **Diseño Glassmorphism & Plus Jakarta Sans**: Acabado de vidrio esmerilado con brillo ámbar, bordes especulares y tipografía moderna Plus Jakarta Sans.
- 💊 **Cápsula Central Dinámica**: Al mover el ratón sobre cualquier gajo, el centro muestra dinámicamente el formato elegido o el peso exacto (`1.2 MB`, `JPG`, `CROP`).
- 🔄 **Sub-Menús Radiales Inteligentes**:
  - Al mantener el cursor quieto sobre **PDF**, se abre el submenú de herramientas: **COMPRESS**, **CROP**, **CREATE PDF**, **COLLAGE**.
  - Al mantener el cursor sobre formatos de imagen (como **TIFF** o **JPEG**), se despliega el menú de herramientas avanzadas con iconos vectoriales minimalistas.
- ✂️ **Ventana de Ajuste Crop Image Profesional**:
  - Recorte manual interactivo arrastrando esquinas o el recuadro libre.
  - Dimensiones **W y H calculadas en PX en tiempo real** (con edición manual para medidas exactas).
  - Selector de relación de aspecto (*Free, 1:1, 16:9, 9:16, 4:3, 3:4*).
  - Botón circular de cierre `✕` y acabado Glassmorphism cálido idéntico a Tangerine.
- 🛠️ **Suite de Herramientas de Imagen**:
  - **Edit**: Ajustes en vivo de brillo, contraste, saturación, rotación 90° y volteo horizontal.
  - **Add BG**: Añade fondos elegantes con degradados y bordes redondeados.
  - **Redact**: Censura interactiva arrastrando cajas negras sobre datos privados.
  - **Annotate**: Lienzo para dibujar notas y flechas sobre la imagen.
  - **Compress, Create PDF, Collage, Metadata Strip**.
- 🤫 **100% Silencioso**: No interrumpe con notificaciones emergentes. El archivo procesado aparece inmediatamente junto al original.
- 🎬 **Soporte Multimedia Total**:
  - **Imágenes**: JPG, PNG, WebP, GIF, BMP, TIFF, HEIC/HEIF, ICO, PDF.
  - **Audios**: To Ogg, To Wav, To Mp3, To Aac.
  - **Videos (12 formatos)**: To Mkv, To Mp4, To Mp4 (Low Quality), To Webm, To Ogv, To Avi, To Gif, To Gif (Low Quality), y extracción de audio a Ogg, Wav, Mp3, Aac.

---

## 📸 Vistas Previas

| Menú Principal Glassmorphic | Documentos Office (8 formatos) | Ventana Crop Image con PX |
| :---: | :---: | :---: |
| ![Glass Preview](radial_glass_preview.png) | ![Document Preview](radial_document_preview.png) | ![Crop Dialog](crop_dialog_preview.png) |

---

## 🚀 Instalación y Uso Rápido

### Requisitos
- **Python 3.10+** instalado en Windows.

### 1. Clonar el repositorio
```bash
git clone https://github.com/JrHector30/tangerine-windows.git
cd tangerine-windows
```

### 2. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 3. Iniciar la aplicación
- **Modo Silencioso (en segundo plano)**:
  Doble clic en `iniciar_tangerine_silencioso.vbs`. Se abrirá en la bandeja del sistema junto al reloj.
- **Modo Interactivo**:
  Doble clic en `iniciar_tangerine.bat` o:
  ```bash
  python run.py
  ```

---

## 📦 ¿Cómo crear un Ejecutable `.exe` independiente?

Para generar un archivo `.exe` y usarlo sin necesidad de abrir Python:

```bash
pip install pyinstaller
pyinstaller --noconsole --onefile --name "Tangerine" run.py
```
El ejecutable se creará en la carpeta `dist/Tangerine.exe`.

---

## 📄 Licencia

Distribuido bajo la licencia MIT. Creado para la comunidad.
