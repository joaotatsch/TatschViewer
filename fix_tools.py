import os

def fix_tool(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    new_lines = []
    for line in lines:
        if "Reverte para modo Normal após o desenho" in line:
            continue
        if "filtro.ferramenta_atual = filtro.ferramentas.get(\"Normal\", filtro.ferramenta_atual)" in line:
            continue
        new_lines.append(line)
        
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

fix_tool(r'd:\Desktop\Projetos\TatschViewer\navegacao\ferramentas\ferramenta_regua.py')
fix_tool(r'd:\Desktop\Projetos\TatschViewer\navegacao\ferramentas\ferramenta_elipse.py')
