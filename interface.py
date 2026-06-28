# -*- coding: utf-8 -*-
import sys
import os
import ctypes
import traceback
from PyQt6.QtWidgets import QMainWindow, QApplication, QMessageBox
from PyQt6.QtCore import Qt

from traducoes import tr
import traducoes
from ui.main_window_builder import UIBuilder
from core.thread_manager import ThreadManager
from controladores.gerenciador_eventos_arquivos import GerenciadorEventosArquivos
from controladores.gerenciador_processamento import GerenciadorProcessamento
from controladores.gerenciador_ferramentas import GerenciadorFerramentas
from controladores.gerenciador_layouts import GerenciadorLayouts
from controladores.gerenciador_eventos_teclado import FiltroTeclado
from core.utils_profiling import profiler_time
from PyQt6.QtWidgets import QApplication

class MainWindow(QMainWindow):
    """
    Controlador Principal e Orquestrador de Alto Nível do TatschViewer.
    Após a refatoração, esta classe delega as responsabilidades de UI,
    processamento, eventos e gerenciamento de layout para controladores especializados.
    """
    @profiler_time
    def __init__(self):
        super().__init__()
        try:
            import pyi_splash
            if pyi_splash.is_alive():
                pyi_splash.update_text('Carregando Interface...')
                pyi_splash.close()
        except (ImportError, RuntimeError):
            pass

        self.setWindowTitle("TatschViewer - Visualizador DICOM Avançado")
        self.resize(1200, 800)
        self.setAcceptDrops(True)

        # Inicializa gerenciadores centrais
        self.thread_manager = ThreadManager(self)
        self.gerenciador_arquivos = GerenciadorEventosArquivos(self)
        self.gerenciador_processamento = GerenciadorProcessamento(self)
        self.gerenciador_ferramentas = GerenciadorFerramentas(self)
        self.gerenciador_layouts = GerenciadorLayouts(self)

        # Referências a instâncias de volume e cache
        self.active_quadrante = None
        self.filtro_teclado = FiltroTeclado(self)
        app = QApplication.instance()
        if app:
            app.installEventFilter(self.filtro_teclado)
        else:
            self.installEventFilter(self.filtro_teclado)
        
        self.diretorio_ativo = ""
        self.series_carregadas = []
        self._sitk_img_ref = None
        self._np_view_ref = None
        self.vtk_image_ativa = None
        self._prop_dicom_ref = None
        self.modo_projecao_atual = "Normal"
        self.coordenador_navegacao = None
        self.cache_series = {}

        # Constrói a interface delegando ao UIBuilder
        UIBuilder.setup_ui(self)


    def alterar_idioma(self, idioma):
        traducoes.IDIOMA_ATUAL = idioma
        self.statusBar().showMessage(tr("status_pronto"))
        QMessageBox.information(self, tr("btn_idioma"), tr("btn_idioma") + f" alterado para {idioma.upper()}. Algumas mudanças podem exigir reinicialização.")

    def closeEvent(self, event):
        self.thread_manager.close_all()
        event.accept()

    def dragEnterEvent(self, event):
        self.gerenciador_arquivos.dragEnterEvent(event)

    def dropEvent(self, event):
        self.gerenciador_arquivos.dropEvent(event)

    def is_sincronizacao_ativa(self) -> bool:
        if hasattr(self, 'gerenciador_layouts') and self.gerenciador_layouts:
            return self.gerenciador_layouts.is_sincronizacao_ativa()
        return False

    def sincronizar_rolagem_global(self, coordenador_origem, nome_visao, delta_mm):
        if hasattr(self, 'gerenciador_layouts') and self.gerenciador_layouts:
            self.gerenciador_layouts.sincronizar_rolagem_global(coordenador_origem, nome_visao, delta_mm)

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            myappid = 'tatsch.viewer.dicom.1_5'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

    app = QApplication(sys.argv)
    
    css_global = """
        QMessageBox {
            background-color: #1a1a1a;
            color: #e0e0e0;
        }
        QMessageBox QLabel {
            color: #e0e0e0;
        }
        QMessageBox QPushButton {
            background-color: #2d2d2d;
            color: #e0e0e0;
            border: 1px solid #3d3d3d;
            border-radius: 4px;
            padding: 4px 12px;
        }
        QMessageBox QPushButton:hover {
            background-color: #3d3d3d;
        }
    """
    app.setStyleSheet(css_global)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
