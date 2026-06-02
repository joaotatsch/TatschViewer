"""
Módulo de coordenação de janelamento em visualizações 2D (MPR).
"""
from PyQt6.QtCore import QObject
import vtk

class CoordenadorJanelamento2D(QObject):
    """
    Coordenará como se dará o janelamento 2D (das imagens em MPR), definindo
    os parâmetros de brilho e contraste diretamente nos visualizadores planares.
    """
    def __init__(self):
        super().__init__()

    def aplicar_janelamento_mpr(self, largura: float, nivel: float, plano: str):
        """
        Aplica os valores de janela a um plano ortogonal específico (Axial, Sagital ou Coronal).
        """
        pass
