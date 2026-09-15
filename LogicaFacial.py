import os
import pickle
import tempfile
import threading
import uuid
import cv2
import numpy as np
from deepface import DeepFace

class FaceBrain:
    def __init__(self, directorioSalida, callbackLog=None, callbackProgreso=None):
        self.directorioSalida = directorioSalida
        self.knownEmbeddings = {}
        self.callbackLog = callbackLog
        self.callbackProgreso = callbackProgreso
        self.estaCargando = False
        self.nombreModelo = "ArcFace"
        self.backendDetector = "retinaface"
        self.umbral = 0.65
        self.umbralConfianza = 0.85
        self.archivoCache = os.path.join(self.directorioSalida, "embeddingsCache.pkl")

    def log(self, mensaje):
        if self.callbackLog:
            try:
                self.callbackLog(mensaje)
            except:
                print(mensaje)
        else:
            print(mensaje)

    def cargarReferenciasAsync(self):
        hilo = threading.Thread(target=self._procesarCargaOptimizada)
        hilo.daemon = True
        hilo.start()

    def esRostroVisible(self, rutaImagen):
        """Verifica que exista un rostro claro en la imagen con alta confianza"""
        try:
            rostros = DeepFace.extract_faces(
                img_path=rutaImagen,
                detector_backend=self.backendDetector,
                enforce_detection=True
            )

            if rostros and len(rostros) > 0:
                confianza = rostros[0].get('confidence', 0)
                if confianza >= self.umbralConfianza:
                    return True
        except Exception:
            pass

        return False

    def esRostroValido(self, rutaImagen):
        """Verifica que exista un rostro claro en la imagen."""
        try:
            rostros = DeepFace.extract_faces(
                img_path=rutaImagen,
                detector_backend='opencv',
                enforce_detection=True
            )
            return len(rostros) > 0
        except Exception:
            return False

    def reentrenarCarpeta(self, nombrePersona):
        """Purga las referencias de una persona y vuelve a escanear su directorio."""
        if nombrePersona in self.knownEmbeddings:
            del self.knownEmbeddings[nombrePersona]

        self.knownEmbeddings[nombrePersona] = []
        directorioPersona = os.path.join(self.directorioSalida, nombrePersona)

        if not os.path.exists(directorioPersona):
            return

        archivosValidos = [f for f in os.listdir(directorioPersona) if not f.startswith('.') and not f.startswith('._')]
        imagenesCargadas = 0

        for nombreArchivo in archivosValidos:
            if imagenesCargadas >= 5:  # Tu límite definido
                break

            rutaImagen = os.path.join(directorioPersona, nombreArchivo)

            if self.esRostroValido(rutaImagen):
                try:
                    representacion = DeepFace.represent(
                        img_path=rutaImagen,
                        model_name=self.nombreModelo,
                        enforce_detection=True,
                        detector_backend=self.backendDetector
                    )
                    self.knownEmbeddings[nombrePersona].append(representacion[0]["embedding"])
                    imagenesCargadas += 1
                except Exception:
                    pass

        self._guardarCache()

    def extraerFotogramasVideo(self, rutaVideo):
        rutasTemporales = []
        try:
            captura = cv2.VideoCapture(rutaVideo)
            totalFotogramas = int(captura.get(cv2.CAP_PROP_FRAME_COUNT))

            puntosExtraccion = [
                int(totalFotogramas * 0.2),
                int(totalFotogramas * 0.5),
                int(totalFotogramas * 0.8)
            ]

            for punto in puntosExtraccion:
                captura.set(cv2.CAP_PROP_POS_FRAMES, punto)
                exito, fotograma = captura.read()

                if exito:
                    rutaTemporal = os.path.join(tempfile.gettempdir(), f"temp_{uuid.uuid4().hex}.jpg")
                    cv2.imwrite(rutaTemporal, fotograma)
                    rutasTemporales.append(rutaTemporal)

            captura.release()
        except Exception as error:
            self.log(f"Error procesando video {error}")

        return rutasTemporales

    def _procesarCargaOptimizada(self):
        self.estaCargando = True

        if self.callbackProgreso:
            self.callbackProgreso(-1, 100, "Iniciando Motor")

        if not os.path.exists(self.directorioSalida):
            self.log("Carpeta destino no existe")
            self.estaCargando = False
            return

        if os.path.exists(self.archivoCache):
            try:
                with open(self.archivoCache, "rb") as archivo:
                    self.knownEmbeddings = pickle.load(archivo)

                self.log("Cache de memoria cargada")
                if self.callbackProgreso:
                    self.callbackProgreso(100, 100, "Inteligencia Activa")

                self.estaCargando = False
                return
            except Exception as error:
                self.log(f"Error leyendo cache recalculando {error}")

        self.log(f"Iniciando motor {self.backendDetector}")

        personas = [p for p in os.listdir(self.directorioSalida) if
                    os.path.isdir(os.path.join(self.directorioSalida, p))]
        totalPersonas = len(personas)

        for i, nombrePersona in enumerate(personas):
            if self.callbackProgreso:
                self.callbackProgreso(i, totalPersonas, f"Aprendiendo {nombrePersona}")

            directorioPersona = os.path.join(self.directorioSalida, nombrePersona)
            self.knownEmbeddings[nombrePersona] = []

            imagenesCargadas = 0
            for nombreArchivo in os.listdir(directorioPersona):
                if nombreArchivo.startswith('.') or nombreArchivo.startswith('._'):
                    continue

                rutaArchivo = os.path.join(directorioPersona, nombreArchivo)
                esImagen = nombreArchivo.lower().endswith(('.jpg', '.png', '.jpeg'))
                esVideo = nombreArchivo.lower().endswith(('.mp4', '.avi', '.mov', '.mkv'))

                if not (esImagen or esVideo):
                    continue

                rutasAProcesar = [rutaArchivo] if esImagen else self.extraerFotogramasVideo(rutaArchivo)

                for ruta in rutasAProcesar:
                    if imagenesCargadas >= 5:
                        break

                    if self.esRostroVisible(ruta):
                        try:
                            representacion = DeepFace.represent(
                                img_path=ruta,
                                model_name=self.nombreModelo,
                                enforce_detection=True,
                                detector_backend=self.backendDetector
                            )
                            embedding = representacion[0]["embedding"]
                            self.knownEmbeddings[nombrePersona].append(embedding)
                            imagenesCargadas += 1
                        except Exception:
                            pass

                if esVideo:
                    for rutaTemp in rutasAProcesar:
                        if os.path.exists(rutaTemp):
                            try:
                                os.remove(rutaTemp)
                            except Exception:
                                pass

                if imagenesCargadas >= 5:
                    break

            if imagenesCargadas > 0:
                self.log(f"Aprendido {nombrePersona}")

        self._guardarCache()

        self.estaCargando = False
        self.log(f"Carga Finalizada")

        if self.callbackProgreso:
            self.callbackProgreso(totalPersonas, totalPersonas, "Inteligencia Activa")

    def _guardarCache(self):
        """Actualiza el archivo fisico de cache de forma segura"""
        try:
            with open(self.archivoCache, "wb") as archivo:
                pickle.dump(self.knownEmbeddings, archivo)
            self.log("Memoria actualizada en cache")
        except Exception as error:
            self.log(f"Error al guardar cache {error}")

    def calcularDistanciaCoseno(self, representacionOrigen, representacionPrueba):
        a = np.matmul(np.transpose(representacionOrigen), representacionPrueba)
        b = np.sum(np.multiply(representacionOrigen, representacionOrigen))
        c = np.sum(np.multiply(representacionPrueba, representacionPrueba))
        return 1 - (a / (np.sqrt(b) * np.sqrt(c)))

    def sugerirPersona(self, rutaImagen):
        if self.estaCargando: return "Cargando Motor"
        if not self.knownEmbeddings: return "Sin Referencias"

        try:
            objetivo = DeepFace.represent(
                img_path=rutaImagen,
                model_name=self.nombreModelo,
                enforce_detection=True,
                detector_backend=self.backendDetector
            )
            embeddingObjetivo = objetivo[0]["embedding"]
        except:
            return "Rostro no visible"

        mejorCoincidencia = None
        distanciaMinima = float('inf')

        for nombre, listaEmbeddings in self.knownEmbeddings.items():
            for embeddingReferencia in listaEmbeddings:
                distancia = self.calcularDistanciaCoseno(embeddingObjetivo, embeddingReferencia)
                if distancia < distanciaMinima:
                    distanciaMinima = distancia
                    mejorCoincidencia = nombre

        if distanciaMinima < self.umbral:
            confianza = round((1 - distanciaMinima) * 100, 1)
            return f"{mejorCoincidencia} ({confianza}%)"

        return "Desconocido"

    def agregarImagenReferencia(self, nombrePersona, rutaImagen):
        """Calcula el embedding de la nueva imagen si cumple con la calidad y lo agrega a la memoria"""
        if nombrePersona not in self.knownEmbeddings:
            self.knownEmbeddings[nombrePersona] = []

        if len(self.knownEmbeddings[nombrePersona]) >= 5:
            return

        if not self.esRostroVisible(rutaImagen):
            self.log(f"Imagen ignorada por baja calidad {rutaImagen}")
            return

        try:
            representacion = DeepFace.represent(
                img_path=rutaImagen,
                model_name=self.nombreModelo,
                enforce_detection=True,
                detector_backend=self.backendDetector
            )

            if representacion and len(representacion) > 0:
                nuevoEmbedding = representacion[0]["embedding"]
                self.knownEmbeddings[nombrePersona].append(nuevoEmbedding)
                self.log(f"Nuevo rostro aprendido para {nombrePersona}")
                self._guardarCache()

        except Exception as error:
            self.log(f"Error al intentar aprender rostro {error}")

    def reentrenarPersona(self, nombrePersona, rutaCarpeta):
        """Borra la memoria de una persona y recalcula sus referencias con filtro de calidad"""
        self.log(f"Reevaluando referencias para {nombrePersona}")

        self.knownEmbeddings[nombrePersona] = []

        archivos = [f for f in os.listdir(rutaCarpeta) if
                    f.lower().endswith(('.jpg', '.png', '.jpeg')) and not f.startswith('._')]
        imagenesCargadas = 0

        for nombreImagen in archivos:
            if imagenesCargadas >= 5:
                break

            rutaImagen = os.path.join(rutaCarpeta, nombreImagen)

            if self.esRostroVisible(rutaImagen):
                try:
                    representacion = DeepFace.represent(
                        img_path=rutaImagen,
                        model_name=self.nombreModelo,
                        enforce_detection=True,
                        detector_backend=self.backendDetector
                    )
                    if representacion and len(representacion) > 0:
                        self.knownEmbeddings[nombrePersona].append(representacion[0]["embedding"])
                        imagenesCargadas += 1
                except Exception:
                    pass

        self.log(f"Persona reentrenada con imagenes validas")
        self._guardarCache()