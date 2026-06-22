# -*- coding: utf-8 -*-
from PyQt6.QtCore import QThread, pyqtSignal
from carregamento.carregamento_dicom import CarregadorDicom
from core.utils_profiling import profiler_time

class ThreadCarregamento(QThread):
    resultado = pyqtSignal(object)
    erro_carregamento = pyqtSignal(str)
    resultado_cache_silencioso = pyqtSignal(object, str)
    prefetch_concluido = pyqtSignal(object, str)   # novo: sinal de pré-busca concluída

    def __init__(self, coordenador, diretorio, series_id, silencioso=False, prefetch=False):
        super().__init__()
        self.coordenador = coordenador
        self.diretorio = diretorio
        self.series_id = series_id
        self.silencioso = silencioso
        self.prefetch = prefetch
        self._cancelled = False
        self._paused = False

    @profiler_time
    def run(self):
        try:
            resultado = self.coordenador.carregar_serie(self.diretorio, self.series_id)
            if self.prefetch:
                self.prefetch_concluido.emit(resultado, self.series_id)
            elif self.silencioso:
                self.resultado_cache_silencioso.emit(resultado, self.series_id)
            else:
                self.resultado.emit(resultado)
        except Exception as e:
            if not self.silencioso and not self.prefetch:
                self.erro_carregamento.emit(str(e))
            else:
                pass
