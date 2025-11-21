import os
import shutil
import platform
from tkinter import Tk, Label, Button, filedialog, messagebox, Frame, Entry, LabelFrame, Canvas, Toplevel, Scrollbar
from PIL import Image, ImageTk
import cv2
import threading
import pygame
from moviepy import VideoFileClip

# Configuración de ffmpeg y ffprobe
os.environ["FFMPEG_BINARY"] = "/opt/homebrew/bin/ffmpeg"  # Cambia esto por la ruta en tu sistema
os.environ["FFPROBE_BINARY"] = "/opt/homebrew/bin/ffprobe"

class Clasificador:
    def __init__(self):
        self.ventana = Tk()
        # Forzar la actualización para garantizar que las dimensiones sean correctas
        self.ventana.update_idletasks()
        
        # Variables para la pantalla
        ancho = self.ventana.winfo_screenwidth()
        alto = self.ventana.winfo_screenheight()
        self.color = '#2c3e50'
        self.cursor = self.cursor if platform.system() == 'Darwin' else 'hand2'
        
        self.ventana.geometry(f'{ancho}x{alto}+{ancho // 2 - ancho // 2}+{alto // 2 - alto // 2}')
        self.ventana.resizable(True, True)
        self.ventana.configure(bg=self.color)
        self.ventana.title("Clasificador de Imágenes")
        
        # Frames de organización
        self.frameIzquierda = Frame(self.ventana, width=ancho/2, bg=self.color)
        self.frameIzquierda.pack(side='left', fill='both', expand=True)
        # Frames Internos
        self.frameSuperior = Frame(self.frameIzquierda, bg=self.color)
        self.frameSuperior.pack(side='top', fill='both', expand=False)
        # Frames Superiores
        self.frameSuperiorIzq = Frame(self.frameSuperior, width=self.frameSuperior.winfo_screenwidth()/2, bg=self.color)
        self.frameSuperiorIzq.pack(side='left', fill='both', expand=True)
        self.frameSuperiorDer = Frame(self.frameSuperior, width=self.frameSuperior.winfo_screenwidth()/2, bg=self.color)
        self.frameSuperiorDer.pack(side='left', fill='both', expand=True)
        # Frame Inferior
        self.frameInferior = Frame(self.frameIzquierda, bg=self.color)
        self.frameInferior.pack(side='bottom', fill='both', expand=True)
        # Frame Derecho
        self.labelFrame = LabelFrame(self.ventana, bg=self.color)
        self.labelFrame.pack(side='right', fill='both', expand=False)
        # ScrollBar
        self.scrollbar = Scrollbar(self.labelFrame)
        self.canvas = Canvas(self.labelFrame, yscrollcommand=self.scrollbar.set, highlightthickness=0)
        self.scrollbar.config(command=self.canvas.yview)
        self.scrollbar.pack(side='right', fill='y')
        self.scrollFrame = Frame(self.canvas)
        self.canvas.pack(side='right', fill='both', expand=False)
        self.canvas.create_window(0,0, window=self.scrollFrame, anchor='ne')
        self.scrollFrame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind("<Configure>", self.ajustar_scrollFrame)
        
        # Vincular eventos de desplazamiento al Canvas y al Frame interno
        self.canvas.bind("<MouseWheel>", self.scroll_with_mouse)       # Windows/Linux (Canvas)
        self.scrollFrame.bind("<MouseWheel>", self.scroll_with_mouse)  # Windows/Linux (Frame)
        self.canvas.bind("<Button-4>", self.scroll_with_mouse)         # macOS hacia arriba (Canvas)
        self.scrollFrame.bind("<Button-4>", self.scroll_with_mouse)    # macOS hacia arriba (Frame)
        self.canvas.bind("<Button-5>", self.scroll_with_mouse)         # macOS hacia abajo (Canvas)
        self.scrollFrame.bind("<Button-5>", self.scroll_with_mouse)    # macOS hacia abajo (Frame)

        # Variables
        self.lista = []
        self.indiceActual = 0
        self.etiquetaElemento = None
        self.carpetaOrigen = ""
        self.carpetaDestino = ''    # Carpeta principal
        self.carpetasDestino = {}
        # Extensiones válidas para imágenes y videos
        self.imagenValida = ('.png', '.jpg', '.jpeg', '.bmp', '.git')
        self.videoValido = ('.mp4', '.avi', '.mov', '.mkv')
        
        # Crear la interfaz
        self.interface()
        self.ventana.mainloop()    

    def interface(self):
        # Botón para seleccionar la carpeta de origen
        Button(self.frameSuperiorIzq, text='Seleccionar Carpeta de Origen', command=self.seleccionarCarpeta, padx=10, pady=10, relief='groove', cursor=self.cursor).pack(pady=10, anchor='center')

        # Botón para seleccionar la carpeta principal de destino
        Button(self.frameSuperiorIzq, text='Seleccionar Carpeta de Destino', command=self.carpetaPrincipalDestino, padx=10, pady=10, cursor=self.cursor).pack(pady=10, anchor='center')
        
        # Botón para crear nueva carpeta
        Button(self.frameSuperiorIzq, text='Agregar Nueva Carpeta', command=self.nuevaCarpetaPopup, padx=10, pady=10, cursor=self.cursor).pack(pady=10, anchor='center')
        
        # Botón para saltar a la siguiente imagen
        Button(self.frameSuperiorDer, text='Siguiente Imagen', command=self.siguienteElemento, padx=10, pady=10, cursor=self.cursor).pack(pady=10, anchor='center', side='bottom')
        
        # Botón para poner la imagen anterior
        Button(self.frameSuperiorDer, text='Imagen Anterior', command=self.anteriorElemento, padx=10, pady=10, cursor=self.cursor).pack(pady=10, anchor='center', side='bottom')
        
        # Etiqueta para mostrar elementos
        self.etiquetaElemento = Label(self.frameInferior)
        self.etiquetaElemento.pack(side='top', fill='both', pady=10, anchor='center', expand=True) 
  
    def ajustar_scrollFrame(self, event=None):
        """Ajustar el ancho del scrollFrame para alinearlo a la derecha dentro del canvas."""
        canvas_width = self.canvas.winfo_width()
        self.canvas.itemconfig(self.canvas.create_window((canvas_width, 0), window=self.scrollFrame, anchor='ne'))
    
    def scroll_with_mouse(self, event):
        """Maneja el desplazamiento del Canvas con la rueda del ratón o el trackpad."""
        if event.num == 4 or event.delta > 0:  # Desplazar hacia arriba
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:  # Desplazar hacia abajo
            self.canvas.yview_scroll(1, "units")
        
    def seleccionarCarpeta(self):
        """Selecciona la Carpeta de Origen, de la que se extraeran los archivos."""
        self.carpetaOrigen = filedialog.askdirectory(title='Seleccione la Carpeta de Origen')
        self.cargarElementos()
        
    def carpetaPrincipalDestino(self):
        """Selecciona la carpeta principal de destino y actualiza los botones con las subcarpetas."""
        self.carpetaDestino = filedialog.askdirectory(title='Selecione la Carpeta Destino')
        
        if not self.carpetaDestino:
            messagebox.showerror("Error","No seleccionaste ninguna carpeta")
            return
        
        # Cargar subcarpetas
        self.carpetasDestino = {
            folder: os.path.join(self.carpetaDestino, folder)
            for folder in os.listdir(self.carpetaDestino)
            if os.path.isdir(os.path.join(self.carpetaDestino, folder))
        }
        
        if not self.carpetasDestino: messagebox.showinfo("Información", "No se encontraron subcarpetas en la carpeta seleccionada.")
        else: self.actualizarBotones()
    
    def cargarElementos(self):
        """Carga las subcarpetas de la carpeta principal."""
        if not self.carpetaDestino:
            return
        
        self.carpetasDestino = {
            folder: os.path.join(self.carpetaDestino, folder)
            for folder in os.listdir(self.carpetaDestino)
            if os.path.isdir(os.path.join(self.carpetaDestino, folder))
        }
        self.actualizarBotones()

    def actualizarBotones(self):
        """Actualiza los botones de las categorías en la interfaz."""
        # Eliminar botones previos en el frame derecho
        for widget in self.scrollFrame.winfo_children(): widget.destroy()
        
        # Crear un botón por cada subcarpeta encontrada
        for carpeta, ruta in self.carpetasDestino.items():
            Button(self.scrollFrame, text=carpeta, command=lambda c = carpeta: self.clasificar(c), padx=5, pady=5, cursor=self.cursor).pack(padx=5, pady=5, fill='x')
            
        self.canvas.config(scrollregion=self.canvas.bbox('all'))

    def nuevaCarpetaPopup(self):
        """Crea y muestra un popup para ingresar el nombre de la nueva carpeta."""
        if not self.carpetaDestino:
            messagebox.showerror('Error', 'No hay una carpeta de destino cargada.')
        else:
            popup = Toplevel(self.ventana)
            popup.title("Crear Nueva Carpeta")
            xPop = self.ventana.winfo_screenwidth() // 2 - 300 // 2
            yPop = self.ventana.winfo_screenheight() // 2 - 150 // 2
            popup.geometry(f'300x150+{xPop}+{yPop}')
            
            # Etiqueta para la instrucción
            Label(popup, text='Ingrese el nombre de la nueva carpeta:').pack(pady=10)
            
            # Campo de entrada para el nombre de la nueva carpeta
            nombre = Entry(popup, width=30)
            nombre.pack(pady=5)
            
            # Botón para confirmar la creación de la carpeta
            Button(popup, text='Crear Carpeta', command=lambda: self.agregarNuevaCarpeta(nombre.get(), popup), cursor=self.cursor).pack(pady=10)
    
    def agregarNuevaCarpeta(self, nombreCarpeta, popup):
        """Agrega una nueva carpeta (subcarpeta) en la carpeta principal."""
        if not nombreCarpeta:
            messagebox.showerror(title='Error', message='El nombre de la carpeta no puede estar vacío.')
            return
        if nombreCarpeta in self.carpetasDestino:
            messagebox.showerror('Error', 'Ya existe una carpeta con ese nombre.')
        if any(char in nombreCarpeta for char in r'<>:"/º|?*'):
            messagebox.showerror('Error', 'El nombre de la carpeta contiene caracteres no permitidos.')
        
        nuevaCarpeta = os.path.join(self.carpetaDestino, nombreCarpeta)
        
        try:
            os.makedirs(nuevaCarpeta, exist_ok=True)
            self.carpetasDestino[nombreCarpeta] = nuevaCarpeta
            popup.destroy()
            self.actualizarBotones()
            messagebox.showinfo(title='Proceso Exitoso', message=f'Carpeta "{nombreCarpeta}" agregada.')
        except Exception as e:
            messagebox.showerror('Error', f'No se pudo crear la carpeta:\n{str(e)}')
            return
    
    def cargarElementos(self):
        """Carga imágenes y videos de la carpeta de origen."""
        if not self.carpetaOrigen:
            messagebox.showerror(title='Error', message='Por favor, seleccione una carpeta de origen primero.')
            return
        
        self.lista = [
            os.path.join(self.carpetaOrigen, f) for f in os.listdir(self.carpetaOrigen)
            if f.lower().endswith(self.imagenValida + self.videoValido)
        ]
        
        if not self.lista:
            messagebox.showerror(title='Error', message='No se encontraron imágenes o videos en la carpeta seleccionada.')
            return
        
        messagebox.showinfo(title='Proceso Exitoso', message=f'Se cargaron {len(self.lista)} archivos.')
        self.indiceActual = 0
        self.mostrarContenido()
        
    def mostrarContenido(self):
        """Muestra la imagen o el primer cuadro del video actual."""
        if not self.lista: return

        contenido = self.lista[self.indiceActual]
        extension = os.path.splitext(contenido)[1].lower()
        
        # Obtener el tamaño del frame donde se muestra la imagen
        self.ventana.update_idletasks()
        anchoFrame = self.etiquetaElemento.winfo_width()
        altoFrame = self.etiquetaElemento.winfo_height()
        
        # Eliminar cualquier botón previo de "Reproducir Video"
        for widget in self.frameSuperiorDer.winfo_children():
            if isinstance(widget, Button) and widget.cget("text") == "Reproducir Video":
                widget.destroy()
        
        if extension in (self.imagenValida):
            # Mostrar imagen
            imagen = Image.open(contenido)
            # Calcular proporciones para mantener la relación de aspecto
            anchoImagen, altoImagen = imagen.size
            aspectoRatio = anchoImagen/altoImagen
            
            # Ajustar imagen para que se escale correctamente al frame
            if anchoFrame / altoFrame > aspectoRatio:
                altura = altoFrame
                ancho = int(altoFrame * aspectoRatio)
            else:
                ancho = anchoFrame
                altura = int(anchoFrame/aspectoRatio)
                
            imagen = imagen.resize((ancho, altura))
            foto = ImageTk.PhotoImage(imagen)
            
            self.etiquetaElemento.config(image=foto)
            self.etiquetaElemento.image = foto
        elif extension in (self.videoValido):
            # Mostrar primer cuadro del video
            cap = cv2.VideoCapture(contenido)
            ret, frame = cap.read()
            cap.release()
            
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                imagen = Image.fromarray(frame)
                imagen = imagen.resize((anchoFrame, altoFrame))
                foto = ImageTk.PhotoImage(imagen)
                
                self.etiquetaElemento.config(image=foto)
                self.etiquetaElemento.image = foto

            # Crear botón para reproducir video
            reproducirvideo = Button(self.frameSuperiorDer, text='Reproducir Video', command=lambda: self.reproducirVideo(contenido), padx=10, pady=10, cursor=self.cursor)
            reproducirvideo.pack(pady=10, side='top')
        self.ventana.title(f'Archivo {self.indiceActual + 1} de {len(self.lista)}')
   
    def reproducirVideo(self, rutaVideo):
        """Abre un popup y reproduce el video en él."""
        popupVideo = Toplevel(self.ventana)
        popupVideo.title('Reproduciendo Video')
        xPopVideo = self.ventana.winfo_screenwidth() // 2 - 800 // 2 # 800
        yPopVideo = self.ventana.winfo_screenheight() // 2 - 1000 // 2 # 1000
        popupVideo.geometry(f'800x1000+{xPopVideo}+{yPopVideo}')
        
        # Etiqueta para mostrar los frames del video
        etiquetaVideo = Label(popupVideo)
        etiquetaVideo.pack(fill='both', expand=True)
        
        # Variable para controlar el hilo del video
        self.detenerAudio = threading.Event()
        
        def reproducirAudio():
            """Reproduce el audio del video usando Pygame."""
            clip = VideoFileClip(rutaVideo)
            audioPath = "temp_audio.mp3"
            clip.audio.write_audiofile(audioPath, logger=None)
            
            pygame.mixer.init()
            pygame.mixer.music.load(audioPath)  # Carga el audio desde el archivo de video
            pygame.mixer.music.play()   # Reproducir el audio
            
            # Esperar a que se detenga el audio o termine
            while pygame.mixer.music.get_busy():
                if self.detenerAudio.is_set():
                    pygame.mixer.music.stop()
                    break
            
            # Eliminar el archivo de audio temporal
            if os.path.exists(audioPath):
                os.remove(audioPath)
        
        def reproducir():
            """Reproduce el video"""
            ret, frame = cap.read()
            if not ret or self.detenerAudio.is_set():
                cap.release()
                return
            
            # Convertir frame a RGB para mostrarlo en Tkinter
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = cv2.resize(frame, (800, 1000))
            imagen = Image.fromarray(frame)
            foto = ImageTk.PhotoImage(imagen)
            etiquetaVideo.config(image=foto)
            etiquetaVideo.image = foto

            popupVideo.after(int(1000/fps * speed), reproducir)
            
        cap = cv2.VideoCapture(rutaVideo)
        fps = cap.get(cv2.CAP_PROP_FPS)
        speed = 1
        if fps == 0: fps = 30
        elif fps == 30: speed = 1.411
        elif fps > 30: speed = 0.53
        
        reproducir()
        
        hiloAudio = threading.Thread(target=reproducirAudio)
        hiloAudio.start()
            
        def cerrarPopup():
            """Detener audio y cerrar el popup."""
            self.detenerAudio.set()
            popupVideo.destroy()
        
        # Asociar el cierre del popup con la función cerrar_popup
        popupVideo.protocol("WM_DELETE_WINDOW", cerrarPopup)
        
        # Ejecutar el video en un hilo independiente para no bloquear la interfaz
        popupVideo.after(int(1000/fps), reproducir)
    
    def clasificar(self, carpeta):
        """Mueve el archivo actual a la carpeta especificada."""
        if not self.lista:
            messagebox.showerror('Error', message='No hay archivos cargados.')
            return
        
        if carpeta not in self.carpetasDestino:
            messagebox.showerror('Error', message=f'La carpeta "{carpeta}" no existe.')
            return
        
        # Obtener el archivo actual
        contenido = self.lista[self.indiceActual]
        carpetaDestino = os.path.join(self.carpetasDestino[carpeta], os.path.basename(contenido))
        
        try:
            # Mover el archivo
            shutil.move(contenido, carpetaDestino)
            messagebox.showinfo('Proceso Exitoso', message=f'Archivo movido a "{carpeta}"')
            
            # Eliminar el archivo de la lista
            self.lista.pop(self.indiceActual)

            # Actualizar la lista de archivos restantes
            if self.lista:
                self.indiceActual %= len(self.lista)
                self.mostrarContenido()
            else:
                self.etiquetaElemento.config(image=None)
                self.etiquetaElemento.image = None
                self.ventana.title("No hay más archivos para mostrar.")
        except Exception as e:
            messagebox.showerror('Error', f'No se pudo mover el archivo:\n{e}')
            
    def siguienteElemento(self):
        """Muestra el siguiente archivo."""
        if not self.lista:
            messagebox.showerror(title='Error', message='No hay archivos cargados por mostrar.')
            return
        
        self.indiceActual = (self.indiceActual + 1) % len(self.lista)
        self.mostrarContenido()
    
    def anteriorElemento(self):
        """Muestra el elemento anterior en la lista."""
        if not self.lista:
            messagebox.showerror('Error', 'No hay archivos cargados por mostrar.')
            return
        
        self.indiceActual = (self.indiceActual - 1) % len(self.lista)
        self.mostrarContenido()

Clasificador()