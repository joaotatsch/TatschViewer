"""
Módulo de coordenação de construção e renderização da imagem.
"""
from PyQt6.QtCore import QObject
import SimpleITK as sitk
import vtk

class CoordenadorConstrucaoImagem(QObject):
    """
    Coordenará como o arquivo DICOM e seus volumes correspondentes serão renderizados,
    gerando os dados necessários para exibições 2D e reconstruções 3D.
    """
    def __init__(self):
        super().__init__()

    def construir_volume(self, imagem_sitk: sitk.Image) -> vtk.vtkImageData:
        """
        Converte a imagem SimpleITK em dados compatíveis com o VTK para renderização de volumes e fatias.
        """
        pass
