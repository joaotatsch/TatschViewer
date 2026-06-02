"""
Módulo de exibição do arquivo DICOM.
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout
import vtk

class CoordenadorExibicao(QWidget):
    """
    Coordenador principal que define qual o Layout em que o arquivo DICOM será exibido.
    Alterna entre MPR Clássico e Múltiplas Telas de forma dinâmica.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout_principal = QVBoxLayout(self)
        self.layout_principal.setContentsMargins(0, 0, 0, 0)
        
        from .layout_4_up import Layout4Up
        self.widget_layout_ativo = Layout4Up(self)
        self.layout_principal.addWidget(self.widget_layout_ativo)

    def definir_layout(self, tipo_layout: str):
        # 1. EXORCISMO DO WIDGET ANTIGO: Remove da interface e agenda a destruição no C++
        if hasattr(self, 'widget_layout_ativo') and self.widget_layout_ativo is not None:
            self.layout_principal.removeWidget(self.widget_layout_ativo)
            self.widget_layout_ativo.deleteLater() # Mata o contexto OpenGL antigo
            self.widget_layout_ativo = None
            
        # 2. INSTANCIA O NOVO LAYOUT
        if tipo_layout == "MPR" or tipo_layout == "Normal" or tipo_layout == "4-Up":
            from .layout_4_up import Layout4Up
            self.widget_layout_ativo = Layout4Up(self)
        elif tipo_layout in ["1x2", "1x3", "2x2", "2x3"]:
            from .multiplas_telas import LayoutDinamico
            self.widget_layout_ativo = LayoutDinamico(self)
            linhas, colunas = map(int, tipo_layout.split("x"))
            self.widget_layout_ativo.configurar_grade(linhas, colunas)

        # 3. ADICIONA À TELA
        if self.widget_layout_ativo:
            self.layout_principal.addWidget(self.widget_layout_ativo)
