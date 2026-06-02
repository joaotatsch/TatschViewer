"""
Módulo de presets de janelamento 3D.
"""
from PyQt6.QtCore import QObject
import vtk

class PresetsJanelamento3D(QObject):
    """
    Organizará como se darão os presets de janelamento 3D, definindo tabelas
    de cores e funções de opacidade padrão para tecidos, ossos, vasos (MIP) e MIP colorido.
    """
    def __init__(self):
        super().__init__()

    def obter_funcoes_transferencia(self, nome_preset: str) -> tuple:
        """
        Retorna as funções de opacidade (vtkPiecewiseFunction) e de cores (vtkColorTransferFunction) do preset.
        """
        pass

    def listar_presets(self) -> list:
        """
        Retorna a lista de nomes de todos os presets disponíveis para 3D.
        """
        pass
