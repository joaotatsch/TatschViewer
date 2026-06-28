import os

file_filtros = r'd:\Desktop\Projetos\TatschViewer\navegacao\filtros_eventos.py'

with open(file_filtros, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "'Normal': FerramentaNormal()," in line and "FerramentaBisturi" in "".join(lines[lines.index(line):lines.index(line)+5]):
        new_lines.append("            'Normal': FerramentaBase(),\n")
    elif "from .ferramentas import FerramentaNormal, FerramentaBisturi" in line:
        new_lines.append("        from .ferramentas import FerramentaNormal, FerramentaBisturi\n")
        new_lines.append("        from .ferramentas_base import FerramentaBase\n")
    else:
        new_lines.append(line)

with open(file_filtros, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
