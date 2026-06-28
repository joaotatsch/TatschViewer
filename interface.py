# -*- coding: utf-8 -*-
import sys
import os
import ctypes
import traceback
from PyQt6.QtWidgets import QMainWindow, QApplication, QMessageBox, QFileDialog, QProgressDialog, QDialog, QVBoxLayout, QLabel, QDialogButtonBox, QListWidgetItem
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
        self.conectar_sinais_arquivos()


    def alterar_idioma(self, idioma):
        traducoes.IDIOMA_ATUAL = idioma
        self.statusBar().showMessage(tr("status_pronto"))
        QMessageBox.information(self, tr("btn_idioma"), tr("btn_idioma") + f" alterado para {idioma.upper()}. Algumas mudanças podem exigir reinicialização.")

    def closeEvent(self, event):
        self.thread_manager.close_all()
        event.accept()

    def conectar_sinais_arquivos(self):
        self.gerenciador_arquivos.sinal_progresso_escanear.connect(self.on_progresso_escanear)
        self.gerenciador_arquivos.sinal_progresso_exportar.connect(self.on_progresso_exportar)
        self.gerenciador_arquivos.sinal_status_mensagem.connect(self.on_status_mensagem)
        self.gerenciador_arquivos.sinal_erro.connect(self.on_erro)
        self.gerenciador_arquivos.sinal_fim_progresso.connect(self.on_fim_progresso)
        self.gerenciador_arquivos.sinal_cursor_espera.connect(self.on_cursor_espera)

    def on_progresso_escanear(self, atual, total):
        if not hasattr(self, 'progresso_dialog') or self.progresso_dialog is None:
            self.progresso_dialog = QProgressDialog("Analisando cabeçalhos DICOM...", "Cancelar", 0, total, self)
            self.progresso_dialog.setWindowTitle("Escaneando Pasta")
            self.progresso_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            self.progresso_dialog.show()
        
        self.progresso_dialog.setMaximum(total)
        self.progresso_dialog.setValue(atual)
        QApplication.processEvents()
        
        if self.progresso_dialog.wasCanceled():
            self.gerenciador_arquivos._cancelar_operacao = True

    def on_progresso_exportar(self, atual, total):
        if not hasattr(self, 'progresso_dialog') or self.progresso_dialog is None:
            self.progresso_dialog = QProgressDialog("Lendo e anonimizando do disco...", "Cancelar", 0, total, self)
            self.progresso_dialog.setWindowTitle("Processando")
            self.progresso_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            self.progresso_dialog.show()
            
        self.progresso_dialog.setMaximum(total)
        self.progresso_dialog.setValue(atual)
        QApplication.processEvents()
        
        if self.progresso_dialog.wasCanceled():
            self.gerenciador_arquivos._cancelar_operacao = True

    def on_fim_progresso(self):
        if hasattr(self, 'progresso_dialog') and self.progresso_dialog is not None:
            self.progresso_dialog.close()
            self.progresso_dialog = None

    def on_status_mensagem(self, msg):
        self.statusBar().showMessage(msg)

    def on_erro(self, titulo, msg):
        QMessageBox.warning(self, titulo, msg)

    def on_cursor_espera(self, espera):
        if espera:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        else:
            QApplication.restoreOverrideCursor()

    def mostrar_dicas_navegacao(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("lbl_dicas_btn"))
        dialog.resize(800, 600)
        dialog.setStyleSheet("QDialog { background-color: #1a1a1a; color: #e0e0e0; } QLabel { color: #e0e0e0; font-size: 12px; } QPushButton { background-color: #2a2a2a; color: white; padding: 6px 12px; border-radius: 4px; border: 1px solid #3d3d3d; } QPushButton:hover { background-color: #353535; }")
        
        layout = QVBoxLayout(dialog)
        from ui.custom_widgets import LabelImagemResponsiva
        imagem_boas_vindas = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icones", "tela_boas_vindas.png")
        label_imagem = LabelImagemResponsiva(dialog, imagem_boas_vindas)
        layout.addWidget(label_imagem, 1)
        
        label_texto = QLabel(tr("label_dicas_navegacao"))
        label_texto.setWordWrap(True)
        label_texto.setTextFormat(Qt.TextFormat.RichText)
        label_texto.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label_texto)
        
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)
        
        dialog.exec()

    def abrir_pasta_dialog(self):
        diretorio = QFileDialog.getExistingDirectory(self, "Selecionar Pasta de Série DICOM")
        if diretorio:
            self.gerenciador_arquivos.carregar_diretorio_dicom(diretorio)

    def iniciar_exportacao_anonimizada(self):
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

        diretorio_destino = QFileDialog.getExistingDirectory(
            self, 
            "Selecionar Diretório de Destino para Anonimização"
        )
        if not diretorio_destino:
            return

        series_alvo = self.series_carregadas if exportar_todas else [serie_ativa]
        self.gerenciador_arquivos.anonimizar_e_exportar(series_alvo, diretorio_destino, exportar_todas)

    def popular_lista_series_ui(self, series):
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

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                path = url.toLocalFile()
                if os.path.isdir(path) or path.lower().endswith((".zip", ".nrrd", ".nii.gz")):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                path = url.toLocalFile()
                if os.path.isdir(path):
                    self.statusBar().showMessage(f"Diretório arrastado detectado: {path}")
                    self.gerenciador_arquivos.carregar_diretorio_dicom(path)
                    break
                elif path.lower().endswith(".zip"):
                    self.statusBar().showMessage(f"Arquivo ZIP arrastado detectado: {path}")
                    self.gerenciador_arquivos.carregar_arquivo_zip(path)
                    break
                elif path.lower().endswith((".nrrd", ".nii.gz")):
                    self.statusBar().showMessage(f"Volume Médico arrastado detectado: {path}")
                    self.gerenciador_arquivos.carregar_arquivo_nrrd(path)
                    break
            event.acceptProposedAction()

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
