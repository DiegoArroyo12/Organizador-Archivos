import os
import shutil
import platform
import uuid
import time
import tempfile
from tkinter import Tk, Label, Button, filedialog, messagebox, Frame, Entry, LabelFrame, Canvas, Toplevel, Scrollbar, StringVar, Listbox, END, ttk, LEFT, RIGHT, BooleanVar, Checkbutton
from PIL import Image, ImageTk
import cv2
import threading
import pygame
from moviepy import VideoFileClip
from LogicaRenombramiento import RenamerTool
from LogicaFacial import FaceBrain
from EditorImagen import EditorImagen

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    print("Soporte HEIC Activado")
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
except:
    print("Sin soporte HEIC (instala: pip install pillow-heif)")

COLOR_BG = "#202124"
COLOR_SIDEBAR = "#2f3136"
COLOR_ACCENT = "#5865F2"
COLOR_SUCCESS = "#3ba55c"
COLOR_WARNING = "#faa61a"
COLOR_TEXT = "#ffffff"
COLOR_TEXT_SEC = "#b9bbbe"
FONT_MAIN = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 11, "bold")

class Clasificador:
    def __init__(self):
        self.ventana = Tk()
        self.ventana.update_idletasks()
        
        ancho = self.ventana.winfo_screenwidth()
        alto = self.ventana.winfo_screenheight()
        self.cursor = 'hand2' if platform.system() != 'Darwin' else 'pointinghand'
        
        try: pygame.mixer.init()
        except: print("No se pudo iniciar el audio")
        
        self.renamer = RenamerTool(log_callback=print)
        self.ia = None
        self.sugerenciaIA = StringVar(value="IA Inactiva")
        self.estado_carga_texto = StringVar(value="Esperando configuración...")
        
        self.var_autoclose = BooleanVar(value=True)
        self.current_job_id = 0
        
        self.popup_video_actual = None
        
        self.ventana.geometry(f'{ancho}x{alto}+{ancho // 2 - ancho // 2}+{alto // 2 - alto // 2}')
        self.ventana.resizable(True, True)
        self.ventana.configure(bg=COLOR_BG)
        self.ventana.title("Clasificador Inteligente de Archivos")
        
        self.lista = []
        self.indiceActual = 0
        self.etiquetaElemento = None
        self.carpetaOrigen = ""
        self.carpetaDestino = ''
        self.carpetasDestino = {}
        self.imagenValida = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.heic', '.heif', '.bmp')
        self.videoValido = ('.mp4', '.avi', '.mov', '.mkv')
        self.historial_movimientos = []
        self.MAX_HISTORIAL = 50
        self.archivos_temp_activos = set()
        self.temp_cleanup_lock = threading.Lock()
        self.ia_lock = threading.Lock()
        self.ia_analyzing = False
        self.limpiar_archivos_temp_antiguos()
        
        self.ventana.protocol("WM_DELETE_WINDOW", self.cerrar_aplicacion)
        
        self.setup_ui()
        self.ventana.mainloop()

    def setup_ui(self):
        self.panel_izquierdo = Frame(self.ventana, bg=COLOR_SIDEBAR, width=250)
        self.panel_izquierdo.pack(side='left', fill='y')
        self.panel_izquierdo.pack_propagate(False)

        Label(self.panel_izquierdo, text="CONFIGURACIÓN", bg=COLOR_SIDEBAR, fg=COLOR_TEXT_SEC, font=("Arial", 8, "bold")).pack(pady=(20, 5), anchor="w", padx=15)
        
        self.crearBotonModerno(self.panel_izquierdo, "Origen", self.seleccionarCarpeta, COLOR_ACCENT, rutaImagen="iconos/carpetaIcono.png")
        self.crearBotonModerno(self.panel_izquierdo, "Destino (IA)", self.carpetaPrincipalDestino, COLOR_ACCENT, rutaImagen="iconos/carpetaIcono.png")
        
        self.check_autoclose = Checkbutton(self.panel_izquierdo, text="Auto-Cerrar Videos", variable=self.var_autoclose,
                                           bg=COLOR_SIDEBAR, fg="white", selectcolor=COLOR_BG, activebackground=COLOR_SIDEBAR, activeforeground="white",
                                           font=("Segoe UI", 9), bd=0, highlightthickness=0)
        self.check_autoclose.pack(fill='x', padx=15, pady=(5, 10))
        
        Frame(self.panel_izquierdo, bg="#40444b", height=1).pack(fill='x', padx=15, pady=15)
        
        Label(self.panel_izquierdo, text="ACCIONES", bg=COLOR_SIDEBAR, fg=COLOR_TEXT_SEC, font=("Arial", 8, "bold")).pack(pady=(5, 5), anchor="w", padx=15)
        self.crearBotonModerno(self.panel_izquierdo, "Nueva Carpeta", self.nuevaCarpetaPopup, "#4f545c", rutaImagen="iconos/agregarIcono.png")
        self.crearBotonModerno(self.panel_izquierdo, "Herramientas", self.abrir_menu_herramientas, colorFondo=COLOR_WARNING, rutaImagen="iconos/herramientasIcono.png")

        self.btn_deshacer = self.crearBotonModerno(self.panel_izquierdo, "Deshacer Último", self.deshacer_ultimo_movimiento, '#ed4245', rutaImagen="iconos/deshacer.png")
        self.btn_deshacer.config(state='disabled')
        self.lbl_historial = Label(self.panel_izquierdo, text="0 movimientos", bg=COLOR_SIDEBAR, fg="#8e8e93", font=("Segoe UI", 8))
        self.lbl_historial.pack(anchor="w", padx=15, pady=(0,5))

        # Deshacer (Ctrl + Z)
        def atajo_deshacer(event=None):
            if event and event.widget.winfo_class() in ('Entry', 'Text'): return
            # Seguridad: Solo ejecuta la acción si el botón está habilitado
            # (es decir, si realmente hay algo en el historial para deshacer)
            if self.btn_deshacer['state'] == 'normal':
                self.deshacer_ultimo_movimiento()

        # Vincular Ctrl+Z (Windows/Linux)
        self.ventana.bind('<Control-z>', atajo_deshacer)
        self.ventana.bind('<Control-Z>', atajo_deshacer)  # Por si tienes el Bloq Mayús activado

        # Vincular Command+Z (Solo para Mac)
        if platform.system() == 'Darwin':
            self.ventana.bind('<Command-z>', atajo_deshacer)
            self.ventana.bind('<Command-Z>', atajo_deshacer)

        # Atajos para las Flechas de Navegación
        def atajo_anterior(event=None):
            if event and event.widget.winfo_class() in ('Entry', 'Text'): return
            self.anteriorElemento()

        def atajo_siguiente(event=None):
            if event and event.widget.winfo_class() in ('Entry', 'Text'): return
            self.siguienteElemento()

        self.ventana.bind('<Left>', atajo_anterior)
        self.ventana.bind('<Right>', atajo_siguiente)

        # Información y Eliminación del Archivo
        self.frameArchivoActual = Frame(self.panel_izquierdo, bg="#202225", padx=10, pady=10)
        # side='bottom' asegura que siempre se quede pegado abajo
        self.frameArchivoActual.pack(side='bottom', fill='x', padx=10, pady=20)

        Label(self.frameArchivoActual, text="📄 ARCHIVO ACTUAL", bg="#202225", fg=COLOR_TEXT_SEC,
              font=("Arial", 8, "bold")).pack(anchor="w", pady=(0, 5))

        # wraplength=210 permite que los nombres largos hagan salto de línea automáticamente
        self.lbl_nombre_archivo = Label(self.frameArchivoActual, text="...", bg="#202225", fg="white",
                                        font=("Segoe UI", 9), wraplength=210, justify="left")
        self.lbl_nombre_archivo.pack(anchor="w", pady=(0, 10))

        self.btnEliminar = Button(
            self.frameArchivoActual,
            text="Eliminar (Supr)",
            command=self.eliminarArchivoActual,
            bg="#ed4245",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            bd=0,
            padx=10,
            pady=8,
            cursor=self.cursor
        )
        self.btnEliminar.pack(fill='x')

        # Atajos de teclado para eliminar
        def atajoEliminar(event=None):
            if event and event.widget.winfo_class() in ('Entry', 'Text'):
                return
            self.eliminarArchivoActual()

        self.ventana.bind('<Delete>', atajoEliminar)
        self.ventana.bind('<BackSpace>', atajoEliminar)

        self.panel_derecho = Frame(self.ventana, bg=COLOR_SIDEBAR, width=280)
        self.panel_derecho.pack(side='right', fill='y')
        self.panel_derecho.pack_propagate(False)

        self.card_ia = Frame(self.panel_derecho, bg="#202225", padx=10, pady=10)
        self.card_ia.pack(fill='x', padx=10, pady=20)
        
        Label(self.card_ia, text="MOTOR DE IA", bg="#202225", fg=COLOR_TEXT_SEC, font=("Arial", 8, "bold")).pack(anchor="w")
        
        style = ttk.Style()
        style.theme_use('default')
        style.configure("green.Horizontal.TProgressbar", background=COLOR_SUCCESS, troughcolor="#40444b", borderwidth=0)
        
        self.barra_carga = ttk.Progressbar(self.card_ia, orient="horizontal", mode="determinate", style="green.Horizontal.TProgressbar")
        self.barra_carga.pack(fill='x', pady=5)
        Label(self.card_ia, textvariable=self.estado_carga_texto, bg="#202225", fg="#dcddde", font=("Arial", 8)).pack(anchor="w")

        Frame(self.card_ia, bg="#40444b", height=1).pack(fill='x', pady=10)

        Label(self.card_ia, text="SUGERENCIA:", bg="#202225", fg=COLOR_TEXT_SEC, font=("Arial", 8)).pack(anchor="w")
        Label(self.card_ia, textvariable=self.sugerenciaIA, bg="#202225", fg=COLOR_SUCCESS, font=("Segoe UI", 16, "bold"), wraplength=240, justify="left").pack(anchor="w", pady=2)

        self.btn_accion_ia = Button(self.card_ia, text="Mover Aquí", bg=COLOR_ACCENT, fg="white", 
                                    font=("Segoe UI", 9, "bold"), bd=0, padx=10, pady=5, cursor=self.cursor)

        self.botonRecalcular = Button(
            self.card_ia,
            text="Recalcular Memoria IA",
            command=self.recalcularMemoriaIA,
            bg="#f44336",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            bd=0,
            padx=10,
            pady=5,
            cursor=self.cursor
        )
        
        #  Campo de búsqueda/filtro
        Label(self.panel_derecho, text="CLASIFICAR EN:", bg=COLOR_SIDEBAR, fg=COLOR_TEXT_SEC, 
            font=("Arial", 8, "bold")).pack(pady=(10, 5), anchor="w", padx=15)

        # Frame del filtro
        self.frame_filtro = Frame(self.panel_derecho, bg=COLOR_SIDEBAR)
        self.frame_filtro.pack(fill='x', padx=15, pady=(0, 10))

        # Variable para el texto del filtro
        self.filtro_texto = StringVar()
        self.filtro_texto.trace_add('write', lambda *args: self.aplicarFiltro())

        # Entry de búsqueda
        self.entryFiltro = Entry(self.frame_filtro, textvariable=self.filtro_texto,
                                bg="#40444b", fg="white", font=("Segoe UI", 10),
                                bd=0, insertbackground="white", relief="flat")
        self.entryFiltro.pack(side='left', fill='x', expand=True, ipady=5)

        # Placeholder text
        self.entryFiltro.insert(0, "Buscar Carpeta...")
        self.entryFiltro.config(fg="#8e8e93")

        # Eventos para el placeholder
        def on_entry_click(event):
            if self.entryFiltro.get() == "Buscar Carpeta...":
                self.entryFiltro.delete(0, "end")
                self.entryFiltro.config(fg="white")

        def on_focusout(event):
            if self.entryFiltro.get() == "":
                self.entryFiltro.insert(0, "Buscar Carpeta...")
                self.entryFiltro.config(fg="#8e8e93")

        self.entryFiltro.bind('<FocusIn>', on_entry_click)
        self.entryFiltro.bind('<FocusOut>', on_focusout)

        self.entryFiltro.bind('<KeyRelease>', self.aplicarFiltro())

        # Botón para limpiar filtro
        self.btn_limpiar_filtro = Button(self.frame_filtro,
                                        command=self.limpiar_filtro,
                                        bg="#40444b", fg="#8e8e93",
                                        font=("Segoe UI", 11, "bold"),
                                        bd=0, padx=8, cursor=self.cursor,
                                        relief="flat")
        img = Image.open('iconos/x.png').resize((24, 24), Image.Resampling.LANCZOS)
        foto = ImageTk.PhotoImage(img)
        self.btn_limpiar_filtro.config(image=foto, compound="left", padx=15)
        self.btn_limpiar_filtro.image = foto
        self.btn_limpiar_filtro.pack(side='right', padx=(5, 0))

        def on_enter_x(e): self.btn_limpiar_filtro['fg'] = "white"
        def on_leave_x(e): self.btn_limpiar_filtro['fg'] = "#8e8e93"
        self.btn_limpiar_filtro.bind("<Enter>", on_enter_x)
        self.btn_limpiar_filtro.bind("<Leave>", on_leave_x)
        
        self.frame_lista = Frame(self.panel_derecho, bg=COLOR_SIDEBAR)
        self.frame_lista.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.canvas = Canvas(self.frame_lista, bg=COLOR_SIDEBAR, highlightthickness=0)
        self.scrollbar = Scrollbar(self.frame_lista, orient="vertical", command=self.canvas.yview)
        self.scrollFrame = Frame(self.canvas, bg=COLOR_SIDEBAR)
        
        self.scrollFrame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scrollFrame, anchor="nw", width=250)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self._bind_mouse_scroll(self.canvas)

        self.panel_central = Frame(self.ventana, bg=COLOR_BG)
        self.panel_central.pack(side='left', fill='both', expand=True)
        
        self.frame_imagen = Frame(self.panel_central, bg=COLOR_BG)
        self.frame_imagen.pack(fill='both', expand=True, padx=20, pady=20)
        self.frame_imagen.pack_propagate(False)
        
        self.etiquetaElemento = Label(self.frame_imagen, bg="#000000", text="Sin Imagen Cargada", fg="#555")
        self.etiquetaElemento.pack(fill='both', expand=True)

        self.frame_nav = Frame(self.panel_central, bg=COLOR_BG, pady=20, height=80)
        self.frame_nav.pack(side='bottom', fill='x')
        self.frame_nav.pack_propagate(False)
        
        self.btn_crear_nav(self.frame_nav, "Anterior", self.anteriorElemento, side=LEFT, ruta_imagen='iconos/anterior.png')
        self.btn_crear_nav(self.frame_nav, "Siguiente", self.siguienteElemento, side=RIGHT, ruta_imagen='iconos/siguiente.png', iconSide='right')

        self.frame_info_centro = Frame(self.frame_nav, bg=COLOR_BG)
        self.frame_info_centro.pack(side=LEFT, fill='both', expand=True)
        
        self.lbl_contador = Label(self.frame_info_centro, text="0 / 0", 
                                  bg=COLOR_BG, fg="white", font=("Segoe UI", 18, "bold"))
        self.lbl_contador.pack(expand=True)

        # Quitar el foco del buscador al hacer clic fuera
        def quitar_foco(event):
            try:
                elemento_actual = self.ventana.focus_get()

                # Si el foco no está en un Entry o Text, NO hacemos nada.
                if not elemento_actual or elemento_actual.winfo_class() not in ('Entry', 'Text'): return

                # Validamos que el clic haya sido en la ventana principal.
                if event.widget.winfo_toplevel() == self.ventana:
                    # Si dimos clic en algo que NO es un Entry, le quitamos el foco
                    if event.widget.winfo_class() not in ('Entry', 'Text'):
                        self.ventana.after(10, self.ventana.focus_set)
            except Exception: pass  # Silenciar errores fantasma si se cierra una ventana de golpe

        self.ventana.bind_all("<Button-1>", quitar_foco)

    def crearBotonModerno(self, contenedorPadre, texto, comando, colorFondo="#36393f", rutaImagen=None):
        boton = Button(
            contenedorPadre,
            text=texto,
            command=comando,
            bg=colorFondo,
            fg="white",
            font=FONT_BOLD,
            bd=0,
            padx=20,
            pady=12,
            cursor=self.cursor,
            activebackground=colorFondo,
            activeforeground="white"
        )

        if rutaImagen and os.path.exists(rutaImagen):
            try:
                imagen = Image.open(rutaImagen).resize((24, 24), Image.Resampling.LANCZOS)
                fotoTk = ImageTk.PhotoImage(imagen)
                boton.config(image=fotoTk, compound="left", padx=15)
                boton.image = fotoTk
            except:
                pass

        boton.pack(fill='x', padx=15, pady=5)

        boton.bind("<Enter>", lambda evento: boton.config(bg=self.adjust_color_lightness(colorFondo, 1.2)))
        boton.bind("<Leave>", lambda evento: boton.config(bg=colorFondo))

        return boton

    def btn_crear_nav(self, parent, text, command, side, ruta_imagen=None, iconSide='left'):
        btn = Button(parent, text=text, command=command, bg="#40444b", fg="white", font=("Segoe UI", 12), bd=0, padx=30, pady=5, cursor=self.cursor)
        if ruta_imagen and os.path.exists(ruta_imagen):
            try:
                img = Image.open(ruta_imagen).resize((28, 28), Image.Resampling.LANCZOS)
                foto = ImageTk.PhotoImage(img)
                btn.config(image=foto, compound=iconSide, padx=15)
                btn.image = foto 
            except: pass
        btn.pack(side=side, padx=20)
        def on_enter(e): btn['bg'] = "#585d66"
        def on_leave(e): btn['bg'] = "#40444b"
        btn.bind("<Enter>", on_enter); btn.bind("<Leave>", on_leave)

    def btn_crear_categoria(self, parent, text, command):
        btn = self.crearBotonModerno(parent, f"{text}", command, "#36393f", "iconos/carpetaIcono.png")
        btn.pack(fill='x', padx=2, pady=1)
        self._bind_mouse_scroll(btn) 
        def on_enter(e): btn['bg'] = COLOR_ACCENT; btn['fg'] = "white"
        def on_leave(e): btn['bg'] = "#36393f"; btn['fg'] = "#dcddde"
        btn.bind("<Enter>", on_enter, add='+'); btn.bind("<Leave>", on_leave, add='+')

    def adjust_color_lightness(self, color_hex, factor):
        try:
            r, g, b = int(color_hex[1:3], 16), int(color_hex[3:5], 16), int(color_hex[5:7], 16)
            r = min(255, int(r * factor)); g = min(255, int(g * factor)); b = min(255, int(b * factor))
            return f"#{r:02x}{g:02x}{b:02x}"
        except: return color_hex

    def _bind_mouse_scroll(self, widget):
        widget.bind("<MouseWheel>", self.scroll_with_mouse)
        widget.bind("<Button-4>", self.scroll_with_mouse); widget.bind("<Button-5>", self.scroll_with_mouse)

    def ajustar_scrollFrame(self, event=None):
        self.canvas.itemconfig(self.canvas.create_window((0, 0), window=self.scrollFrame, anchor='nw', width=self.canvas.winfo_width()))
    
    def scroll_with_mouse(self, event):
        if event.num == 4 or event.delta > 0: self.canvas.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0: self.canvas.yview_scroll(1, "units")

    def actualizarBotones(self):
        """Actualiza la lista de carpetas agregando un botón de vista previa."""
        for widget in self.scrollFrame.winfo_children(): widget.destroy()
        if not self.carpetasDestino:
            Label(self.scrollFrame, text="No hay subcarpetas", bg=COLOR_SIDEBAR, fg="gray").pack(pady=10)
            return

        self._bind_mouse_scroll(self.scrollFrame)

        for carpeta in sorted(self.carpetasDestino.keys()):
            btnCarpeta = self.crearBotonModerno(
                self.scrollFrame,
                f"{carpeta}",
                comando=lambda c=carpeta: self.clasificar(c),
                rutaImagen="iconos/carpetaIcono.png"
            )
            btnCarpeta.pack(fill='x', padx=2, pady=1)

            # Eventos de clic derecho para abrir vista previa
            btnCarpeta.bind("<Button-3>", lambda e, c=carpeta: self.mostrarVistaPrevia(c))
            btnCarpeta.bind("<Button-2>", lambda e, c=carpeta: self.mostrarVistaPrevia(c))

            self._bind_mouse_scroll(btnCarpeta)

            def onEnter(e, btn=btnCarpeta):
                btn['bg'] = COLOR_ACCENT
                btn['fg'] = "white"

            def onLeave(e, btn=btnCarpeta):
                btn['bg'] = "#36393f"
                btn['fg'] = "#dcddde"

            btnCarpeta.bind("<Enter>", onEnter, add='+')
            btnCarpeta.bind("<Leave>", onLeave, add='+')

        self.canvas.config(scrollregion=self.canvas.bbox('all'))

    def mostrarVistaPrevia(self, nombreCarpeta):
        """Abre un popup ultrarápido mostrando hasta 5 imágenes de la carpeta."""
        rutaCarpeta = self.carpetasDestino[nombreCarpeta]

        archivosImagen = [os.path.join(rutaCarpeta, f) for f in os.listdir(rutaCarpeta)
                          if f.lower().endswith(self.imagenValida) and not f.startswith("._")]

        if not archivosImagen:
            messagebox.showinfo("Vista Previa", f"La carpeta '{nombreCarpeta}' no tiene imagenes aun.")
            return

        popup = Toplevel(self.ventana)
        popup.title(f"Referencias de {nombreCarpeta}")
        popup.configure(bg=COLOR_BG)
        popup.resizable(False, False)
        popup.bind('<Escape>', lambda e: popup.destroy())

        Label(popup, text=f"Primeras imagenes en {nombreCarpeta}",
              bg=COLOR_BG, fg="white", font=FONT_BOLD).pack(pady=10)

        galeriaFrame = Frame(popup, bg=COLOR_BG)
        galeriaFrame.pack(pady=10, padx=10)

        popup.listaFotos = []

        # Bucle de carga y escalado optimizado
        for imgPath in archivosImagen[:5]:
            try:
                imgOpen = Image.open(imgPath)
                if imgOpen.mode != 'RGB':
                    imgOpen = imgOpen.convert('RGB')

                imgOpen.thumbnail((250, 250), Image.Resampling.LANCZOS)
                fotoTk = ImageTk.PhotoImage(imgOpen)
                popup.listaFotos.append(fotoTk)

                lblImg = Label(galeriaFrame, image=fotoTk, bg="#000000", bd=2)
                lblImg.pack(side='left', padx=5)
            except Exception as e:
                print(f"Error cargando miniatura: {e}")

        # Logica de centrado dinamico
        popup.update_idletasks()
        anchoPop = popup.winfo_width()
        altoPop = popup.winfo_height()
        posicionX = self.ventana.winfo_screenwidth() // 2 - anchoPop // 2
        posicionY = self.ventana.winfo_screenheight() // 2 - altoPop // 2
        popup.geometry(f"+{posicionX}+{posicionY}")

        # --- Botón para reentrenar la memoria de esta carpeta ---
        def dispararReentrenamiento():
            if not self.ia: return

            # Cambiamos el texto para dar retroalimentación visual
            btnReentrenar.config(text="Reentrenando...", state="disabled", bg="#faa61a")
            self.ventana.update_idletasks()

            # Ejecutamos en segundo plano para no congelar la UI
            def hiloTrabajo():
                self.ia.reentrenarCarpeta(nombreCarpeta)
                self.ventana.after(0, lambda: [
                    messagebox.showinfo("Éxito", f"Memoria de {nombreCarpeta} actualizada."),
                    popup.destroy()
                ])

            threading.Thread(target=hiloTrabajo, daemon=True).start()

        btnReentrenar = Button(
            popup,
            text="Reentrenar IA con esta carpeta",
            command=dispararReentrenamiento,
            bg="#5865F2", fg="white", font=("Segoe UI", 9, "bold"),
            bd=0, padx=10, pady=5, cursor=self.cursor
        )
        btnReentrenar.pack(pady=(10, 5))

    def recalcularMemoriaIA(self):
        if not hasattr(self, 'ia') or not self.ia:
            return

        confirmacion = messagebox.askyesno(
            "Recalcular Memoria",
            "Deseas borrar la memoria actual y recalcular todas las referencias desde cero"
        )

        if confirmacion:
            if os.path.exists(self.ia.archivoCache):
                try:
                    os.remove(self.ia.archivoCache)
                except Exception as error:
                    print(f"Error borrando cache {error}")

            self.ia.knownEmbeddings.clear()
            self.estado_carga_texto.set("Recalculando Motor IA")
            self.ia.cargarReferenciasAsync()

    def actualizar_barra_ia(self, actual, total, texto=""):
        if actual == -1:
            self.barra_carga.config(mode='indeterminate')
            self.barra_carga.start(10)
            self.estado_carga_texto.set("Cargando Motor RetinaFace (Espere)...")
        else:
            self.barra_carga.stop()
            self.barra_carga.config(mode='determinate')
            if total > 0:
                porcentaje = (actual / total) * 100
                self.barra_carga['value'] = porcentaje
                self.estado_carga_texto.set(f"{texto} ({actual}/{total})")
            if actual >= total:
                self.barra_carga['value'] = 100
                self.estado_carga_texto.set("IA Activa y Lista")
                if self.lista:
                    self.sugerenciaIA.set("Re-Analizando...")
                    self.current_job_id += 1
                    threading.Thread(target=self._predecir_actual, args=(self.lista[self.indiceActual], self.current_job_id), daemon=True).start()
        self.ventana.update_idletasks()
        
    def aplicarFiltro(self, event=None):
        if not hasattr(self, 'scrollFrame') or not hasattr(self, 'carpetasDestino'):
            return

        textoBusqueda = self.entryFiltro.get().lower().strip()

        if textoBusqueda == "buscar carpeta...":
            textoBusqueda = ""

        hayResultados = False

        # Primera fase Limpieza visual
        for widget in self.scrollFrame.winfo_children():
            if isinstance(widget, Label):
                widget.destroy()
            elif isinstance(widget, Button):
                widget.pack_forget()

        # Segunda fase Reconstruccion en orden
        for widget in self.scrollFrame.winfo_children():
            if isinstance(widget, Button):
                textoBoton = widget.cget("text").lower()

                if textoBusqueda in textoBoton:
                    widget.pack(fill='x', padx=2, pady=1)
                    hayResultados = True

        # Validacion de resultados nulos
        if not hayResultados and self.carpetasDestino and textoBusqueda:
            Label(
                self.scrollFrame,
                text=f"No se encontro: {textoBusqueda}",
                bg="#2f3136",
                fg="#faa61a",
                font=("Segoe UI", 9)
            ).pack(pady=20)

        self.canvas.config(scrollregion=self.canvas.bbox('all'))

    def limpiar_filtro(self):
        """Limpia el campo de búsqueda sin romper el foco"""
        # Quitamos el foco y lo pasamos a la ventana
        self.ventana.focus_set()
        # Reseteamos el texto y color al estado inactivo
        self.entryFiltro.delete(0, "end")
        self.entryFiltro.insert(0, "Buscar Carpeta...")
        self.entryFiltro.config(fg="#8e8e93")
        # Forzamos la actualización visual para volver a mostrar los elementos
        self.entryFiltro.focus()

    def seleccionarCarpeta(self):
        self.carpetaOrigen = filedialog.askdirectory(title='Seleccione Carpeta Origen')
        self.cargarElementos()
        
    def carpetaPrincipalDestino(self):
        self.carpetaDestino = filedialog.askdirectory(title='Seleccione Carpeta Destino')
        if not self.carpetaDestino: return
        self.barra_carga['value'] = 0
        self.estado_carga_texto.set("Iniciando Motor IA...")
        self.ia = FaceBrain(self.carpetaDestino, callbackLog=print, callbackProgreso=self.actualizar_barra_ia)
        self.ia.cargarReferenciasAsync()
        self.carpetasDestino = {f: os.path.join(self.carpetaDestino, f) for f in os.listdir(self.carpetaDestino) if os.path.isdir(os.path.join(self.carpetaDestino, f))}
        self.actualizarBotones()
        
    def cargarElementos(self):
        if not self.carpetaOrigen: return
        try:
            self.lista = [os.path.join(self.carpetaOrigen, f) for f in os.listdir(self.carpetaOrigen) if f.lower().endswith(self.imagenValida + self.videoValido) and not f.startswith('._')]
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo leer la carpeta: {e}")
            return
        if not self.lista: messagebox.showerror('Info', 'Carpeta vacía de multimedia.')
        else:
            self.indiceActual = 0
            self.mostrarContenido()

    def mostrarContenido(self):
        if not self.lista: return
        self.current_job_id += 1
        job_id = self.current_job_id
        contenido = self.lista[self.indiceActual]
        ext = os.path.splitext(contenido)[1].lower()
        nombre_archivo = os.path.basename(contenido)

        def atajoRecorte(event=None):
            if event and event.widget.winfo_class() in ('Entry', 'Text'): return
            if ext in self.imagenValida: self.abrirEditor(contenido)
            elif ext in self.videoValido: self.abrirEditorVideo(contenido)

        def atajoReproducir(event=None):
            if event and event.widget.winfo_class() in ('Entry', 'Text'): return
            if ext in self.videoValido: self.reproducirVideo(contenido)

        # Quitamos los atajos temporalmente por seguridad
        self.ventana.unbind('<r>')
        self.ventana.unbind('<R>')
        self.ventana.unbind('<p>')
        self.ventana.unbind('<P>')

        # Vinculamos R siempre, pero P solo si es video
        self.ventana.bind('<r>', atajoRecorte)
        self.ventana.bind('<R>', atajoRecorte)
        if ext in self.videoValido:
            self.ventana.bind('<p>', atajoReproducir)
            self.ventana.bind('<P>', atajoReproducir)

        if not self.es_archivo_icloud_descargado(contenido):
            self.ventana.unbind('<r>')
            self.ventana.unbind('<R>')
            self.etiquetaElemento.config(
                image="",
                text=f"Archivo descargándose desde iCloud\n\n{nombre_archivo}\n\nEspera un momento...",
                compound="none"
            )
            self.lbl_contador.config(text=f"{self.indiceActual + 1} / {len(self.lista)}")
            self.lbl_nombre_archivo.config(text=nombre_archivo + " (descargando...)")
            self.ventana.after(2000, self.mostrarContenido)
            return

        self.ventana.bind('<r>', atajoRecorte)
        self.ventana.bind('<R>', atajoRecorte)

        self.lbl_contador.config(text=f"{self.indiceActual + 1} / {len(self.lista)}")
        self.lbl_nombre_archivo.config(text=nombre_archivo)
        self.ventana.update_idletasks()

        w_frame = self.frame_imagen.winfo_width()
        h_frame = self.frame_imagen.winfo_height()
        if w_frame < 50: w_frame = 800
        if h_frame < 50: h_frame = 600

        for widget in self.frame_imagen.winfo_children():
            if isinstance(widget, Button): widget.destroy()

        if ext in self.imagenValida:
            try:
                img = Image.open(contenido)
                if img.mode != 'RGB': img = img.convert('RGB')
                img.thumbnail((w_frame, h_frame), Image.Resampling.LANCZOS)
                foto = ImageTk.PhotoImage(img)
                self.etiquetaElemento.config(image=foto, text="", compound="none")
                self.etiquetaElemento.image = foto

                btn_edit = self.crearBotonModerno(
                    self.frame_imagen,
                    "Recortar Imagen (R)",
                    lambda: self.abrirEditor(contenido),
                    "#40444b",
                    "iconos/recortarIcono.png")
                btn_edit.place(relx=0.95, rely=0.05, anchor="ne")
            except Exception as e:
                self.etiquetaElemento.config(
                    image="",
                    text=f"No se pudo cargar la imagen:\n\n{e}",
                    compound="none",
                    fg="#ed4245"
                )

        elif ext in self.videoValido:
            cap = cv2.VideoCapture(contenido)
            ret, frame = cap.read()
            cap.release()
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img_pil = Image.fromarray(frame)
                img_pil.thumbnail((w_frame, h_frame))
                foto = ImageTk.PhotoImage(img_pil)
                self.etiquetaElemento.config(image=foto, text="", compound="none")
                self.etiquetaElemento.image = foto

                btn_play = self.crearBotonModerno(
                    self.frame_imagen,
                    "REPRODUCIR (P)",
                    lambda: self.reproducirVideo(contenido),
                    COLOR_ACCENT,
                    "iconos/play.png")
                btn_play.place(relx=0.5, rely=0.9, anchor="center")

                btn_crop = self.crearBotonModerno(
                    self.frame_imagen,
                    "Recortar Video (R)",
                    lambda: self.abrirEditorVideo(contenido),
                    "#40444b",
                    "iconos/recortarIcono.png")
                btn_crop.place(relx=0.95, rely=0.05, anchor="ne")
            else:
                self.etiquetaElemento.config(text="Video sin vista previa", image="", compound="none")

        # Manejo de Documentos (PDF, EXCEL, OTROS)
        else:
            # Quitamos el atajo de recorte porque no aplica a documentos
            self.ventana.unbind('<r>')
            self.ventana.unbind('<R>')

            # Textos e íconos por defecto
            texto_mostrar = f"Este archivo es un {ext.upper()}"
            ruta_icono = "iconos/txt.png"

            # Personalización según extensión
            if ext == '.pdf':
                texto_mostrar = "Este archivo es un PDF"
                ruta_icono = "iconos/pdf.png"
            elif ext in ('.xls', '.xlsx', '.csv'):
                texto_mostrar = "Este archivo es un EXCEL"
                ruta_icono = "iconos/excel.png"

            # Intentar cargar el ícono
            try:
                if os.path.exists(ruta_icono):
                    img_doc = Image.open(ruta_icono).resize((120, 120), Image.Resampling.LANCZOS)
                    foto_doc = ImageTk.PhotoImage(img_doc)
                    self.etiquetaElemento.config(
                        image=foto_doc,
                        text=f"{texto_mostrar}\n\n{nombre_archivo}",
                        compound="top",  # Pone la imagen arriba del texto
                        font=("Segoe UI", 12, "bold"),
                        fg="#b9bbbe"
                    )
                    self.etiquetaElemento.image = foto_doc
                else:
                    self.etiquetaElemento.config(
                        image="",
                        text=f"{texto_mostrar}\n\n{nombre_archivo}\n(Icono '{ruta_icono}' no encontrado)",
                        compound="none",
                        font=("Segoe UI", 12, "bold"),
                        fg="#b9bbbe"
                    )
            except:
                self.etiquetaElemento.config(image="", text=f"{texto_mostrar}\n\n{nombre_archivo}", compound="none")

        self.btn_accion_ia.pack_forget()
        self.card_ia.config(bg="#202225")

        if self.ia:
            self.sugerenciaIA.set("Analizando...")

            def iniciarAnalisisDelay():
                time.sleep(0.3)
                if job_id == self.current_job_id:
                    threading.Thread(
                        target=self._predecir_actual,
                        args=(contenido, job_id),
                        daemon=True
                    ).start()

            # Ejecutar en un thread separado
            threading.Thread(target=iniciarAnalisisDelay, daemon=True).start()
        else: self.sugerenciaIA.set("IA Inactiva")
            
    def abrirEditor(self, image_path):
        """Abre el editor de imágenes con manejo de errores mejorado"""
        if not os.path.exists(image_path):
            messagebox.showerror("Error", f"El archivo no existe:\n{image_path}")
            return
        
        ext = os.path.splitext(image_path)[1].lower()
        if ext in self.videoValido:
            messagebox.showerror("Error", "Este es un archivo de video, no una imagen.")
            return
        
        if not self.es_archivo_icloud_descargado(image_path):
            messagebox.showwarning("Descargando", 
                "El archivo aún se está descargando desde iCloud.\n"
                "Espera a que termine la descarga e intenta de nuevo.")
            return
        
        try:
            test_img = Image.open(image_path)
            test_img.verify()
            test_img.close()
            test_img = Image.open(image_path)
            width, height = test_img.size
            test_img.close()
            
            if width == 0 or height == 0: raise Exception("La imagen no tiene dimensiones válidas")
        except Exception as e:
            messagebox.showerror("Error", 
                f"No se puede abrir la imagen:\n{str(e)}\n\n"
                "Posibles causas:\n"
                "• Archivo corrupto o incompleto\n"
                "• Formato no soportado\n"
                "• Archivo aún descargándose de iCloud")
            return
        
        # Cancelar análisis mientras se edita
        self.current_job_id += 1
        
        def alTerminar(coords=None):
            try:
                # Dar tiempo para que PIL suelte el archivo
                time.sleep(0.3)
                
                # Recargar contenido visual
                self.mostrarContenido()
                
                # Re-analizar con IA SIEMPRE que exista IA
                if self.ia and os.path.exists(image_path):
                    self.current_job_id += 1
                    nuevo_job_id = self.current_job_id
                    
                    # Actualizar UI inmediatamente
                    self.sugerenciaIA.set("Analizando...")
                    
                    def analizarImagenEditada():
                        # Esperar a que el archivo esté listo
                        time.sleep(0.5)
                        
                        # Verificar que seguimos en la misma imagen
                        if self.lista and self.indiceActual < len(self.lista):
                            archivoActual = self.lista[self.indiceActual]
                            if archivoActual == image_path:
                                self._predecir_actual(image_path, nuevo_job_id)
                            else:
                                print(f"Usuario cambió de imagen, cancelando análisis")
                        else:
                            print(f"Lista vacía, cancelando análisis")
                    threading.Thread(target=analizarImagenEditada, daemon=True).start()
                else:
                    # Si no hay IA, limpiar UI
                    self.sugerenciaIA.set("IA Inactiva" if not self.ia else "-")
                    
            except Exception as e:
                print(f"Error en callback de editor: {e}")
                import traceback
                traceback.print_exc()
        try:
            EditorImagen(self.ventana, image_path, alTerminar, modo_video=False)
        except Exception as e:
            print(f"Error al abrir editor: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", f"No se pudo abrir el editor:\n{e}")

    def abrirEditorVideo(self, video_path):
        """Abre el editor de videos con manejo de errores mejorado"""
        
        if not os.path.exists(video_path):
            messagebox.showerror("Errro", f"El archivo no existe:\n{video_path}")
            return
        
        try:
            cap = cv2.VideoCapture(video_path)
            ret, frame = cap.read()
            cap.release()
            
            if not ret: 
                messagebox.showerror("Error", 
                    "No se pudo leer el video.\n\n"
                    "Posibles causas:\n"
                    "• Codec no compatible\n"
                    "• Archivo corrupto\n"
                    "• Archivo aún descargándose de iCloud")
                return
            
            temp_ref = f"temp_ref_{uuid.uuid4().hex}.jpg"
            cv2.imwrite(temp_ref, frame)
            self.registrar_archivo_temp(temp_ref)
            
        except Exception as error_inicial:
            messagebox.showerror("Error", 
                f"No se pudo procesar el video:\n{str(error_inicial)}\n\n"
                "Si el archivo está en iCloud, espera a que termine de descargar.")
            return

        def al_recibir_coords(coords):
            self.eliminar_archivo_temp(temp_ref)
            
            if not coords: 
                return
            
            x1, y1, x2, y2 = coords
            
            def procesar():
                popup = None
                try:
                    popup = Toplevel(self.ventana)
                    popup.title("Procesando Video...")
                    popup.geometry("350x120")
                    popup.configure(bg=COLOR_BG)
                    
                    Label(popup, text="Recortando video, espera...", 
                        font=("Arial", 10), bg=COLOR_BG, fg="white").pack(pady=20)
                    
                    dir_name = os.path.dirname(video_path)
                    base_name = os.path.basename(video_path)
                    temp_out = os.path.join(dir_name, f"temp_crop_{base_name}")
                    
                    clip = VideoFileClip(video_path)
                    cropped_clip = clip.cropped(x1=x1, y1=y1, x2=x2, y2=y2)
                    cropped_clip.write_videofile(temp_out, codec="libx264", 
                                                audio_codec="aac", logger=None)
                    clip.close()
                    cropped_clip.close()
                    
                    time.sleep(0.5)
                    shutil.move(temp_out, video_path)
                    
                    self.ventana.after(0, lambda: messagebox.showinfo(
                        "Éxito", "Video Recortado Correctamente."
                    ))
                    self.ventana.after(0, self.mostrarContenido)
                    
                except Exception as error_proceso:
                    error_msg = str(error_proceso)
                    self.ventana.after(0, lambda msg=error_msg: messagebox.showerror(
                        "Error", f"Fallo al Procesar:\n{msg}"
                    ))
                finally:
                    if popup:
                        self.ventana.after(0, popup.destroy)
            
            threading.Thread(target=procesar, daemon=True).start()

        EditorImagen(self.ventana, temp_ref, al_recibir_coords, modo_video=True)
        
    def es_archivo_icloud_descargado(self, ruta):
        """Verifica si un archivo de iCloud está completamente descargado"""
        if not os.path.exists(ruta):
            return False
        
        # En Windows, iCloud crea archivos .icloud mientras descarga
        directorio = os.path.dirname(ruta)
        nombre = os.path.basename(ruta)
        archivo_icloud = os.path.join(directorio, f".{nombre}.icloud")
        
        if os.path.exists(archivo_icloud):
            return False  # Aún descargándose
        
        # Verificar que el archivo tenga tamaño > 0
        try:
            tamaño = os.path.getsize(ruta)
            return tamaño > 0
        except:
            return False

    def _predecir_actual(self, image_path, job_id):
        if job_id != self.current_job_id: return
        
        if not self.ia: return
        
        # Verificar que el archivo existe
        if not os.path.exists(image_path):
            print(f"Archivo no encontrado para análisis: {image_path}")
            return
        
        lock_adquirido = self.ia_lock.acquire(blocking=False)
        if not lock_adquirido: return
        
        try:
            self.ia_analyzing = True
            img_para_analisis = image_path
            temp_frame_path = None
            es_video = False

            estension = os.path.splitext(image_path)[1].lower()
            
            if estension in self.videoValido:
                try:
                    cap = cv2.VideoCapture(image_path)
                    length = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    if length > 10: 
                        cap.set(cv2.CAP_PROP_POS_FRAMES, int(length * 0.15))
                    ret, frame = cap.read()
                    cap.release()
                    
                    if ret:
                        temp_frame_path = f"temp_frame_{uuid.uuid4().hex}.jpg"
                        cv2.imwrite(temp_frame_path, frame)
                        self.registrar_archivo_temp(temp_frame_path)
                        img_para_analisis = temp_frame_path
                        es_video = True
                    else: 
                        return
                except Exception as e:
                    print(f"Error al extraer frame de video: {e}")
                    return

            if job_id != self.current_job_id: 
                if temp_frame_path: self.eliminar_archivo_temp(temp_frame_path)
                return

            # Intentar analizar con reintentos si el archivo está bloqueado
            res = None
            max_intentos = 3
            
            for intento in range(max_intentos):
                # Verificar job_id en cada intento
                if job_id != self.current_job_id:
                    if temp_frame_path:
                        self.eliminar_archivo_temp(temp_frame_path)
                    return
                
                try:
                    if not os.path.exists(img_para_analisis): break
                    
                    try:
                        res = self.ia.sugerirPersona(img_para_analisis)
                        break  # Éxito
                    except Exception as e:
                        # Si es error de TensorFlow/Retval, reintentar
                        if "Retval" in str(e) or "INTERNAL" in str(e):
                            print(f"Error de TensorFlow, reintentando ({intento+1}/{max_intentos})...")
                            time.sleep(0.5)
                            continue
                        else: raise  # Re-lanzar otros errores
                    
                except (PermissionError, IOError) as e:
                    if intento < max_intentos - 1:
                        print(f"Archivo en uso, reintentando análisis ({intento+1}/{max_intentos})...")
                        time.sleep(0.5)
                    else:
                        print(f"No se pudo analizar después de {max_intentos} intentos")
                        res = "Error: Archivo en uso"
                except Exception as e:
                    print(f"Error en análisis de IA: {e}")
                    res = "Error en análisis"
                    break
            
            # Limpiar archivo temporal
            if temp_frame_path:
                self.eliminar_archivo_temp(temp_frame_path)

            # Verificar una última vez antes de actualizar UI
            if job_id != self.current_job_id:
                print(f"Análisis completado pero obsoleto (job {job_id})")
                return

            if res:
                def update_ui_ia():
                    if "Desconocido" in res or "No detecto" in res or "Error" in res:
                        self.card_ia.config(bg="#202225")
                        self.btn_accion_ia.pack_forget()
                        self.ventana.unbind('<i>')
                        self.ventana.unbind('<I>')
                    else:
                        nombre_carpeta = res.split(" (")[0]
                        if nombre_carpeta in self.carpetasDestino:
                            self.botonRecalcular.pack(fill='x', pady=5)

                            self.btn_accion_ia.config(
                                text=f"Mover a: {nombre_carpeta} (I)",
                                command=lambda: self.clasificar(nombre_carpeta)
                            )
                            self.btn_accion_ia.pack(fill='x', pady=5)

                            def aceptar_sugerencia_ia(event=None):
                                if event and event.widget.winfo_class() in ('Entry', 'Text'): return
                                # Medida de seguridad: Validar que el usuario no haya cambiado de imagen
                                if job_id == self.current_job_id:
                                    self.clasificar(nombre_carpeta)
                                    # Desvincular inmediatamente después de mover
                                    self.ventana.unbind('<i>')
                                    self.ventana.unbind('<I>')

                            self.ventana.bind('<i>', aceptar_sugerencia_ia)
                            self.ventana.bind('<I>', aceptar_sugerencia_ia)

                    self.sugerenciaIA.set(res)
                
                self.ventana.after(0, update_ui_ia)
        finally:
            # Liberar el Lock
            self.ia_analyzing = False
            self.ia_lock.release()
            
            if job_id != self.current_job_id and res is None:
                def limpiarUI():
                    if self.sugerenciaIA.get() == "Analizando...": self.sugerenciaIA.set("-")
                self.ventana.after(0, limpiarUI)

    def siguienteElemento(self):
        if self.lista:
            self.indiceActual = (self.indiceActual + 1) % len(self.lista)
            self.mostrarContenido()

    def anteriorElemento(self):
        if self.lista:
            self.indiceActual = (self.indiceActual - 1) % len(self.lista)
            self.mostrarContenido()

    def eliminarArchivoActual(self):
        if not self.lista:
            return

        archivoActual = self.lista[self.indiceActual]
        nombreArchivo = os.path.basename(archivoActual)

        confirmacion = messagebox.askyesno(
            "Confirmar Eliminación",
            f"¿Estás seguro de que deseas eliminar permanentemente este archivo del disco?\n\n{nombreArchivo}"
        )

        if confirmacion:
            try:
                # Si el archivo es un video y se está reproduciendo, forzamos su cierre
                # para que el sistema operativo libere el archivo y nos permita borrarlo.
                if hasattr(self, 'video_activo') and self.video_activo:
                    try:
                        self.cerrarVideoCompletamente()
                    except:
                        pass

                # Eliminación permanente del sistema
                os.remove(archivoActual)

                # Sacamos el archivo de nuestra lista en memoria
                self.lista.pop(self.indiceActual)

                # Refrescamos la vista
                if self.lista:
                    self.indiceActual %= len(self.lista)
                    self.mostrarContenido()
                else:
                    # Si borramos el último archivo disponible
                    self.etiquetaElemento.config(image="", text="No hay más archivos.", compound="none")
                    self.lbl_contador.config(text="0 / 0")
                    self.lbl_nombre_archivo.config(text="...")
                    self.btn_accion_ia.pack_forget()
                    self.sugerenciaIA.set("-")

            except Exception as errorEliminacion:
                messagebox.showerror(
                    "Error de Sistema",
                    f"No se pudo eliminar el archivo. Puede que esté abierto en otro programa:\n\n{errorEliminacion}"
                )

    def clasificar(self, carpeta):
        if not self.lista: return
        contenido = self.lista[self.indiceActual]
        nombre_archivo = os.path.basename(contenido)
        carpeta_origen = os.path.dirname(contenido)
        destino = os.path.join(self.carpetasDestino[carpeta], nombre_archivo)
        
        # Detectar si es un video
        es_video = contenido.lower().endswith(self.videoValido)
        
        # Si es video y está reproduciéndose, cerrarlo COMPLETAMENTE
        if es_video:
            # Verificar si es el video actual reproduciéndose
            video_reproduciendose = False
            
            if hasattr(self, 'ruta_video_actual') and self.ruta_video_actual == contenido:
                if hasattr(self, 'popup_video_actual') and self.popup_video_actual:
                    try:
                        if self.popup_video_actual.winfo_exists():
                            video_reproduciendose = True
                    except:
                        pass
            
            if video_reproduciendose:
                respuesta = messagebox.askyesno(
                    "Video en reproducción",
                    "El video está reproduciéndose.\n\n"
                    "Para moverlo, se cerrará el reproductor y se esperará "
                    "a que el sistema libere el archivo (puede tardar 1-2 segundos).\n\n"
                    "¿Continuar?",
                    icon='question'
                )
                if not respuesta: return
                
                self.cerrarVideoCompletamente()
                
                # Dar MUCHO más tiempo para que Windows libere el archivo
                time.sleep(1.5)
        
        # Cancelar cualquier análisis de IA en curso
        self.current_job_id += 1
        time.sleep(0.1)
        
        try:
            if not os.path.exists(contenido):
                messagebox.showerror("Error", f"El archivo ya no existe:\n{nombre_archivo}")
                return
            
            # Para videos, intentos más agresivos
            intentos = 0
            max_intentos = 15 if es_video else 5
            delay_base = 0.8 if es_video else 0.3
            
            while intentos < max_intentos:
                try:
                    with open(contenido, 'rb') as test_file: pass
                    break
                except (PermissionError, IOError) as e:
                    intentos += 1
                    delay = delay_base * (1 + intentos * 0.1)  # Delay creciente
                    
                    if intentos < max_intentos:
                        time.sleep(delay)
                    else:
                        respuesta = messagebox.askyesnocancel(
                            "Archivo bloqueado",
                            f"El archivo '{nombre_archivo}' sigue bloqueado después de {max_intentos} intentos.\n\n"
                            "Posibles causas:\n"
                            "• El sistema operativo aún no lo liberó completamente\n"
                            "• Otra aplicación lo tiene abierto\n\n"
                            "¿Deseas?\n"
                            "• SÍ: Esperar 3 segundos más y reintentar\n"
                            "• NO: Cancelar el movimiento\n"
                            "• CANCELAR: Volver sin hacer nada",
                            icon='warning'
                        )
                        
                        if respuesta is None:
                            return
                        elif respuesta:
                            time.sleep(3)
                            intentos = 0
                            continue
                        else:
                            raise Exception(
                                f"No se pudo acceder al archivo después de múltiples intentos.\n"
                                "Intenta cerrar todas las aplicaciones y esperar unos segundos."
                            )
            
            # Resto del código de clasificar() igual...
            self.historial_movimientos.append({
                'origen': carpeta_origen,
                'destino': destino,
                'nombre': nombre_archivo,
                'carpeta_nombre': carpeta,
                'indice_original': self.indiceActual
            })
            
            if len(self.historial_movimientos) > self.MAX_HISTORIAL:
                self.historial_movimientos.pop(0)
            
            shutil.move(contenido, destino)

            # Aprendizaje Activo
            extension = os.path.splitext(contenido)[1].lower()
            if hasattr(self, 'ia') and self.ia and extension in self.imagenValida:
                # Usar un hilo secundario para evitar que la interfaz se congele
                threading.Thread(
                    target=self.ia.agregarImagenReferencia,
                    args=(carpeta, destino),
                    daemon=True
                ).start()
            
            self.lista.pop(self.indiceActual)
            self.btn_deshacer.config(state='normal', bg="#ed4245")
            
            if hasattr(self, 'lbl_historial'):
                self.lbl_historial.config(text=f"{len(self.historial_movimientos)} movimientos")
            
            if self.lista:
                self.indiceActual %= len(self.lista)
                self.mostrarContenido()
            else:
                self.etiquetaElemento.config(image="", text="¡Carpeta terminada!")
                self.lbl_contador.config(text="0 / 0")
                self.lbl_nombre_archivo.config(text="...")
                self.sugerenciaIA.set("-")
                self.btn_accion_ia.pack_forget()
        
        except Exception as e:
            if self.historial_movimientos and self.historial_movimientos[-1]['nombre'] == nombre_archivo:
                self.historial_movimientos.pop()
            
            print(f"❌ Error al mover archivo: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror('Error', f'Error al mover:\n{str(e)}')

    def nuevaCarpetaPopup(self):
        if not self.carpetaDestino:
            messagebox.showwarning("Atención", "Selecciona primero la carpeta de destino.")
            return
        top = Toplevel(self.ventana)
        top.title("Nueva Carpeta")
        top.bind('<Escape>', lambda e: top.destroy())
        w_pop, h_pop = 300, 150
        x = self.ventana.winfo_screenwidth() // 2 - w_pop // 2
        y = self.ventana.winfo_screenheight() // 2 - h_pop // 2
        top.geometry(f"{w_pop}x{h_pop}+{x}+{y}")
        top.configure(bg=COLOR_BG)
        Label(top, text="Nombre de la carpeta:", bg=COLOR_BG, fg="white").pack(pady=10)
        entry = Entry(top); entry.pack(pady=5); entry.focus()
        def confirmar(event = None):
            nombre = entry.get()
            if nombre:
                path = os.path.join(self.carpetaDestino, nombre)
                try:
                    os.makedirs(path, exist_ok=True)
                    self.carpetasDestino[nombre] = path
                    self.actualizarBotones()
                    top.destroy()
                except Exception as e: messagebox.showerror("Error", str(e))
        top.bind('<Return>', confirmar)
        Button(top, text="Crear", command=confirmar, bg=COLOR_SUCCESS, fg="white", bd=0, padx=10, pady=5).pack(pady=10)

    def abrir_menu_herramientas(self):
        top = Toplevel(self.ventana)
        top.title("Herramientas Avanzadas")
        top.bind('<Escape>', lambda e: top.destroy())
        w_pop, h_pop = 450, 500
        x = self.ventana.winfo_screenwidth() // 2 - w_pop // 2
        y = self.ventana.winfo_screenheight() // 2 - h_pop // 2
        top.geometry(f"{w_pop}x{h_pop}+{x}+{y}")
        top.configure(bg=COLOR_BG)
        lbl_status = Label(top, text="Esperando...", bg=COLOR_BG, fg="gray"); lbl_status.pack(side="bottom", pady=5)
        pb_renombrar = ttk.Progressbar(top, orient="horizontal", mode="determinate", length=400); pb_renombrar.pack(side="bottom", pady=5, padx=20)
        def update_ui_safe(current, total, msg):
            pb_renombrar["maximum"] = total; pb_renombrar["value"] = current
            lbl_status.config(text=f"{msg} ({int(current/total*100)}%)" if total > 0 else msg)
        def progress_adapter(current, total, msg=""): top.after(0, lambda: update_ui_safe(current, total, msg))
        self.renamer.progress_callback = progress_adapter
        def run_threaded(rutas):
            if not isinstance(rutas, list): rutas = [rutas]
            if messagebox.askyesno("Confirmar", "El proceso iniciará ahora."):
                pb_renombrar["value"] = 0
                def worker():
                    for path in rutas: self.renamer.procesar_carpeta(path)
                    top.after(0, lambda: messagebox.showinfo("Listo", "Proceso finalizado"))
                    top.after(0, lambda: [self.cargarElementos(), self.actualizarBotones(), top.destroy()])
                threading.Thread(target=worker, daemon=True).start()

        Label(top, text="Limpieza y Renombrado", bg=COLOR_BG, fg="white", font=FONT_BOLD).pack(pady=10)
        if self.carpetaOrigen: Button(top, text="Limpiar Carpeta Origen (Actual)", command=lambda: run_threaded(self.carpetaOrigen), bg=COLOR_SIDEBAR, fg="white", bd=0, pady=8, width=40).pack(pady=5)
        if self.carpetaDestino:
            rutas_destino = [os.path.join(self.carpetaDestino, d) for d in os.listdir(self.carpetaDestino) if os.path.isdir(os.path.join(self.carpetaDestino, d))]
            Button(top, text="Limpiar TODAS las Subcarpetas Destino", command=lambda: run_threaded(rutas_destino), bg=COLOR_WARNING, fg="white", bd=0, pady=8, width=40).pack(pady=5)
            Label(top, text="--- O selecciona una específica ---", bg=COLOR_BG, fg=COLOR_TEXT_SEC).pack(pady=(15, 5))
            frame_list = Frame(top, bg=COLOR_BG); frame_list.pack(fill='both', expand=True, padx=20, pady=5)
            scrollbar = Scrollbar(frame_list, orient="vertical"); listbox = Listbox(frame_list, yscrollcommand=scrollbar.set, bg=COLOR_SIDEBAR, fg="white", selectbackground=COLOR_ACCENT, bd=0, highlightthickness=0)
            scrollbar.config(command=listbox.yview); listbox.pack(side="left", fill="both", expand=True); scrollbar.pack(side="right", fill="y")
            for carpeta in sorted(self.carpetasDestino.keys()): listbox.insert(END, carpeta)
            def procesar_seleccion():
                sel = listbox.curselection()
                if sel: run_threaded(self.carpetasDestino[listbox.get(sel[0])])
                else: messagebox.showwarning("Atención", "Selecciona una carpeta de la lista")
            Button(top, text="Procesar Selección", command=procesar_seleccion, bg=COLOR_ACCENT, fg="white", bd=0, pady=8, width=40).pack(pady=10)
            
    def deshacer_ultimo_movimiento(self):
        """Revierte el último movimiento realizado"""
        if not self.historial_movimientos:
            messagebox.showinfo("Info", "No hay movimientos para deshacer")
            return
        
        ultimo = self.historial_movimientos.pop()
        self.lbl_historial.config(text=f"{(len(self.historial_movimientos))} movimientos")
        
        archivo_actual = ultimo['destino']
        ruta_origen = os.path.join(ultimo['origen'], ultimo['nombre'])
        
        try:
            # Verificar que el archivo existe en destino
            if not os.path.exists(archivo_actual):
                messagebox.showerror("Error", f"El archivo '{ultimo['nombre']} ya no existe en la carpeta destino\n" "No se puede deshacer")
                return
            
            # Verificar que no haya conflicto en origen
            if os.path.exists(ruta_origen):
                respuesta = messagebox.askyesno(
                    "Conflicto",
                    f"Ya existe un archivo con ese nombre en la carpeta origen.\n"
                    f"¿Sobrescribir?",
                    icon='warning'
                )
                
                if not respuesta:
                    # Restaurar al historial si cancela
                    self.historial_movimientos.append(ultimo)
                    return
                
            # Mover de vuelta
            shutil.move(archivo_actual, ruta_origen)
            
            # Recargar la carpeta origen
            if self.carpetaOrigen == ultimo['origen']:
                self.cargarElementos()
                
                # Intentar volver al archivo restaurado
                try:
                    indice_restaurado = self.lista.index(ruta_origen)
                    self.indiceActual = indice_restaurado
                except ValueError:
                    self.indiceActual = 0
                    
                self.mostrarContenido()
                
            # Mostrar confirmación
            self.ventana.after(100, lambda: messagebox.showinfo("Deshecho", f"'{ultimo['nombre']}' restaurado a su ubicación original"))
            
            # Deshabilitar botón si no hay más historial
            if not self.historial_movimientos: self.btn_deshacer.config(state='disabled', bg='#4f545c')
            
        except Exception as e:
            # Restaurar al historial si falla
            self.historial_movimientos.append(ultimo)
            messagebox.showerror('Error', f"No se pudo deshacer: {e}")

    def reproducirVideo(self, rutaVideo):
        # Si ya hay un video reproduciéndose, cerrarlo primero
        if hasattr(self, 'popup_video_actual') and self.popup_video_actual:
            try:
                if self.popup_video_actual.winfo_exists():
                    self.cerrarVideoCompletamente()
                    time.sleep(0.5)
            except:
                pass

        popupVideo = Toplevel(self.ventana)
        self.popup_video_actual = popupVideo
        self.ruta_video_actual = rutaVideo  # Guardar ruta

        popupVideo.title('Reproductor')
        popupVideo.bind('<Escape>', lambda e: self.cerrarVideoCompletamente())
        popupVideo.configure(bg="black")

        w_pop, h_pop = 800, 1000
        x = self.ventana.winfo_screenwidth() // 2 - w_pop // 2
        y = self.ventana.winfo_screenheight() // 2 - h_pop // 2
        popupVideo.geometry(f'{w_pop}x{h_pop}+{x}+{y}')
        popupVideo.focus_set()
        
        etiquetaVideo = Label(popupVideo, bg="black")
        etiquetaVideo.pack(fill='both', expand=True)
        
        self.video_activo = True
        self.detenerAudio = threading.Event()
        self.audio_filename = os.path.join(tempfile.gettempdir(), f"temp_audio_{uuid.uuid4().hex}.mp3")
        self.moviepy_clip = None  # Guardar referencia

        def reproducirAudio():
            try:
                # Guardar referencia global para poder cerrarla después
                self.moviepy_clip = VideoFileClip(rutaVideo)
                
                if self.moviepy_clip.audio:
                    self.moviepy_clip.audio.write_audiofile(self.audio_filename, logger=None)
                    
                    # Cerrar clip INMEDIATAMENTE después de extraer audio
                    self.moviepy_clip.close()
                    self.moviepy_clip = None
                    
                    # Ahora reproducir el audio del archivo temporal
                    pygame.mixer.music.load(self.audio_filename)
                    pygame.mixer.music.play()
                    
                    while pygame.mixer.music.get_busy():
                        if self.detenerAudio.is_set():
                            pygame.mixer.music.stop()
                            break
                        time.sleep(0.1)
            except Exception as e:
                print(f"⚠️ Error en audio: {e}")
            finally:
                # Asegurar que el clip esté cerrado
                if self.moviepy_clip:
                    try: 
                        self.moviepy_clip.close()
                        self.moviepy_clip = None
                    except: 
                        pass

        # VideoCapture para los frames
        self.cap_video_actual = cv2.VideoCapture(rutaVideo)
        cap = self.cap_video_actual
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        speed = 0.8
        if fps == 0: 
            fps = 30
        elif fps > 50: 
            speed = 0.5

        def reproducir():
            if not self.video_activo: 
                return
            if not cap or not cap.isOpened(): 
                return

            ret, frame = cap.read()
            if not ret:
                if self.var_autoclose.get():
                    self.cerrarVideoCompletamente()
                else:
                    if cap:
                        cap.release()
                        self.cap_video_actual = None
                return
            
            try:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame = cv2.resize(frame, (w_pop, h_pop)) 
                imagen = Image.fromarray(frame)
                foto = ImageTk.PhotoImage(imagen)
                if etiquetaVideo.winfo_exists():
                    etiquetaVideo.config(image=foto)
                    etiquetaVideo.image = foto
            except: 
                pass

            delay = int(1000/fps * speed)
            if delay < 1: 
                delay = 1
            
            if self.video_activo and popupVideo.winfo_exists():
                popupVideo.after(delay, reproducir)
            
        reproducir()
        threading.Thread(target=reproducirAudio, daemon=True).start()
        
        popupVideo.protocol("WM_DELETE_WINDOW", self.cerrarVideoCompletamente)

    def cerrarVideoCompletamente(self):
        """Cierra TODOS los recursos del video para liberar el archivo"""
        if not hasattr(self, 'video_activo'):
            return
        
        if not self.video_activo:
            return
        
        self.video_activo = False
        
        # 1. Detener audio inmediatamente
        if hasattr(self, 'detenerAudio'):
            self.detenerAudio.set()
        
        # 2. Cerrar MoviePy clip si existe
        if hasattr(self, 'moviepy_clip') and self.moviepy_clip:
            try:
                self.moviepy_clip.close()
                del self.moviepy_clip
                self.moviepy_clip = None
            except Exception as e:
                print(f"⚠️ Error cerrando MoviePy: {e}")
        
        # 3. Liberar VideoCapture
        if hasattr(self, 'cap_video_actual') and self.cap_video_actual:
            try:
                self.cap_video_actual.release()
                self.cap_video_actual = None
            except Exception as e:
                print(f"⚠️ Error liberando VideoCapture: {e}")
        
        # 4. Detener y liberar pygame
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
        except:
            pass
        
        # 5. Destruir ventana
        if hasattr(self, 'popup_video_actual') and self.popup_video_actual:
            try:
                if self.popup_video_actual.winfo_exists():
                    self.popup_video_actual.destroy()
                self.popup_video_actual = None
            except:
                pass
        
        # 6. Forzar garbage collection
        import gc
        gc.collect()
        
        # 7. Esperar a que el sistema operativo libere el archivo
        time.sleep(1.0)  # Espera más larga
        
        # 8. Limpiar archivo de audio en background
        if hasattr(self, 'audio_filename'):
            audio_file = self.audio_filename
            def limpiar_audio():
                for intento in range(15):  # Más intentos
                    try:
                        if os.path.exists(audio_file):
                            os.remove(audio_file)
                        break
                    except:
                        time.sleep(0.3)
            
            threading.Thread(target=limpiar_audio, daemon=True).start()
        
    def limpiar_archivos_temp_antiguos(self):
        """Limpia archivos temporales de ejecuciones anteriores"""
        try:
            directorio_actual = os.getcwd()
            archivos_eliminados = 0
            
            # Buscar archivos temp_frame_*.jpg y temp_ref_*.jpg
            for archivo in os.listdir(directorio_actual):
                if (archivo.startswith("temp_frame_") and archivo.endswith(".jpg")) or \
                (archivo.startswith("temp_ref_") and archivo.endswith(".jpg")):
                    try:
                        ruta_completa = os.path.join(directorio_actual, archivo)
                        os.remove(ruta_completa)
                        archivos_eliminados += 1
                    except Exception as e:
                        print(f"⚠️ No se pudo eliminar {archivo}: {e}")
        except Exception as e:
            print(f"⚠️ Error en limpieza inicial: {e}")
            
    def registrar_archivo_temp(self, ruta):
        """Registra un archivo temporal para limpieza posterior"""
        try:
            if not hasattr(self, 'temp_cleanup_lock'):
                self.temp_cleanup_lock = threading.Lock()
            if not hasattr(self, 'arhivos_temp_activos'):
                self.archivos_temp_activos = set()
                
            with self.temp_cleanup_lock:
                self.archivos_temp_activos.add(ruta)
        except Exception as e:
            print(f"Error al registrar temp {e}")

    def eliminar_archivo_temp(self, ruta):
        """Elimina un archivo temporal y lo quita del registro"""
        try:
            # Crear atributos si no existen
            if not hasattr(self, 'temp_cleanup_lock'):
                self.temp_cleanup_lock = threading.Lock()
            if not hasattr(self, 'archivos_temp_activos'):
                self.archivos_temp_activos = set()
            
            # Eliminar archivo
            if os.path.exists(ruta):
                try:
                    os.remove(ruta)
                except Exception as e:
                    print(f"⚠️ No se pudo eliminar {ruta}: {e}")
            
            # Remover del set
            with self.temp_cleanup_lock:
                self.archivos_temp_activos.discard(ruta)
        except Exception as e:
            print(f"⚠️ Error al eliminar temp: {e}")

    def limpiar_todos_los_temp(self):
        """Limpia todos los archivos temporales registrados"""
        try:
            if not hasattr(self, 'temp_cleanup_lock'):
                self.temp_cleanup_lock = threading.Lock()
            if not hasattr(self, 'archivos_temp_activos'):
                self.archivos_temp_activos = set()
            
            with self.temp_cleanup_lock:
                archivos_a_limpiar = list(self.archivos_temp_activos)
            
            for ruta in archivos_a_limpiar:
                if os.path.exists(ruta):
                    try:
                        os.remove(ruta)
                    except Exception as e:
                        print(f"⚠️ No se pudo eliminar {ruta}: {e}")
            
            if hasattr(self, 'archivos_temp_activos'):
                self.archivos_temp_activos.clear()
                
        except Exception as e:
            print(f"⚠️ Error en limpieza final: {e}")
            
    def cerrar_aplicacion(self):
        """Limpia recursos y cierra la aplicación"""
        try:
            # Detener video si está activo
            if hasattr(self, 'video_activo'):
                self.video_activo = False
            
            # Limpiar todos los archivos temporales
            self.limpiar_todos_los_temp()
            
            # Cerrar pygame si está activo
            try: pygame.mixer.quit()
            except: pass
        except Exception as e:
            print(f"⚠️ Error al cerrar: {e}")
        finally:
            try: self.ventana.destroy()
            except: pass

if __name__ == "__main__":
    Clasificador()