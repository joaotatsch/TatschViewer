"""
Módulo de coordenação do modo de exibição 4-Up (Padrão).
"""
from PyQt6.QtWidgets import QWidget, QGridLayout, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt, QObject, QEvent
import vtk
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

class QuadranteVisualizador(QWidget):
    """
    Widget auxiliar que encapsula um QVTKRenderWindowInteractor e uma label de identificação
    sobreposta no canto do visualizador.
    """
    def __init__(self, nome: str, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # Interator VTK
        self.interactor = QVTKRenderWindowInteractor(self)
        self.layout.addWidget(self.interactor)
        
        # Inicializa o Renderizador VTK associado
        self.renderer = vtk.vtkRenderer()
        self.interactor.GetRenderWindow().AddRenderer(self.renderer)
        self.renderer.SetBackground(0.05, 0.05, 0.05)  # Fundo clínico escuro #0d0d0d
        
        self.setAcceptDrops(True)
        style = vtk.vtkInteractorStyleImage()
        self.interactor.SetInteractorStyle(style)
        
        # Label de sobreposição para identificar o plano
        self.label = QLabel(nome, self)

        bg_color = "rgba(18, 18, 18, 200)"
        text_color = "#e0e0e0"

        if "AXIAL" in nome.upper():
            bg_color = "rgba(231, 76, 60, 220)"  # Vermelho
            text_color = "#ffffff"
        elif "CORONAL" in nome.upper():
            bg_color = "rgba(52, 152, 219, 220)"  # Azul
            text_color = "#ffffff"
        elif "SAGITAL" in nome.upper():
            bg_color = "rgba(241, 196, 15, 220)"  # Amarelo
            text_color = "#000000" # Fonte preta para contraste
            
        self.label.setStyleSheet(f"""
            QLabel {{
                color: {text_color};
                background-color: {bg_color};
                border: 1px solid #111111;
                border-radius: 4px;
                padding: 4px 10px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-weight: bold;
                font-size: 11px;
            }}
        """)
        # Evita interferência nos cliques de mouse do VTK
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def dragEnterEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        main_window = self.window()
        item = main_window.list_series.currentItem()
        if item:
            dados = item.data(Qt.ItemDataRole.UserRole)
            main_window.carregar_serie_no_quadrante(dados, self)
        event.acceptProposedAction()


    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.label.adjustSize()
        self.label.move(10, self.height() - self.label.height() - 35)


class FiltroDuploClique(QObject):
    def __init__(self, layout, quadrante):
        super().__init__(layout)
        self.layout = layout
        self.quadrante = quadrante
        
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonDblClick:
            if event.button() == Qt.MouseButton.LeftButton:
                self.layout.alternar_maximizacao(self.quadrante)
                return True
        return False

class Layout4Up(QWidget):
    """
    Coordenador do modo de exibição 4-up padrão, contendo 3 visões ortogonais 2D
    (Axial, Sagital e Coronal em MPR) e uma visão tridimensional (Reconstrução 3D).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout_grade = QGridLayout(self)
        self.layout_grade.setContentsMargins(2, 2, 2, 2)
        self.layout_grade.setSpacing(4)  # Pequeno espaçamento cinza entre as telas
        
        # Dicionário para manter referência das visões
        self.visoes = {}
        self.quadrante_maximizado = None
        self.filtros = []
        self.inicializar_telas()

    def inicializar_telas(self):
        """
        Inicializa as quatro telas de visualização e seus respectivos renderizadores VTK.
        """
        # Criando os quadrantes
        self.visoes["Axial"] = QuadranteVisualizador("AXIAL", self)
        self.visoes["Sagital"] = QuadranteVisualizador("SAGITAL", self)
        self.visoes["Coronal"] = QuadranteVisualizador("CORONAL", self)
        self.visoes["3D"] = QuadranteVisualizador("3D RECONSTRUCTION", self)
        
        # Adicionando à grade (2x2)
        self.layout_grade.addWidget(self.visoes["Axial"], 0, 0)
        self.layout_grade.addWidget(self.visoes["3D"], 0, 1)
        self.layout_grade.addWidget(self.visoes["Coronal"], 1, 0)
        self.layout_grade.addWidget(self.visoes["Sagital"], 1, 1)
        
        # Configura as proporções da grade para serem iguais
        self.layout_grade.setRowStretch(0, 1)
        self.layout_grade.setRowStretch(1, 1)
        self.layout_grade.setColumnStretch(0, 1)
        self.layout_grade.setColumnStretch(1, 1)
        
        # Inicializa o loop de eventos dos interactors do VTK
        for visao in self.visoes.values():
            visao.interactor.Initialize()
            filtro = FiltroDuploClique(self, visao)
            visao.interactor.installEventFilter(filtro)
            self.filtros.append(filtro)

    def alternar_maximizacao(self, quadrante):
        if self.quadrante_maximizado is None:
            # Maximizar
            for v in self.visoes.values():
                if v != quadrante:
                    v.hide()
            self.layout_grade.setRowStretch(0, 0)
            self.layout_grade.setRowStretch(1, 0)
            self.layout_grade.setColumnStretch(0, 0)
            self.layout_grade.setColumnStretch(1, 0)
            self.quadrante_maximizado = quadrante
        else:
            # Restaurar
            for v in self.visoes.values():
                v.show()
            self.layout_grade.setRowStretch(0, 1)
            self.layout_grade.setRowStretch(1, 1)
            self.layout_grade.setColumnStretch(0, 1)
            self.layout_grade.setColumnStretch(1, 1)
            self.quadrante_maximizado = None

    def aplicar_modo_visualizacao(self, modo: str):
        """
        Altera a exibição dos quadrantes ativando/desativando visões e
        ajustando as proporções (stretches) do QGridLayout sem recriar objetos.
        """
        # Sempre resetar o maxímo temporário do duplo-clique
        self.quadrante_maximizado = None
        
        # 1-up: Apenas Axial
        if modo == "1-up":
            self.visoes["Axial"].show()
            self.visoes["Sagital"].hide()
            self.visoes["Coronal"].hide()
            self.visoes["3D"].hide()
            self.layout_grade.setRowStretch(0, 1)
            self.layout_grade.setRowStretch(1, 0)
            self.layout_grade.setColumnStretch(0, 1)
            self.layout_grade.setColumnStretch(1, 0)
            
        # 3-up: MPR Clássico sem o 3D
        elif modo == "3-up":
            self.visoes["Axial"].show()
            self.visoes["Sagital"].show()
            self.visoes["Coronal"].show()
            self.visoes["3D"].hide()
            self.layout_grade.setRowStretch(0, 1)
            self.layout_grade.setRowStretch(1, 1)
            self.layout_grade.setColumnStretch(0, 1)
            self.layout_grade.setColumnStretch(1, 1)
            
        # 3D: Apenas o Volume Rendering
        elif modo == "3d":
            self.visoes["Axial"].hide()
            self.visoes["Sagital"].hide()
            self.visoes["Coronal"].hide()
            self.visoes["3D"].show()
            self.layout_grade.setRowStretch(0, 1)
            self.layout_grade.setRowStretch(1, 0)
            self.layout_grade.setColumnStretch(0, 0)
            self.layout_grade.setColumnStretch(1, 1)
            
        # 4-up: Padrão com tudo
        elif modo == "4-up":
            self.visoes["Axial"].show()
            self.visoes["Sagital"].show()
            self.visoes["Coronal"].show()
            self.visoes["3D"].show()
            self.layout_grade.setRowStretch(0, 1)
            self.layout_grade.setRowStretch(1, 1)
            self.layout_grade.setColumnStretch(0, 1)
            self.layout_grade.setColumnStretch(1, 1)
