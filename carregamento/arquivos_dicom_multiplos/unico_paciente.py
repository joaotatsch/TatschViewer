"""
Módulo para gerenciamento de arquivos DICOM de um único paciente.
"""
from PyQt6.QtCore import QObject
import SimpleITK as sitk

class GerenciadorUnicoPaciente(QObject):
    """
    Dita como o sistema lidará com múltiplos arquivos DICOM pertencentes
    a um único paciente (ex: múltiplos estudos, exames ou séries do mesmo paciente).
    """
    def __init__(self):
        super().__init__()

    def organizar_estudos(self, arquivos: list) -> dict:
        """
        Organiza e classifica arquivos DICOM de um único paciente agrupando-os por estudos e séries.
        """
        pass
