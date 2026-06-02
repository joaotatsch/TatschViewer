import sys

filepath = 'd:/Desktop/Projetos/Neuroviewer/interface.py'
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for i in range(len(lines)):
    if i >= 2715 and i <= 2723:
        pass # delete old lines
    else:
        new_lines.append(lines[i])

injection = '''        def on_loaded(res, q=quadrante):
            nome_visao = q.label.text()
            vtk_image, sitk_image, np_view, prop_dicom = res

            tempo_antes = time.perf_counter()
            self.coordenador_navegacao.inicializar_tela_dinamica(nome_visao, vtk_image, q, self.on_mouse_janelamento_changed, self.on_mouse_espessura_changed)
            tempo_final = time.perf_counter()
            print(f"[SENSOR DRAW] Tempo total para inicializar e desenhar na tela: {tempo_final - tempo_antes:.4f}s")

            self.coordenador_navegacao.navegador_2d.meta_actors[nome_visao].SetInput(self.extrair_texto_hud(prop_dicom))

            # --- GARANTE A PRESERVAÇÃO DE MEMÓRIA DA TELA NO DRAG & DROP ---
            win = self
            while win is not None and not hasattr(win, "buffers_vivos"):
                win = win.parent() if hasattr(win, "parent") else None
                
            if win is not None:
                win.buffers_vivos[nome_visao] = (sitk_image, np_view, vtk_image)
            elif not hasattr(self, "buffers_vivos"):
                self.buffers_vivos = {nome_visao: (sitk_image, np_view, vtk_image)}

            import gc
            QTimer.singleShot(100, gc.collect)
'''

new_lines.insert(2715, injection)

with open(filepath, 'w', encoding='utf-8') as f:
    for line in new_lines:
        f.write(line)
