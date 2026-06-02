"""
Módulo de presets de janelamento 2D (MPR) específicos para neurologia.
"""
from PyQt6.QtCore import QObject

class PresetsJanelamento2D(QObject):
    """
    Organiza e fornece os presets de janelamento (Window Width e Window Level) pré-definidos
    para diagnósticos clínicos em imagens 2D (MPR).
    """
    def __init__(self):
        super().__init__()
        # Presets neurológicos clínicos padrão
        self.presets = {
            "avc_isquemico": {"nome": "AVC Isquêmico Agudo", "ww": 30, "wl": 30},
            "cerebro": {"nome": "Cérebro (Parênquima)", "ww": 80, "wl": 40},
            "osso": {"nome": "Osso (Janela Óssea)", "ww": 2000, "wl": 500},
            "sangue_agudo": {"nome": "Sangue Agudo (Hemorragia)", "ww": 150, "wl": 70}
        }

    def obter_preset(self, nome_preset: str) -> tuple:
        """
        Retorna uma tupla (WW, WL) contendo os valores pré-definidos para o preset solicitado.
        """
        if nome_preset in self.presets:
            preset = self.presets[nome_preset]
            return preset["ww"], preset["wl"]
        return 80, 40  # Default to cérebro if not found

    def listar_presets(self) -> list:
        """
        Retorna a lista de chaves de todos os presets disponíveis para 2D.
        """
        return list(self.presets.keys())
        
    def obter_dados_presets(self) -> dict:
        """
        Retorna o dicionário completo com informações de todos os presets.
        """
        return self.presets
