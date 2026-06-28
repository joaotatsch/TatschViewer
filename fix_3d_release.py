import os

file_filtros = r'd:\Desktop\Projetos\TatschViewer\navegacao\filtros_eventos.py'

with open(file_filtros, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if "if getattr(self, 'arrastando_bisturi', False):" in line and "FiltroEventosDicom3D" in "".join(lines[max(0, i-60):i]):
        indent = line[:len(line) - len(line.lstrip())]
        new_lines.append(indent + "if getattr(self, 'arrastando_janelamento', False):\n")
        new_lines.append(indent + "    self.arrastando_janelamento = False\n")
        new_lines.append(indent + "    return True\n")
        new_lines.append(line)
    else:
        new_lines.append(line)

with open(file_filtros, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
