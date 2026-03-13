import tkinter as tk
from tkinter import Toplevel, Canvas, Button, messagebox, Frame, Label
from PIL import Image, ImageTk
import os

class EditorImagen:
    def __init__(self, master, image_path, callback_guardado, modo_video=False):
        """
        Args:
            master: Ventana padre
            image_path: Ruta de la imagen a editar
            callback_guardado: Función callback
                - Si modo_video=True: callback(coords) donde coords=(x1, y1, x2, y2)
                - Si modo_video=False: callback() después de sobrescribir la imagen
            modo_video: True si se está editando un frame de video para obtener coordenadas
        """
        self.master = master
        self.image_path = image_path
        self.callback_guardado = callback_guardado
        self.modo_video = modo_video
        
        self.window = Toplevel(master)
        self.window.title("✂️ Recortar Imagen" if not modo_video else "✂️ Recortar Video")
        self.window.configure(bg="#1c1c1e")
        
        # Maximizar ventana
        w = master.winfo_screenwidth() - 100
        h = master.winfo_screenheight() - 100
        self.window.geometry(f"{w}x{h}+50+50")
        self.window.transient(master)
        
        # Manejar el cierre de ventana
        self.window.protocol("WM_DELETE_WINDOW", self.cancelar)
        
        # grab_set después de que la ventana esté completamente creada
        self.window.update()
        self.window.grab_set()

        # Cargar imagen original
        try:
            self.original_image = Image.open(image_path)
            self.original_w, self.original_h = self.original_image.size
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar la imagen: {e}")
            self.window.destroy()
            return
        
        # Calcular tamaño para mostrar en pantalla
        self.display_w = w - 100
        self.display_h = h - 200
        
        ratio = min(self.display_w/self.original_w, self.display_h/self.original_h)
        self.new_w = int(self.original_w * ratio)
        self.new_h = int(self.original_h * ratio)
        
        # Imagen redimensionada para vista previa
        self.resized_image = self.original_image.resize(
            (self.new_w, self.new_h), 
            Image.Resampling.LANCZOS
        )
        self.tk_image = ImageTk.PhotoImage(self.resized_image)

        # Header
        header = Frame(self.window, bg="#1c1c1e", height=60)
        header.pack(fill="x", padx=20, pady=(10, 0))
        
        Label(header, text="Arrastra para seleccionar el área a conservar", 
              bg="#1c1c1e", fg="#ffffff", font=("Segoe UI", 12)).pack(side="left", pady=10)
        
        Button(header, text="✕ Cancelar", command=self.cancelar,
               bg="#3a3a3c", fg="white", font=("Segoe UI", 10), 
               padx=15, pady=5, relief="flat", cursor="hand2").pack(side="right", padx=5)

        # Canvas con la imagen
        canvas_frame = Frame(self.window, bg="#000000")
        canvas_frame.pack(pady=10, padx=20)
        
        self.canvas = Canvas(canvas_frame, width=self.new_w, height=self.new_h, 
                            cursor="crosshair", bg="#000000", highlightthickness=0)
        self.canvas.pack()
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_image)

        # Variables de selección
        self.rect_id = None
        self.overlay_ids = []  # Para oscurecer área no seleccionada
        self.handles = []  # Esquinas para redimensionar
        self.start_x = None
        self.start_y = None
        self.end_x = None
        self.end_y = None
        self.dragging = False
        self.resizing = False
        self.resize_handle = None

        # Eventos del Mouse
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

        # Footer con botones
        footer = Frame(self.window, bg="#1c1c1e", height=80)
        footer.pack(fill="x", side="bottom", padx=20, pady=20)
        
        btn_text = "💾 Guardar" if not modo_video else "✓ Aplicar Recorte"
        self.btn_guardar = Button(footer, text=btn_text, command=self.guardar,
                                   bg="#007aff", fg="white", font=("Segoe UI", 12, "bold"),
                                   padx=40, pady=12, relief="flat", cursor="hand2",
                                   state="disabled")
        self.btn_guardar.pack(side="bottom", pady=5)
        
        self.label_info = Label(footer, text="", bg="#1c1c1e", fg="#8e8e93", 
                               font=("Segoe UI", 9))
        self.label_info.pack(side="bottom", pady=5)

    def on_press(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        
        # Verificar si está clickeando en un handle de redimensión
        if self.handles:
            for i, handle in enumerate(self.handles):
                coords = self.canvas.coords(handle)
                if coords and len(coords) == 4:
                    if coords[0] <= x <= coords[2] and coords[1] <= y <= coords[3]:
                        self.resizing = True
                        self.resize_handle = i
                        return
        
        # Verificar si está dentro de la selección existente (para mover)
        if self.rect_id:
            rect_coords = self.canvas.coords(self.rect_id)
            if rect_coords and len(rect_coords) == 4:
                if (rect_coords[0] <= x <= rect_coords[2] and 
                    rect_coords[1] <= y <= rect_coords[3]):
                    self.dragging = True
                    self.drag_start_x = x
                    self.drag_start_y = y
                    self.drag_rect_coords = rect_coords.copy()
                    return
        
        # Nueva selección
        self.start_x = x
        self.start_y = y
        self.limpiar_seleccion()
        self.rect_id = self.canvas.create_rectangle(
            x, y, x, y, 
            outline="#007aff", 
            width=3
        )

    def on_drag(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        
        # Limitar a los bordes del canvas
        x = max(0, min(x, self.new_w))
        y = max(0, min(y, self.new_h))
        
        if self.resizing and self.resize_handle is not None:
            # Redimensionar desde una esquina
            rect_coords = list(self.canvas.coords(self.rect_id))
            if self.resize_handle == 0:  # Superior izquierda
                rect_coords[0] = x
                rect_coords[1] = y
            elif self.resize_handle == 1:  # Superior derecha
                rect_coords[2] = x
                rect_coords[1] = y
            elif self.resize_handle == 2:  # Inferior derecha
                rect_coords[2] = x
                rect_coords[3] = y
            elif self.resize_handle == 3:  # Inferior izquierda
                rect_coords[0] = x
                rect_coords[3] = y
            
            self.canvas.coords(self.rect_id, *rect_coords)
            self.actualizar_overlay()
            self.actualizar_handles()
            self.actualizar_info()
            
        elif self.dragging:
            # Mover toda la selección
            dx = x - self.drag_start_x
            dy = y - self.drag_start_y
            
            new_coords = [
                self.drag_rect_coords[0] + dx,
                self.drag_rect_coords[1] + dy,
                self.drag_rect_coords[2] + dx,
                self.drag_rect_coords[3] + dy
            ]
            
            # Limitar movimiento a los bordes
            if new_coords[0] < 0:
                offset = -new_coords[0]
                new_coords[0] += offset
                new_coords[2] += offset
            if new_coords[1] < 0:
                offset = -new_coords[1]
                new_coords[1] += offset
                new_coords[3] += offset
            if new_coords[2] > self.new_w:
                offset = new_coords[2] - self.new_w
                new_coords[0] -= offset
                new_coords[2] -= offset
            if new_coords[3] > self.new_h:
                offset = new_coords[3] - self.new_h
                new_coords[1] -= offset
                new_coords[3] -= offset
            
            self.canvas.coords(self.rect_id, *new_coords)
            self.actualizar_overlay()
            self.actualizar_handles()
            
        elif self.rect_id:
            # Dibujando nueva selección
            self.canvas.coords(self.rect_id, self.start_x, self.start_y, x, y)
            self.actualizar_overlay()
            self.actualizar_info()

    def on_release(self, event):
        if self.rect_id:
            coords = self.canvas.coords(self.rect_id)
            if coords:
                # Normalizar coordenadas
                x1 = min(coords[0], coords[2])
                y1 = min(coords[1], coords[3])
                x2 = max(coords[0], coords[2])
                y2 = max(coords[1], coords[3])
                
                # Verificar que la selección tenga tamaño mínimo
                if (x2 - x1) > 10 and (y2 - y1) > 10:
                    self.canvas.coords(self.rect_id, x1, y1, x2, y2)
                    self.end_x = x2
                    self.end_y = y2
                    self.start_x = x1
                    self.start_y = y1
                    self.actualizar_overlay()
                    self.crear_handles()
                    self.btn_guardar.config(state="normal")
                else:
                    self.limpiar_seleccion()
        
        self.dragging = False
        self.resizing = False
        self.resize_handle = None
        self.actualizar_info()

    def limpiar_seleccion(self):
        if self.rect_id:
            self.canvas.delete(self.rect_id)
            self.rect_id = None
        for overlay_id in self.overlay_ids:
            self.canvas.delete(overlay_id)
        self.overlay_ids = []
        for handle in self.handles:
            self.canvas.delete(handle)
        self.handles = []
        self.btn_guardar.config(state="disabled")
        self.label_info.config(text="")

    def actualizar_overlay(self):
        """Oscurece el área fuera de la selección (estilo iPhone)"""
        for overlay_id in self.overlay_ids:
            self.canvas.delete(overlay_id)
        self.overlay_ids = []
        
        if not self.rect_id:
            return
        
        coords = self.canvas.coords(self.rect_id)
        if not coords or len(coords) != 4:
            return
        
        x1, y1, x2, y2 = coords
        
        # Cuatro rectángulos oscuros alrededor de la selección
        # Arriba
        self.overlay_ids.append(
            self.canvas.create_rectangle(0, 0, self.new_w, y1, 
                                        fill="#000000", stipple="gray50", 
                                        outline="")
        )
        # Abajo
        self.overlay_ids.append(
            self.canvas.create_rectangle(0, y2, self.new_w, self.new_h, 
                                        fill="#000000", stipple="gray50", 
                                        outline="")
        )
        # Izquierda
        self.overlay_ids.append(
            self.canvas.create_rectangle(0, y1, x1, y2, 
                                        fill="#000000", stipple="gray50", 
                                        outline="")
        )
        # Derecha
        self.overlay_ids.append(
            self.canvas.create_rectangle(x2, y1, self.new_w, y2, 
                                        fill="#000000", stipple="gray50", 
                                        outline="")
        )
        
        # Mantener el rectángulo de selección al frente
        self.canvas.tag_raise(self.rect_id)

    def crear_handles(self):
        """Crea los puntos de arrastre en las esquinas (estilo iPhone)"""
        for handle in self.handles:
            self.canvas.delete(handle)
        self.handles = []
        
        if not self.rect_id:
            return
        
        coords = self.canvas.coords(self.rect_id)
        if not coords or len(coords) != 4:
            return
        
        x1, y1, x2, y2 = coords
        handle_size = 12
        
        # Esquinas: superior-izq, superior-der, inferior-der, inferior-izq
        corners = [
            (x1, y1), (x2, y1), (x2, y2), (x1, y2)
        ]
        
        for cx, cy in corners:
            handle = self.canvas.create_oval(
                cx - handle_size, cy - handle_size,
                cx + handle_size, cy + handle_size,
                fill="#007aff", outline="#ffffff", width=2
            )
            self.handles.append(handle)

    def actualizar_handles(self):
        """Actualiza la posición de los handles"""
        if not self.rect_id or not self.handles:
            return
        
        coords = self.canvas.coords(self.rect_id)
        if not coords or len(coords) != 4:
            return
        
        x1, y1, x2, y2 = coords
        handle_size = 12
        corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
        
        for i, (cx, cy) in enumerate(corners):
            if i < len(self.handles):
                self.canvas.coords(
                    self.handles[i],
                    cx - handle_size, cy - handle_size,
                    cx + handle_size, cy + handle_size
                )

    def actualizar_info(self):
        """Muestra las dimensiones de la selección"""
        if not self.rect_id:
            self.label_info.config(text="")
            return
        
        coords = self.canvas.coords(self.rect_id)
        if not coords or len(coords) != 4:
            return
        
        # Calcular dimensiones en píxeles originales
        x1, y1, x2, y2 = coords
        scale_x = self.original_w / self.new_w
        scale_y = self.original_h / self.new_h
        
        width = int((x2 - x1) * scale_x)
        height = int((y2 - y1) * scale_y)
        
        self.label_info.config(text=f"Tamaño: {width} × {height} px")

    def cancelar(self):
        """Cierra sin guardar"""
        try:
            if self.modo_video and self.callback_guardado:
                self.callback_guardado(None)
            
            # Liberar el grab antes de destruir
            if self.window.winfo_exists():
                self.window.grab_release()
                self.window.destroy()
        except Exception:
            pass

    def guardar(self):
        """Guarda la imagen recortada o retorna las coordenadas"""
        if not self.rect_id:
            messagebox.showwarning("Advertencia", "Primero selecciona un área.")
            return

        coords = self.canvas.coords(self.rect_id)
        if not coords or len(coords) != 4:
            return

        # Normalizar coordenadas
        x1 = min(coords[0], coords[2])
        y1 = min(coords[1], coords[3])
        x2 = max(coords[0], coords[2])
        y2 = max(coords[1], coords[3])

        # Calcular factor de escala (Pantalla → Original)
        scale_x = self.original_w / self.new_w
        scale_y = self.original_h / self.new_h

        # Convertir a coordenadas de la imagen original
        real_x1 = int(x1 * scale_x)
        real_y1 = int(y1 * scale_y)
        real_x2 = int(x2 * scale_x)
        real_y2 = int(y2 * scale_y)

        try:
            if self.modo_video:
                # Retornar coordenadas para recorte de video
                if self.window.winfo_exists():
                    self.window.grab_release()
                    self.window.destroy()
                if self.callback_guardado:
                    self.callback_guardado((real_x1, real_y1, real_x2, real_y2))
            else:
                # Recortar y sobrescribir la imagen
                cropped = self.original_image.crop((real_x1, real_y1, real_x2, real_y2))
                cropped.save(self.image_path)
                
                if self.window.winfo_exists():
                    self.window.grab_release()
                    self.window.destroy()
                
                messagebox.showinfo("✓ Guardado", "Imagen recortada correctamente.")
                
                if self.callback_guardado:
                    self.callback_guardado()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar: {e}")