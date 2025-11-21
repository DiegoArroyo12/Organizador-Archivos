# Clasificador Facial
Organizador de fotos por reconocimiento facial con Python

**Dependencias:**

```
pip install deepface tf-keras opencv-python pillow
```

### Ajustes que puedes hacer:
- `threshold = 0.6` (Baja este valor si es muy estricto a 0.4 - 0.5), sube si es muy permisivo (0.7 - 0.8).
- Cambiar el modelo: se ocupa el modelo `VGG-Face` que es el más preciso, pero puedes optar por estas otras opciones:
- `Facenet` - Más rápido
- `OpenFace` - Balance entre velocidad y precisión
- `DeepFace` - Modelo original


### Cómo funcionan los videos
El parámetro `sample_rate=30` significa que analiza 1 de cada 30 fotogramas. Puedes ajustarlo: 

- Valor bajo (5 - 10): Más análisis pero más lento
- Valor alto (50+): Más rápido pero menos preciso

Si quieres cambiar la precisión, modifica esta línea:
```
file_encodings = self.extract_faces_from_video(file_path, sample_rate=15)  # Analiza más fotogramas
```

# Renombramiento
Programa que dada una carpeta, toma las imágenes y videos de este y borra los duplicados, después, renombra todos los elementos con el nombre de la carpeta en la que se encuentra y concatena con un contador.

La forma en la que borra los archivos duplicados es con un "hash". Un hash es como una huella digital única para cada archivo. Si dos archivos tienen la misma huella digital, son 100% idénticos, sin importar cómo se llamen.

### Instrucciones de uso

1. Abre una terminal o símbolo del sistema, navega a donde guardaste el archivo y escribe:

```
python Renombramiento.py
```
2. Usa la interfaz:
    - Haz clic en "Seleccionar..." y elige la carpeta que quieres organizar.
    - Verás la ruta en la pantalla.
    Haz clic en "Iniciar Proceso". Te pedirá una confirmación final, ya que borrar archivos es una acción permanente.
    - El cuadro de texto inferior te mostrará exactamente qué archivos se borran y cómo progresa el renombrado.

***Advertencia: Este script elimina archivos permanentemente.***

### Consideraciones
- Rendimiento: Calcular la huella digital de archivos muy grandes (como películas) tardará mucho más que con las fotos. Si procesas una carpeta con 50GB de videos, tomará un buen rato. El programa no estará colgado, estará trabajando en leer y calcular el hash de cada uno.

- Definición de "duplicado": El script solo encontrará copias 100% idénticas. No encontrará:
    - El mismo video pero re-codificado (ej. uno en `.mov` y otro en `.mp4`).
    - El mismo video pero con una calidad diferente (ej. uno en 1080p y otro en 4K).
    - Videos que son casi idénticos (ej. uno con 2 segundos extra al final).

# Clasificador Manual
Progama para visualizar y ordenar imágenes y videos de una carpeta seleccionada a un grupo de carpetas.

```
pip install pygame moviepy
```