import os

def inject_log(filepath, func_name, class_name):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    new_lines = []
    in_func = False
    for i, line in enumerate(lines):
        new_lines.append(line)
        if line.strip().startswith(f"def {func_name}("):
            indent = line[:len(line) - len(line.lstrip())] + "    "
            new_lines.append(f"{indent}print('LOG-EVENT: {class_name}.{func_name} chamado')\n")
            
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

inject_log(r'd:\Desktop\Projetos\TatschViewer\navegacao\filtros_eventos.py', 'eventFilter', 'FiltroEventosDicom')

def inject_log_tools(filepath, class_name):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    new_lines = []
    for line in lines:
        new_lines.append(line)
        if line.strip().startswith("def on_mouse_press("):
            indent = line[:len(line) - len(line.lstrip())] + "    "
            new_lines.append(f"{indent}print('LOG-TOOL: {class_name} on_mouse_press')\n")
        elif line.strip().startswith("def on_mouse_move("):
            indent = line[:len(line) - len(line.lstrip())] + "    "
            new_lines.append(f"{indent}print('LOG-TOOL: {class_name} on_mouse_move')\n")
        elif line.strip().startswith("def on_mouse_release("):
            indent = line[:len(line) - len(line.lstrip())] + "    "
            new_lines.append(f"{indent}print('LOG-TOOL: {class_name} on_mouse_release')\n")
            
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

inject_log_tools(r'd:\Desktop\Projetos\TatschViewer\navegacao\ferramentas\ferramenta_normal.py', 'FerramentaNormal')
inject_log_tools(r'd:\Desktop\Projetos\TatschViewer\navegacao\ferramentas\ferramenta_regua.py', 'FerramentaRegua')
inject_log_tools(r'd:\Desktop\Projetos\TatschViewer\navegacao\ferramentas\ferramenta_elipse.py', 'FerramentaElipse')
inject_log_tools(r'd:\Desktop\Projetos\TatschViewer\navegacao\ferramentas\ferramenta_bisturi.py', 'FerramentaBisturi')

