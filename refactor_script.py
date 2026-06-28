import os
import re

file_path = r'd:\Desktop\Projetos\TatschViewer\navegacao\filtros_eventos.py'

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
in_event_filter = False
skip = False

for i, line in enumerate(lines):
    # INJECT REGISTRY AT __init__
    if 'self.ferramenta_ativa = "Normal"' in line and 'FiltroEventosDicom' in "".join(lines[max(0, i-50):i]):
        indent = line[:len(line) - len(line.lstrip())]
        new_lines.append(line)
        new_lines.append(indent + "from .ferramentas import (\n")
        new_lines.append(indent + "    FerramentaNormal, FerramentaSemente, FerramentaSementeDSA,\n")
        new_lines.append(indent + "    FerramentaRegua, FerramentaElipse, FerramentaCropBox,\n")
        new_lines.append(indent + "    FerramentaCrosshair, FerramentaReslice, FerramentaBisturi\n")
        new_lines.append(indent + ")\n")
        new_lines.append(indent + "self.ferramentas = {\n")
        new_lines.append(indent + "    'Normal': FerramentaNormal(),\n")
        new_lines.append(indent + "    'Semente': FerramentaSemente(),\n")
        new_lines.append(indent + "    'SementeDSA': FerramentaSementeDSA(),\n")
        new_lines.append(indent + "    'Regua': FerramentaRegua(),\n")
        new_lines.append(indent + "    'Elipse': FerramentaElipse(),\n")
        new_lines.append(indent + "    'CropBox': FerramentaCropBox(),\n")
        new_lines.append(indent + "    'Crosshair': FerramentaCrosshair(),\n")
        new_lines.append(indent + "    'Reslice': FerramentaReslice(),\n")
        new_lines.append(indent + "    'Bisturi': FerramentaBisturi()\n")
        new_lines.append(indent + "}\n")
        new_lines.append(indent + "self.ferramenta_atual = self.ferramentas['Normal']\n")
        continue

    # 3D Filtro
    if 'self.ferramenta_ativa = "Normal"' in line and 'FiltroEventosDicom3D' in "".join(lines[max(0, i-30):i]):
        indent = line[:len(line) - len(line.lstrip())]
        new_lines.append(line)
        new_lines.append(indent + "from .ferramentas import FerramentaNormal, FerramentaBisturi\n")
        new_lines.append(indent + "self.ferramentas = {\n")
        new_lines.append(indent + "    'Normal': FerramentaNormal(),\n")
        new_lines.append(indent + "    'Bisturi': FerramentaBisturi()\n")
        new_lines.append(indent + "}\n")
        new_lines.append(indent + "self.ferramenta_atual = self.ferramentas['Normal']\n")
        continue

    # REPLACE THE MOUSE BLOCKS IN FiltroEventosDicom
    if 'elif event.type() == QEvent.Type.MouseButtonPress:' in line and 'elif event.type() == QEvent.Type.MouseButtonDblClick' not in lines[i+1]:
        indent = line[:len(line) - len(line.lstrip())]
        new_lines.append(line)
        new_lines.append(indent + "    if hasattr(self, 'ferramenta_atual'):\n")
        new_lines.append(indent + "        if self.ferramenta_atual.on_mouse_press(event, self):\n")
        new_lines.append(indent + "            return True\n")
        skip = True
        continue
    
    if 'elif event.type() == QEvent.Type.MouseMove:' in line:
        indent = line[:len(line) - len(line.lstrip())]
        new_lines.append(line)
        new_lines.append(indent + "    if hasattr(self, 'ferramenta_atual'):\n")
        new_lines.append(indent + "        if self.ferramenta_atual.on_mouse_move(event, self):\n")
        new_lines.append(indent + "            return True\n")
        skip = True
        continue

    if 'elif event.type() == QEvent.Type.MouseButtonRelease:' in line:
        indent = line[:len(line) - len(line.lstrip())]
        new_lines.append(line)
        new_lines.append(indent + "    if hasattr(self, 'ferramenta_atual'):\n")
        new_lines.append(indent + "        if self.ferramenta_atual.on_mouse_release(event, self):\n")
        new_lines.append(indent + "            return True\n")
        new_lines.append(indent + "    # Consome releases perdidos se alguma flag ficou ativada\n")
        new_lines.append(indent + "    if getattr(self, 'arrastando_janelamento', False) or getattr(self, 'arrastando_zoom', False) or getattr(self, 'arrastando_pan', False):\n")
        new_lines.append(indent + "        self.arrastando_janelamento = self.arrastando_zoom = self.arrastando_pan = False\n")
        new_lines.append(indent + "        self.interactor.setCursor(Qt.CursorShape.ArrowCursor)\n")
        new_lines.append(indent + "        return True\n")
        skip = True
        continue
        
    if skip:
        # Detect where the block ends: usually the next elif or a return or except
        # We know MouseButtonPress ends at MouseButtonDblClick
        if 'elif event.type() == QEvent.Type.MouseButtonDblClick:' in line:
            skip = False
        # We know MouseMove ends at MouseButtonRelease
        elif 'elif event.type() == QEvent.Type.MouseButtonRelease:' in line:
            # But we are skipping it right now, so this won't hit! Wait!
            pass
        elif 'except Exception as e:' in line and 'print(f"Erro no eventFilter:' in lines[i+1]:
            skip = False

    # For 3D Filtro
    if 'if event.type() == QEvent.Type.MouseButtonPress:' in line and 'if obj == self.interactor:' in lines[i-1]:
        indent = line[:len(line) - len(line.lstrip())]
        new_lines.append(line)
        new_lines.append(indent + "    if hasattr(self, 'ferramenta_atual'):\n")
        new_lines.append(indent + "        if self.ferramenta_atual.on_mouse_press(event, self):\n")
        new_lines.append(indent + "            return True\n")
        skip = True
        continue
        
    if skip and 'elif event.type() == QEvent.Type.MouseMove:' in line and 'FiltroEventosDicom3D' in "".join(lines[max(0, i-200):i]):
        skip = False
        indent = line[:len(line) - len(line.lstrip())]
        new_lines.append(line)
        new_lines.append(indent + "    if hasattr(self, 'ferramenta_atual'):\n")
        new_lines.append(indent + "        if self.ferramenta_atual.on_mouse_move(event, self):\n")
        new_lines.append(indent + "            return True\n")
        skip = True
        continue
        
    if skip and 'elif event.type() == QEvent.Type.MouseButtonRelease:' in line and 'FiltroEventosDicom3D' in "".join(lines[max(0, i-200):i]):
        skip = False
        indent = line[:len(line) - len(line.lstrip())]
        new_lines.append(line)
        new_lines.append(indent + "    if hasattr(self, 'ferramenta_atual'):\n")
        new_lines.append(indent + "        if self.ferramenta_atual.on_mouse_release(event, self):\n")
        new_lines.append(indent + "            return True\n")
        skip = True
        continue
        
    if not skip:
        new_lines.append(line)

with open('refatorado_filtros.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
