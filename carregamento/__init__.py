"""
Módulo principal para coordenação de carregamento de arquivos DICOM.
"""
from PyQt6.QtCore import QObject
import SimpleITK as sitk
import numpy as np
import vtk

from .carregamento_dicom import CarregadorDicom
from .carregamento_pastas_dicom import CarregadorPastasDicom

class CoordenadorCarregamento(QObject):
    """
    Classe responsável por coordenar como os arquivos DICOM serão carregados
    a partir de seus arquivos e módulos subalternos.
    """
    def __init__(self):
        super().__init__()
        self.carregador_dicom = CarregadorDicom()
        self.carregador_pastas = CarregadorPastasDicom()

    def escanear_diretorio(self, caminho_diretorio: str, progress_callback=None) -> list:
        """
        Escaneia um diretório e lista as séries DICOM encontradas com seus respectivos arquivos.
        """
        return self.carregador_pastas.escanear_pasta(caminho_diretorio, progress_callback)

    def carregar_serie(self, caminho_serie: str, series_id: str = "", ignorar_cache: bool = False) -> tuple[vtk.vtkImageData, sitk.Image, np.ndarray, dict]:
        """
        Carrega uma série DICOM a partir de um diretório com técnica zero-copy,
        alinhando sua geometria (LPS para RAS) e retornando os dados prontos para o VTK.
        
        Também valida se o SeriesInstanceUID da imagem processada corresponde ao solicitado
        pela UI (Mecanismo 'Force-Reload' contra caches discrepantes).
        """
        uid_solicitado = series_id.split('_')[0] if series_id else ""
        
        # 1. Tenta carregar
        vtk_image, sitk_image, np_array, propriedades = self.carregador_dicom.carregar_serie(caminho_serie, series_id, ignorar_cache)
        
        # 2. Mecanismo 'Force-Reload': Se o UID processado não bater com o solicitado, força a decodificação DICOM original
        uid_processado = propriedades.get("SeriesInstanceUID", "")
        if not ignorar_cache and uid_solicitado and uid_processado and uid_processado != uid_solicitado:
            print(f"[FORCE-RELOAD] UID processado ({uid_processado}) não bate com solicitado ({uid_solicitado}). Recarregando e forçando bypass do cache!")
            vtk_image, sitk_image, np_array, propriedades = self.carregador_dicom.carregar_serie(caminho_serie, series_id, ignorar_cache=True)
            
        # 3. Anexa informações dinamicamente no vtk_image para auditoria subsequente
        vtk_image.SeriesInstanceUID = propriedades.get("SeriesInstanceUID", "")
        vtk_image.requested_uid = series_id
        
        return vtk_image, sitk_image, np_array, propriedades
