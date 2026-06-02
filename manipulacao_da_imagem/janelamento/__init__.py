"""
Módulo de coordenação geral de janelamento (Windowing).
"""
from PyQt6.QtCore import QObject
import vtk

class CoordenadorJanelamento(QObject):
    """
    Coordenará como se dará o janelamento (ajuste de brilho e contraste global)
    distribuindo ações de modificação para os visualizadores 2D (MPR) e 3D.
    """
    def __init__(self):
        super().__init__()

    def ajustar_janela_global(self, largura: float, nivel: float):
        """
        Aplica os valores de largura (WW) e nível (WL) de janela a todos os visualizadores aplicáveis.
        """
        pass
