import os

# 1. Create carregamento/threads_carregamento.py
os.makedirs('carregamento', exist_ok=True)
with open('carregamento/threads_carregamento.py', 'w', encoding='utf-8') as f:
    f.write("""# -*- coding: utf-8 -*-
from PyQt6.QtCore import QThread, pyqtSignal

class ThreadCarregamento(QThread):
    resultado = pyqtSignal(object)
    erro_carregamento = pyqtSignal(str)
    resultado_cache_silencioso = pyqtSignal(object, str)
    prefetch_concluido = pyqtSignal(object, str)   # novo: sinal de pré-busca concluída

    def __init__(self, coordenador, diretorio, series_id, silencioso=False, prefetch=False):
        super().__init__()
        self.coordenador = coordenador
        self.diretorio = diretorio
        self.series_id = series_id
        self.silencioso = silencioso
        self.prefetch = prefetch

    def run(self):
        try:
            resultado = self.coordenador.carregar_serie(self.diretorio, self.series_id)
            if self.prefetch:
                self.prefetch_concluido.emit(resultado, self.series_id)
            elif self.silencioso:
                self.resultado_cache_silencioso.emit(resultado, self.series_id)
            else:
                self.resultado.emit(resultado)
        except Exception as e:
            if not self.silencioso and not self.prefetch:
                self.erro_carregamento.emit(str(e))
            else:
                print(f"[PREFETCH] Erro no background: {e}")
""")

# 2. Create exibicao/formatador_hud.py
os.makedirs('exibicao', exist_ok=True)
with open('exibicao/formatador_hud.py', 'w', encoding='utf-8') as f:
    f.write("""# -*- coding: utf-8 -*-

def formatar_texto_hud(prop_dicom: dict) -> str:
    linhas = []
    
    nome = prop_dicom.get("Nome", "").strip()
    nomes_ignorados = ["", "ANONIMO", "PACIENTE ANONIMIZADO", "DESCONHECIDO", "N/A"]
    if nome.upper() not in nomes_ignorados:
        linhas.append(f"Paciente: {nome}")
        
    inst = prop_dicom.get("Inst", "").strip()
    inst_ignoradas = ["", "ANONIMA", "INSTITUICAO ANONIMA", "HOSPITAL DE NEUROIMAGEM", "N/A"]
    if inst.upper() not in inst_ignoradas:
        linhas.append(f"Inst: {inst}")
        
    data = prop_dicom.get("Data", "").strip()
    if len(data) == 8 and data.isdigit():
        data = f"{data[6:8]}/{data[4:6]}/{data[0:4]}"

    hora = prop_dicom.get("Hora", "").strip()
    hora_limpa = hora.split(".")[0] if "." in hora else hora
    if len(hora_limpa) >= 4:
        hora = f"{hora_limpa[0:2]}:{hora_limpa[2:4]}"
    
    linha_data_hora = ""
    datas_ignoradas = ["", "N/A", "01/01/2000", "01/01/1900", "20000101", "19000101"]
    
    if data and data not in datas_ignoradas:
        linha_data_hora += f"Data: {data}"
        
    if hora and hora not in ["", "N/A"]:
        separador = "   " if linha_data_hora else ""
        linha_data_hora += f"{separador}Hora: {hora}"
        
    if linha_data_hora.strip():
        linhas.append(linha_data_hora.strip())
        
    return "\\n".join(linhas)
""")

# 3. Refactor interface.py
with open('interface.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# A) Encontrar ThreadCarregamento e remover
start_thread = -1
end_thread = -1
for i, line in enumerate(lines):
    if line.startswith("class ThreadCarregamento(QThread):"):
        start_thread = i
    if start_thread != -1 and line.startswith("from processamento_imagem.threads_subtracao import "):
        end_thread = i
        break

# B) Encontrar extrair_texto_hud e remover
start_hud = -1
end_hud = -1
for i, line in enumerate(lines):
    if line.startswith("    def extrair_texto_hud(self, prop_dicom: dict) -> str:"):
        start_hud = i
    if start_hud != -1 and i > start_hud and line.startswith("    def aplicar_preset_por_nome(self, nome_preset: str):"):
        end_hud = i
        break

if start_thread == -1 or end_thread == -1 or start_hud == -1 or end_hud == -1:
    print("Failed to find blocks!")
    print(f"start_thread={start_thread}, end_thread={end_thread}, start_hud={start_hud}, end_hud={end_hud}")
    exit(1)

# Sort removals from bottom to top to avoid index shifting
indices_to_remove = list(range(start_hud, end_hud)) + list(range(start_thread, end_thread))
indices_to_remove = sorted(indices_to_remove, reverse=True)

for i in indices_to_remove:
    del lines[i]

# Add imports around where ThreadCarregamento used to be (which is now index start_thread)
imports = (
    "from carregamento.threads_carregamento import ThreadCarregamento\n"
    "from exibicao.formatador_hud import formatar_texto_hud\n"
)
lines.insert(start_thread, imports)

# Replace all occurrences of self.extrair_texto_hud with formatar_texto_hud
for i in range(len(lines)):
    lines[i] = lines[i].replace("self.extrair_texto_hud", "formatar_texto_hud")

with open('interface.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Phase 2 refactoring executed successfully.")
