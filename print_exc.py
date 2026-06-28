import os

file_filtros = r'd:\Desktop\Projetos\TatschViewer\navegacao\filtros_eventos.py'

with open(file_filtros, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    new_lines.append(line)
    if line.strip() == "except Exception:":
        indent = line[:len(line) - len(line.lstrip())] + "    "
        new_lines.append(f"{indent}import traceback; traceback.print_exc()\n")

with open(file_filtros, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
