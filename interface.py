# -*- coding: utf-8 -*-
"""
Módulo principal de interface do usuário do Neuroviewer.
"""
import os
import time
from PyQt6.QtWidgets import (
    QMainWindow, QApplication, QToolBar, QFileDialog, QDockWidget, 
    QListWidget, QListWidgetItem, QComboBox, QSpinBox, QLabel, QToolButton, QMenu,
    QPushButton, QStyle, QProgressDialog, QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QDialogButtonBox,
    QWidget, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QAction, QIcon
import SimpleITK as sitk
import vtk
import traceback

from exibicao import CoordenadorExibicao
from carregamento.controlador_arquivos import ControladorArquivos

from ui.textos_e_estilos import (
    HTML_BOAS_VINDAS, HTML_DICAS_NAVEGACAO, PRESETS_CLINICOS
)
from exibicao.formatador_hud import formatar_texto_hud
from carregamento.threads_carregamento import ThreadCarregamento
from processamento_imagem.threads_subtracao import (
    ThreadSubtracaoLenta, ThreadSubtracaoRapida, ThreadSubtracaoSemente, ThreadSubtracaoOssea
)
from ajuda import GerenciadorAjuda
from traducoes import tr, Tradutor


class MainWindow(QMainWindow):
    """
    Classe principal responsável por organizar toda a interface do usuário (UI),
    incluindo menus, barras de ferramentas, painéis laterais e áreas de visualização.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle(tr("app_title"))
        self.resize(1300, 850)
        self.setMinimumWidth(1100)
        
        # Habilita Drag and Drop
        self.setAcceptDrops(True)
        
        # Referências de segurança de memória para o buffer DICOM
        self._sitk_img_ref = None
        self._np_view_ref = None
        self.temp_dirs = []
        self.modo_projecao_atual = "Normal"
        self.cache_series = {}
        # Dicionário de threads de pré-busca ativas: series_id -> ThreadCarregamento
        self._threads_prefetch: dict = {}
        self.controlador_arquivos = ControladorArquivos(self)
        self._layout_explicitamente_escolhido = False
        
        self.inicializar_ui()

    def inicializar_ui(self):
        """
        Estrutura e carrega todos os componentes visuais principais da janela.
        """
        # 1. Configuração do Visual Clínico Dark Mode
        self.setStyleSheet("""
            QMainWindow { background-color: #121212; color: #e0e0e0; }
            QToolBar { background-color: #1a1a1a; border-bottom: 1px solid #2d2d2d; spacing: 12px; padding: 6px; }
            QStatusBar { background-color: #1a1a1a; color: #888888; border-top: 1px solid #2d2d2d; font-family: 'Segoe UI', Arial, sans-serif; font-size: 11px; }
            QDockWidget { color: #e0e0e0; font-weight: bold; }
            QDockWidget::title { background-color: #1a1a1a; padding: 6px; border-bottom: 1px solid #2d2d2d; }
            QListWidget { background-color: #151515; color: #e0e0e0; border: 1px solid #2d2d2d; outline: 0; }
            QListWidget::item { padding: 8px 12px; border-bottom: 1px solid #222222; }
            QListWidget::item:hover { background-color: #252525; }
            QListWidget::item:selected { background-color: #2a2a2a; color: #007acc; border-left: 3px solid #007acc; }
            QPushButton, QToolButton { background-color: #2d2d2d; color: #e0e0e0; border: 1px solid #3d3d3d; border-radius: 4px; padding: 4px; }
            QPushButton:hover, QToolButton:hover { background-color: #3d3d3d; }
            QPushButton:checked, QToolButton:checked { background-color: #007acc; color: white; border: 1px solid #005a9e; }
            QToolBar QToolButton, QToolBar QPushButton { background-color: transparent; border: none; }
            QToolBar QToolButton:hover, QToolBar QPushButton:hover { background-color: #3a3a3a; border-radius: 4px; }
            QToolBar QToolButton:checked, QToolBar QPushButton:checked { background-color: #007acc; color: white; border-radius: 4px; }
            QMessageBox { background-color: #1a1a1a; color: #e0e0e0; }
            QMessageBox QLabel { color: #e0e0e0; }
            QPushButton#btn_crosshair, QPushButton#btn_sync_scroll { font-size: 35px; min-width: 58px; min-height: 58px; }
            QToolButton::menu-indicator {
                image: none;
                width: 0px;
            }
        """)

        self._construir_toolbar()
        self._construir_area_central()
        self._construir_painel_lateral()

    def _construir_toolbar(self):
        # 2. Barra de Status para feedback ao usuário
        self.statusBar().showMessage(tr("status_pronto"))

        # 3. Criação da Barra de Ferramentas (QToolBar) no Topo
        self.toolbar = QToolBar("Barra de Ferramentas Principal", self)
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)
        self.toolbar.setIconSize(QSize(36, 36))
        
        # Ação: Abrir Pasta
        self.action_abrir = QAction(tr("btn_abrir"), self)
        self.action_abrir.setIcon(QIcon(os.path.join("icones", "abrir_pasta.png")))
        self.action_abrir.setStatusTip(tr("tip_abrir"))
        self.action_abrir.triggered.connect(self.abrir_pasta)
        
        # Ação: Anonimizar e Exportar
        self.action_anonimizar = QAction(tr("btn_anonimizar"), self)
        self.action_anonimizar.setIcon(QIcon(os.path.join("icones", "anonimizar.png")))
        self.action_anonimizar.setStatusTip(tr("tip_anonimizar"))
        self.action_anonimizar.triggered.connect(self.anonimizar_e_exportar)

        # Estilo padrão para botões da barra de ferramentas
        for action in [self.action_abrir, self.action_anonimizar]:
            widget = self.toolbar.widgetForAction(action)
            if widget:
                widget.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)

        # Menu de Presets Unificado
        self.btn_presets = QToolButton(self)
        self.btn_presets.setIcon(QIcon(os.path.join("icones", "janelamento.png")))
        self.btn_presets.setIconSize(QSize(36, 36))
        self.btn_presets.setToolTip(tr("btn_presets"))
        self.btn_presets.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.menu_presets = QMenu(self.btn_presets)
        
        # Grupo Neuro
        self.action_header_neuro = self.menu_presets.addAction("[Grupo Neuro]")
        self.action_header_neuro.setEnabled(False)
        self.action_preset_angiotc = self.menu_presets.addAction("Angio-TC Vascular (WW: 600 / WL: 150)")
        self.action_preset_cerebro = self.menu_presets.addAction("Cérebro Genérico (WW: 80 / WL: 40)")
        self.action_preset_avc = self.menu_presets.addAction("AVC Isquêmico (WW: 35 / WL: 35)")
        self.action_preset_hemorragia = self.menu_presets.addAction("Hemorragia Aguda (WW: 160 / WL: 120)")
        
        self.menu_presets.addSeparator()
        
        # Grupo Corpo
        self.action_header_corpo = self.menu_presets.addAction("[Grupo Corpo]")
        self.action_header_corpo.setEnabled(False)
        self.action_preset_osso = self.menu_presets.addAction("Osso (WW: 2000 / WL: 500)")
        self.action_preset_pulmao = self.menu_presets.addAction("Pulmão (WW: 1500 / WL: -600)")
        self.action_preset_mediastino = self.menu_presets.addAction("Mediastino (WW: 350 / WL: 50)")
        self.action_preset_abdome = self.menu_presets.addAction("Abdome (WW: 400 / WL: 40)")
        
        self.menu_presets.addSeparator()
        
        # Outros
        self.action_header_outros = self.menu_presets.addAction("[Outros]")
        self.action_header_outros.setEnabled(False)
        self.action_preset_customizado = self.menu_presets.addAction("Customizado...")
        
        self.presets_clinicos = PRESETS_CLINICOS
        
        self.action_preset_angiotc.triggered.connect(lambda checked, k="angio_tc": self.on_preset_changed(k))
        self.action_preset_cerebro.triggered.connect(lambda checked, k="cerebro": self.on_preset_changed(k))
        self.action_preset_avc.triggered.connect(lambda checked, k="avc_isquemico": self.on_preset_changed(k))
        self.action_preset_hemorragia.triggered.connect(lambda checked, k="hemorragia": self.on_preset_changed(k))
        self.action_preset_osso.triggered.connect(lambda checked, k="osso": self.on_preset_changed(k))
        self.action_preset_pulmao.triggered.connect(lambda checked, k="pulmao": self.on_preset_changed(k))
        self.action_preset_mediastino.triggered.connect(lambda checked, k="mediastino": self.on_preset_changed(k))
        self.action_preset_abdome.triggered.connect(lambda checked, k="abdome": self.on_preset_changed(k))
        self.action_preset_customizado.triggered.connect(lambda checked, k="customizado": self.on_preset_changed(k))
        
        self.btn_presets.setMenu(self.menu_presets)
        
        self.btn_mip = QToolButton(self)
        self.btn_mip.setIcon(QIcon(os.path.join("icones", "mip.png")))
        self.btn_mip.setIconSize(QSize(36, 36))
        self.btn_mip.setToolTip(tr("btn_mip"))
        self.btn_mip.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        
        self.menu_mip = QMenu(self.btn_mip)
        
        for modo in ["Normal", "MIP", "MinIP", "Average"]:
            action = self.menu_mip.addAction(modo)
            action.triggered.connect(lambda checked, m=modo: self.on_projecao_changed(m))
        self.btn_mip.setMenu(self.menu_mip)
        
        # Botão Layout Dinâmico
        self.btn_layout = QToolButton(self)
        self.btn_layout.setIcon(QIcon(os.path.join("icones", "multiplas_telas.png")))
        self.btn_layout.setIconSize(QSize(42, 42))
        self.btn_layout.setToolTip(tr("btn_layout"))
        self.btn_layout.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        
        self.menu_layout = QMenu(self.btn_layout)
        
        layout_acoes = {
            "MPR Clássico (4-Up)": "MPR",
            "Comparação Lado a Lado (1x2)": "1x2",
            "Comparação Tripla (1x3)": "1x3",
            "Grade (2x2)": "2x2",
            "Grade (2x3)": "2x3"
        }
        for nome_acao, modo_acao in layout_acoes.items():
            action = self.menu_layout.addAction(nome_acao)
            action.triggered.connect(lambda checked, m=modo_acao: self.on_layout_selecionado(m))
        self.btn_layout.setMenu(self.menu_layout)
        
        # QSpinBox para Espessura
        self.spin_espessura = QSpinBox(self)
        self.spin_espessura.setSuffix(" mm")
        self.spin_espessura.setToolTip(tr("tip_espessura"))
        self.spin_espessura.setRange(0, 50)
        self.spin_espessura.setValue(0)
        self.spin_espessura.setFixedWidth(85)
        self.spin_espessura.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spin_espessura.valueChanged.connect(self.on_projecao_changed)
        
        # Botão Crosshair
        self.btn_crosshair = QPushButton("⌖", self)
        self.btn_crosshair.setObjectName("btn_crosshair")
        self.btn_crosshair.setToolTip(tr("btn_crosshair"))
        self.btn_crosshair.setCheckable(True)
        self.btn_crosshair.toggled.connect(self.on_crosshair_toggled)
        
        self.btn_regua = QToolButton(self)
        self.btn_regua.setIcon(QIcon(os.path.join("icones", "regua.png")))
        self.btn_regua.setIconSize(QSize(36, 36))
        self.btn_regua.setToolTip(tr("btn_regua"))
        self.btn_regua.setCheckable(True)
        self.btn_regua.toggled.connect(self.on_regua_toggled)
        
        self.btn_elipse = QToolButton(self)
        self.btn_elipse.setIcon(QIcon(os.path.join("icones", "elipse.png")))
        self.btn_elipse.setIconSize(QSize(36, 36))
        self.btn_elipse.setToolTip(tr("btn_elipse"))
        self.btn_elipse.setCheckable(True)
        self.btn_elipse.toggled.connect(self.on_elipse_toggled)

        self.btn_visualizacao = QToolButton(self)
        self.btn_visualizacao.setIcon(QIcon(os.path.join("icones", "visualizacao.png")))
        self.btn_visualizacao.setIconSize(QSize(44, 44))
        self.btn_visualizacao.setToolTip(tr("menu_visualizacao"))
        self.btn_visualizacao.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        
        self.menu_visualizacao = QMenu(self.btn_visualizacao)
        
        visualizacao_acoes = {
            tr("layout_1up"): "1-up",
            tr("layout_3up"): "3-up",
            tr("layout_3d"): "3d",
            tr("layout_4up"): "4-up"
        }
        for nome_acao, modo_acao in visualizacao_acoes.items():
            action = self.menu_visualizacao.addAction(nome_acao)
            action.triggered.connect(lambda checked, m=modo_acao: self.on_visualizacao_changed(m))
        self.btn_visualizacao.setMenu(self.menu_visualizacao)

        self.btn_reslice = QToolButton(self)
        self.btn_reslice.setIcon(QIcon(os.path.join("icones", "reslice.png")))
        self.btn_reslice.setIconSize(QSize(36, 36))
        self.btn_reslice.setToolTip(tr("btn_reslice"))
        self.btn_reslice.setCheckable(True)
        self.btn_reslice.toggled.connect(self.on_reslice_toggled)

        self.btn_subtracao_ossea = QToolButton(self)
        self.btn_subtracao_ossea.setIcon(QIcon(os.path.join("icones", "subtracao_ossea.png")))
        self.btn_subtracao_ossea.setIconSize(QSize(36, 36))
        self.btn_subtracao_ossea.setToolTip(tr("btn_subtracao"))
        self.btn_subtracao_ossea.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        
        self.menu_subtracao = QMenu(self.btn_subtracao_ossea)
        
        self.action_subtracao_rapida = QAction(tr("subtracao_rapida"), self)
        self.action_subtracao_rapida.triggered.connect(self.ativar_ferramenta_semente_dsa)
        
        self.action_subtracao_lenta = QAction(tr("subtracao_lenta"), self)
        self.action_subtracao_lenta.triggered.connect(self.iniciar_subtracao_lenta)
        
        self.menu_subtracao.addAction(self.action_subtracao_rapida)
        self.menu_subtracao.addAction(self.action_subtracao_lenta)
        self.btn_subtracao_ossea.setMenu(self.menu_subtracao)

        # Botão Sync Scroll
        self.btn_sync_scroll = QPushButton("🔗", self)
        self.btn_sync_scroll.setObjectName("btn_sync_scroll")
        self.btn_sync_scroll.setToolTip(tr("btn_sync"))
        self.btn_sync_scroll.setCheckable(True)
        self.btn_sync_scroll.toggled.connect(self.on_sync_scroll_toggled)

        # Menu Dissecção 3D (Box Cropping)
        self.btn_disseccao = QToolButton(self)
        self.btn_disseccao.setText(tr("btn_disseccao"))
        self.btn_disseccao.setIcon(QIcon(os.path.join("icones", "disseccao.png")))
        self.btn_disseccao.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.btn_disseccao.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        
        self.menu_disseccao = QMenu(self.btn_disseccao)
        
        self.menu_cubo = QMenu(tr("disseccao_cubo"), self.menu_disseccao)
        self.menu_cubo.setIcon(QIcon(os.path.join("icones", "cubo.png")))
        
        self.action_caixa_recorte = QAction(tr("disseccao_caixa"), self)
        self.action_caixa_recorte.setIcon(QIcon(os.path.join("icones", "tesoura.png")))
        self.action_caixa_recorte.setCheckable(True)
        self.action_caixa_recorte.triggered.connect(self.on_box_adjust_toggled)
        
        self.action_aplicar_recorte = QAction(tr("disseccao_aplicar"), self)
        self.action_aplicar_recorte.setIcon(QIcon(os.path.join("icones", "tesoura.png")))
        self.action_aplicar_recorte.triggered.connect(self.on_box_apply_clicked)
        
        self.action_resetar_3d = QAction(tr("disseccao_resetar"), self)
        self.action_resetar_3d.setIcon(QIcon(os.path.join("icones", "reset.png")))
        self.action_resetar_3d.triggered.connect(self.on_box_reset_clicked)
        
        self.menu_cubo.addAction(self.action_caixa_recorte)
        self.menu_cubo.addAction(self.action_aplicar_recorte)
        self.menu_cubo.addAction(self.action_resetar_3d)
        
        self.menu_bisturi = QMenu(tr("disseccao_bisturi"), self.menu_disseccao)
        self.menu_bisturi.setIcon(QIcon(os.path.join("icones", "bisturi.png")))
        
        self.action_bisturi_desenhar = QAction(tr("bisturi_desenhar"), self)
        self.action_bisturi_desenhar.setIcon(QIcon(os.path.join("icones", "elipse.png")))
        self.action_bisturi_desenhar.setCheckable(True)
        self.action_bisturi_desenhar.triggered.connect(self.on_bisturi_toggled)
        
        self.action_bisturi_cortar_interior = QAction(tr("bisturi_interior"), self)
        self.action_bisturi_cortar_interior.setIcon(QIcon(os.path.join("icones", "tesoura.png")))
        self.action_bisturi_cortar_interior.triggered.connect(lambda: self.on_bisturi_aplicar_clicked(cortar_fora=False))
        
        self.action_bisturi_cortar_exterior = QAction(tr("bisturi_exterior"), self)
        self.action_bisturi_cortar_exterior.setIcon(QIcon(os.path.join("icones", "tesoura.png")))
        self.action_bisturi_cortar_exterior.triggered.connect(lambda: self.on_bisturi_aplicar_clicked(cortar_fora=True))
        
        self.action_bisturi_reset = QAction(tr("bisturi_reset"), self)
        self.action_bisturi_reset.setIcon(QIcon(os.path.join("icones", "reset.png")))
        self.action_bisturi_reset.triggered.connect(self.on_bisturi_reset_clicked)
        
        self.menu_bisturi.addAction(self.action_bisturi_desenhar)
        self.menu_bisturi.addAction(self.action_bisturi_cortar_interior)
        self.menu_bisturi.addAction(self.action_bisturi_cortar_exterior)
        self.menu_bisturi.addAction(self.action_bisturi_reset)
        
        self.menu_disseccao.addMenu(self.menu_cubo)
        self.menu_disseccao.addMenu(self.menu_bisturi)
        self.btn_disseccao.setMenu(self.menu_disseccao)

        # ==============================================================================
        # ORDENAÇÃO FINAL DA BARRA DE FERRAMENTAS (LÓGICA CLÍNICA)
        # ==============================================================================
        
        # Bloco 1: Arquivos (I/O)
        self.toolbar.addAction(self.action_abrir)
        self.toolbar.addAction(self.action_anonimizar)
        self.toolbar.addSeparator()
        
        # Bloco 2: Visualização Geral
        self.toolbar.addWidget(self.btn_visualizacao)
        self.toolbar.addWidget(self.btn_layout)
        self.toolbar.addWidget(self.btn_sync_scroll)
        self.toolbar.addSeparator()
        
        # Bloco 3: Manipulação de Imagem
        self.toolbar.addWidget(self.btn_presets)
        self.toolbar.addWidget(self.btn_mip)
        self.toolbar.addWidget(self.spin_espessura)
        self.toolbar.addSeparator()
        
        # Bloco 4: Ferramentas 2D / MPR
        self.toolbar.addWidget(self.btn_reslice)
        self.toolbar.addWidget(self.btn_crosshair)
        self.toolbar.addWidget(self.btn_regua)
        self.toolbar.addWidget(self.btn_elipse)
        self.toolbar.addSeparator()
        
        # Bloco 5: Ferramentas 3D Avançadas
        self.toolbar.addWidget(self.btn_subtracao_ossea)
        self.toolbar.addWidget(self.btn_disseccao)

        # Bloco 6: Sistema de Ajuda (Empurrado para a direita)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toolbar.addWidget(spacer)
        
        css_ajuda_sobre = """
            QToolButton {
                background-color: transparent;
                color: #e0e0e0;
                font-size: 16px;
                font-weight: bold;
                padding: 8px;
            }
            QToolButton:hover {
                background-color: #2a2a2a;
                border-radius: 4px;
            }
            QToolButton::menu-indicator {
                image: none;
                width: 0px;
            }
        """
        
        self.btn_ajuda = QToolButton(self)
        self.btn_ajuda.setText(tr("btn_ajuda"))
        self.btn_ajuda.setIconSize(QSize(54, 54))
        self.btn_ajuda.setStyleSheet(css_ajuda_sobre)
        self.btn_ajuda.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        
        self.menu_ajuda = QMenu(self.btn_ajuda)
        
        topicos_diretos = [
            (tr("ajuda_abrir_lbl"), "Abrindo arquivos DICOM"),
            (tr("ajuda_anonimizador_lbl"), "Anonimizador"),
            (tr("ajuda_multitelas_lbl"), "Usando múltiplas telas"),
            (tr("ajuda_sync_lbl"), "Botão de Sincronizar (Toggle)"),
            (tr("ajuda_janela_lbl"), "Janelamento"),
            (tr("ajuda_mip_lbl"), "MIP, MinIP e Average"),
            (tr("ajuda_reslice_lbl"), "Reslice"),
            (tr("ajuda_crosshair_lbl"), "Crosshair (Mira)"),
            (tr("ajuda_regua_lbl"), "Régua"),
            (tr("ajuda_elipse_lbl"), "Elipse (ROI)")
        ]
        
        for label, topico in topicos_diretos:
            action = self.menu_ajuda.addAction(label)
            action.triggered.connect(lambda checked, t=topico: GerenciadorAjuda.mostrar_ajuda(t, self))
            
        self.menu_ajuda.addSeparator()
        
        # Submenu Subtração Óssea
        self.menu_ajuda_subtracao = QMenu(tr("btn_subtracao"), self.menu_ajuda)
        
        action_sub_rapida = self.menu_ajuda_subtracao.addAction(tr("subtracao_rapida"))
        action_sub_rapida.triggered.connect(lambda checked: GerenciadorAjuda.mostrar_ajuda("Subtração Óssea > Rápida", self))
        
        action_sub_lenta = self.menu_ajuda_subtracao.addAction(tr("subtracao_lenta"))
        action_sub_lenta.triggered.connect(lambda checked: GerenciadorAjuda.mostrar_ajuda("Subtração Óssea > Lenta", self))
        
        self.menu_ajuda.addMenu(self.menu_ajuda_subtracao)
        
        # Submenu Dissecção
        self.menu_ajuda_disseccao = QMenu(tr("btn_disseccao"), self.menu_ajuda)
        
        action_diss_cubo = self.menu_ajuda_disseccao.addAction(tr("disseccao_cubo"))
        action_diss_cubo.triggered.connect(lambda checked: GerenciadorAjuda.mostrar_ajuda("Dissecção > Cubo de Interesse", self))
        
        action_diss_bisturi = self.menu_ajuda_disseccao.addAction(tr("disseccao_bisturi"))
        action_diss_bisturi.triggered.connect(lambda checked: GerenciadorAjuda.mostrar_ajuda("Dissecção > Bisturi de Mão livre", self))
        
        self.menu_ajuda.addMenu(self.menu_ajuda_disseccao)
        
        self.btn_ajuda.setMenu(self.menu_ajuda)
        self.toolbar.addWidget(self.btn_ajuda)

        # Botão Sobre o Programa
        self.btn_sobre = QToolButton(self)
        self.btn_sobre.setText(tr("btn_sobre"))
        self.btn_sobre.setIconSize(QSize(54, 54))
        self.btn_sobre.setStyleSheet(css_ajuda_sobre)
        self.btn_sobre.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        
        self.menu_sobre = QMenu(self.btn_sobre)
        
        sobre_acoes = [
            ("Intuito do Programa", "Intuito do Programa"),
            ("Sobre o Autor", "Sobre o Autor"),
            ("Site", "Site Oficial"),
            ("Entre em contato", "Entre em Contato")
        ]
        
        for label, topico in sobre_acoes:
            trad_label = label
            if label == "Intuito do Programa": trad_label = tr("sobre_intuito_lbl")
            elif label == "Sobre o Autor": trad_label = tr("sobre_autor_lbl")
            elif label == "Site": trad_label = tr("sobre_site_lbl")
            elif label == "Entre em contato": trad_label = tr("sobre_contato_lbl")
            
            action = self.menu_sobre.addAction(trad_label)
            action.triggered.connect(lambda checked, t=topico: GerenciadorAjuda.mostrar_sobre(t, self))
            
        self.btn_sobre.setMenu(self.menu_sobre)
        self.toolbar.addWidget(self.btn_sobre)

        # Botão de Idioma na Interface (🌐 PT / EN)
        self.btn_idioma = QToolButton(self)
        self.btn_idioma.setText(tr("btn_idioma"))
        self.btn_idioma.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        
        self.menu_idioma = QMenu(self.btn_idioma)
        
        action_pt = self.menu_idioma.addAction("🇧🇷 Português")
        action_pt.triggered.connect(lambda checked: self.alterar_idioma("pt"))
        
        action_en = self.menu_idioma.addAction("🇺🇸 English")
        action_en.triggered.connect(lambda checked: self.alterar_idioma("en"))
        
        self.btn_idioma.setMenu(self.menu_idioma)
        self.toolbar.addWidget(self.btn_idioma)

    def _construir_area_central(self):
        self.coordenador_exibicao = CoordenadorExibicao(self)
        self.coordenador_exibicao.hide()
        
        self.label_boas_vindas = QLabel(self)
        self.label_boas_vindas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_boas_vindas.setText(tr("label_boas_vindas"))
        self.setCentralWidget(self.label_boas_vindas)

    def _construir_painel_lateral(self):
        self.dock_series = QDockWidget(tr("lbl_series_dock"), self)
        self.dock_series.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.dock_series.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        
        self.list_series = QListWidget(self)
        self.list_series.itemDoubleClicked.connect(self.carregar_serie_selecionada)
        self.list_series.setDragEnabled(True)
        self.list_series.setDefaultDropAction(Qt.DropAction.CopyAction)
        
        from PyQt6.QtWidgets import QWidget, QVBoxLayout
        container_lateral = QWidget()
        layout_lateral = QVBoxLayout(container_lateral)
        layout_lateral.setContentsMargins(0, 0, 0, 0)
        layout_lateral.setSpacing(0)

        layout_lateral.addWidget(self.list_series)

        self.btn_dicas = QPushButton(tr("lbl_dicas_btn"))
        self.btn_dicas.clicked.connect(self.mostrar_dicas_navegacao)
        layout_lateral.addWidget(self.btn_dicas)

        self.dock_series.setWidget(container_lateral)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock_series)

    def _popular_lista_series(self, series):
        self.list_series.clear()
        for s in series:
            s_id = s["SeriesID"]
            num_slices = len(s["Files"])
            
            desc_serie = s.get("Description", "Desconhecida")
            num_serie = s.get("Number", "N/A")
            if len(desc_serie) > 25:
                desc_serie = desc_serie[:22] + "..."
                
            texto_item = f"Série {num_serie}: {desc_serie} ({num_slices} fatias)"
            item = QListWidgetItem(texto_item)
            item.setData(Qt.ItemDataRole.UserRole, {"id": s_id, "dir": s["Directory"], "files": s["Files"]})
            item.setToolTip(f"ID Completo: {s_id}\nDescrição: {s.get('Description', 'N/A')}\nNúmero: {num_serie}\nFatias: {num_slices}\nDiretório: {s['Directory']}")
            self.list_series.addItem(item)
        
        if self.list_series.count() > 0:
            self.list_series.setCurrentRow(0)
    def mostrar_dicas_navegacao(self):
        from PyQt6.QtWidgets import QMessageBox
        msg = QMessageBox(self)
        msg.setWindowTitle(tr("lbl_dicas_btn"))
        msg.setText(tr("label_dicas_navegacao"))
        msg.exec()

    def alterar_layout_modo(self, tipo_layout: str):
        """
        Chama o coordenador de exibição para reestruturar os widgets ativos na tela.
        """


        # 1. KILL-SWITCH: Desarma os filtros de eventos antigos ANTES de destruir o layout
        if hasattr(self, 'coordenador_navegacao') and self.coordenador_navegacao:
            if hasattr(self.coordenador_navegacao, 'filtros_eventos'):
                for filtro in self.coordenador_navegacao.filtros_eventos.values():
                    if filtro:
                        filtro.ativo = False
            
            # Desativa interatores C++ antigos nativamente
            if hasattr(self, 'coordenador_exibicao') and hasattr(self.coordenador_exibicao, 'widget_layout_ativo'):
                if hasattr(self.coordenador_exibicao.widget_layout_ativo, 'visoes'):
                    for visao_nome, widget_vtk in self.coordenador_exibicao.widget_layout_ativo.visoes.items():
                        try:
                            if hasattr(widget_vtk, 'interactor') and widget_vtk.interactor:
                                widget_vtk.interactor.Disable()
                        except Exception:
                            pass

        # 2. Transição Física: Altera o layout dos widgets do PyQt6 (Isso agora destruirá os widgets antigos via deleteLater)
        self.coordenador_exibicao.definir_layout(tipo_layout)
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()

        # 3. Lógica de Hard Reset Simplificada para a volta ao MPR (4-up)
        if tipo_layout == "MPR" or tipo_layout == "Normal" or tipo_layout == "4-Up":
            if hasattr(self, 'coordenador_navegacao'):
                self.coordenador_navegacao = None
            if hasattr(self, 'vtk_image_ativa'):
                self.vtk_image_ativa = None
                
            self.statusBar().showMessage("Layout reiniciado. Selecione uma série na lista para carregar.")
            return

        # 4. Lógica para transição para os layouts de Comparação (Múltiplas Telas)
        self.statusBar().showMessage(f"Layout alterado para: {tipo_layout}")
        if hasattr(self, 'coordenador_navegacao') and self.coordenador_navegacao and hasattr(self, 'vtk_image_ativa') and self.vtk_image_ativa:
            self.coordenador_navegacao.inicializar_visualizacao(
                self.vtk_image_ativa,
                self.coordenador_exibicao.widget_layout_ativo.visoes,
                janelamento_callback=self.on_mouse_janelamento_changed,
                espessura_callback=self.on_mouse_espessura_changed
            )

    def on_visualizacao_changed(self, modo: str):
        if hasattr(self, 'coordenador_exibicao') and hasattr(self.coordenador_exibicao, 'widget_layout_ativo'):
            layout_ativo = self.coordenador_exibicao.widget_layout_ativo
            if hasattr(layout_ativo, 'aplicar_modo_visualizacao'):
                layout_ativo.aplicar_modo_visualizacao(modo)
                
                if hasattr(layout_ativo, 'visoes'):
                    for quadrante in layout_ativo.visoes.values():
                        if not quadrante.isHidden() and hasattr(quadrante, 'interactor') and quadrante.interactor:
                            try:
                                quadrante.interactor.GetRenderWindow().Render()
                            except Exception:
                                pass

    def on_preset_changed(self, chave_preset):
        """
        Callback acionado quando o preset clínico é alterado.
        Sincroniza os QSpinBoxes e aplica a calibração nas visões 2D.
        """
        try:
            # Guarda anti-crash: valida se a chave é uma string válida
            if not isinstance(chave_preset, str):
                print(f"[PRESET] Erro: argumento inválido recebido ({type(chave_preset).__name__}: {chave_preset!r}). Esperado str.")
                return
                
            if not hasattr(self, 'presets_clinicos') or chave_preset not in self.presets_clinicos:
                print(f"[PRESET] Erro: Preset '{chave_preset}' não encontrado no dicionário presets_clinicos.")
                return
                
            preset = self.presets_clinicos[chave_preset]
            ww = preset["ww"]
            wl = preset["wl"]
            nome = preset["nome"]
            
            if chave_preset == "customizado":
                self.btn_presets.setToolTip("Preset: Customizado")
                return
                
            self.btn_presets.setToolTip(f"Preset: {nome}")
            self.aplicar_ww_wl(ww, wl)
            
        except Exception as e:
            print("[ERRO CRÍTICO PRESET] Falha em on_preset_changed:")
            traceback.print_exc()
            self.statusBar().showMessage("Falha ao aplicar preset em múltiplas telas.")

    def aplicar_ww_wl(self, ww: float, wl: float):
        """
        Propaga WW/WL para TODAS as telas ativas no layout atual.

        Arquitetura de múltiplas telas:
        - Modo MPR (4-Up): aplica no coordenador_navegacao principal (visões Axial/Coronal/Sagital
          via navegador_2d.aplicar_preset) e no volume 3D via navegador_3d.
        - Modo Dinâmico (TELA 1..N): para cada tela visível, chama
          atualizar_janelamento por nome_visao no navegador_2d compartilhado.

        Toda chamada VTK é blindada com null-checks para evitar C++ segfaults
        ao acessar ponteiros de janelas já destruídas ou ocultas.
        """
        try:
            # 1. Aplica o preset nas visões 2D ativas
            if hasattr(self.coordenador_navegacao, 'navegador_2d') and self.coordenador_navegacao.navegador_2d:
                self.coordenador_navegacao.navegador_2d.aplicar_preset(ww, wl)

            # 2. Obtém o layout ativo para forçar a renderização das telas
            if hasattr(self, 'coordenador_exibicao') and hasattr(self.coordenador_exibicao, 'widget_layout_ativo'):
                layout_ativo = self.coordenador_exibicao.widget_layout_ativo
                
                if layout_ativo and hasattr(layout_ativo, 'visoes'):
                    # Identifica dinamicamente se estamos no Layout4Up
                    is_layout_4_up = (layout_ativo.__class__.__name__ == "Layout4Up")
                    
                    for nome_visao, quadrante in layout_ativo.visoes.items():
                        if hasattr(quadrante, 'interactor') and quadrante.interactor:
                            # Se for a visão 3D no layout 4-up, não aplica o render aqui para não sobrescrever o preset cinematográfico do 3D
                            if is_layout_4_up and nome_visao == "3D":
                                continue
                            quadrante.interactor.GetRenderWindow().Render()

        except Exception as e:
            print("[ERRO CRÍTICO PRESET] Falha em aplicar_ww_wl:")
            traceback.print_exc()
            self.statusBar().showMessage("Falha ao propagar preset nas telas ativas.")


    def on_mouse_espessura_changed(self, esp_val):
        self.spin_espessura.blockSignals(True)
        self.spin_espessura.setValue(int(esp_val))
        self.spin_espessura.blockSignals(False)

    def on_projecao_changed(self, modo=None):
        if modo is not None:
            self.modo_projecao_atual = modo
        else:
            modo = self.modo_projecao_atual

        esp = self.spin_espessura.value()
        
        if modo != "Normal" and esp == 0:
            self.spin_espessura.blockSignals(True)
            self.spin_espessura.setValue(20)
            self.spin_espessura.blockSignals(False)
            esp = 20
        elif modo == "Normal" and esp != 0:
            self.spin_espessura.blockSignals(True)
            self.spin_espessura.setValue(0)
            self.spin_espessura.blockSignals(False)
            esp = 0
            
        if hasattr(self, 'coordenador_navegacao') and hasattr(self.coordenador_navegacao, 'operador_projecao'):
            self.coordenador_navegacao.operador_projecao.aplicar_projecao_global(modo, esp)
            
            if hasattr(self.coordenador_navegacao, 'navegador_2d'):
                planos = self.coordenador_navegacao.navegador_2d.planos
                if 'Sagital' in planos and 'Coronal' in planos and 'Axial' in planos:
                    cx = planos['Sagital'].GetOrigin()[0]
                    cy = planos['Coronal'].GetOrigin()[1]
                    cz = planos['Axial'].GetOrigin()[2]
                    self.coordenador_navegacao.operador_projecao.atualizar_linhas(cx, cy, cz, planos)

            if hasattr(self, 'coordenador_exibicao') and hasattr(self.coordenador_exibicao, 'widget_layout_ativo') and self.coordenador_exibicao.widget_layout_ativo:
                if hasattr(self.coordenador_exibicao.widget_layout_ativo, 'visoes'):
                    for nome, quadrante in self.coordenador_exibicao.widget_layout_ativo.visoes.items():
                        quadrante.interactor.GetRenderWindow().Render()

    def on_crosshair_toggled(self, checked):
        if checked:
            if hasattr(self, 'btn_regua') and self.btn_regua.isChecked(): self.btn_regua.setChecked(False)
            if hasattr(self, 'btn_elipse') and self.btn_elipse.isChecked(): self.btn_elipse.setChecked(False)
            if hasattr(self, 'btn_reslice') and self.btn_reslice.isChecked(): self.btn_reslice.setChecked(False)
            if hasattr(self, 'action_adicionar_semente') and self.action_adicionar_semente.isChecked(): self.action_adicionar_semente.setChecked(False)
            if hasattr(self, 'action_caixa_recorte') and self.action_caixa_recorte.isChecked():
                self.action_caixa_recorte.setChecked(False)
                self.on_box_adjust_toggled(False)
            if hasattr(self, 'action_bisturi_desenhar') and self.action_bisturi_desenhar.isChecked():
                self.action_bisturi_desenhar.setChecked(False)
                self.on_bisturi_toggled(False)
        if hasattr(self.coordenador_navegacao, 'operador_crosshair'):
            if hasattr(self.coordenador_navegacao.operador_crosshair, 'ator'):
                self.coordenador_navegacao.operador_crosshair.ator.SetVisibility(checked)
            for nome, filtro in self.coordenador_navegacao.filtros_eventos.items():
                if hasattr(filtro, 'modo_crosshair'):
                    filtro.modo_crosshair = checked
            if hasattr(self, 'coordenador_exibicao') and hasattr(self.coordenador_exibicao, 'widget_layout_ativo') and self.coordenador_exibicao.widget_layout_ativo:
                if hasattr(self.coordenador_exibicao.widget_layout_ativo, 'visoes'):
                    for nome, quadrante in self.coordenador_exibicao.widget_layout_ativo.visoes.items():
                        quadrante.interactor.GetRenderWindow().Render()
 
    def on_regua_toggled(self, checked):
        if checked:
            if hasattr(self, 'btn_crosshair') and self.btn_crosshair.isChecked(): self.btn_crosshair.setChecked(False)
            if hasattr(self, 'btn_elipse') and self.btn_elipse.isChecked(): self.btn_elipse.setChecked(False)
            if hasattr(self, 'btn_reslice') and self.btn_reslice.isChecked(): self.btn_reslice.setChecked(False)
            if hasattr(self, 'action_adicionar_semente') and self.action_adicionar_semente.isChecked(): self.action_adicionar_semente.setChecked(False)
            if hasattr(self, 'action_caixa_recorte') and self.action_caixa_recorte.isChecked():
                self.action_caixa_recorte.setChecked(False)
                self.on_box_adjust_toggled(False)
            if hasattr(self, 'action_bisturi_desenhar') and self.action_bisturi_desenhar.isChecked():
                self.action_bisturi_desenhar.setChecked(False)
                self.on_bisturi_toggled(False)
        for nome, filtro in self.coordenador_navegacao.filtros_eventos.items():
            if hasattr(filtro, 'ferramenta_ativa'):
                filtro.ferramenta_ativa = "Regua" if checked else "Normal"
                
    def on_elipse_toggled(self, checked):
        if checked:
            if hasattr(self, 'btn_crosshair') and self.btn_crosshair.isChecked(): self.btn_crosshair.setChecked(False)
            if hasattr(self, 'btn_regua') and self.btn_regua.isChecked(): self.btn_regua.setChecked(False)
            if hasattr(self, 'btn_reslice') and self.btn_reslice.isChecked(): self.btn_reslice.setChecked(False)
            if hasattr(self, 'action_adicionar_semente') and self.action_adicionar_semente.isChecked(): self.action_adicionar_semente.setChecked(False)
            if hasattr(self, 'action_caixa_recorte') and self.action_caixa_recorte.isChecked():
                self.action_caixa_recorte.setChecked(False)
                self.on_box_adjust_toggled(False)
        for nome, filtro in self.coordenador_navegacao.filtros_eventos.items():
            if hasattr(filtro, 'ferramenta_ativa'):
                filtro.ferramenta_ativa = "Elipse" if checked else "Normal"

    def on_reslice_toggled(self, checked):
        if checked:
            if hasattr(self, 'btn_crosshair') and self.btn_crosshair.isChecked(): self.btn_crosshair.setChecked(False)
            if hasattr(self, 'btn_regua') and self.btn_regua.isChecked(): self.btn_regua.setChecked(False)
            if hasattr(self, 'btn_elipse') and self.btn_elipse.isChecked(): self.btn_elipse.setChecked(False)
            if hasattr(self, 'action_adicionar_semente') and self.action_adicionar_semente.isChecked(): self.action_adicionar_semente.setChecked(False)
            if hasattr(self, 'action_caixa_recorte') and self.action_caixa_recorte.isChecked():
                self.action_caixa_recorte.setChecked(False)
                self.on_box_adjust_toggled(False)
            if hasattr(self, 'action_bisturi_desenhar') and self.action_bisturi_desenhar.isChecked():
                self.action_bisturi_desenhar.setChecked(False)
                self.on_bisturi_toggled(False)
        for nome, filtro in self.coordenador_navegacao.filtros_eventos.items():
            if hasattr(filtro, 'ferramenta_ativa'):
                filtro.ferramenta_ativa = "Reslice" if checked else "Normal"
                
        if hasattr(self.coordenador_navegacao, 'operador_projecao'):
            self.coordenador_navegacao.operador_projecao.set_reslice_ativo(checked)
            
        # Força a atualização da tela
        if hasattr(self.coordenador_exibicao.widget_layout_ativo, 'visoes'):
            for quadrante in self.coordenador_exibicao.widget_layout_ativo.visoes.values():
                quadrante.interactor.GetRenderWindow().Render()

    def on_semente_toggled(self, checked):
        if checked:
            if hasattr(self, 'btn_crosshair') and self.btn_crosshair.isChecked(): self.btn_crosshair.setChecked(False)
            if hasattr(self, 'btn_regua') and self.btn_regua.isChecked(): self.btn_regua.setChecked(False)
            if hasattr(self, 'btn_elipse') and self.btn_elipse.isChecked(): self.btn_elipse.setChecked(False)
            if hasattr(self, 'btn_reslice') and self.btn_reslice.isChecked(): self.btn_reslice.setChecked(False)
            if hasattr(self, 'action_caixa_recorte') and self.action_caixa_recorte.isChecked():
                self.action_caixa_recorte.setChecked(False)
                self.on_box_adjust_toggled(False)
            if hasattr(self, 'action_bisturi_desenhar') and self.action_bisturi_desenhar.isChecked():
                self.action_bisturi_desenhar.setChecked(False)
                self.on_bisturi_toggled(False)
        
        for nome, filtro in self.coordenador_navegacao.filtros_eventos.items():
            if hasattr(filtro, 'ferramenta_ativa'):
                filtro.ferramenta_ativa = "Semente" if checked else "Normal"

    def processar_sementes(self):
        if self._sitk_img_ref is None:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Aviso", "Nenhuma série carregada para processamento.")
            return

        lista_seeds = self.coordenador_navegacao.lista_sementes
        if not lista_seeds:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Aviso", "Por favor, adicione pelo menos uma semente antes de processar.")
            return

        from PyQt6.QtWidgets import QProgressDialog
        self.progresso_subtracao = QProgressDialog("Extraindo Vasos por Sementes (Region Growing)...", None, 0, 0, self)
        self.progresso_subtracao.setWindowModality(Qt.WindowModality.WindowModal)
        self.progresso_subtracao.setCancelButton(None)
        self.progresso_subtracao.show()

        # Desativa os botões
        if hasattr(self, 'action_processar_sementes'):
            self.action_processar_sementes.setEnabled(False)

        self.thread_semente = ThreadSubtracaoSemente(self._sitk_img_ref, lista_seeds)
        self.thread_semente.resultado.connect(self.on_semente_concluida)
        self.thread_semente.erro.connect(self.on_erro_semente)
        self.thread_semente.start()

    def on_semente_concluida(self, sitk_img_result):
        if hasattr(self, 'progresso_subtracao') and self.progresso_subtracao:
            self.progresso_subtracao.close()

        if hasattr(self, 'action_processar_sementes'):
            self.action_processar_sementes.setEnabled(True)
        
        # Desativa a ferramenta após concluir
        if hasattr(self, 'action_adicionar_semente') and self.action_adicionar_semente.isChecked():
            self.action_adicionar_semente.setChecked(False)

        # Limpa as sementes visuais da tela
        if hasattr(self, 'coordenador_navegacao'):
            self.coordenador_navegacao.limpar_sementes()

        self.on_subtracao_concluida(sitk_img_result)

    def on_erro_semente(self, mensagem):
        if hasattr(self, 'progresso_subtracao') and self.progresso_subtracao:
            self.progresso_subtracao.close()
        if hasattr(self, 'action_processar_sementes'):
            self.action_processar_sementes.setEnabled(True)
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(self, "Erro de Processamento", f"Falha na extração por semente: {mensagem}")

    def limpar_sementes(self):
        if hasattr(self, 'coordenador_navegacao'):
            self.coordenador_navegacao.limpar_sementes()

    def on_sync_scroll_toggled(self, checked):
        self.sincronizacao_ativa = checked

    def is_sincronizacao_ativa(self):
        """
        Rastreia dinamicamente na interface se o botão de sincronização '🔗' está ativado.
        """
        if getattr(self, "sincronizacao_ativa", False):
            return True
            
        from PyQt6.QtWidgets import QAbstractButton
        # Varre todos os botões (QToolButton, QPushButton) filhos da MainWindow
        for btn in self.findChildren(QAbstractButton):
            texto = btn.text() or ""
            nome_objeto = btn.objectName().lower() or ""
            if "🔗" in texto or "sync" in nome_objeto or "sinc" in nome_objeto:
                if btn.isCheckable() and btn.isChecked():
                    return True
        return False

    def sincronizar_rolagem_global(self, coordenador_origem, nome_visao, delta_mm):
        
        from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
        interactors = self.findChildren(QVTKRenderWindowInteractor)
        
        for idx, interactor in enumerate(interactors):
            tem_filtro = hasattr(interactor, "filtro_dicom")
            if tem_filtro:
                filtro = interactor.filtro_dicom
                if filtro and hasattr(filtro, "parent") and filtro.parent() == coordenador_origem:
                    continue
                    
                try:
                    nav = filtro.navegador_2d if filtro else None
                    if nav:
                        plano_alvo = None
                        if nome_visao in nav.planos:
                            plano_alvo = nav.planos[nome_visao]
                        elif len(nav.planos) > 0:
                            plano_alvo = list(nav.planos.values())[0]
                            
                        if plano_alvo:
                            plano_alvo.Push(delta_mm)
                            
                            for visao_nome, rnd in nav.renderers_2d.items():
                                if hasattr(self.coordenador_exibicao.widget_layout_ativo, "visoes"):
                                    if visao_nome in self.coordenador_exibicao.widget_layout_ativo.visoes:
                                        if rnd and rnd.GetRenderWindow():
                                            rnd.ResetCameraClippingRange()
                                            rnd.GetRenderWindow().Render()
                except Exception as e:
                    print(f"[SYNC-ERR] Falha ao sincronizar tela espelho: {e}", flush=True)

    def on_box_adjust_toggled(self, checked):
        try:
            import vtk
            
            if checked:
                if hasattr(self, 'btn_crosshair') and self.btn_crosshair.isChecked(): self.btn_crosshair.setChecked(False)
                if hasattr(self, 'btn_regua') and self.btn_regua.isChecked(): self.btn_regua.setChecked(False)
                if hasattr(self, 'btn_elipse') and self.btn_elipse.isChecked(): self.btn_elipse.setChecked(False)
                if hasattr(self, 'btn_reslice') and self.btn_reslice.isChecked(): self.btn_reslice.setChecked(False)
                if hasattr(self, 'action_adicionar_semente') and self.action_adicionar_semente.isChecked(): self.action_adicionar_semente.setChecked(False)
                if hasattr(self, 'action_bisturi_desenhar') and self.action_bisturi_desenhar.isChecked():
                    self.action_bisturi_desenhar.setChecked(False)
                    self.on_bisturi_toggled(False)
                
            if not hasattr(self, 'coordenador_navegacao') or getattr(self, 'coordenador_navegacao') is None:
                return
            nav = self.coordenador_navegacao
            
            # Atualiza o estado da ferramenta nos filtros de eventos
            if hasattr(nav, 'filtros_eventos'):
                for filtro in nav.filtros_eventos.values():
                    if hasattr(filtro, 'ferramenta_ativa'):
                        if checked:
                            filtro.ferramenta_ativa = "CropBox"
                        else:
                            if filtro.ferramenta_ativa == "CropBox":
                                filtro.ferramenta_ativa = "Normal"
            
            # 1. Ativa/Desativa o Box Widget no 3D
            if hasattr(nav, 'navegador_3d') and getattr(nav, 'navegador_3d') is not None:
                if hasattr(nav.navegador_3d, 'mostrar_caixa_recorte'):
                    nav.navegador_3d.mostrar_caixa_recorte(checked)
                    
                # 2. Recupera a representação compartilhada
                rep_compartilhada = getattr(nav.navegador_3d, 'crop_representation', None)
                if rep_compartilhada is None:
                    return
                    
                layout_ativo = getattr(self.coordenador_exibicao, 'widget_layout_ativo', None)
                visoes = getattr(layout_ativo, 'visoes', {}) if layout_ativo else {}
                
                # Sub-função para renderizar todas as janelas ao interagir com qualquer widget
                def renderizar_todas_as_telas(obj, event):
                    for visao in visoes.values():
                        if hasattr(visao, 'interactor') and visao.interactor and visao.interactor.GetRenderWindow():
                            visao.interactor.GetRenderWindow().Render()
                            
                # Adiciona observer no widget 3D para renderizar as telas 2D
                if not hasattr(nav.navegador_3d, 'crop_obs_id'):
                    if hasattr(nav.navegador_3d, 'crop_widget') and nav.navegador_3d.crop_widget:
                        nav.navegador_3d.crop_obs_id = nav.navegador_3d.crop_widget.AddObserver("InteractionEvent", renderizar_todas_as_telas)
                        
                # 3. Instanciar e sincronizar os widgets 2D
                nav2d = getattr(nav, 'navegador_2d', None)
                if nav2d:
                    if not hasattr(nav2d, 'crop_widgets'):
                        nav2d.crop_widgets = {}
                        
                    for nome in ["Axial", "Coronal", "Sagital"]:
                        if nome in visoes:
                            # Cria o widget para a visão se ainda não existir
                            if nome not in nav2d.crop_widgets:
                                bw = vtk.vtkBoxWidget2()
                                bw.SetInteractor(visoes[nome].interactor)
                                bw.SetRepresentation(rep_compartilhada)
                                bw.SetRotationEnabled(False)
                                bw.AddObserver("InteractionEvent", renderizar_todas_as_telas)
                                nav2d.crop_widgets[nome] = bw
                                
                            # Ativa ou desativa conforme o estado do botão
                            if checked:
                                nav2d.crop_widgets[nome].EnabledOn()
                                # Desliga o janelamento C++ nativo
                                visoes[nome].interactor.SetInteractorStyle(vtk.vtkInteractorStyleUser())
                            else:
                                nav2d.crop_widgets[nome].EnabledOff()
                                # Restaura o estilo de navegação nativo guardado no filtro
                                if hasattr(nav, 'filtros_eventos') and nome in nav.filtros_eventos:
                                    visoes[nome].interactor.SetInteractorStyle(nav.filtros_eventos[nome].style)
                                
                # Força a atualização da tela imediatamente
                renderizar_todas_as_telas(None, None)
                
        except Exception as e:
            print(f"[CROP 3D] Erro ao ajustar caixa: {e}")

    def on_box_apply_clicked(self):
        try:
            if not hasattr(self, 'coordenador_navegacao') or getattr(self, 'coordenador_navegacao') is None:
                return
            nav = self.coordenador_navegacao
            if hasattr(nav, 'navegador_3d') and getattr(nav, 'navegador_3d') is not None:
                if hasattr(nav.navegador_3d, 'aplicar_recorte_caixa'):
                    nav.navegador_3d.aplicar_recorte_caixa()
            if hasattr(self, 'action_caixa_recorte'):
                self.action_caixa_recorte.setChecked(False)
        except Exception as e:
            print(f"[CROP 3D] Erro ao aplicar recorte: {e}")

    def on_box_reset_clicked(self):
        try:
            if not hasattr(self, 'coordenador_navegacao') or getattr(self, 'coordenador_navegacao') is None:
                return
            nav = self.coordenador_navegacao
            if hasattr(nav, 'navegador_3d') and getattr(nav, 'navegador_3d') is not None:
                if hasattr(nav.navegador_3d, 'resetar_recorte'):
                    nav.navegador_3d.resetar_recorte()
        except Exception as e:
            print(f"[CROP 3D] Erro ao resetar recorte: {e}")

    def on_bisturi_toggled(self, checked):
        try:
            if checked:
                if hasattr(self, 'btn_crosshair') and self.btn_crosshair.isChecked(): self.btn_crosshair.setChecked(False)
                if hasattr(self, 'btn_regua') and self.btn_regua.isChecked(): self.btn_regua.setChecked(False)
                if hasattr(self, 'btn_elipse') and self.btn_elipse.isChecked(): self.btn_elipse.setChecked(False)
                if hasattr(self, 'btn_reslice') and self.btn_reslice.isChecked(): self.btn_reslice.setChecked(False)
                if hasattr(self, 'action_adicionar_semente') and self.action_adicionar_semente.isChecked(): self.action_adicionar_semente.setChecked(False)
                if hasattr(self, 'action_caixa_recorte') and self.action_caixa_recorte.isChecked():
                    self.action_caixa_recorte.setChecked(False)
                    self.on_box_adjust_toggled(False)
                    
            if not hasattr(self, 'coordenador_navegacao') or getattr(self, 'coordenador_navegacao') is None:
                return
            nav = self.coordenador_navegacao
            
            # Atualiza o estado nos filtros de eventos 3D e 2D
            if hasattr(nav, 'filtros_eventos'):
                for filtro in nav.filtros_eventos.values():
                    if hasattr(filtro, 'ferramenta_ativa'):
                        if checked:
                            filtro.ferramenta_ativa = "Bisturi"
                        else:
                            if filtro.ferramenta_ativa == "Bisturi":
                                filtro.ferramenta_ativa = "Normal"
                                if hasattr(filtro, 'limpar_bisturi_tela'):
                                    filtro.limpar_bisturi_tela()
                                    
        except Exception as e:
            print(f"[BISTURI] Erro ao alternar bisturi: {e}")

    def on_bisturi_aplicar_clicked(self, cortar_fora=False):
        try:
            if not hasattr(self, 'coordenador_navegacao') or getattr(self, 'coordenador_navegacao') is None:
                return
            nav = self.coordenador_navegacao
            # Chamada para o coordenador de navegação acionar os filtros e coletar os pontos
            if hasattr(nav, 'aplicar_bisturi'):
                nav.aplicar_bisturi(cortar_fora)
            if hasattr(self, 'action_bisturi_desenhar'):
                self.action_bisturi_desenhar.setChecked(False)
                self.on_bisturi_toggled(False)
        except Exception as e:
            print(f"[BISTURI] Erro ao aplicar corte: {e}")

    def on_bisturi_reset_clicked(self):
        try:
            if not hasattr(self, 'coordenador_navegacao') or getattr(self, 'coordenador_navegacao') is None:
                return
            nav = self.coordenador_navegacao
            if hasattr(nav, 'resetar_bisturi'):
                nav.resetar_bisturi()
        except Exception as e:
            print(f"[BISTURI] Erro ao resetar corte original: {e}")

    def on_mouse_janelamento_changed(self, ww, wl):
        """
        Callback acionado quando o usuário arrasta o mouse nos viewports 2D/3D.
        Verifica a lista de presets para atualizar o ToolTip.
        """
        if not hasattr(self, 'presets_clinicos'):
            return
            
        preset_encontrado = None
        for chave, preset in self.presets_clinicos.items():
            if chave == "customizado":
                continue
            if int(ww) == int(preset["ww"]) and int(wl) == int(preset["wl"]):
                preset_encontrado = preset
                break
                
        if preset_encontrado:
            self.btn_presets.setToolTip(f"Preset: {preset_encontrado['nome']}")
        else:
            self.btn_presets.setToolTip("Preset: Customizado")

    def aplicar_preset_por_nome(self, nome_preset: str):
        """
        Aplica as calibrações de presets atualizando os widgets da toolbar de forma limpa.
        """
        try:
            if not hasattr(self, 'presets_clinicos'):
                return
                
            if nome_preset not in self.presets_clinicos:
                print(f"[PRESET] Erro: Preset '{nome_preset}' não encontrado em presets_clinicos.")
                return
                
            preset = self.presets_clinicos[nome_preset]
            self.btn_presets.setToolTip(f"Preset: {preset['nome']}")
            self.aplicar_ww_wl(preset["ww"], preset["wl"])
            
        except Exception as e:
            print("[ERRO CRÍTICO PRESET] Falha em aplicar_preset_por_nome:")
            traceback.print_exc()
            self.statusBar().showMessage("Falha ao aplicar preset em múltiplas telas.")

    def dragEnterEvent(self, event):
        """
        Trata o evento de arrastar um diretório ou arquivo sobre a janela do aplicativo.
        """
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                path = url.toLocalFile()
                if os.path.isdir(path) or path.lower().endswith((".zip", ".nrrd", ".nii.gz")):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        """
        Trata o recebimento da pasta ou arquivo arrastado pelo usuário.
        """
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                path = url.toLocalFile()
                if os.path.isdir(path):
                    self.statusBar().showMessage(f"Diretório arrastado detectado: {path}")
                    self.carregar_diretorio_dicom(path)
                    break
                elif path.lower().endswith(".zip"):
                    self.statusBar().showMessage(f"Arquivo ZIP arrastado detectado: {path}")
                    self.carregar_arquivo_zip(path)
                    break
                elif path.lower().endswith((".nrrd", ".nii.gz")):
                    self.statusBar().showMessage(f"Volume Médico arrastado detectado: {path}")
                    self.carregar_arquivo_nrrd(path)
                    break
            event.acceptProposedAction()

    def carregar_arquivo_zip(self, caminho_zip: str):
        """
        Descompacta o arquivo zip temporariamente e carrega as séries encontradas.
        """
        if not caminho_zip or not os.path.exists(caminho_zip):
            return
            
        self.statusBar().showMessage(f"Extraindo e escaneando arquivo ZIP: {caminho_zip}...")
        try:
            series, temp_dir = self.controlador_arquivos.descompactar_zip(caminho_zip)
            
            if not series or not temp_dir:
                self.statusBar().showMessage("Nenhuma série DICOM válida encontrada no arquivo ZIP.")
                return
                
            # Salva o diretório temporário para mantê-lo vivo na memória
            if not hasattr(self, "temp_dirs"):
                self.temp_dirs = []
            self.temp_dirs.append(temp_dir)
            
            # Popula as séries e carrega da mesma forma que carregar_diretorio_dicom
            self.diretorio_ativo = temp_dir.name
            self.series_carregadas = series
            
            self._popular_lista_series(series)
            
            # Carrega a primeira série do diretório em background de forma padrão e assíncrona
            self.statusBar().showMessage("Carregando série DICOM extraída do ZIP...")
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            
            primeira_serie_id = series[0]["SeriesID"]
            
            from carregamento import CoordenadorCarregamento
            coordenador = CoordenadorCarregamento()
            
            self.thread_carregamento = ThreadCarregamento(coordenador, series[0]["Files"], primeira_serie_id)
            self.thread_carregamento.resultado.connect(lambda res: self.on_carregamento_concluido(res, primeira_serie_id))
            self.thread_carregamento.erro_carregamento.connect(self.on_carregamento_erro)
            self.thread_carregamento.start()
            
        except Exception as e:
            self.statusBar().showMessage(f"Erro ao carregar arquivo ZIP: {str(e)}")
            import traceback
            traceback.print_exc()

    def iniciar_subtracao_lenta(self):
        if not hasattr(self, "series_carregadas") or not self.series_carregadas:
            QMessageBox.warning(self, "Aviso", "Nenhuma série carregada. Abra uma pasta DICOM primeiro.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Subtração Óssea Lenta (Registration)")
        dialog.setMinimumWidth(400)
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel("Selecione a Fase Angio-TC (Com Contraste):"))
        combo_angio = QComboBox()
        layout.addWidget(combo_angio)

        layout.addWidget(QLabel("Selecione a Fase Pré-Contraste (Sem Contraste):"))
        combo_sem_contraste = QComboBox()
        layout.addWidget(combo_sem_contraste)

        for s in self.series_carregadas:
            s_id = s.get("SeriesID")
            dir_serie = s.get("Directory")
            num_slices = len(s.get("Files", []))
            desc_serie = s.get("Description", "Desconhecida")
            num_serie = s.get("Number", "N/A")
            
            # Formatação amigável para o médico
            texto_item = f"Série {num_serie}: {desc_serie} ({num_slices} fatias)"
            
            # Adicionando nos dois ComboBoxes (guardando os dados necessários no userData)
            dados_serie = {"id": s_id, "dir": dir_serie, "files": s.get("Files", [])}
            combo_angio.addItem(texto_item, userData=dados_serie)
            combo_sem_contraste.addItem(texto_item, userData=dados_serie)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        layout.addWidget(btn_box)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            serie_angio = combo_angio.currentData()
            serie_sem = combo_sem_contraste.currentData()

            if serie_angio["id"] == serie_sem["id"]:
                QMessageBox.warning(self, "Aviso", "Por favor, selecione séries diferentes para o Registro.")
                return

            def get_sitk_img(serie_dados):
                s_id = serie_dados["id"]
                if hasattr(self, "cache_series") and s_id in self.cache_series:
                    return self.cache_series[s_id][1]
                reader = sitk.ImageSeriesReader()
                reader.SetFileNames(serie_dados["files"])
                return reader.Execute()

            try:
                img_angio = get_sitk_img(serie_angio)
                img_sem = get_sitk_img(serie_sem)
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao ler imagem: {str(e)}")
                return

            # Cria dialog de progresso
            self.progresso_dsa = QProgressDialog("Inicializando Registro 3D...", None, 0, 0, self)
            self.progresso_dsa.setWindowTitle("Subtração Lenta")
            self.progresso_dsa.setWindowModality(Qt.WindowModality.WindowModal)
            self.progresso_dsa.setCancelButton(None)
            self.progresso_dsa.show()

            self.thread_dsa = ThreadSubtracaoLenta(img_sem, img_angio)
            self.thread_dsa.progresso_sinal.connect(
                lambda it, val: self.progresso_dsa.setLabelText(f"Iteração {it} | Métrica: {val:.5f}")
            )
            self.thread_dsa.log_sinal.connect(self.progresso_dsa.setLabelText)
            self.thread_dsa.virtual_sinal.connect(self.on_serie_virtual_criada)
            self.thread_dsa.erro_sinal.connect(self.on_subtracao_erro)
            self.thread_dsa.start()

    def ativar_ferramenta_semente_dsa(self):
        if not hasattr(self, 'coordenador_navegacao') or not self.coordenador_navegacao: return
        self.statusBar().showMessage("Semente Vascular ativada: Clique na Aorta na visão 2D.")
        
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Subtração Rápida", "Clique no vaso de interesse na visão 2D.")
        
        for nome, filtro in self.coordenador_navegacao.filtros_eventos.items():
            if hasattr(filtro, 'ferramenta_ativa'):
                filtro.ferramenta_ativa = "SementeDSA"

    def atualizar_progresso_dsa(self, valor, mensagem):
        if hasattr(self, 'progress_dsa'):
            self.progress_dsa.setValue(valor)
            self.progress_dsa.setLabelText(mensagem)

    def iniciar_subtracao_semente(self, index_itk):
        if not hasattr(self, '_sitk_img_ref') or self._sitk_img_ref is None:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Aviso", "Nenhuma série carregada para subtração.")
            return
            
        self.statusBar().showMessage("Inundando árvore vascular...")
        
        if hasattr(self, 'btn_subtracao_ossea') and self.btn_subtracao_ossea:
            self.btn_subtracao_ossea.setEnabled(False)
            
        from PyQt6.QtWidgets import QProgressDialog
        from PyQt6.QtCore import Qt
        
        self.progress_dsa = QProgressDialog("Iniciando subtração...", "Cancelar", 0, 100, self)
        self.progress_dsa.setWindowTitle("Subtração Óssea Guiada")
        self.progress_dsa.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dsa.setAutoClose(True)
        self.progress_dsa.show()
        
        self.thread_semente = ThreadSubtracaoSemente(self._sitk_img_ref, index_itk)
        self.thread_semente.progresso_sinal.connect(self.atualizar_progresso_dsa)
        self.thread_semente.virtual_sinal.connect(self.on_serie_virtual_criada)
        self.thread_semente.log_sinal.connect(self.statusBar().showMessage)
        self.thread_semente.erro_sinal.connect(self.on_subtracao_erro)
        self.thread_semente.start()

    def on_subtracao_erro(self, msg):
        from PyQt6.QtWidgets import QMessageBox
        self.statusBar().showMessage("Erro no processamento da subtração.")
        QMessageBox.warning(self, "Erro de Processamento", f"Falha na subtração óssea:\n{msg}")
        
        # Reabilitar o botão caso tenha sido desativado
        if hasattr(self, 'btn_subtracao_ossea') and self.btn_subtracao_ossea:
            self.btn_subtracao_ossea.setEnabled(True)

    def iniciar_subtracao_rapida(self):
        if not hasattr(self, '_sitk_img_ref') or self._sitk_img_ref is None:
            QMessageBox.warning(self, "Aviso", "Nenhuma série carregada para subtração.")
            return

        self.progresso_dsa = QProgressDialog("Iniciando Morfologia Matemática...", None, 0, 0, self)
        self.progresso_dsa.setWindowTitle("Subtração Rápida")
        self.progresso_dsa.setWindowModality(Qt.WindowModality.WindowModal)
        self.progresso_dsa.setCancelButton(None)
        self.progresso_dsa.show()

        self.thread_dsa = ThreadSubtracaoRapida(self._sitk_img_ref)
        self.thread_dsa.log_sinal.connect(self.progresso_dsa.setLabelText)
        self.thread_dsa.virtual_sinal.connect(self.on_serie_virtual_criada)
        self.thread_dsa.erro_sinal.connect(self.on_subtracao_erro)
        self.thread_dsa.start()

    def on_serie_virtual_criada(self, vtk_image, sitk_image, nome):
        if hasattr(self, "progresso_dsa"):
            self.progresso_dsa.close()
            
        # Força o reset global da ferramenta e do cursor
        if hasattr(self, 'coordenador_navegacao') and self.coordenador_navegacao:
            for n, filtro in self.coordenador_navegacao.filtros_eventos.items():
                filtro.ferramenta_ativa = "Normal"
                if hasattr(filtro, 'interactor') and filtro.interactor:
                    from PyQt6.QtCore import Qt
                    filtro.interactor.setCursor(Qt.CursorShape.ArrowCursor)
                    filtro.interactor.GetRenderWindow().Render()
                    
        item = QListWidgetItem(nome)
        dados = {
            "virtual": True, 
            "vtk_image": vtk_image, 
            "sitk_image": sitk_image,
            "np_array": getattr(vtk_image, "_np_ref", None)
        }
        item.setData(Qt.ItemDataRole.UserRole, dados)
        item.setToolTip(f"Série gerada virtualmente em RAM.")
        self.list_series.addItem(item)
        
        # Seleciona o novo item na lista para visualização imediata
        self.list_series.setCurrentItem(item)
        self.carregar_serie_selecionada(item)
        
        QMessageBox.information(self, "Sucesso", f"{nome} processada e anexada na lista com sucesso!")

    def on_subtracao_erro(self, erro):
        if hasattr(self, "progresso_dsa"):
            self.progresso_dsa.close()
        QMessageBox.critical(self, "Erro", f"Ocorreu um erro durante a subtração:\n{erro}")

    def carregar_arquivo_nrrd(self, caminho_nrrd: str):
        """
        Carrega um arquivo .nrrd ou .nii.gz isolado usando SimpleITK e injeta na cena VTK (zero-copy).
        """
        if not caminho_nrrd or not os.path.exists(caminho_nrrd):
            return
            
        self.statusBar().showMessage(f"Carregando volume: {caminho_nrrd}...")
        try:
            sitk_img = self.controlador_arquivos.carregar_nrrd(caminho_nrrd)
            # Reutiliza o fluxo de injeção que já inicializa todos os mappers
            self.on_subtracao_concluida(sitk_img)
            self.statusBar().showMessage(f"Volume carregado com sucesso: {caminho_nrrd}")
        except Exception as e:
            self.statusBar().showMessage(f"Erro ao carregar volume: {str(e)}")
            import traceback
            traceback.print_exc()

    def aplicar_subtracao_ossea(self):
        if self._sitk_img_ref is None:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Aviso", "Nenhuma série carregada para subtração.")
            return

        from PyQt6.QtWidgets import QProgressDialog
        self.progresso_subtracao = QProgressDialog("Processando Subtração Óssea (IA)...", None, 0, 0, self)
        self.progresso_subtracao.setWindowModality(Qt.WindowModality.WindowModal)
        self.progresso_subtracao.setCancelButton(None)
        self.progresso_subtracao.show()

        # Desativa os botões temporariamente
        if hasattr(self, 'btn_subtracao_ossea') and self.btn_subtracao_ossea:
            self.btn_subtracao_ossea.setEnabled(False)

        self.thread_subtracao = ThreadSubtracaoOssea(self._sitk_img_ref)
        self.thread_subtracao.resultado.connect(self.on_subtracao_concluida)
        self.thread_subtracao.erro.connect(self.on_erro_subtracao)
        self.thread_subtracao.start()

    def on_erro_subtracao(self, mensagem):
        if hasattr(self, 'progresso_subtracao') and self.progresso_subtracao:
            self.progresso_subtracao.close()
        if hasattr(self, 'btn_subtracao_ossea') and self.btn_subtracao_ossea:
            self.btn_subtracao_ossea.setEnabled(True)
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(self, "Erro de Processamento", f"Falha na subtração óssea: {mensagem}")

    def on_subtracao_concluida(self, sitk_img_result):
        import numpy as np
        if hasattr(self, 'progresso_subtracao') and self.progresso_subtracao:
            self.progresso_subtracao.close()
        
        if hasattr(self, 'btn_subtracao_ossea') and self.btn_subtracao_ossea:
            self.btn_subtracao_ossea.setEnabled(True)

        # Atualiza a referência global
        self._sitk_img_ref = sitk_img_result
        np_array = sitk.GetArrayFromImage(sitk_img_result)
        
        if not np_array.flags["C_CONTIGUOUS"]:
            np_array = np.ascontiguousarray(np_array)
        self._np_view_ref = np_array # Protege GC (Garbage Collector)

        spacing = sitk_img_result.GetSpacing()
        origin = sitk_img_result.GetOrigin()
        direction = sitk_img_result.GetDirection()
        
        dims = np_array.shape # Z, Y, X
        nx, ny, nz = dims[2], dims[1], dims[0]

        # Conversão LPS -> RAS (Origem e Matriz de Direção)
        if len(origin) >= 3:
            origin_vtk = [-origin[0], -origin[1], origin[2]]
        else:
            origin_vtk = [0.0, 0.0, 0.0]

        import_vtk = vtk.vtkImageImport()
        import_vtk.SetImportVoidPointer(np_array)
        import_vtk.SetDataScalarTypeToShort()
        import_vtk.SetNumberOfScalarComponents(1)
        import_vtk.SetDataExtent(0, nx-1, 0, ny-1, 0, nz-1)
        import_vtk.SetWholeExtent(0, nx-1, 0, ny-1, 0, nz-1)
        import_vtk.SetDataSpacing(*spacing)
        import_vtk.SetDataOrigin(*origin_vtk)
        import_vtk.Update()
        
        vtk_image = import_vtk.GetOutput()
        
        # Geometria / Flip Direcional LPS -> RAS
        mat = vtk.vtkMatrix3x3()
        for r in range(3):
            for c in range(3):
                val = direction[r*3 + c]
                mat.SetElement(r, c, -val if r in (0,1) else val)
        vtk_image.SetDirectionMatrix(mat)
        
        vtk_image.ComputeBounds()
        vtk_image.GetScalarRange()

        # 1. Entrega a imagem desossada para os motores 2D e 3D do VTK
        self.coordenador_navegacao.navegador_2d.atualizar_volume(vtk_image)
        self.coordenador_navegacao.navegador_3d.atualizar_volume(vtk_image)
        
        # 2. Atualiza a Bounding Box do MIP para a nova imagem
        if hasattr(self.coordenador_navegacao, 'operador_projecao'):
            self.coordenador_navegacao.operador_projecao.bounds = vtk_image.GetBounds()
            
        # 3. Força a Placa de Vídeo a redesenhar as 4 telas instantaneamente
        if hasattr(self.coordenador_exibicao.widget_layout_ativo, "visoes"):
            for quadrante in self.coordenador_exibicao.widget_layout_ativo.visoes.values():
                quadrante.interactor.GetRenderWindow().Render()

    def anonimizar_e_exportar(self):
        """
        Exporta a série de imagens ativa aplicando a rotina de anonimização nas tags DICOM,
        ou permite exportar todas as séries carregadas em lote.
        """
        item = self.list_series.currentItem()
        if not item:
            self.statusBar().showMessage("Nenhuma série carregada para anonimizar.")
            return
            
        if not hasattr(self, "series_carregadas") or not self.series_carregadas:
            self.statusBar().showMessage("Erro: Séries não localizadas.")
            return

        dados = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(dados, dict) and dados.get("virtual"):
            QMessageBox.warning(
                self,
                "Aviso",
                "Séries virtuais processadas em RAM não podem ser anonimizadas/exportadas por este módulo."
            )
            return

        series_id = dados["id"] if isinstance(dados, dict) else dados
        serie_ativa = next((s for s in self.series_carregadas if s["SeriesID"] == series_id), None)

        from PyQt6.QtWidgets import QMessageBox, QProgressDialog, QApplication
        import os

        # Caixa de diálogo para escolha
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Exportar Séries Anonimizadas")
        msg_box.setText("Deseja anonimizar apenas a série ativa ou TODAS as séries deste diretório?")
        msg_box.setIcon(QMessageBox.Icon.Question)
        btn_ativa = msg_box.addButton("Apenas Série Ativa", QMessageBox.ButtonRole.ActionRole)
        btn_todas = msg_box.addButton("Todas as Séries", QMessageBox.ButtonRole.ActionRole)
        btn_cancelar = msg_box.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        msg_box.exec()

        escolha = msg_box.clickedButton()
        if escolha == btn_cancelar:
            return

        exportar_todas = (escolha == btn_todas)

        # Seleciona o diretório de destino
        diretorio_destino = QFileDialog.getExistingDirectory(
            self, 
            "Selecionar Diretório de Destino para Anonimização"
        )
        if not diretorio_destino:
            return

        try:
            series_alvo = self.series_carregadas if exportar_todas else [serie_ativa]
            
            # Recalcula o total de arquivos para a barra de progresso
            total_arquivos = 0
            for s in series_alvo:
                if s and "Files" in s:
                    total_arquivos += len(s["Files"])

            progresso_dialog = QProgressDialog("Lendo e anonimizando do disco...", "Cancelar", 0, total_arquivos, self)
            progresso_dialog.setWindowTitle("Processando")
            progresso_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            progresso_dialog.show()

            def progress_callback(valor):
                progresso_dialog.setValue(valor)
                QApplication.processEvents()

            def check_canceled():
                return progresso_dialog.wasCanceled()

            sucesso = self.controlador_arquivos.anonimizar_e_exportar(
                series_alvo=series_alvo,
                diretorio_ativo=getattr(self, 'diretorio_ativo', ''),
                diretorio_destino=diretorio_destino,
                exportar_todas=exportar_todas,
                progress_callback=progress_callback,
                check_canceled=check_canceled
            )

            if progresso_dialog.wasCanceled():
                self.statusBar().showMessage("Anonimização cancelada pelo usuário.")
                return

            if sucesso:
                msg = f"Anonimização concluída com sucesso em: {diretorio_destino}"
                self.statusBar().showMessage(msg)
            else:
                self.statusBar().showMessage("Falha parcial ao anonimizar os arquivos.")

        except Exception as e:
            traceback.print_exc()
            self.statusBar().showMessage(f"Erro no processo de anonimização: {str(e)}")

    def abrir_pasta(self):
        """
        Abre o seletor de arquivos de sistema para o usuário escolher o diretório DICOM.
        """
        diretorio = QFileDialog.getExistingDirectory(self, "Selecionar Pasta de Série DICOM")
        if diretorio:
            self.carregar_diretorio_dicom(diretorio)

    def carregar_diretorio_dicom(self, diretorio: str):
        """
        Efetua a varredura recursiva de pastas e o carregamento inteligente da primeira série.
        """
        t_inicio_dir = time.perf_counter()
        
        if not diretorio:
            return
            
        self.statusBar().showMessage(f"Escaneando diretório: {diretorio}...")
        try:
            from PyQt6.QtWidgets import QProgressDialog
            progresso = QProgressDialog("Analisando cabeçalhos DICOM...", "Cancelar", 0, 100, self)
            progresso.setWindowTitle("Escaneando Pasta")
            progresso.setWindowModality(Qt.WindowModality.WindowModal)
            progresso.show()

            def update_progress(atual, total):
                progresso.setMaximum(total)
                progresso.setValue(atual)
                QApplication.processEvents()
                return not progresso.wasCanceled()

            series = self.controlador_arquivos.escanear_dicom(diretorio, progress_callback=update_progress)
            
            if progresso.wasCanceled():
                self.statusBar().showMessage("Escaneamento cancelado pelo usuário.")
                return
            
            progresso.close()
            
            if not series:
                self.statusBar().showMessage("Nenhuma série DICOM válida encontrada no diretório.")
                return
            
            # Salva o diretório ativo e as séries carregadas
            self.diretorio_ativo = diretorio
            self.series_carregadas = series
            
            self._popular_lista_series(series)
            
            # Carrega a primeira série do diretório em background
            self.statusBar().showMessage("Carregando série DICOM em alta velocidade...")
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            
            primeira_serie_id = series[0]["SeriesID"]
            
            from carregamento import CoordenadorCarregamento
            coordenador = CoordenadorCarregamento()
            
            self.thread_carregamento = ThreadCarregamento(coordenador, series[0]["Files"], primeira_serie_id)
            self.thread_carregamento.resultado.connect(lambda res: self.on_carregamento_concluido(res, primeira_serie_id))
            self.thread_carregamento.erro_carregamento.connect(self.on_carregamento_erro)
            self.thread_carregamento.start()
            
        except Exception as e:
            self.statusBar().showMessage(f"Erro ao analisar diretório DICOM: {str(e)}")
            import traceback
            traceback.print_exc()

    def on_carregamento_concluido(self, resultado_tupla, series_id):
        import time
        t_concluido_inicio = time.perf_counter()
        QApplication.restoreOverrideCursor()
        vtk_image, sitk_image, np_view, prop_dicom = resultado_tupla
        
        # Salva referências para evitar Garbage Collector do buffer C++
        self._sitk_img_ref = sitk_image
        self._np_view_ref = np_view
        self.vtk_image_ativa = vtk_image
        
        # Guardião de Memória contra Garbage Collector do Python
        if not hasattr(self, "buffers_vivos"):
            self.buffers_vivos = {}
        self.buffers_vivos[series_id] = (sitk_image, np_view, vtk_image)
        
        # ——————————————————————————————————————————————————————————————————————————————————————
        # Executado obrigatoriamente ANTES de atualizar os Mappers
        try:
            from carregamento.carregamento_dicom import verificar_integridade_fase
            from vtk.util import numpy_support
            import numpy as np
            
            # Extrai a média de HU do centro
            scalars = vtk_image.GetPointData().GetScalars()
            media_hu = 0.0
            if scalars is not None:
                np_arr = numpy_support.vtk_to_numpy(scalars)
                dims = vtk_image.GetDimensions()
                np_vol = np_arr.reshape((dims[2], dims[1], dims[0]))
                cz, cy, cx = dims[2] // 2, dims[1] // 2, dims[0] // 2
                rz, ry, rx = 5, 5, 5
                sample = np_vol[
                    max(0, cz-rz):min(dims[2], cz+rz+1),
                    max(0, cy-ry):min(dims[1], cy+ry+1),
                    max(0, cx-rx):min(dims[0], cx+rx+1)
                ]
                if sample.size > 0:
                    media_hu = float(np.mean(sample))
            
            # Exibe no Console de Debug e no Status Bar
            log_auditoria = f"[AUDITORIA] Série: {series_id} | Fase Estimada: {media_hu:.2f} HU"
            print(log_auditoria)
            self.statusBar().showMessage(log_auditoria)
            
            # Identifica se a fase esperada é Pré-Contraste
            nome_fase_esperada = "Pré-Contraste" if "_PRE" in series_id or "PRE" in series_id.upper() else "Outra"
            
            # Executa a auditoria completa
            alerta = verificar_integridade_fase(vtk_image, nome_fase_esperada, series_id)
            if alerta:
                print(alerta)
                self.statusBar().showMessage(f"⚠️ {alerta}")
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "Alerta de Auditoria Médica", alerta)
        except Exception as e_aud:
            pass
            
        # a) Tempo gasto atualizando os volumes nas visões 2D e 3D.
        t_a_inicio = time.perf_counter()
        # Inicializa a renderização 2D (MPR) e 3D (Volume Rendering)
        if hasattr(self, 'coordenador_navegacao') and self.coordenador_navegacao is not None:
            # Object Pool Hot-Swapping! Não destrói os atores nem reseta câmeras
            self.coordenador_navegacao.navegador_2d.update_volume_data(vtk_image)
            t_mpr = time.perf_counter()
            pass
            
            self.coordenador_navegacao.navegador_3d.update_volume_data(vtk_image)
            t_3d = time.perf_counter()
            pass
            
            if hasattr(self.coordenador_navegacao, 'operador_projecao'):
                self.coordenador_navegacao.operador_projecao.bounds = vtk_image.GetBounds()
        else:
            # Primeira vez abrindo um exame, faz o processo completo
            from navegacao import CoordenadorNavegacao
            self.coordenador_navegacao = CoordenadorNavegacao(self)



            self.coordenador_navegacao.inicializar_visualizacao(
                vtk_image,
                self.coordenador_exibicao.widget_layout_ativo.visoes,
                janelamento_callback=self.on_mouse_janelamento_changed,
                espessura_callback=self.on_mouse_espessura_changed
            )
            t_mpr_3d = time.perf_counter()
            pass
        
        # b) Tempo gasto na extração de Metadados (HUD).
        t_b_inicio = time.perf_counter()
        # Extração dos Metadados para o HUD
        hud_texto = formatar_texto_hud(prop_dicom)
        self.coordenador_navegacao.navegador_2d.atualizar_metadados_hud(hud_texto)
        self.coordenador_navegacao.navegador_3d.atualizar_metadados_hud(hud_texto)

        try:
            if hasattr(self, 'label_boas_vindas') and self.label_boas_vindas is not None:
                self.label_boas_vindas.hide()
                self.label_boas_vindas.deleteLater()
                self.label_boas_vindas = None
        except RuntimeError:
            self.label_boas_vindas = None

        if hasattr(self, 'coordenador_exibicao'):
            self.coordenador_exibicao.show()

        # c) Tempo gasto no Hard Reset de Mappers e Câmeras.
        # Hard Reset do Cinturão Vascular para o novo carregamento
        self.modo_projecao_atual = "Normal"
        self.spin_espessura.blockSignals(True)
        self.spin_espessura.setValue(0)
        self.spin_espessura.blockSignals(False)
        if hasattr(self, 'coordenador_navegacao') and hasattr(self.coordenador_navegacao, 'operador_projecao'):
            self.coordenador_navegacao.operador_projecao.aplicar_projecao_global("Normal", 0.0)

        # Configura as visões no layout 4-up
        if hasattr(self, 'coordenador_exibicao') and hasattr(self.coordenador_exibicao, 'widget_layout_ativo'):
            self.coordenador_exibicao.show()
            self.setCentralWidget(self.coordenador_exibicao)
            
            # Start-Leve Inteligente: só força 1-up se o usuário não escolheu um layout explicitamente
            if getattr(self, '_layout_explicitamente_escolhido', False):
                self.on_visualizacao_changed("4-up")
            else:
                self.on_visualizacao_changed("1-up")

        # Aplica o preset padrão Angio-TC Vascular (WW: 600 / WL: 150)
        self.aplicar_preset_por_nome("angio_tc")
        
        # Restaura o balanço cinematográfico (Pele Translúcida e Osso) apenas no 3D
        if hasattr(self, 'coordenador_navegacao') and hasattr(self.coordenador_navegacao, 'navegador_3d'):
            self.coordenador_navegacao.navegador_3d.atualizar_transfer_functions(500.0, 150.0)
        
        # d) Tempo gasto no "Render" final (o loop final onde chama GetRenderWindow().Render()).
        t_d_inicio = time.perf_counter()
        if hasattr(self.coordenador_exibicao.widget_layout_ativo, "visoes"):
            for visao_nome, widget_vtk in self.coordenador_exibicao.widget_layout_ativo.visoes.items():
                # Removido ResetCamera() repetitivo
                if hasattr(widget_vtk, "GetRenderWindow") and widget_vtk.GetRenderWindow():
                    widget_vtk.GetRenderWindow().Render()
        t_d_fim = time.perf_counter()
        pass
        
        dim = vtk_image.GetDimensions()
        info_msg = f"Série carregada: {series_id} | Resolução: {dim[0]}x{dim[1]}x{dim[2]}"
        self.statusBar().showMessage(info_msg)

        def _deferred_update_3d():
            if hasattr(self, 'coordenador_navegacao') and hasattr(self.coordenador_navegacao, 'navegador_3d'):
                if self.coordenador_navegacao.navegador_3d.volume_ator:
                    mapper_3d = self.coordenador_navegacao.navegador_3d.volume_ator.GetMapper()
                    if mapper_3d:
                        mapper_3d.Update()
            if hasattr(self, 'coordenador_exibicao') and hasattr(self.coordenador_exibicao, 'widget_layout_ativo'):
                if hasattr(self.coordenador_exibicao.widget_layout_ativo, "visoes"):
                    if "3D" in self.coordenador_exibicao.widget_layout_ativo.visoes:
                        widget_3d = self.coordenador_exibicao.widget_layout_ativo.visoes["3D"]
                        if hasattr(widget_3d, "GetRenderWindow") and widget_3d.GetRenderWindow():
                            widget_3d.GetRenderWindow().Render()

        QTimer.singleShot(100, _deferred_update_3d)

        # Atualiza o cache e dispara cache preditivo da próxima série
        if series_id in self.cache_series:
            del self.cache_series[series_id]
        self.cache_series[series_id] = resultado_tupla
        if len(self.cache_series) > 3:
            del self.cache_series[next(iter(self.cache_series))]
            
        self._iniciar_cache_preditivo(series_id)
        
    def _iniciar_cache_preditivo(self, series_id_atual):
        """Inicia pré-carregamento da próxima série em background com IdlePriority."""
        if not hasattr(self, 'list_series'): return

        prox_item = None
        for i in range(self.list_series.count()):
            item = self.list_series.item(i)
            dados = item.data(Qt.ItemDataRole.UserRole)
            if dados and dados.get("id") == series_id_atual:
                if i + 1 < self.list_series.count():
                    prox_item = self.list_series.item(i + 1)
                break

        if not prox_item:
            return

        dados_prox = prox_item.data(Qt.ItemDataRole.UserRole)
        if not dados_prox:
            return

        prox_id  = dados_prox.get("id")
        arquivos = dados_prox.get("files")

        # Já está no cache de memória ou já existe uma thread de prefetch
        if not prox_id or not arquivos:
            return
        if prox_id in self.cache_series:
            pass
            return
        if prox_id in self._threads_prefetch:
            pass
            return

        from carregamento import CoordenadorCarregamento
        coordenador = CoordenadorCarregamento()
        thread = ThreadCarregamento(coordenador, arquivos, prox_id, prefetch=True)
        thread.prefetch_concluido.connect(self._on_prefetch_concluido)
        thread.finished.connect(lambda t=prox_id: self._threads_prefetch.pop(t, None))

        self._threads_prefetch[prox_id] = thread

        # IdlePriority: o SO só cede CPU quando nenhum outro processo precisa
        thread.start(QThread.Priority.IdlePriority)
        pass

    def _on_prefetch_concluido(self, resultado_tupla, series_id):
        """Recebe o resultado do prefetch e deposita no cache de memória."""
        pass
        if series_id in self.cache_series:
            del self.cache_series[series_id]
        self.cache_series[series_id] = resultado_tupla
        if len(self.cache_series) > 3:
            del self.cache_series[next(iter(self.cache_series))]
        # Remove da fila de prefetch
        self._threads_prefetch.pop(series_id, None)

    def _on_cache_silencioso_concluido(self, resultado_tupla, series_id):
        if series_id in self.cache_series:
            del self.cache_series[series_id]
        self.cache_series[series_id] = resultado_tupla
        if len(self.cache_series) > 3:
            del self.cache_series[next(iter(self.cache_series))]

    def on_layout_selecionado(self, modo: str):
        if not hasattr(self, 'coordenador_exibicao'):
            return
            
        self._layout_explicitamente_escolhido = True
        self.alterar_layout_modo(modo)
        
        # Sincroniza o Modo de Visualização para expor todos os quadrantes do layout
        if modo == "MPR" or modo in ["1x2", "1x3", "2x2", "2x3"]:
            self.on_visualizacao_changed("4-up")
        
        # Força o repinte do fundo nas visões ativas
        if hasattr(self.coordenador_exibicao.widget_layout_ativo, "visoes"):
            for visao_nome, widget_vtk in self.coordenador_exibicao.widget_layout_ativo.visoes.items():
                if hasattr(widget_vtk, "GetRenderWindow") and widget_vtk.GetRenderWindow():
                    widget_vtk.GetRenderWindow().Render()

    def on_carregamento_erro(self, msg):
        QApplication.restoreOverrideCursor()
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.warning(self, "Aviso de Carregamento", f"Falha ao carregar a série:\n{msg}")
        self.statusBar().showMessage(f"Erro durante carregamento multithread.")

    def carregar_serie_virtual(self, vtk_image, sitk_image, np_array):
        # Salva referências para evitar Garbage Collector do buffer C++
        self._sitk_img_ref = sitk_image
        self._np_view_ref = np_array
        
        # Entrega a imagem desossada para os motores 2D e 3D do VTK
        if hasattr(self, 'coordenador_navegacao') and self.coordenador_navegacao is not None:
            self.coordenador_navegacao.navegador_2d.update_volume_data(vtk_image)
            self.coordenador_navegacao.navegador_3d.update_volume_data(vtk_image)
            
            if hasattr(self.coordenador_navegacao, 'operador_projecao'):
                self.coordenador_navegacao.operador_projecao.bounds = vtk_image.GetBounds()
        else:
            from navegacao import CoordenadorNavegacao
            self.coordenador_navegacao = CoordenadorNavegacao(self)
            self.coordenador_navegacao.inicializar_visualizacao(
                vtk_image,
                self.coordenador_exibicao.widget_layout_ativo.visoes,
                janelamento_callback=self.on_mouse_janelamento_changed,
                espessura_callback=self.on_mouse_espessura_changed
            )
            
        # Hard Reset do Cinturão Vascular para o novo carregamento
        self.modo_projecao_atual = "Normal"
        self.spin_espessura.blockSignals(True)
        self.spin_espessura.setValue(0)
        self.spin_espessura.blockSignals(False)
        if hasattr(self, 'coordenador_navegacao') and hasattr(self.coordenador_navegacao, 'operador_projecao'):
            self.coordenador_navegacao.operador_projecao.aplicar_projecao_global("Normal", 0.0)

        # Configura as visões no layout 4-up
        if hasattr(self, 'coordenador_exibicao') and hasattr(self.coordenador_exibicao, 'widget_layout_ativo'):
            self.coordenador_exibicao.show()
            self.setCentralWidget(self.coordenador_exibicao)
            
            # Start-Leve Inteligente: só força 1-up se o usuário não escolheu um layout explicitamente
            if getattr(self, '_layout_explicitamente_escolhido', False):
                self.on_visualizacao_changed("4-up")
            else:
                self.on_visualizacao_changed("1-up")

        # Aplica o preset padrão Angio-TC Vascular (WW: 600 / WL: 150)
        self.aplicar_preset_por_nome("angio_tc")
        
        # Aplica o preset 3D específico para DSA
        if hasattr(self, 'coordenador_navegacao') and self.coordenador_navegacao is not None:
            if hasattr(self.coordenador_navegacao, 'navegador_3d') and self.coordenador_navegacao.navegador_3d is not None:
                self.coordenador_navegacao.navegador_3d.aplicar_preset_dsa()
        
        # Renderização Final
        if hasattr(self.coordenador_exibicao.widget_layout_ativo, "visoes"):
            for visao_nome, widget_vtk in self.coordenador_exibicao.widget_layout_ativo.visoes.items():
                if hasattr(widget_vtk, "GetRenderWindow") and widget_vtk.GetRenderWindow():
                    widget_vtk.GetRenderWindow().Render()
                    
        def _deferred_update_3d():
            if hasattr(self, 'coordenador_navegacao') and hasattr(self.coordenador_navegacao, 'navegador_3d'):
                if self.coordenador_navegacao.navegador_3d.volume_ator:
                    mapper_3d = self.coordenador_navegacao.navegador_3d.volume_ator.GetMapper()
                    if mapper_3d:
                        mapper_3d.Update()
            if hasattr(self, 'coordenador_exibicao') and hasattr(self.coordenador_exibicao, 'widget_layout_ativo'):
                if hasattr(self.coordenador_exibicao.widget_layout_ativo, "visoes"):
                    if "3D" in self.coordenador_exibicao.widget_layout_ativo.visoes:
                        widget_3d = self.coordenador_exibicao.widget_layout_ativo.visoes["3D"]
                        if hasattr(widget_3d, "GetRenderWindow") and widget_3d.GetRenderWindow():
                            widget_3d.GetRenderWindow().Render()

        QTimer.singleShot(100, _deferred_update_3d)
        
        self.statusBar().showMessage(f"Série Virtual carregada com sucesso.")
 
    def carregar_serie_selecionada(self, item):
        """
        Carrega dinamicamente a série selecionada no list widget de forma assíncrona.
        
        Se a série já estiver no cache de memória (incluindo por prefetch), é instantâneo.
        Se estiver sendo carregada em background (prefetch), promove a prioridade da thread.
        """
        if not item or not hasattr(self, "series_carregadas") or not self.series_carregadas:
            return
 
        dados = item.data(Qt.ItemDataRole.UserRole)
        if not dados or not isinstance(dados, dict):
            return
            
        # Hot-swapping de Série Virtual
        if dados.get("virtual"):
            self.statusBar().showMessage("Carregando Série Virtual instantaneamente...")
            self.on_subtracao_concluida(dados["sitk_image"])
            
            nome_serie = item.text()
            if "[SUB]" in nome_serie:
                if hasattr(self, 'coordenador_navegacao') and hasattr(self.coordenador_navegacao, 'navegador_3d'):
                    self.coordenador_navegacao.navegador_3d.aplicar_preset_angio()
            
            return

        series_id = dados.get("id")
        diretorio_serie = dados.get("dir")

        if not series_id or not diretorio_serie:
            self.statusBar().showMessage("Erro: Dados da série inválidos no item.")
            return

        # 1. Cache de memória: entrega instantânea
        if series_id in getattr(self, 'cache_series', {}):
            self.statusBar().showMessage("âš¡ Série em CACHE! Troca instantânea.")
            self.on_carregamento_concluido(self.cache_series[series_id], series_id)
            return

        # 2. Prefetch em andamento: promove para HighPriority e aguarda
        if series_id in self._threads_prefetch:
            thread_bg = self._threads_prefetch[series_id]
            if thread_bg.isRunning():
                pass
                thread_bg.setPriority(QThread.Priority.HighPriority)
                self.statusBar().showMessage("ðŸ”„ Acelerando carregamento em background...")
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

                # Redireciona o sinal de prefetch para a tela principal e aguarda
                thread_bg.prefetch_concluido.disconnect()
                thread_bg.prefetch_concluido.connect(
                    lambda res, sid=series_id: self._on_prefetch_promovido(res, sid)
                )
                return

        # 3. Série não está no cache nem em prefetch: carregamento normal
        self.statusBar().showMessage("Carregando série...")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        if hasattr(self, 'coordenador_navegacao'):
            self.coordenador_navegacao.navegador_2d.atualizar_metadados_hud("CARREGANDO SÃ‰RIE ALTA RESOLUÃ‡ÃƒO...")
            self.coordenador_navegacao.navegador_3d.atualizar_metadados_hud("CARREGANDO SÃ‰RIE ALTA RESOLUÃ‡ÃƒO...")

        from carregamento import CoordenadorCarregamento
        coordenador = CoordenadorCarregamento()
        arquivos = dados.get("files")
        print(f"DEBUG: Carregando Série {dados['id']} do diretório {dados['dir']}")
        self.thread_carregamento = ThreadCarregamento(coordenador, arquivos, series_id)
        self.thread_carregamento.resultado.connect(lambda res: self.on_carregamento_concluido(res, series_id))
        self.thread_carregamento.erro_carregamento.connect(self.on_carregamento_erro)
        self.thread_carregamento.start()

    def _on_prefetch_promovido(self, resultado_tupla, series_id):
        """Chamado quando uma thread de prefetch promovida termina."""
        QApplication.restoreOverrideCursor()
        self._on_prefetch_concluido(resultado_tupla, series_id)  # deposita no cache
        self.on_carregamento_concluido(resultado_tupla, series_id)  # exibe na tela

    def carregar_serie_no_quadrante(self, dados_serie, quadrante):
        pass
        t_inicio_dd = time.perf_counter()
        
        series_id = dados_serie.get("id")
        
        if series_id in getattr(self, 'cache_series', {}):
            tupla = self.cache_series[series_id]
            vtk_image = tupla[0]
            prop_dicom = tupla[3]
            nome_visao = quadrante.label.text()
            
            tempo_antes = time.perf_counter()
            if getattr(self, 'coordenador_navegacao', None) is None:
                from navegacao import CoordenadorNavegacao
                self.coordenador_navegacao = CoordenadorNavegacao(self)
                # Como é o primeiro carregamento após o reset, inicializa a arquitetura inteira
                self.coordenador_navegacao.inicializar_visualizacao(
                    vtk_image,
                    self.coordenador_exibicao.widget_layout_ativo.visoes,
                    janelamento_callback=self.on_mouse_janelamento_changed,
                    espessura_callback=self.on_mouse_espessura_changed
                )
                # Garante a cor 3D cinematográfica e interrompe
                if hasattr(self.coordenador_navegacao, 'navegador_3d'):
                    self.coordenador_navegacao.navegador_3d.atualizar_transfer_functions(500.0, 150.0)
                
                # Preserva a memória da tela no drag & drop
                win = self
                while win is not None and not hasattr(win, "buffers_vivos"):
                    win = win.parent() if hasattr(win, "parent") else None
                if win is not None:
                    win.buffers_vivos[nome_visao] = (tupla[1], tupla[2], vtk_image)
                elif not hasattr(self, "buffers_vivos"):
                    self.buffers_vivos = {nome_visao: (tupla[1], tupla[2], vtk_image)}
                return
                
            self.coordenador_navegacao.inicializar_tela_dinamica(nome_visao, vtk_image, quadrante, self.on_mouse_janelamento_changed, self.on_mouse_espessura_changed)
            tempo_final = time.perf_counter()
            
            self.coordenador_navegacao.navegador_2d.meta_actors[nome_visao].SetInput(formatar_texto_hud(prop_dicom))

            # --- GARANTE A PRESERVAÇÃO DE MEMÓRIA DA TELA NO DRAG & DROP ---
            win = self
            while win is not None and not hasattr(win, "buffers_vivos"):
                win = win.parent() if hasattr(win, "parent") else None
            if win is not None:
                win.buffers_vivos[nome_visao] = (tupla[1], tupla[2], vtk_image)
            elif not hasattr(self, "buffers_vivos"):
                self.buffers_vivos = {nome_visao: (tupla[1], tupla[2], vtk_image)}
            
            import gc
            QTimer.singleShot(100, gc.collect)
            return
            
        arquivos = dados_serie.get("files")
        if not arquivos:
            return
            
        from carregamento import CoordenadorCarregamento
        coordenador = CoordenadorCarregamento()
        
        thread_isolada = ThreadCarregamento(coordenador, arquivos, series_id)
        if not hasattr(self, 'threads_isoladas'): self.threads_isoladas = []
        self.threads_isoladas.append(thread_isolada)
        
        def on_loaded(res, q=quadrante):
            nome_visao = q.label.text()
            vtk_image, sitk_image, np_view, prop_dicom = res
            
            tempo_antes = time.perf_counter()
            if getattr(self, 'coordenador_navegacao', None) is None:
                from navegacao import CoordenadorNavegacao
                self.coordenador_navegacao = CoordenadorNavegacao(self)
                # Como é o primeiro carregamento após o reset, inicializa a arquitetura inteira
                self.coordenador_navegacao.inicializar_visualizacao(
                    vtk_image,
                    self.coordenador_exibicao.widget_layout_ativo.visoes,
                    janelamento_callback=self.on_mouse_janelamento_changed,
                    espessura_callback=self.on_mouse_espessura_changed
                )
                # Garante a cor 3D cinematográfica e interrompe
                if hasattr(self.coordenador_navegacao, 'navegador_3d'):
                    self.coordenador_navegacao.navegador_3d.atualizar_transfer_functions(500.0, 150.0)
                
                # Preserva a memória da tela no drag & drop
                win = self
                while win is not None and not hasattr(win, "buffers_vivos"):
                    win = win.parent() if hasattr(win, "parent") else None
                if win is not None:
                    win.buffers_vivos[nome_visao] = (sitk_image, np_view, vtk_image)
                elif not hasattr(self, "buffers_vivos"):
                    self.buffers_vivos = {nome_visao: (sitk_image, np_view, vtk_image)}
                return
                
            self.coordenador_navegacao.inicializar_tela_dinamica(nome_visao, vtk_image, q, self.on_mouse_janelamento_changed, self.on_mouse_espessura_changed)
            tempo_final = time.perf_counter()
            
            self.coordenador_navegacao.navegador_2d.meta_actors[nome_visao].SetInput(formatar_texto_hud(prop_dicom))
            
            # --- GARANTE A PRESERVAÇÃO DE MEMÓRIA DA TELA NO DRAG & DROP ---
            win = self
            while win is not None and not hasattr(win, "buffers_vivos"):
                win = win.parent() if hasattr(win, "parent") else None
                
            if win is not None:
                win.buffers_vivos[nome_visao] = (sitk_image, np_view, vtk_image)
            elif not hasattr(self, "buffers_vivos"):
                self.buffers_vivos = {nome_visao: (sitk_image, np_view, vtk_image)}
                
            import gc
            QTimer.singleShot(100, gc.collect)
            
        thread_isolada.resultado.connect(on_loaded)
        thread_isolada.finished.connect(lambda t=thread_isolada: self.threads_isoladas.remove(t) if t in self.threads_isoladas else None)
        thread_isolada.start()

    def alterar_idioma(self, sigla_idioma: str):
        Tradutor().definir_idioma(sigla_idioma)
        from PyQt6.QtWidgets import QMessageBox
        
        msg = QMessageBox(self)
        msg.setWindowTitle(tr("msg_aviso_reinicio"))
        msg.setText(tr("msg_idioma_alterado"))
        
        msg.exec()
