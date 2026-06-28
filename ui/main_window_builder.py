# -*- coding: utf-8 -*-
import os
from PyQt6.QtWidgets import (
    QToolBar, QMenu, QToolButton, QSpinBox, QPushButton, QWidget,
    QSizePolicy, QDockWidget, QListWidget, QVBoxLayout, QLabel, QDialog, QDialogButtonBox,
    QComboBox, QApplication
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QAction
from traducoes import tr
from ajuda import GerenciadorAjuda
from ui.custom_widgets import LabelImagemResponsiva
from core.utils_profiling import profiler_time
from ui.textos_e_estilos import PRESETS_CLINICOS

class UIBuilder:
    @staticmethod
    @profiler_time
    def setup_ui(main_window):
        # 1. Configuração do Visual Clínico Dark Mode
        main_window.setStyleSheet("""
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

        UIBuilder._construir_toolbar(main_window)
        UIBuilder._construir_area_central(main_window)
        UIBuilder._construir_painel_lateral(main_window)

    @staticmethod
    def _construir_toolbar(main_window):
        # 2. Barra de Status para feedback ao usuário
        main_window.statusBar().showMessage(tr("status_pronto"))

        # 3. Criação da Barra de Ferramentas (QToolBar) no Topo
        main_window.toolbar = QToolBar("Barra de Ferramentas Principal", main_window)
        main_window.toolbar.setMovable(False)
        main_window.addToolBar(main_window.toolbar)
        main_window.toolbar.setIconSize(QSize(36, 36))
        
        # Ação: Abrir Pasta
        main_window.action_abrir = QAction(tr("btn_abrir"), main_window)
        main_window.action_abrir.setIcon(QIcon(os.path.join("icones", "abrir_pasta.png")))
        main_window.action_abrir.setStatusTip(tr("tip_abrir"))
        main_window.action_abrir.triggered.connect(main_window.abrir_pasta_dialog)
        
        # Ação: Anonimizar e Exportar
        main_window.action_anonimizar = QAction(tr("btn_anonimizar"), main_window)
        main_window.action_anonimizar.setIcon(QIcon(os.path.join("icones", "anonimizar.png")))
        main_window.action_anonimizar.setStatusTip(tr("tip_anonimizar"))
        main_window.action_anonimizar.triggered.connect(main_window.iniciar_exportacao_anonimizada)

        # Estilo padrão para botões da barra de ferramentas
        for action in [main_window.action_abrir, main_window.action_anonimizar]:
            widget = main_window.toolbar.widgetForAction(action)
            if widget:
                widget.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)

        # Menu de Presets Unificado
        main_window.btn_presets = QToolButton(main_window)
        main_window.btn_presets.setIcon(QIcon(os.path.join("icones", "janelamento.png")))
        main_window.btn_presets.setIconSize(QSize(36, 36))
        main_window.btn_presets.setToolTip(tr("btn_presets"))
        main_window.btn_presets.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        main_window.menu_presets = QMenu(main_window.btn_presets)
        
        # Grupo Neuro
        main_window.action_header_neuro = main_window.menu_presets.addAction("[Grupo Neuro]")
        main_window.action_header_neuro.setEnabled(False)
        main_window.action_preset_angiotc = main_window.menu_presets.addAction("Angio-TC Vascular (WW: 600 / WL: 150)")
        main_window.action_preset_cerebro = main_window.menu_presets.addAction("Cérebro Genérico (WW: 80 / WL: 40)")
        main_window.action_preset_avc = main_window.menu_presets.addAction("AVC Isquêmico (WW: 35 / WL: 35)")
        main_window.action_preset_hemorragia = main_window.menu_presets.addAction("Hemorragia Aguda (WW: 160 / WL: 120)")
        
        main_window.menu_presets.addSeparator()
        
        # Grupo Corpo
        main_window.action_header_corpo = main_window.menu_presets.addAction("[Grupo Corpo]")
        main_window.action_header_corpo.setEnabled(False)
        main_window.action_preset_osso = main_window.menu_presets.addAction("Osso (WW: 2000 / WL: 500)")
        main_window.action_preset_pulmao = main_window.menu_presets.addAction("Pulmão (WW: 1500 / WL: -600)")
        main_window.action_preset_mediastino = main_window.menu_presets.addAction("Mediastino (WW: 350 / WL: 50)")
        main_window.action_preset_abdome = main_window.menu_presets.addAction("Abdome (WW: 400 / WL: 40)")
        
        main_window.menu_presets.addSeparator()
        
        # Outros
        main_window.action_header_outros = main_window.menu_presets.addAction("[Outros]")
        main_window.action_header_outros.setEnabled(False)
        main_window.action_preset_customizado = main_window.menu_presets.addAction("Customizado...")
        
        main_window.presets_clinicos = PRESETS_CLINICOS
        
        main_window.action_preset_angiotc.triggered.connect(lambda checked, k="angio_tc": main_window.gerenciador_ferramentas.on_preset_changed(k))
        main_window.action_preset_cerebro.triggered.connect(lambda checked, k="cerebro": main_window.gerenciador_ferramentas.on_preset_changed(k))
        main_window.action_preset_avc.triggered.connect(lambda checked, k="avc_isquemico": main_window.gerenciador_ferramentas.on_preset_changed(k))
        main_window.action_preset_hemorragia.triggered.connect(lambda checked, k="hemorragia": main_window.gerenciador_ferramentas.on_preset_changed(k))
        main_window.action_preset_osso.triggered.connect(lambda checked, k="osso": main_window.gerenciador_ferramentas.on_preset_changed(k))
        main_window.action_preset_pulmao.triggered.connect(lambda checked, k="pulmao": main_window.gerenciador_ferramentas.on_preset_changed(k))
        main_window.action_preset_mediastino.triggered.connect(lambda checked, k="mediastino": main_window.gerenciador_ferramentas.on_preset_changed(k))
        main_window.action_preset_abdome.triggered.connect(lambda checked, k="abdome": main_window.gerenciador_ferramentas.on_preset_changed(k))
        main_window.action_preset_customizado.triggered.connect(lambda checked, k="customizado": main_window.gerenciador_ferramentas.on_preset_changed(k))
        
        main_window.btn_presets.setMenu(main_window.menu_presets)
        
        main_window.btn_mip = QToolButton(main_window)
        main_window.btn_mip.setIcon(QIcon(os.path.join("icones", "mip.png")))
        main_window.btn_mip.setIconSize(QSize(36, 36))
        main_window.btn_mip.setToolTip(tr("btn_mip"))
        main_window.btn_mip.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        
        main_window.menu_mip = QMenu(main_window.btn_mip)
        
        for modo in ["Normal", "MIP", "MinIP", "Average"]:
            action = main_window.menu_mip.addAction(modo)
            action.triggered.connect(lambda checked, m=modo: main_window.gerenciador_ferramentas.on_projecao_changed(m))
        main_window.btn_mip.setMenu(main_window.menu_mip)
        
        # Botão Layout Dinâmico
        main_window.btn_layout = QToolButton(main_window)
        main_window.btn_layout.setIcon(QIcon(os.path.join("icones", "multiplas_telas.png")))
        main_window.btn_layout.setIconSize(QSize(42, 42))
        main_window.btn_layout.setToolTip(tr("btn_layout"))
        main_window.btn_layout.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        
        main_window.menu_layout = QMenu(main_window.btn_layout)
        
        layout_acoes = {
            "MPR Clássico (4-Up)": "MPR",
            "Comparação Lado a Lado (1x2)": "1x2",
            "Comparação Tripla (1x3)": "1x3",
            "Grade (2x2)": "2x2",
            "Grade (2x3)": "2x3"
        }
        for nome_acao, modo_acao in layout_acoes.items():
            action = main_window.menu_layout.addAction(nome_acao)
            action.triggered.connect(lambda checked, m=modo_acao: main_window.gerenciador_layouts.on_layout_selecionado(m))
        main_window.btn_layout.setMenu(main_window.menu_layout)
        
        # QSpinBox para Espessura
        main_window.spin_espessura = QSpinBox(main_window)
        main_window.spin_espessura.setSuffix(" mm")
        main_window.spin_espessura.setToolTip(tr("tip_espessura"))
        main_window.spin_espessura.setRange(0, 50)
        main_window.spin_espessura.setValue(0)
        main_window.spin_espessura.setFixedWidth(85)
        main_window.spin_espessura.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_window.spin_espessura.valueChanged.connect(main_window.gerenciador_ferramentas.on_projecao_changed)
        
        # Botão Crosshair
        main_window.btn_crosshair = QPushButton("⌖", main_window)
        main_window.btn_crosshair.setObjectName("btn_crosshair")
        main_window.btn_crosshair.setToolTip(tr("btn_crosshair"))
        main_window.btn_crosshair.setCheckable(True)
        main_window.btn_crosshair.toggled.connect(main_window.gerenciador_ferramentas.on_crosshair_toggled)
        
        main_window.btn_regua = QToolButton(main_window)
        main_window.btn_regua.setIcon(QIcon(os.path.join("icones", "regua.png")))
        main_window.btn_regua.setIconSize(QSize(36, 36))
        main_window.btn_regua.setToolTip(tr("btn_regua"))
        main_window.btn_regua.setCheckable(True)
        main_window.btn_regua.toggled.connect(main_window.gerenciador_ferramentas.on_regua_toggled)
        
        main_window.btn_elipse = QToolButton(main_window)
        main_window.btn_elipse.setIcon(QIcon(os.path.join("icones", "elipse.png")))
        main_window.btn_elipse.setIconSize(QSize(36, 36))
        main_window.btn_elipse.setToolTip(tr("btn_elipse"))
        main_window.btn_elipse.setCheckable(True)
        main_window.btn_elipse.toggled.connect(main_window.gerenciador_ferramentas.on_elipse_toggled)

        main_window.btn_visualizacao = QToolButton(main_window)
        main_window.btn_visualizacao.setIcon(QIcon(os.path.join("icones", "visualizacao.png")))
        main_window.btn_visualizacao.setIconSize(QSize(44, 44))
        main_window.btn_visualizacao.setToolTip(tr("menu_visualizacao"))
        main_window.btn_visualizacao.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        
        main_window.menu_visualizacao = QMenu(main_window.btn_visualizacao)
        
        visualizacao_acoes = {
            tr("layout_1up"): "1-up",
            tr("layout_3up"): "3-up",
            tr("layout_3d"): "3d",
            tr("layout_4up"): "4-up"
        }
        for nome_acao, modo_acao in visualizacao_acoes.items():
            action = main_window.menu_visualizacao.addAction(nome_acao)
            action.triggered.connect(lambda checked, m=modo_acao: main_window.gerenciador_layouts.on_visualizacao_changed(m))
        main_window.btn_visualizacao.setMenu(main_window.menu_visualizacao)

        main_window.btn_reslice = QToolButton(main_window)
        main_window.btn_reslice.setIcon(QIcon(os.path.join("icones", "reslice.png")))
        main_window.btn_reslice.setIconSize(QSize(36, 36))
        main_window.btn_reslice.setToolTip(tr("btn_reslice"))
        main_window.btn_reslice.setCheckable(True)
        main_window.btn_reslice.toggled.connect(main_window.gerenciador_ferramentas.on_reslice_toggled)

        main_window.btn_subtracao_ossea = QToolButton(main_window)
        main_window.btn_subtracao_ossea.setIcon(QIcon(os.path.join("icones", "subtracao_ossea.png")))
        main_window.btn_subtracao_ossea.setIconSize(QSize(36, 36))
        main_window.btn_subtracao_ossea.setToolTip(tr("btn_subtracao"))
        main_window.btn_subtracao_ossea.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        
        main_window.menu_subtracao = QMenu(main_window.btn_subtracao_ossea)
        
        main_window.action_subtracao_rapida = QAction(tr("subtracao_rapida"), main_window)
        main_window.action_subtracao_rapida.triggered.connect(main_window.gerenciador_processamento.iniciar_subtracao_rapida)
        
        main_window.action_subtracao_lenta = QAction(tr("subtracao_lenta"), main_window)
        main_window.action_subtracao_lenta.triggered.connect(main_window.gerenciador_processamento.iniciar_subtracao_lenta)
        
        main_window.menu_subtracao.addAction(main_window.action_subtracao_rapida)
        main_window.menu_subtracao.addAction(main_window.action_subtracao_lenta)
        main_window.btn_subtracao_ossea.setMenu(main_window.menu_subtracao)

        # Botão Sync Scroll
        main_window.btn_sync_scroll = QPushButton("🔗", main_window)
        main_window.btn_sync_scroll.setObjectName("btn_sync_scroll")
        main_window.btn_sync_scroll.setToolTip(tr("btn_sync"))
        main_window.btn_sync_scroll.setCheckable(True)
        main_window.btn_sync_scroll.toggled.connect(main_window.gerenciador_layouts.on_sync_scroll_toggled)

        # Menu Dissecção 3D (Box Cropping)
        main_window.btn_disseccao = QToolButton(main_window)
        main_window.btn_disseccao.setText(tr("btn_disseccao"))
        main_window.btn_disseccao.setIcon(QIcon(os.path.join("icones", "disseccao.png")))
        main_window.btn_disseccao.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        main_window.btn_disseccao.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        
        main_window.menu_disseccao = QMenu(main_window.btn_disseccao)
        
        main_window.menu_cubo = QMenu(tr("disseccao_cubo"), main_window.menu_disseccao)
        main_window.menu_cubo.setIcon(QIcon(os.path.join("icones", "cubo.png")))
        
        main_window.action_caixa_recorte = QAction(tr("disseccao_caixa"), main_window)
        main_window.action_caixa_recorte.setIcon(QIcon(os.path.join("icones", "tesoura.png")))
        main_window.action_caixa_recorte.setCheckable(True)
        main_window.action_caixa_recorte.triggered.connect(main_window.gerenciador_ferramentas.on_box_adjust_toggled)
        
        main_window.action_aplicar_recorte = QAction(tr("disseccao_aplicar"), main_window)
        main_window.action_aplicar_recorte.setIcon(QIcon(os.path.join("icones", "tesoura.png")))
        main_window.action_aplicar_recorte.triggered.connect(main_window.gerenciador_ferramentas.on_box_apply_clicked)
        
        main_window.action_resetar_3d = QAction(tr("disseccao_resetar"), main_window)
        main_window.action_resetar_3d.setIcon(QIcon(os.path.join("icones", "reset.png")))
        main_window.action_resetar_3d.triggered.connect(main_window.gerenciador_ferramentas.on_box_reset_clicked)
        
        main_window.menu_cubo.addAction(main_window.action_caixa_recorte)
        main_window.menu_cubo.addAction(main_window.action_aplicar_recorte)
        main_window.menu_cubo.addAction(main_window.action_resetar_3d)
        
        main_window.menu_bisturi = QMenu(tr("disseccao_bisturi"), main_window.menu_disseccao)
        main_window.menu_bisturi.setIcon(QIcon(os.path.join("icones", "bisturi.png")))
        
        main_window.action_bisturi_desenhar = QAction(tr("bisturi_desenhar"), main_window)
        main_window.action_bisturi_desenhar.setIcon(QIcon(os.path.join("icones", "elipse.png")))
        main_window.action_bisturi_desenhar.setCheckable(True)
        main_window.action_bisturi_desenhar.triggered.connect(main_window.gerenciador_ferramentas.on_bisturi_toggled)
        
        main_window.action_bisturi_cortar_interior = QAction(tr("bisturi_interior"), main_window)
        main_window.action_bisturi_cortar_interior.setIcon(QIcon(os.path.join("icones", "tesoura.png")))
        main_window.action_bisturi_cortar_interior.triggered.connect(lambda: main_window.gerenciador_ferramentas.on_bisturi_aplicar_clicked(cortar_fora=False))
        
        main_window.action_bisturi_cortar_exterior = QAction(tr("bisturi_exterior"), main_window)
        main_window.action_bisturi_cortar_exterior.setIcon(QIcon(os.path.join("icones", "tesoura.png")))
        main_window.action_bisturi_cortar_exterior.triggered.connect(lambda: main_window.gerenciador_ferramentas.on_bisturi_aplicar_clicked(cortar_fora=True))
        
        main_window.action_bisturi_reset = QAction(tr("bisturi_reset"), main_window)
        main_window.action_bisturi_reset.setIcon(QIcon(os.path.join("icones", "reset.png")))
        main_window.action_bisturi_reset.triggered.connect(main_window.gerenciador_ferramentas.on_bisturi_reset_clicked)
        
        main_window.menu_bisturi.addAction(main_window.action_bisturi_desenhar)
        main_window.menu_bisturi.addAction(main_window.action_bisturi_cortar_interior)
        main_window.menu_bisturi.addAction(main_window.action_bisturi_cortar_exterior)
        main_window.menu_bisturi.addAction(main_window.action_bisturi_reset)
        
        main_window.menu_disseccao.addMenu(main_window.menu_cubo)
        main_window.menu_disseccao.addMenu(main_window.menu_bisturi)
        main_window.btn_disseccao.setMenu(main_window.menu_disseccao)

        # ORDENAÇÃO FINAL DA BARRA DE FERRAMENTAS
        main_window.toolbar.addAction(main_window.action_abrir)
        main_window.toolbar.addAction(main_window.action_anonimizar)
        main_window.toolbar.addSeparator()
        
        main_window.toolbar.addWidget(main_window.btn_visualizacao)
        main_window.toolbar.addWidget(main_window.btn_layout)
        main_window.toolbar.addWidget(main_window.btn_sync_scroll)
        main_window.toolbar.addSeparator()
        
        main_window.toolbar.addWidget(main_window.btn_presets)
        main_window.toolbar.addWidget(main_window.btn_mip)
        main_window.toolbar.addWidget(main_window.spin_espessura)
        main_window.toolbar.addSeparator()
        
        main_window.toolbar.addWidget(main_window.btn_reslice)
        main_window.toolbar.addWidget(main_window.btn_crosshair)
        main_window.toolbar.addWidget(main_window.btn_regua)
        main_window.toolbar.addWidget(main_window.btn_elipse)
        main_window.toolbar.addSeparator()
        
        main_window.toolbar.addWidget(main_window.btn_subtracao_ossea)
        main_window.toolbar.addWidget(main_window.btn_disseccao)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        main_window.toolbar.addWidget(spacer)
        
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
        
        main_window.btn_ajuda = QToolButton(main_window)
        main_window.btn_ajuda.setText(tr("btn_ajuda"))
        main_window.btn_ajuda.setIconSize(QSize(54, 54))
        main_window.btn_ajuda.setStyleSheet(css_ajuda_sobre)
        main_window.btn_ajuda.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        
        main_window.menu_ajuda = QMenu(main_window.btn_ajuda)
        
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
            action = main_window.menu_ajuda.addAction(label)
            action.triggered.connect(lambda checked, t=topico: GerenciadorAjuda.mostrar_ajuda(t, main_window))
            
        main_window.menu_ajuda.addSeparator()
        
        main_window.menu_ajuda_subtracao = QMenu(tr("btn_subtracao"), main_window.menu_ajuda)
        action_sub_rapida = main_window.menu_ajuda_subtracao.addAction(tr("subtracao_rapida"))
        action_sub_rapida.triggered.connect(lambda checked: GerenciadorAjuda.mostrar_ajuda("Subtração Óssea > Rápida", main_window))
        action_sub_lenta = main_window.menu_ajuda_subtracao.addAction(tr("subtracao_lenta"))
        action_sub_lenta.triggered.connect(lambda checked: GerenciadorAjuda.mostrar_ajuda("Subtração Óssea > Lenta", main_window))
        main_window.menu_ajuda.addMenu(main_window.menu_ajuda_subtracao)
        
        main_window.menu_ajuda_disseccao = QMenu(tr("btn_disseccao"), main_window.menu_ajuda)
        action_diss_cubo = main_window.menu_ajuda_disseccao.addAction(tr("disseccao_cubo"))
        action_diss_cubo.triggered.connect(lambda checked: GerenciadorAjuda.mostrar_ajuda("Dissecção > Cubo de Interesse", main_window))
        action_diss_bisturi = main_window.menu_ajuda_disseccao.addAction(tr("disseccao_bisturi"))
        action_diss_bisturi.triggered.connect(lambda checked: GerenciadorAjuda.mostrar_ajuda("Dissecção > Bisturi de Mão livre", main_window))
        main_window.menu_ajuda.addMenu(main_window.menu_ajuda_disseccao)
        
        main_window.btn_ajuda.setMenu(main_window.menu_ajuda)
        main_window.toolbar.addWidget(main_window.btn_ajuda)

        main_window.btn_sobre = QToolButton(main_window)
        main_window.btn_sobre.setText(tr("btn_sobre"))
        main_window.btn_sobre.setIconSize(QSize(54, 54))
        main_window.btn_sobre.setStyleSheet(css_ajuda_sobre)
        main_window.btn_sobre.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        
        main_window.menu_sobre = QMenu(main_window.btn_sobre)
        
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
            
            action = main_window.menu_sobre.addAction(trad_label)
            action.triggered.connect(lambda checked, t=topico: GerenciadorAjuda.mostrar_sobre(t, main_window))
            
        main_window.btn_sobre.setMenu(main_window.menu_sobre)
        main_window.toolbar.addWidget(main_window.btn_sobre)

        main_window.btn_idioma = QToolButton(main_window)
        main_window.btn_idioma.setText(tr("btn_idioma"))
        main_window.btn_idioma.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        
        main_window.menu_idioma = QMenu(main_window.btn_idioma)
        
        action_pt = main_window.menu_idioma.addAction("🇧🇷 Português")
        action_pt.triggered.connect(lambda checked: main_window.alterar_idioma("pt"))
        
        action_en = main_window.menu_idioma.addAction("🇺🇸 English")
        action_en.triggered.connect(lambda checked: main_window.alterar_idioma("en"))
        main_window.btn_idioma.setMenu(main_window.menu_idioma)
        main_window.toolbar.addWidget(main_window.btn_idioma)

    @staticmethod
    def _construir_area_central(main_window):
        from exibicao import CoordenadorExibicao
        main_window.coordenador_exibicao = CoordenadorExibicao(main_window)
        main_window.coordenador_exibicao.hide()
        
        imagem_boas_vindas = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "icones", "tela_boas_vindas.png")
        main_window.label_boas_vindas = LabelImagemResponsiva(main_window, imagem_boas_vindas)
        main_window.setCentralWidget(main_window.label_boas_vindas)

    @staticmethod
    def _construir_painel_lateral(main_window):
        main_window.dock_series = QDockWidget(tr("lbl_series_dock"), main_window)
        main_window.dock_series.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)
        main_window.dock_series.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        
        main_window.list_series = QListWidget(main_window)
        main_window.list_series.itemDoubleClicked.connect(main_window.gerenciador_arquivos.carregar_serie_selecionada)
        main_window.list_series.setDragEnabled(True)
        main_window.list_series.setDefaultDropAction(Qt.DropAction.CopyAction)
        
        container_lateral = QWidget()
        layout_lateral = QVBoxLayout(container_lateral)
        layout_lateral.setContentsMargins(0, 0, 0, 0)
        layout_lateral.setSpacing(0)

        layout_lateral.addWidget(main_window.list_series)

        main_window.btn_dicas = QPushButton(tr("lbl_dicas_btn"))
        main_window.btn_dicas.clicked.connect(main_window.mostrar_dicas_navegacao)
        layout_lateral.addWidget(main_window.btn_dicas)

        main_window.dock_series.setWidget(container_lateral)
        main_window.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, main_window.dock_series)
