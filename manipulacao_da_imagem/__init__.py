"""
Módulo de coordenação geral de manipulação da imagem 2D e 3D.
"""
from PyQt6.QtCore import QObject
import vtk

class CoordenadorManipulacaoImagem(QObject):
    """
    Coordenará como se dará a manipulação da imagem 2D (fatias) e 3D (volume),
    centralizando requisições de janelamento, reconstruções oblíquas, reslice e projeções.
    """
    def __init__(self):
        super().__init__()

    def resetar_manipulacoes(self):
        """
        Restaura todos os filtros, janelamento e transformações aplicadas à imagem para os valores originais.
        """
        pass
