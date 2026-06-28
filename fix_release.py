import os

file_normal = r'd:\Desktop\Projetos\TatschViewer\navegacao\ferramentas\ferramenta_normal.py'

with open(file_normal, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    new_lines.append(line)

new_lines.append("\n")
new_lines.append("    def on_mouse_release(self, event, filtro) -> bool:\n")
new_lines.append("        if event.button() == Qt.MouseButton.LeftButton:\n")
new_lines.append("            if getattr(filtro, 'arrastando_medida', False):\n")
new_lines.append("                filtro.arrastando_medida = False\n")
new_lines.append("                filtro.ultima_posicao_medida = None\n")
new_lines.append("                filtro.interactor.setCursor(Qt.CursorShape.OpenHandCursor)\n")
new_lines.append("                return True\n")
new_lines.append("            \n")
new_lines.append("            filtro.arrastando_janelamento = False\n")
new_lines.append("            filtro.arrastando_rotacao = False\n")
new_lines.append("            if getattr(filtro, 'alvo_arraste', None):\n")
new_lines.append("                filtro.alvo_arraste = None\n")
new_lines.append("                filtro.interactor.setCursor(Qt.CursorShape.ArrowCursor)\n")
new_lines.append("            return True\n")
new_lines.append("        return False\n")

with open(file_normal, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
