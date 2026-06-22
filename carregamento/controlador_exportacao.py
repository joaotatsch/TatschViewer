import os
import re
import SimpleITK as sitk
from PyQt6.QtCore import QThread, pyqtSignal, pyqtSlot
from anonimizador import AnonimizadorDicom

class ThreadAnonimizacao(QThread):
    progresso = pyqtSignal(int)
    concluido = pyqtSignal(bool, str)
    erro = pyqtSignal(str)

    def __init__(self, series_alvo, diretorio_ativo, diretorio_destino, exportar_todas):
        super().__init__()
        self.series_alvo = series_alvo
        self.diretorio_ativo = diretorio_ativo
        self.diretorio_destino = diretorio_destino
        self.exportar_todas = exportar_todas
        self.anonimizador = AnonimizadorDicom()
        self._is_cancelled = False

    @pyqtSlot()
    def cancelar(self):
        self._is_cancelled = True

    def check_cancel(self):
        return self._is_cancelled

    def run(self):
        try:
            arquivos_processados = 0
            todas_sucesso = True

            for s in self.series_alvo:
                if not s: continue
                
                if self._is_cancelled:
                    self.concluido.emit(False, "Cancelado pelo usuário.")
                    return

                arquivos_completos = s.get("Files", [])
                if not arquivos_completos:
                    dir_busca = s.get("Directory", self.diretorio_ativo)
                    uid_real = s["SeriesID"].split('_')[0]
                    arquivos_completos = sitk.ImageSeriesReader.GetGDCMSeriesFileNames(dir_busca, uid_real)
                
                pasta_alvo = self.diretorio_destino
                if self.exportar_todas:
                    nome_pasta = f"Serie_{s['SeriesNumber']}" if s.get("SeriesNumber") else f"Serie_{s['SeriesID'][-6:]}"
                    nome_pasta = re.sub(r'[<>:"/\\|?*]', '_', nome_pasta)
                    pasta_alvo = os.path.join(self.diretorio_destino, nome_pasta)

                # Precisamos passar o valor atual por default argument para criar a closure correta
                def local_callback(idx, total_serie, atual=arquivos_processados):
                    self.progresso.emit(atual + idx)

                sucesso_serie = self.anonimizador.anonimizar_serie(
                    list(arquivos_completos), 
                    pasta_alvo, 
                    progress_callback=local_callback,
                    check_cancel=self.check_cancel
                )
                
                if self._is_cancelled:
                    self.concluido.emit(False, "Cancelado pelo usuário.")
                    return
                    
                arquivos_processados += len(arquivos_completos)
                
                if not sucesso_serie:
                    todas_sucesso = False

            if todas_sucesso:
                self.concluido.emit(True, self.diretorio_destino)
            else:
                self.erro.emit("Falha parcial ao anonimizar os arquivos.")

        except Exception as e:
            self.erro.emit(str(e))

class ControladorExportacao:
    def __init__(self):
        pass

    def calcular_total_arquivos(self, series_alvo, diretorio_ativo):
        total_arquivos = 0
        for s in series_alvo:
            if s:
                arqs = s.get("Files", [])
                if not arqs:
                    dir_busca = s.get("Directory", diretorio_ativo)
                    uid_real = s["SeriesID"].split('_')[0]
                    arqs = sitk.ImageSeriesReader.GetGDCMSeriesFileNames(dir_busca, uid_real)
                total_arquivos += len(arqs)
        return total_arquivos

