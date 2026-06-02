"""
Módulo para subtração óssea em imagens médicas.
"""
from PyQt6.QtCore import QObject
import SimpleITK as sitk
import vtk

class SubtratorOsseo(QObject):
    """
    Coordenará como se dará a subtração óssea do volume tomográfico ou de ressonância magnética,
    isolando tecidos moles, estruturas vasculares ou o parênquima cerebral.
    """
    def __init__(self):
        super().__init__()

    def processar_subtracao(self, volume: sitk.Image) -> sitk.Image:
        """
        Executa algoritmos de segmentação para subtrair e remover as estruturas ósseas do volume DICOM.
        """
        pass
