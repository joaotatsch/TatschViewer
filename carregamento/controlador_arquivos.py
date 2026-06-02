# -*- coding: utf-8 -*-
import os
import SimpleITK as sitk
from PyQt6.QtCore import QObject
from carregamento.carregamento_arquivos_zip import CarregadorArquivosZip
from carregamento.carregamento_pastas_dicom import CarregadorPastasDicom

class ControladorArquivos(QObject):
    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window

    def descompactar_zip(self, caminho_zip: str):
        carregador = CarregadorArquivosZip()
        return carregador.extrair_e_carregar(caminho_zip)

    def carregar_nrrd(self, caminho_nrrd: str):
        return sitk.ReadImage(caminho_nrrd)

    def escanear_dicom(self, diretorio: str, progress_callback=None):
        varredor = CarregadorPastasDicom()
        return varredor.escanear_pasta(diretorio, progress_callback=progress_callback)

    def anonimizar_e_exportar(self, series_alvo, diretorio_ativo, diretorio_destino, exportar_todas, progress_callback, check_canceled):
        from anonimizador import AnonimizadorDicom
        anonimizador = AnonimizadorDicom()
        arquivos_processados = 0
        todas_sucesso = True

        for s in series_alvo:
            if not s:
                continue
            
            if check_canceled():
                return False

            arquivos_completos = s.get("Files", [])
            if not arquivos_completos:
                continue
            
            # SEMPRE cria uma subpasta dedicada para evitar poluição de diretório com arquivos não-DICOM
            num = s.get('SeriesNumber')
            nome_pasta = f"Serie_{num}_Anonimizada" if num else f"Serie_{s['SeriesID'][-6:]}_Anonimizada"
            pasta_alvo = os.path.join(diretorio_destino, nome_pasta)

            # Closure de progresso com os valores acumulados
            def callback_progresso(idx, total_serie, atual=arquivos_processados):
                progress_callback(atual + idx)

            sucesso_serie = anonimizador.anonimizar_serie(
                list(arquivos_completos), 
                pasta_alvo, 
                progress_callback=callback_progresso,
                check_cancel=check_canceled
            )
            arquivos_processados += len(arquivos_completos)
            
            if not sucesso_serie:
                todas_sucesso = False

            if check_canceled():
                return False

        return todas_sucesso
