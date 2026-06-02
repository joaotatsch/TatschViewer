# -*- coding: utf-8 -*-

HTML_BOAS_VINDAS = (
    "<h2 align='center'>Bem-vindo ao Neuroviewer</h2>"
    "<p align='center'>Arraste e solte uma pasta DICOM ou arquivo .zip aqui para começar.</p>"
    "<br><br>"
    "<table width='80%' align='center' cellpadding='15' style='border-collapse: collapse;'>"
    "<tr>"
    "<td width='50%' valign='top' style='border-right: 1px solid #3d3d3d;'>"
    "<h3 align='center' style='color: #007acc;'>Navegação 2D (MPR)</h3>"
    "<ul style='line-height: 1.6;'>"
    "<li><b>Botão Esquerdo (Fundo):</b> Ajuste de Contraste</li>"
    "<li><b>Botão Esquerdo (Linhas):</b> Arrastar fatias / Espessura MIP</li>"
    "<li><b>Scroll (Roda):</b> Navegar entre Fatias</li>"
    "<li><b>Botão do Meio:</b> Mover a Imagem (Pan)</li>"
    "<li><b>Botão Direito:</b> Zoom In / Out</li>"
    "<li><b>Duplo-Clique:</b> Maximizar Tela</li>"
    "<li><b>Crosshair:</b> Segure a letra <b>\"C\"</b> ou ative o botão para sincronizar as telas</li>"
    "</ul>"
    "</td>"
    "<td width='50%' valign='top'>"
    "<h3 align='center' style='color: #e74c3c;'>Navegação 3D (Volume)</h3>"
    "<ul style='line-height: 1.6;'>"
    "<li><b>Botão Esquerdo:</b> Rotacionar o modelo 3D</li>"
    "<li><b style='color: #f1c40f;'>Shift + Esquerdo:</b> Janelamento 3D (Transparência)</li>"
    "<li><b>Botão do Meio:</b> Mover o modelo 3D (Pan)</li>"
    "<li><b>Botão Direito:</b> Zoom In / Out</li>"
    "<li><b>Duplo-Clique:</b> Maximizar Tela</li>"
    "</ul>"
    "</td>"
    "</tr>"
    "</table>"
)

HTML_DICAS_NAVEGACAO = (
    "<table width='100%' align='center' cellpadding='15' style='border-collapse: collapse;'>"
    "<tr>"
    "<td width='50%' valign='top' style='border-right: 1px solid #3d3d3d;'>"
    "<h3 align='center' style='color: #007acc;'>Navegação 2D (MPR)</h3>"
    "<ul style='line-height: 1.6;'>"
    "<li><b>Botão Esquerdo (Fundo):</b> Ajuste de Contraste</li>"
    "<li><b>Botão Esquerdo (Linhas):</b> Arrastar fatias / Espessura MIP</li>"
    "<li><b>Scroll (Roda):</b> Navegar entre Fatias</li>"
    "<li><b>Botão do Meio:</b> Mover a Imagem (Pan)</li>"
    "<li><b>Botão Direito:</b> Zoom In / Out</li>"
    "<li><b>Duplo-Clique:</b> Maximizar Tela</li>"
    "<li><b>Crosshair:</b> Segure a letra <b>\"C\"</b> ou ative o botão para sincronizar as telas</li>"
    "</ul>"
    "</td>"
    "<td width='50%' valign='top'>"
    "<h3 align='center' style='color: #e74c3c;'>Navegação 3D (Volume)</h3>"
    "<ul style='line-height: 1.6;'>"
    "<li><b>Botão Esquerdo:</b> Rotacionar o modelo 3D</li>"
    "<li><b style='color: #f1c40f;'>Shift + Esquerdo:</b> Janelamento 3D (Transparência)</li>"
    "<li><b>Botão do Meio:</b> Mover o modelo 3D (Pan)</li>"
    "<li><b>Botão Direito:</b> Zoom In / Out</li>"
    "<li><b>Duplo-Clique:</b> Maximizar Tela</li>"
    "</ul>"
    "</td>"
    "</tr>"
    "</table>"
)

STYLE_MAIN_WINDOW = """
            QMainWindow {
                background-color: #121212;
            }
            QToolBar {
                background-color: #1a1a1a;
                border-bottom: 1px solid #2d2d2d;
                spacing: 12px;
                padding: 6px;
            }
            QStatusBar {
                background-color: #1a1a1a;
                color: #888888;
                border-top: 1px solid #2d2d2d;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 11px;
            }
        """

STYLE_TOOLBAR_BUTTONS = """
                    QToolButton {
                        background-color: #2a2a2a;
                        color: #e0e0e0;
                        border: 1px solid #3d3d3d;
                        border-radius: 4px;
                        padding: 4px;
                        font-family: 'Segoe UI', Arial, sans-serif;
                        font-size: 12px;
                        font-weight: bold;
                    }
                    QToolButton:hover {
                        background-color: #353535;
                        border-color: #555555;
                        color: #ffffff;
                    }
                    QToolButton:pressed {
                        background-color: #121212;
                        border-color: #007acc;
                        color: #007acc;
                    }
                """

STYLE_MENU = """
            QMenu {
                background-color: #1a1a1a;
                color: #e0e0e0;
                border: 1px solid #3d3d3d;
                padding: 4px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
                border-radius: 4px;
            }
            QMenu::item {
                padding: 8px 24px 8px 12px;
                border-radius: 4px;
                margin: 2px;
            }
            QMenu::item:selected {
                background-color: #007acc;
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background-color: #3d3d3d;
                margin: 4px 8px;
            }
        """

STYLE_BTN_PRESETS = """
            QToolButton {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 4px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
                font-weight: bold;
            }
            QToolButton::menu-indicator { image: none; }
            QToolButton:hover { background-color: #353535; }
        """

STYLE_SPINBOX = """
            QSpinBox {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 4px 6px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-weight: bold;
                font-size: 12px;
            }
        """

STYLE_BTN_CROSSHAIR = """
            QPushButton {
                background-color: #2a2a2a; color: #e0e0e0;
                border: 1px solid #3d3d3d; border-radius: 4px;
                padding: 4px; font-size: 22px; /* Transforma o caractere em ícone */
                min-width: 32px; max-width: 32px; min-height: 28px;
            }
            QPushButton:checked { background-color: #007acc; color: #ffffff; }
        """

STYLE_BTN_TOGGLE = """
            QToolButton {
                background-color: #2a2a2a; border: 1px solid #3d3d3d;
                border-radius: 4px; padding: 4px;
            }
            QToolButton:hover { background-color: #353535; }
            QToolButton:checked { background-color: #007acc; border-color: #007acc; }
        """

STYLE_BTN_SUBTRACAO = """
            QToolButton {
                background-color: #2a2a2a; border: 1px solid #3d3d3d;
                border-radius: 4px; padding: 4px;
            }
            QToolButton:hover { background-color: #353535; }
            QToolButton:pressed { background-color: #121212; border-color: #007acc; color: #007acc; }
        """

STYLE_BTN_SYNC_SCROLL = """
            QPushButton {
                background-color: #2a2a2a; color: #e0e0e0;
                border: 1px solid #3d3d3d; border-radius: 4px;
                padding: 4px; font-size: 18px;
                min-width: 32px; max-width: 32px; min-height: 28px;
            }
            QPushButton:checked { background-color: #27ae60; color: #ffffff; border-color: #27ae60; }
            QPushButton:hover   { background-color: #353535; }
        """

STYLE_LABEL_BOAS_VINDAS = "color: #aaaaaa; font-family: 'Segoe UI'; font-size: 14px;"

STYLE_DOCK_WIDGET = """
            QDockWidget {
                color: #e0e0e0;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
                font-weight: bold;
            }
            QDockWidget::title {
                background-color: #1a1a1a;
                padding: 6px;
                border-bottom: 1px solid #2d2d2d;
            }
        """

STYLE_LIST_WIDGET = """
            QListWidget {
                background-color: #151515;
                color: #e0e0e0;
                border: 1px solid #2d2d2d;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 11px;
                outline: 0;
            }
            QListWidget::item {
                padding: 8px 12px;
                border-bottom: 1px solid #222222;
            }
            QListWidget::item:hover {
                background-color: #252525;
            }
            QListWidget::item:selected {
                background-color: #2a2a2a;
                color: #007acc;
                border-left: 3px solid #007acc;
            }
        """

STYLE_BTN_DICAS = """
            QPushButton {
                background-color: #1a1a1a; color: #888888;
                border-top: 1px solid #2d2d2d; border-bottom: none; border-left: none; border-right: none;
                padding: 10px; font-family: 'Segoe UI'; font-size: 12px; font-weight: bold;
                text-align: left;
            }
            QPushButton:hover { background-color: #252525; color: #ffffff; }
        """

STYLE_MSGBOX_DICAS = "QMessageBox { background-color: #1a1a1a; color: #e0e0e0; min-width: 650px; } QLabel { color: #e0e0e0; font-size: 12px; } QPushButton { background-color: #2a2a2a; color: white; padding: 6px 12px; border-radius: 4px; border: 1px solid #3d3d3d; }"

STYLE_PROGRESS_DIALOG = "QProgressDialog { background-color: #1a1a1a; color: #e0e0e0; } QLabel { color: #e0e0e0; } QPushButton { background-color: #2a2a2a; color: white; border: 1px solid #3d3d3d; padding: 4px; border-radius: 4px;}"

PRESETS_CLINICOS = {
    "angio_tc": {"ww": 600, "wl": 150, "nome": "Angio-TC Vascular"},
    "cerebro": {"ww": 80, "wl": 40, "nome": "Cérebro Genérico"},
    "avc_isquemico": {"ww": 35, "wl": 35, "nome": "AVC Isquêmico"},
    "hemorragia": {"ww": 160, "wl": 120, "nome": "Hemorragia Aguda"},
    "osso": {"ww": 2000, "wl": 500, "nome": "Osso"},
    "pulmao": {"ww": 1500, "wl": -600, "nome": "Pulmão"},
    "mediastino": {"ww": 350, "wl": 50, "nome": "Mediastino"},
    "abdome": {"ww": 400, "wl": 40, "nome": "Abdome"},
    "customizado": {"ww": 0, "wl": 0, "nome": "Customizado"}
}


