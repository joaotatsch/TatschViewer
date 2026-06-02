"""
Módulo para Coordenação de arquivos DICOM Múltiplos.
"""
from PyQt6.QtCore import QObject
import SimpleITK as sitk

class CoordenadorDicomMultiplos(QObject):
    """
    Coordena a lógica de identificação, agrupamento e tratamento quando
    múltiplos arquivos DICOM são carregados simultaneamente de uma mesma fonte.
    """
    def __init__(self):
        super().__init__()

    def processar_multiplos_arquivos(self, caminhos: list):
        """
        Analisa os arquivos carregados para agrupar as imagens por série ou paciente.
        """
        pass
