import os
import re

# 1. FIX FERRAMENTA NORMAL (Girar imagem 2D)
file_normal = r'd:\Desktop\Projetos\TatschViewer\navegacao\ferramentas\ferramenta_normal.py'
with open(file_normal, 'r', encoding='utf-8') as f:
    lines_normal = f.readlines()

new_normal = []
for line in lines_normal:
    if "filtro.operador_interacao_reslice.rotacionar_plano(filtro.nome_visao, dx)" in line:
        indent = line[:len(line) - len(line.lstrip())]
        new_normal.append(line)
        new_normal.append(indent[:-4] + "else:\n")
        new_normal.append(indent + "    renderer = filtro.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()\n")
        new_normal.append(indent + "    if renderer:\n")
        new_normal.append(indent + "        camera = renderer.GetActiveCamera()\n")
        new_normal.append(indent + "        if camera:\n")
        new_normal.append(indent + "            camera.Roll(dx * 0.5)\n")
        new_normal.append(indent + "            filtro.navegador_2d.atualizar_bussola()\n")
        new_normal.append(indent + "            filtro.interactor.GetRenderWindow().Render()\n")
    else:
        new_normal.append(line)

with open(file_normal, 'w', encoding='utf-8') as f:
    f.writelines(new_normal)


# 2. FIX FILTROS_EVENTOS (Janelamento 3D + Property 3D)
file_filtros = r'd:\Desktop\Projetos\TatschViewer\navegacao\filtros_eventos.py'
with open(file_filtros, 'r', encoding='utf-8') as f:
    lines_filtros = f.readlines()

new_filtros = []
in_3d_init = False
for i, line in enumerate(lines_filtros):
    if "class FiltroEventosDicom3D" in line:
        in_3d_init = True
        
    if in_3d_init and "@property" in line:
        # Skip the broken local properties
        pass
    elif in_3d_init and "def ferramenta_ativa(self):" in line:
        pass
    elif in_3d_init and "return getattr(self, '_ferramenta_ativa', 'Normal')" in line:
        pass
    elif in_3d_init and "@ferramenta_ativa.setter" in line:
        pass
    elif in_3d_init and "def ferramenta_ativa(self, value):" in line:
        pass
    elif in_3d_init and "self._ferramenta_ativa = value" in line:
        pass
    elif in_3d_init and "if hasattr(self, 'ferramentas') and value in self.ferramentas:" in line:
        pass
    elif in_3d_init and "if hasattr(self, 'ferramenta_atual') and hasattr(self.ferramenta_atual, 'on_exit'):" in line:
        pass
    elif in_3d_init and "self.ferramenta_atual.on_exit(self)" in line:
        pass
    elif in_3d_init and "self.ferramenta_atual = self.ferramentas[value]" in line:
        pass
    elif in_3d_init and "if hasattr(self.ferramenta_atual, 'on_enter'):" in line:
        pass
    elif in_3d_init and "self.ferramenta_atual.on_enter(self)" in line:
        pass
    elif in_3d_init and "self.bisturi_pontos = []" in line:
        # Inject the correct property AT CLASS LEVEL BEFORE INIT
        # Wait, if we are at __init__, we should inject it BEFORE __init__ or AFTER it but at class level.
        # But we already passed `def __init__`.
        # We can just keep going and we will inject the property at the very end of the file.
        new_filtros.append(line)
    elif "elif event.type() == QEvent.Type.MouseButtonDblClick:" in line:
        # Let's fix the double click just in case! 
        # Pass it forward by returning False instead of True.
        new_filtros.append(line)
    elif "return True" in line and "Impede que o duplo clique ative funções" in "".join(lines_filtros[max(0, i-2):i]):
        new_filtros.append(line.replace("return True", "return False"))
    else:
        new_filtros.append(line)


# Inject 3D windowing into MouseButtonPress and MouseMove for 3D
final_filtros = []
for i, line in enumerate(new_filtros):
    if "if self.ferramenta_atual.on_mouse_press(event, self):" in line and "FiltroEventosDicom3D" in "".join(new_filtros[max(0, i-60):i]):
        indent = line[:len(line) - len(line.lstrip())]
        final_filtros.append(line)
        final_filtros.append(indent + "if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:\n")
        final_filtros.append(indent + "    self.arrastando_janelamento = True\n")
        final_filtros.append(indent + "    self.ultimo_pos_x = event.position().x()\n")
        final_filtros.append(indent + "    self.ultimo_pos_y = event.position().y()\n")
        final_filtros.append(indent + "    return True\n")
        continue

    if "if self.ferramenta_atual.on_mouse_move(event, self):" in line and "FiltroEventosDicom3D" in "".join(new_filtros[max(0, i-60):i]):
        indent = line[:len(line) - len(line.lstrip())]
        final_filtros.append(line)
        final_filtros.append(indent + "if self.arrastando_janelamento and event.buttons() & Qt.MouseButton.LeftButton:\n")
        final_filtros.append(indent + "    dx = event.position().x() - self.ultimo_pos_x\n")
        final_filtros.append(indent + "    dy = event.position().y() - self.ultimo_pos_y\n")
        final_filtros.append(indent + "    self.ultimo_pos_x = event.position().x()\n")
        final_filtros.append(indent + "    self.ultimo_pos_y = event.position().y()\n")
        final_filtros.append(indent + "    ww_atual = self.navegador_3d.ww_3d\n")
        final_filtros.append(indent + "    wl_atual = self.navegador_3d.wl_3d\n")
        final_filtros.append(indent + "    sensibilidade = 2.0\n")
        final_filtros.append(indent + "    novo_ww = max(10.0, ww_atual + dx * sensibilidade)\n")
        final_filtros.append(indent + "    novo_wl = wl_atual - dy * sensibilidade\n")
        final_filtros.append(indent + "    self.navegador_3d.atualizar_transfer_functions(novo_ww, novo_wl)\n")
        final_filtros.append(indent + "    if self.janelamento_callback: self.janelamento_callback(novo_ww, novo_wl)\n")
        final_filtros.append(indent + "    return True\n")
        continue

    final_filtros.append(line)

# Add class-level property for 3D at the very end
prop3d = """
    @property
    def ferramenta_ativa(self):
        return getattr(self, '_ferramenta_ativa', 'Normal')

    @ferramenta_ativa.setter
    def ferramenta_ativa(self, value):
        self._ferramenta_ativa = value
        if hasattr(self, 'ferramentas') and value in self.ferramentas:
            if hasattr(self, 'ferramenta_atual') and hasattr(self.ferramenta_atual, 'on_exit'):
                self.ferramenta_atual.on_exit(self)
            self.ferramenta_atual = self.ferramentas[value]
            if hasattr(self.ferramenta_atual, 'on_enter'):
                self.ferramenta_atual.on_enter(self)
"""
final_filtros.append(prop3d)

with open(file_filtros, 'w', encoding='utf-8') as f:
    f.writelines(final_filtros)
