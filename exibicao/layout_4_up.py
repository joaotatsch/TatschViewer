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
        self.nome = nome
        from PyQt6.QtWidgets import QHBoxLayout, QScrollBar
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(2)
        
        # Interator VTK
        self.interactor = QVTKRenderWindowInteractor(self)
        self.layout.addWidget(self.interactor, stretch=1)
        
        # ScrollBar Vertical
        self.scrollbar = QScrollBar(Qt.Orientation.Vertical, self)
        self.scrollbar.setStyleSheet("""
            QScrollBar:vertical {
                background: #1a1a1a;
                width: 14px;
                margin: 0px 0px 0px 0px;
                border: 1px solid #111111;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #4a4a4a;
                min-height: 30px;
                border-radius: 5px;
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background: #6a6a6a;
            }
            QScrollBar::handle:vertical:pressed {
                background: #8a8a8a;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        self.scrollbar.setMinimum(0)
        self.scrollbar.setMaximum(0)
        self.scrollbar.valueChanged.connect(self._on_scrollbar_changed)
        if "3D" in nome.upper():
            self.scrollbar.hide()
        self.layout.addWidget(self.scrollbar)

        
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
            if hasattr(main_window, 'gerenciador_arquivos') and hasattr(main_window.gerenciador_arquivos, 'carregar_serie_no_quadrante'):
                main_window.gerenciador_arquivos.carregar_serie_no_quadrante(dados, self)
            elif hasattr(main_window, 'carregar_serie_no_quadrante'):
                main_window.carregar_serie_no_quadrante(dados, self)
        event.acceptProposedAction()


    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.label.adjustSize()
        self.label.move(10, self.height() - self.label.height() - 35)

    def _on_scrollbar_changed(self, value):
        if self.scrollbar.signalsBlocked():
            return
            
        main_window = self.window()
        if not hasattr(main_window, 'coordenador_navegacao') or not main_window.coordenador_navegacao:
            return
            
        nome_visao = self.nome.capitalize()
        if nome_visao == "3d reconstruction":
            return
            
        nav = main_window.coordenador_navegacao.navegador_2d
        
        nome_visao_raw = self.nome
        nome_visao_cap = self.nome.capitalize()
        plane = nav.planos.get(nome_visao_raw) or nav.planos.get(nome_visao_cap)
        
        if not plane:
            if len(nav.planos) > 0:
                plane = list(nav.planos.values())[0]
            else:
                return
        if not nav.volume_ativo:
            return
            
        bounds = nav.volume_ativo.GetBounds()
        dims = nav.volume_ativo.GetDimensions()
        
        normal = plane.GetNormal()
        axis = 0 if abs(normal[0]) > 0.5 else (1 if abs(normal[1]) > 0.5 else 2)
        b_min = axis * 2
        b_max = axis * 2 + 1
        
        if dims[axis] <= 1:
            new_pos = bounds[b_min]
        else:
            new_pos = bounds[b_min] + value * (bounds[b_max] - bounds[b_min]) / (dims[axis] - 1)
        
        current_origin = list(plane.GetOrigin())
        current_origin[axis] = new_pos
        plane.SetOrigin(current_origin)
        
        # Renderizar de forma segura todas as visões para atualizar crosshairs
        for q in main_window.coordenador_exibicao.widget_layout_ativo.visoes.values():
            if hasattr(q, 'interactor') and q.interactor and q.interactor.GetRenderWindow():
                q.interactor.GetRenderWindow().Render()

    def sincronizar_scrollbar(self, plane, nav_volume_ativo):
        if not hasattr(self, 'scrollbar') or self.scrollbar.isHidden():
            return
            
        normal = plane.GetNormal()
        axis = 0 if abs(normal[0]) > 0.5 else (1 if abs(normal[1]) > 0.5 else 2)
        b_min = axis * 2
        b_max = axis * 2 + 1
        
        bounds = nav_volume_ativo.GetBounds()
        dims = nav_volume_ativo.GetDimensions()
        
        if self.scrollbar.maximum() != dims[axis] - 1:
            self.scrollbar.setMinimum(0)
            self.scrollbar.setMaximum(max(0, dims[axis] - 1))
            
        plane_pos = plane.GetOrigin()[axis]
        if bounds[b_max] > bounds[b_min] and dims[axis] > 1:
            idx = int(round((plane_pos - bounds[b_min]) / (bounds[b_max] - bounds[b_min]) * (dims[axis] - 1)))
        else:
            idx = 0
            
        idx = max(0, min(idx, dims[axis] - 1))
        
        self.scrollbar.blockSignals(True)
        self.scrollbar.setValue(idx)
        self.scrollbar.blockSignals(False)


class FiltroDuploClique(QObject):
    def __init__(self, layout, quadrante):
        super().__init__(layout)
        self.layout = layout
        self.quadrante = quadrante
        
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            main_window = self.layout.window()
            if hasattr(main_window, 'active_quadrante'):
                main_window.active_quadrante = self.quadrante
                
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
