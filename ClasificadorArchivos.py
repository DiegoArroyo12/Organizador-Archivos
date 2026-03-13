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
        self.imagenValida = ('.png', '.jpg', '.jpeg', '.bmp', '.gif')
        self.videoValido = ('.mp4', '.avi', '.mov', '.mkv')
        
        self.setup_ui()
        self.ventana.mainloop()

    def setup_ui(self):
        self.panel_izquierdo = Frame(self.ventana, bg=COLOR_SIDEBAR, width=250)
        self.panel_izquierdo.pack(side='left', fill='y')
        self.panel_izquierdo.pack_propagate(False)

        Label(self.panel_izquierdo, text="CONFIGURACIÓN", bg=COLOR_SIDEBAR, fg=COLOR_TEXT_SEC, font=("Arial", 8, "bold")).pack(pady=(20, 5), anchor="w", padx=15)
        
        self.btn_crear_moderno(self.panel_izquierdo, "Origen", self.seleccionarCarpeta, COLOR_ACCENT, ruta_imagen="iconos/carpetaIcono.png")
        self.btn_crear_moderno(self.panel_izquierdo, "Destino (IA)", self.carpetaPrincipalDestino, COLOR_ACCENT, ruta_imagen="iconos/carpetaIcono.png")
        
        self.check_autoclose = Checkbutton(self.panel_izquierdo, text="Auto-cerrar Videos", variable=self.var_autoclose,
                                           bg=COLOR_SIDEBAR, fg="white", selectcolor=COLOR_BG, activebackground=COLOR_SIDEBAR, activeforeground="white",
                                           font=("Segoe UI", 9), bd=0, highlightthickness=0)
        self.check_autoclose.pack(fill='x', padx=15, pady=(5, 10))
        
        Frame(self.panel_izquierdo, bg="#40444b", height=1).pack(fill='x', padx=15, pady=15)
        
        Label(self.panel_izquierdo, text="ACCIONES", bg=COLOR_SIDEBAR, fg=COLOR_TEXT_SEC, font=("Arial", 8, "bold")).pack(pady=(5, 5), anchor="w", padx=15)
        self.btn_crear_moderno(self.panel_izquierdo, "Nueva Carpeta", self.nuevaCarpetaPopup, "#4f545c", ruta_imagen="iconos/agregarIcono.png")
        self.btn_crear_moderno(self.panel_izquierdo, "Herramientas", self.abrir_menu_herramientas, COLOR_WARNING, ruta_imagen="iconos/herramientasIcono.png")

        self.panel_derecho = Frame(self.ventana, bg=COLOR_SIDEBAR, width=280)
        self.panel_derecho.pack(side='right', fill='y')
        self.panel_derecho.pack_propagate(False)

        self.card_ia = Frame(self.panel_derecho, bg="#202225", padx=10, pady=10)
        self.card_ia.pack(fill='x', padx=10, pady=20)
        
        Label(self.card_ia, text="🤖 MOTOR DE IA", bg="#202225", fg=COLOR_TEXT_SEC, font=("Arial", 8, "bold")).pack(anchor="w")
        
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
        
        #  Campo de búsqueda/filtro
        Label(self.panel_derecho, text="CLASIFICAR EN:", bg=COLOR_SIDEBAR, fg=COLOR_TEXT_SEC, 
            font=("Arial", 8, "bold")).pack(pady=(10, 5), anchor="w", padx=15)

        # Frame del filtro
        self.frame_filtro = Frame(self.panel_derecho, bg=COLOR_SIDEBAR)
        self.frame_filtro.pack(fill='x', padx=15, pady=(0, 10))

        # Variable para el texto del filtro
        self.filtro_texto = StringVar()
        self.filtro_texto.trace('w', lambda *args: self.aplicar_filtro())

        # Entry de búsqueda
        self.entry_filtro = Entry(self.frame_filtro, textvariable=self.filtro_texto,
                                bg="#40444b", fg="white", font=("Segoe UI", 10),
                                bd=0, insertbackground="white", relief="flat")
        self.entry_filtro.pack(side='left', fill='x', expand=True, ipady=5)

        # Placeholder text
        self.entry_filtro.insert(0, "🔍 Buscar carpeta...")
        self.entry_filtro.config(fg="#8e8e93")

        # Eventos para el placeholder
        def on_entry_click(event):
            if self.entry_filtro.get() == "🔍 Buscar carpeta...":
                self.entry_filtro.delete(0, "end")
                self.entry_filtro.config(fg="white")

        def on_focusout(event):
            if self.entry_filtro.get() == "":
                self.entry_filtro.insert(0, "🔍 Buscar carpeta...")
                self.entry_filtro.config(fg="#8e8e93")

        self.entry_filtro.bind('<FocusIn>', on_entry_click)
        self.entry_filtro.bind('<FocusOut>', on_focusout)

        # Botón para limpiar filtro
        self.btn_limpiar_filtro = Button(self.frame_filtro, text="✕",
                                        command=self.limpiar_filtro,
                                        bg="#40444b", fg="#8e8e93",
                                        font=("Segoe UI", 11, "bold"),
                                        bd=0, padx=8, cursor=self.cursor,
                                        relief="flat")
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
        
        self.etiquetaElemento = Label(self.frame_imagen, bg="#000000", text="Sin imagen cargada", fg="#555")
        self.etiquetaElemento.pack(fill='both', expand=True)

        self.frame_nav = Frame(self.panel_central, bg=COLOR_BG, pady=20, height=80)
        self.frame_nav.pack(side='bottom', fill='x')
        self.frame_nav.pack_propagate(False)
        
        self.btn_crear_nav(self.frame_nav, "◀ Anterior", self.anteriorElemento, side=LEFT)
        self.btn_crear_nav(self.frame_nav, "Siguiente ▶", self.siguienteElemento, side=RIGHT)

        self.frame_info_centro = Frame(self.frame_nav, bg=COLOR_BG)
        self.frame_info_centro.pack(side=LEFT, fill='both', expand=True)
        
        self.lbl_contador = Label(self.frame_info_centro, text="0 / 0", 
                                  bg=COLOR_BG, fg="white", font=("Segoe UI", 18, "bold"))
        self.lbl_contador.pack(side='top', pady=(5, 0))
        
        self.lbl_nombre_archivo = Label(self.frame_info_centro, text="...", 
                                        bg=COLOR_BG, fg=COLOR_TEXT_SEC, font=("Segoe UI", 9))
        self.lbl_nombre_archivo.pack(side='top')

    def btn_crear_moderno(self, parent, text, command, bg_color, ruta_imagen=None):
        btn = Button(parent, text=text, command=command, 
                     bg=bg_color, fg="white", 
                     font=FONT_BOLD, bd=0, padx=20, pady=12, 
                     cursor=self.cursor, activebackground=bg_color, activeforeground="white")
        if ruta_imagen and os.path.exists(ruta_imagen):
            try:
                img = Image.open(ruta_imagen).resize((24, 24), Image.Resampling.LANCZOS)
                foto = ImageTk.PhotoImage(img)
                btn.config(image=foto, compound="left", padx=15)
                btn.image = foto 
            except: pass
        btn.pack(fill='x', padx=15, pady=5)
        def on_enter(e): btn['bg'] = self.adjust_color_lightness(bg_color, 1.2)
        def on_leave(e): btn['bg'] = bg_color
        btn.bind("<Enter>", on_enter); btn.bind("<Leave>", on_leave)
        return btn

    def btn_crear_nav(self, parent, text, command, side):
        btn = Button(parent, text=text, command=command, bg="#40444b", fg="white", font=("Segoe UI", 12), bd=0, padx=30, pady=10, cursor=self.cursor)
        btn.pack(side=side, padx=20)
        def on_enter(e): btn['bg'] = "#585d66"
        def on_leave(e): btn['bg'] = "#40444b"
        btn.bind("<Enter>", on_enter); btn.bind("<Leave>", on_leave)

    def btn_crear_categoria(self, parent, text, command):
        btn = Button(parent, text=f"📁 {text}", command=command, bg="#36393f", fg="#dcddde", font=("Segoe UI", 9), bd=0, anchor="w", padx=10, pady=8, cursor=self.cursor)
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
        """Actualiza la lista de botones"""
        self.aplicar_filtro()
        for widget in self.scrollFrame.winfo_children(): widget.destroy()
        if not self.carpetasDestino:
            Label(self.scrollFrame, text="No hay subcarpetas", bg=COLOR_SIDEBAR, fg="gray").pack(pady=10)
            return
        self._bind_mouse_scroll(self.scrollFrame)
        for carpeta in sorted(self.carpetasDestino.keys()):
            self.btn_crear_categoria(self.scrollFrame, carpeta, lambda c=carpeta: self.clasificar(c))
        self.canvas.config(scrollregion=self.canvas.bbox('all'))

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
        
    def aplicar_filtro(self):
        """Filtra los botones de carpetas según el texto del filtro"""
        texto_busqueda = self.filtro_texto.get().lower()
        
        if texto_busqueda == "🔍 buscar carpeta...":
            texto_busqueda = ""
        
        for widget in self.scrollFrame.winfo_children():
            widget.destroy()
        
        if not self.carpetasDestino:
            Label(self.scrollFrame, text="No hay subcarpetas", 
                bg=COLOR_SIDEBAR, fg="gray").pack(pady=10)
            return
        
        self._bind_mouse_scroll(self.scrollFrame)
        
        carpetas_filtradas = []
        for carpeta in sorted(self.carpetasDestino.keys()):
            if texto_busqueda in carpeta.lower():
                carpetas_filtradas.append(carpeta)
        
        if carpetas_filtradas:
            for carpeta in carpetas_filtradas:
                self.btn_crear_categoria(self.scrollFrame, carpeta, 
                                        lambda c=carpeta: self.clasificar(c))
        else:
            Label(self.scrollFrame, text=f"No se encontró '{texto_busqueda}'", 
                bg=COLOR_SIDEBAR, fg="#faa61a", font=("Segoe UI", 9)).pack(pady=20)
        
        self.canvas.config(scrollregion=self.canvas.bbox('all'))

    def limpiar_filtro(self):
        """Limpia el campo de búsqueda"""
        self.entry_filtro.delete(0, "end")
        self.entry_filtro.insert(0, "🔍 Buscar carpeta...")
        self.entry_filtro.config(fg="#8e8e93")
        self.filtro_texto.set("")
        self.entry_filtro.focus()

    def seleccionarCarpeta(self):
        self.carpetaOrigen = filedialog.askdirectory(title='Seleccione Carpeta Origen')
        self.cargarElementos()
        
    def carpetaPrincipalDestino(self):
        self.carpetaDestino = filedialog.askdirectory(title='Seleccione Carpeta Destino')
        if not self.carpetaDestino: return
        self.barra_carga['value'] = 0
        self.estado_carga_texto.set("Iniciando Motor IA...")
        self.ia = FaceBrain(self.carpetaDestino, log_callback=print, progress_callback=self.actualizar_barra_ia)
        self.ia.cargar_referencias_async()
        self.carpetasDestino = {f: os.path.join(self.carpetaDestino, f) for f in os.listdir(self.carpetaDestino) if os.path.isdir(os.path.join(self.carpetaDestino, f))}
        self.actualizarBotones()
        
    def cargarElementos(self):
        if not self.carpetaOrigen: return
        try:
            self.lista = [os.path.join(self.carpetaOrigen, f) for f in os.listdir(self.carpetaOrigen) if f.lower().endswith(self.imagenValida + self.videoValido)]
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
                img.thumbnail((w_frame, h_frame), Image.Resampling.LANCZOS)
                foto = ImageTk.PhotoImage(img)
                self.etiquetaElemento.config(image=foto, text="")
                self.etiquetaElemento.image = foto
                
                btn_edit = Button(self.frame_imagen, text="✂ Recortar", command=lambda: self.abrirEditor(contenido), bg="#40444b", fg="white", font=FONT_BOLD, bd=0, padx=15, pady=5, cursor=self.cursor)
                btn_edit.place(relx=0.95, rely=0.05, anchor="ne")
            except:
                self.etiquetaElemento.config(image="", text="Error al cargar imagen")
                
        elif ext in self.videoValido:
            cap = cv2.VideoCapture(contenido)
            ret, frame = cap.read()
            cap.release()
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img_pil = Image.fromarray(frame)
                img_pil.thumbnail((w_frame, h_frame))
                foto = ImageTk.PhotoImage(img_pil)
                self.etiquetaElemento.config(image=foto, text="")
                self.etiquetaElemento.image = foto
                
                btn_play = Button(self.frame_imagen, text="▶ REPRODUCIR", command=lambda: self.reproducirVideo(contenido), bg=COLOR_ACCENT, fg="white", font=FONT_BOLD, bd=0, padx=15, pady=5, cursor=self.cursor)
                btn_play.place(relx=0.5, rely=0.9, anchor="center")
                
                btn_crop = Button(self.frame_imagen, text="✂ Recortar Video", command=lambda: self.abrir_editor_video(contenido), bg="#40444b", fg="white", font=FONT_BOLD, bd=0, padx=15, pady=5, cursor=self.cursor)
                btn_crop.place(relx=0.95, rely=0.05, anchor="ne")
            else:
                self.etiquetaElemento.config(text="Video sin vista previa", image="")
        
        self.btn_accion_ia.pack_forget()
        self.card_ia.config(bg="#202225")
        
        if self.ia:
            self.sugerenciaIA.set("Analizando...")
            threading.Thread(target=self._predecir_actual, args=(contenido, job_id), daemon=True).start()
        else:
            self.sugerenciaIA.set("IA Inactiva")

    def abrirEditor(self, image_path):
        def alTerminar(coords=None):
            self.mostrarContenido() 
            if self.ia: threading.Thread(target=self._predecir_actual, args=(image_path, self.current_job_id), daemon=True).start()
        EditorImagen(self.ventana, image_path, alTerminar, modo_video=False)

    def abrir_editor_video(self, video_path):
        try:
            cap = cv2.VideoCapture(video_path)
            ret, frame = cap.read()
            cap.release()
            if not ret: 
                messagebox.showerror("Error", "No se pudo leer el video")
                return
            temp_ref = f"temp_ref_{uuid.uuid4().hex}.jpg"
            cv2.imwrite(temp_ref, frame)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        def al_recibir_coords(coords):
            if os.path.exists(temp_ref):
                try: os.remove(temp_ref)
                except: pass
            if not coords: return
            x1, y1, x2, y2 = coords
            
            def procesar():
                popup = Toplevel(self.ventana)
                popup.title("Procesando Video...")
                popup.geometry("300x100")
                Label(popup, text="Recortando video, espera...", font=("Arial", 10)).pack(pady=20)
                try:
                    dir_name = os.path.dirname(video_path)
                    base_name = os.path.basename(video_path)
                    temp_out = os.path.join(dir_name, f"temp_crop_{base_name}")
                    
                    clip = VideoFileClip(video_path)
                    cropped_clip = clip.cropped(x1=x1, y1=y1, x2=x2, y2=y2)
                    cropped_clip.write_videofile(temp_out, codec="libx264", audio_codec="aac", logger=None)
                    clip.close()
                    cropped_clip.close()
                    time.sleep(0.5) 
                    shutil.move(temp_out, video_path)
                    
                    self.ventana.after(0, lambda: messagebox.showinfo("Éxito", "Video recortado."))
                    self.ventana.after(0, self.mostrarContenido)
                except Exception as e:
                    self.ventana.after(0, lambda: messagebox.showerror("Error", f"Fallo al procesar: {e}"))
                finally:
                    self.ventana.after(0, popup.destroy)
            threading.Thread(target=procesar, daemon=True).start()

        EditorImagen(self.ventana, temp_ref, al_recibir_coords, modo_video=True)

    def _predecir_actual(self, image_path, job_id):
        if job_id != self.current_job_id: return
        if not self.ia: return
        
        img_para_analisis = image_path
        es_video = False
        
        if image_path.lower().endswith(self.videoValido):
            try:
                cap = cv2.VideoCapture(image_path)
                length = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                if length > 10: cap.set(cv2.CAP_PROP_POS_FRAMES, int(length * 0.15))
                ret, frame = cap.read()
                cap.release()
                if ret:
                    temp_frame_path = f"temp_frame_{uuid.uuid4().hex}.jpg"
                    cv2.imwrite(temp_frame_path, frame)
                    img_para_analisis = temp_frame_path
                    es_video = True
                else: return
            except: return

        if job_id != self.current_job_id: 
            if es_video and os.path.exists(img_para_analisis):
                try: os.remove(img_para_analisis)
                except: pass
            return

        res = self.ia.sugerir_persona(img_para_analisis)
        
        if es_video and os.path.exists(img_para_analisis):
            try: os.remove(img_para_analisis)
            except: pass

        if job_id != self.current_job_id: return

        def update_ui_ia():
            if "Desconocido" in res or "No detecto" in res:
                self.card_ia.config(bg="#202225")
                self.btn_accion_ia.pack_forget()
            else:
                nombre_carpeta = res.split(" (")[0]
                if nombre_carpeta in self.carpetasDestino:
                    self.btn_accion_ia.config(text=f"Mover a: {nombre_carpeta}", 
                                            command=lambda: self.clasificar(nombre_carpeta))
                    self.btn_accion_ia.pack(fill='x', pady=5)
            self.sugerenciaIA.set(res)
        self.ventana.after(0, update_ui_ia)

    def siguienteElemento(self):
        if self.lista:
            self.indiceActual = (self.indiceActual + 1) % len(self.lista)
            self.mostrarContenido()

    def anteriorElemento(self):
        if self.lista:
            self.indiceActual = (self.indiceActual - 1) % len(self.lista)
            self.mostrarContenido()

    def clasificar(self, carpeta):
        if not self.lista: return
        contenido = self.lista[self.indiceActual]
        destino = os.path.join(self.carpetasDestino[carpeta], os.path.basename(contenido))
        try:
            shutil.move(contenido, destino)
            self.lista.pop(self.indiceActual)
            if self.lista:
                self.indiceActual %= len(self.lista)
                self.mostrarContenido()
            else:
                self.etiquetaElemento.config(image="", text="¡Carpeta terminada! 🎉")
                self.lbl_contador.config(text="0 / 0")
                self.lbl_nombre_archivo.config(text="...")
                self.sugerenciaIA.set("-")
                self.btn_accion_ia.pack_forget()
        except Exception as e:
            messagebox.showerror('Error', f'Error al mover: {e}')

    def nuevaCarpetaPopup(self):
        if not self.carpetaDestino:
            messagebox.showwarning("Atención", "Selecciona primero la carpeta de destino.")
            return
        top = Toplevel(self.ventana)
        top.title("Nueva Carpeta")
        w_pop, h_pop = 300, 150
        x = self.ventana.winfo_screenwidth() // 2 - w_pop // 2
        y = self.ventana.winfo_screenheight() // 2 - h_pop // 2
        top.geometry(f"{w_pop}x{h_pop}+{x}+{y}")
        top.configure(bg=COLOR_BG)
        Label(top, text="Nombre de la carpeta:", bg=COLOR_BG, fg="white").pack(pady=10)
        entry = Entry(top); entry.pack(pady=5); entry.focus()
        def confirmar():
            nombre = entry.get()
            if nombre:
                path = os.path.join(self.carpetaDestino, nombre)
                try:
                    os.makedirs(path, exist_ok=True)
                    self.carpetasDestino[nombre] = path
                    self.actualizarBotones()
                    top.destroy()
                except Exception as e: messagebox.showerror("Error", str(e))
        Button(top, text="Crear", command=confirmar, bg=COLOR_SUCCESS, fg="white", bd=0, padx=10, pady=5).pack(pady=10)

    def abrir_menu_herramientas(self):
        top = Toplevel(self.ventana)
        top.title("Herramientas Avanzadas")
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

    def reproducirVideo(self, rutaVideo):
        if self.popup_video_actual and self.popup_video_actual.winfo_exists():
            self.popup_video_actual.destroy()
            self.video_activo = False
            time.sleep(0.1)

        popupVideo = Toplevel(self.ventana)
        self.popup_video_actual = popupVideo
        
        popupVideo.title('Reproductor')
        popupVideo.configure(bg="black")
        
        w_pop, h_pop = 800, 1000
        x = self.ventana.winfo_screenwidth() // 2 - w_pop // 2
        y = self.ventana.winfo_screenheight() // 2 - h_pop // 2
        popupVideo.geometry(f'{w_pop}x{h_pop}+{x}+{y}')
        
        etiquetaVideo = Label(popupVideo, bg="black")
        etiquetaVideo.pack(fill='both', expand=True)
        
        self.video_activo = True
        self.detenerAudio = threading.Event()
        audio_filename = os.path.join(tempfile.gettempdir(), f"temp_audio_{uuid.uuid4().hex}.mp3")

        def reproducirAudio():
            clip = None
            try:
                clip = VideoFileClip(rutaVideo)
                clip.audio.write_audiofile(audio_filename, logger=None)
                clip.close() 
                
                pygame.mixer.music.load(audio_filename)
                pygame.mixer.music.play()
                
                while pygame.mixer.music.get_busy():
                    if self.detenerAudio.is_set():
                        pygame.mixer.music.stop()
                        break
            except Exception as e:
                # print(f"Info Audio: {e}") # Silenciado para no ensuciar consola
                pass
            finally:
                if 'clip' in locals() and clip: 
                    try: clip.close()
                    except: pass
                if os.path.exists(audio_filename):
                    try: os.remove(audio_filename)
                    except: pass

        cap = cv2.VideoCapture(rutaVideo)
        fps = cap.get(cv2.CAP_PROP_FPS)
        speed = 0.8
        if fps == 0: fps = 30
        elif fps > 50: speed = 0.5

        def reproducir():
            if not self.video_activo: return
            if not cap.isOpened(): return

            ret, frame = cap.read()
            if not ret:
                if self.var_autoclose.get():
                    cerrarPopup()
                else:
                    cap.release()
                return
            
            try:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame = cv2.resize(frame, (w_pop, h_pop)) 
                imagen = Image.fromarray(frame)
                foto = ImageTk.PhotoImage(imagen)
                if etiquetaVideo.winfo_exists():
                    etiquetaVideo.config(image=foto)
                    etiquetaVideo.image = foto
            except: pass

            delay = int(1000/fps * speed)
            if delay < 1: delay = 1
            
            if self.video_activo and popupVideo.winfo_exists():
                popupVideo.after(delay, reproducir)
            
        reproducir()
        threading.Thread(target=reproducirAudio, daemon=True).start()
            
        def cerrarPopup():
            if not self.video_activo: return
            self.video_activo = False
            
            try: popupVideo.destroy()
            except: pass
            
            def limpieza_bg():
                self.detenerAudio.set()
                if cap.isOpened(): cap.release()
                
                try: 
                    pygame.mixer.music.stop()
                    pygame.mixer.music.unload()
                except: pass
                
                for _ in range(5):
                    try:
                        if os.path.exists(audio_filename):
                            os.remove(audio_filename)
                        break
                    except:
                        time.sleep(0.5)
            
            threading.Thread(target=limpieza_bg, daemon=True).start()
        
        popupVideo.protocol("WM_DELETE_WINDOW", cerrarPopup)

if __name__ == "__main__":
    Clasificador()