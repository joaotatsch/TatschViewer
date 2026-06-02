"""
Módulo para Projeção de Média de Intensidade (Average).
"""
from PyQt6.QtCore import QObject
import vtk

class OperadorAverage(QObject):
    """
    Organizará como funciona a função Average, calculando a intensidade média
    dos voxels atravessados por um raio ao longo da espessura de corte especificada.
    """
    def __init__(self):
        super().__init__()

    def aplicar_media(self, espessura_fatia: float):
        """
        Aplica a projeção de intensidade média (Average) com base na espessura de fatia especificada.
        """
        pass
