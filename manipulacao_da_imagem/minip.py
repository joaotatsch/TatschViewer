"""
Módulo para Projeção de Intensidade Mínima (MinIP).
"""
from PyQt6.QtCore import QObject
import vtk

class OperadorMinIP(QObject):
    """
    Organizará como funciona a função MinIP (Minimum Intensity Projection),
    projetando na tela os pixels com menores valores de intensidade de atenuação ao longo de um raio.
    """
    def __init__(self):
        super().__init__()

    def aplicar_minip(self, espessura_fatia: float):
        """
        Aplica a projeção de intensidade mínima (MinIP) com base na espessura de fatia especificada.
        """
        pass
