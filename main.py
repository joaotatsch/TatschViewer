# -*- coding: utf-8 -*-
import sys
import os
import time

# 1. Ajuste robusto do diretório de trabalho (CWD) para a pasta do script/executável
# Isso garante que caminhos relativos para imagens, ícones e outros assets funcionem perfeitamente
if hasattr(sys, '_MEIPASS'):
    os.chdir(sys._MEIPASS)
else:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 2. Importação dos módulos do PyQt6 necessários para desenhar a Splash Screen e Ícone
from PyQt6.QtWidgets import QApplication, QSplashScreen
from PyQt6.QtGui import QPixmap, QPainter, QColor, QLinearGradient, QFont, QRadialGradient, QPen, QBrush, QIcon
from PyQt6.QtCore import Qt, QPointF, QStandardPaths, QRect
from traducoes import tr, Tradutor

app = QApplication(sys.argv)
# AÇÃO 1: Definir o Ícone Global do Aplicativo
app.setWindowIcon(QIcon(os.path.join("icones", "logo_tatsch.png")))

def gerar_splash_pixmap():
    """
    Gera um QPixmap de 600x500 desenhado puramente via código usando QPainter,
    adotando um estilo de Minimalismo Extremo (Apple/Startups modernas).
    Utiliza o logo_tatsch.png centralizado e escalado suavemente.
    """
    pixmap = QPixmap(600, 500)
    pixmap.fill(QColor("#050505")) # Preto sólido profundo
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    
    # Carrega e desenha o logo oficial
    logo_path = os.path.join("icones", "logo_tatsch.png")
    logo_pixmap = QPixmap(logo_path)
    if not logo_pixmap.isNull():
        # Escala o logo suavemente para 200x200
        scaled_logo = logo_pixmap.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        # Desenha o logo centralizado horizontalmente: (600 - 200) / 2 = 200
        painter.drawPixmap(200, 80, scaled_logo)
    
    # Título Principal "TatschViewer" (Y = 320)
    font_title = QFont("Segoe UI", 32, QFont.Weight.Bold)
    painter.setFont(font_title)
    painter.setPen(QColor("#ffffff"))
    rect_title = QRect(0, 320, 600, 50)
    painter.drawText(rect_title, Qt.AlignmentFlag.AlignCenter, "TatschViewer")
    
    # Status Removendo Poluição Visual (Y = 380)
    font_status = QFont("Segoe UI", 10)
    painter.setFont(font_status)
    painter.setPen(QColor("#777777")) # Cinza escuro discreto
    rect_status = QRect(0, 380, 600, 30)
    painter.drawText(rect_status, Qt.AlignmentFlag.AlignCenter, tr("status_iniciando"))
    
    # Rodapé Discreto (Y = 470)
    font_footer = QFont("Segoe UI", 8)
    painter.setFont(font_footer)
    painter.setPen(QColor("#333333")) # Muito discreto
    rect_footer = QRect(0, 460, 600, 30)
    painter.drawText(rect_footer, Qt.AlignmentFlag.AlignCenter, tr("footer_copyright"))
    
    painter.end()
    return pixmap

# 3. Verificação do Termo de Responsabilidade (EULA)
def checar_eula():
    """
    Verifica a aceitação do termo de responsabilidade médica (EULA) do TatschViewer.
    Se o arquivo oculto `.tatschviewer_accepted` não for encontrado no cache
    do usuário, exibe a caixa de diálogo modal bloqueante.
    """
    cache_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericCacheLocation)
    if not cache_dir:
        cache_dir = os.path.expanduser("~")
    
    os.makedirs(cache_dir, exist_ok=True)
    eula_file = os.path.join(cache_dir, ".tatschviewer_accepted")
    
    if os.path.exists(eula_file):
        return True
        
    from PyQt6.QtWidgets import QMessageBox
    
    msg_box = QMessageBox()
    msg_box.setWindowTitle(tr("eula_titulo"))
    msg_box.setIcon(QMessageBox.Icon.Warning)
    msg_box.setText(tr("eula_texto"))
    
    msg_box.setStyleSheet("""
        QMessageBox {
            background-color: #121212;
        }
        QLabel {
            color: #e0e0e0;
            font-size: 13px;
            font-family: 'Segoe UI';
        }
        QPushButton {
            background-color: #1e1e28;
            color: #00e5ff;
            border: 1px solid #00e5ff;
            border-radius: 4px;
            padding: 6px 16px;
            font-family: 'Segoe UI';
            font-weight: bold;
            min-width: 80px;
        }
        QPushButton:hover {
            background-color: #00e5ff;
            color: #121212;
        }
        QPushButton:pressed {
            background-color: #00b2cc;
        }
    """)
    
    aceitar_texto = "Aceitar" if Tradutor().idioma == "pt" else "Accept"
    recusar_texto = "Recusar" if Tradutor().idioma == "pt" else "Decline"
    
    aceitar_btn = msg_box.addButton(aceitar_texto, QMessageBox.ButtonRole.AcceptRole)
    recusar_btn = msg_box.addButton(recusar_texto, QMessageBox.ButtonRole.RejectRole)
    msg_box.setDefaultButton(recusar_btn)
    
    msg_box.setWindowModality(Qt.WindowModality.ApplicationModal)
    msg_box.raise_()
    msg_box.exec()
    
    if msg_box.clickedButton() == aceitar_btn:
        try:
            with open(eula_file, "w", encoding="utf-8") as f:
                f.write("accepted\n")
            if os.name == 'nt':
                import ctypes
                ctypes.windll.kernel32.SetFileAttributesW(eula_file, 0x02) # oculta no Windows
        except Exception as e:
            print(f"[EULA] Erro ao gravar o arquivo de aceite: {e}")
        return True
    return False

# Executa o EULA antes de inicializar o pesado do app
if not checar_eula():
    sys.exit(0)

# 4. Tratador Global de Exceções Fatais (Crash Reporter)
def excepthook_personalizado(exctype, value, tb):
    """
    Interceptador global de erros não tratados que salva relatórios e avisa o usuário.
    """
    import traceback
    from PyQt6.QtWidgets import QMessageBox
    
    tb_lines = traceback.format_exception(exctype, value, tb)
    tb_text = "".join(tb_lines)
    
    nome_arquivo = "tatschviewer_crash_report.txt"
    caminho_relatorio = nome_arquivo
    
    try:
        with open(nome_arquivo, "w", encoding="utf-8") as f:
            f.write("=== TATSCHVIEWER 1.5 CRASH REPORT ===\n")
            f.write(f"Data e Hora: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Exceção Fatal: {exctype.__name__}: {value}\n\n")
            f.write("Traceback de Execução:\n")
            f.write(tb_text)
    except Exception as e:
        print(f"Erro ao salvar crash report local: {e}")
        
    try:
        caminho_home = os.path.join(os.path.expanduser("~"), nome_arquivo)
        with open(caminho_home, "w", encoding="utf-8") as f:
            f.write("=== TATSCHVIEWER 1.5 CRASH REPORT ===\n")
            f.write(f"Data e Hora: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Exceção Fatal: {exctype.__name__}: {value}\n\n")
            f.write("Traceback de Execução:\n")
            f.write(tb_text)
        caminho_relatorio = caminho_home
    except Exception as e:
        print(f"Erro ao salvar crash report na pasta Home: {e}")
        
    try:
        msg = QMessageBox()
        msg.setWindowTitle(tr("crash_titulo"))
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setText(tr("crash_texto").format(caminho=caminho_relatorio))
        msg.setDetailedText(tb_text)
        
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #121212;
            }
            QLabel {
                color: #e0e0e0;
                font-family: 'Segoe UI';
            }
            QPushButton {
                background-color: #1e1e28;
                color: #ff3b30;
                border: 1px solid #ff3b30;
                border-radius: 4px;
                padding: 6px 16px;
                font-family: 'Segoe UI';
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff3b30;
                color: #121212;
            }
            QTextEdit {
                background-color: #1e1e1e;
                color: #ff3b30;
                font-family: 'Consolas';
                font-size: 11px;
            }
        """)
        msg.exec()
    except Exception as e:
        print(f"Falha ao exibir QMessageBox de erro: {e}")
        
    sys.exit(1)

sys.excepthook = excepthook_personalizado

def main():
    """
    Função principal que instancia a QSplashScreen e orquestra o carregamento tardio.
    """
    t_inicio = time.time()
    
    # AÇÃO 3: Instanciar a Splash Screen com o pixmap gerado
    splash = QSplashScreen(gerar_splash_pixmap(), Qt.WindowType.WindowStaysOnTopHint)
    splash.show()
    app.processEvents()
    
    # Realiza a importação tardia das dependências pesadas e de MainWindow
    import vtk
    # Desativa a janela popup nativa do vtkOutputWindow
    vtk.vtkOutputWindow.SetGlobalWarningDisplay(0)
    
    from interface import MainWindow
    
    # Cria a janela principal do sistema
    window = MainWindow()
    window.show()
    
    # Fecha a Splash Screen assim que a janela principal estiver 100% pronta
    splash.finish(window)
    
    print(f"[PROFILING] Tempo total de inicialização do App: {time.time() - t_inicio:.3f} segundos")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
