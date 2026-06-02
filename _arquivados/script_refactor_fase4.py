import os

# 1. Create carregamento/controlador_exportacao.py
os.makedirs('carregamento', exist_ok=True)
with open('carregamento/controlador_exportacao.py', 'w', encoding='utf-8') as f:
    f.write('''import os
import SimpleITK as sitk
from anonimizador import AnonimizadorDicom

class ControladorExportacao:
    def __init__(self):
        self.anonimizador = AnonimizadorDicom()

    def calcular_total_arquivos(self, series_alvo, diretorio_ativo):
        total_arquivos = 0
        for s in series_alvo:
            if s:
                dir_busca = s.get("Directory", diretorio_ativo)
                arqs = sitk.ImageSeriesReader.GetGDCMSeriesFileNames(dir_busca, s["SeriesID"])
                total_arquivos += len(arqs)
        return total_arquivos

    def executar_exportacao(self, series_alvo, diretorio_ativo, diretorio_destino, exportar_todas, progress_callback, check_canceled):
        arquivos_processados = 0
        todas_sucesso = True

        for s in series_alvo:
            if not s: continue
            
            dir_busca = s.get("Directory", diretorio_ativo)
            arquivos_completos = sitk.ImageSeriesReader.GetGDCMSeriesFileNames(dir_busca, s["SeriesID"])
            
            pasta_alvo = diretorio_destino
            if exportar_todas:
                nome_pasta = f"Serie_{s['SeriesNumber']}" if s.get("SeriesNumber") else f"Serie_{s['SeriesID'][-6:]}"
                pasta_alvo = os.path.join(diretorio_destino, nome_pasta)

            def local_callback(idx, total_serie, atual=arquivos_processados):
                progress_callback(atual + idx)

            sucesso_serie = self.anonimizador.anonimizar_serie(list(arquivos_completos), pasta_alvo, progress_callback=local_callback)
            arquivos_processados += len(arquivos_completos)
            
            if not sucesso_serie:
                todas_sucesso = False

            if check_canceled():
                return False, True # sucesso=False, cancelado=True

        return todas_sucesso, False # sucesso, cancelado
''')

# 2. Process interface.py
with open('interface.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Encontrar índices de inicializar_ui
start_init = -1
end_init = -1
for i, line in enumerate(lines):
    if line.startswith("    def inicializar_ui(self):"):
        start_init = i
    elif start_init != -1 and line.startswith("    def mostrar_dicas_navegacao(self):"):
        end_init = i
        break

if start_init == -1 or end_init == -1:
    print("Could not find inicializar_ui block!")
    exit(1)

# Encontrar sub-blocos dentro de inicializar_ui
idx_toolbar_start = -1
idx_central_start = -1
idx_lateral_start = -1

for i in range(start_init, end_init):
    line = lines[i]
    if "# 3. Criação da Barra de Ferramentas" in line:
        idx_toolbar_start = i
    elif "self.coordenador_exibicao = CoordenadorExibicao(self)" in line:
        idx_central_start = i
    elif "# 5. Barra Lateral de Séries de Imagens" in line:
        idx_lateral_start = i

if idx_toolbar_start == -1 or idx_central_start == -1 or idx_lateral_start == -1:
    print("Could not find sub-blocks for UI componentization!")
    exit(1)

# Montar os novos métodos
method_init = """    def inicializar_ui(self):
        \"\"\"
        Estrutura e carrega todos os componentes visuais principais da janela.
        \"\"\"
        # 1. Configuração do Visual Clínico Dark Mode
        self.setStyleSheet(STYLE_MAIN_WINDOW)

        # 2. Barra de Status para feedback ao usuário
        self.statusBar().showMessage("Pronto")

        self._construir_toolbar()
        self._construir_area_central()
        self._construir_painel_lateral()

    def _construir_toolbar(self):
"""
method_toolbar = "".join(lines[idx_toolbar_start:idx_central_start])

method_central = "    def _construir_area_central(self):\n"
method_central += "".join(lines[idx_central_start:idx_lateral_start])

method_lateral = "    def _construir_painel_lateral(self):\n"
method_lateral += "".join(lines[idx_lateral_start:end_init])

# Substituir o bloco antigo
lines = lines[:start_init] + [method_init, method_toolbar, method_central, method_lateral] + lines[end_init:]


# 3. Refatorar anonimizar_e_exportar
start_anon = -1
end_anon = -1
for i, line in enumerate(lines):
    if line.startswith("    def anonimizar_e_exportar(self):"):
        start_anon = i
    elif start_anon != -1 and line.startswith("    def abrir_pasta(self):"):
        end_anon = i
        break

if start_anon == -1 or end_anon == -1:
    print("Could not find anonimizar_e_exportar block!")
    exit(1)

# Encontrar o try block dentro de anonimizar_e_exportar
idx_try = -1
for i in range(start_anon, end_anon):
    if lines[i].strip() == "try:":
        idx_try = i
        break

if idx_try == -1:
    print("Could not find try block in anonimizar_e_exportar!")
    exit(1)

new_try_block = """        try:
            from carregamento.controlador_exportacao import ControladorExportacao
            controlador_exp = ControladorExportacao()

            series_alvo = self.series_carregadas if exportar_todas else [serie_ativa]
            
            diretorio_base = getattr(self, 'diretorio_ativo', '')
            total_arquivos = controlador_exp.calcular_total_arquivos(series_alvo, diretorio_base)

            progresso_dialog = QProgressDialog("Lendo e anonimizando do disco...", "Cancelar", 0, total_arquivos, self)
            progresso_dialog.setWindowTitle("Processando")
            progresso_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            progresso_dialog.show()

            def update_progress(val):
                progresso_dialog.setValue(val)
                QApplication.processEvents()
            
            def check_cancel():
                return progresso_dialog.wasCanceled()

            sucesso, cancelado = controlador_exp.executar_exportacao(
                series_alvo, diretorio_base, diretorio_destino, exportar_todas, update_progress, check_cancel
            )

            if cancelado:
                self.statusBar().showMessage("Anonimização cancelada pelo usuário.")
                return

            if sucesso:
                msg = f"Anonimização concluída com sucesso em: {diretorio_destino}"
                self.statusBar().showMessage(msg)
            else:
                self.statusBar().showMessage("Falha parcial ao anonimizar os arquivos.")

        except Exception as e:
            self.statusBar().showMessage(f"Erro no processo de anonimização: {str(e)}")

"""

lines = lines[:idx_try] + [new_try_block] + lines[end_anon:]

with open('interface.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Phase 4 refactoring executed successfully!")
