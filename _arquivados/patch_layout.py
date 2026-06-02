import sys

with open('interface.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

start_idx = -1
end_idx = -1

for i, line in enumerate(lines):
    if line.startswith("    def alterar_layout_modo(self, tipo_layout: str):"):
        start_idx = i
    if start_idx != -1 and i > start_idx and line.startswith("    def on_preset_changed(self, chave_preset):"):
        end_idx = i
        break

if start_idx == -1 or end_idx == -1:
    print("Could not find the bounds for alterar_layout_modo!")
    sys.exit(1)

new_method = """    def alterar_layout_modo(self, tipo_layout: str):
        \"\"\"
        Chama o coordenador de exibição para reestruturar os widgets ativos na tela.
        \"\"\"
        print(f"[TELEMETRIA-UI] Iniciando transição/carregamento no layout: {tipo_layout}", flush=True)

        # 1. KILL-SWITCH: Desarma os filtros de eventos antigos ANTES de destruir o layout
        if hasattr(self, 'coordenador_navegacao') and self.coordenador_navegacao:
            if hasattr(self.coordenador_navegacao, 'filtros_eventos'):
                for filtro in self.coordenador_navegacao.filtros_eventos.values():
                    if filtro:
                        filtro.ativo = False
            
            # Desativa interatores C++ antigos nativamente
            if hasattr(self, 'coordenador_exibicao') and hasattr(self.coordenador_exibicao, 'widget_layout_ativo'):
                if hasattr(self.coordenador_exibicao.widget_layout_ativo, 'visoes'):
                    for visao_nome, widget_vtk in self.coordenador_exibicao.widget_layout_ativo.visoes.items():
                        try:
                            if hasattr(widget_vtk, 'interactor') and widget_vtk.interactor:
                                widget_vtk.interactor.Disable()
                        except Exception:
                            pass

        # 2. Transição Física: Altera o layout dos widgets do PyQt6
        self.coordenador_exibicao.definir_layout(tipo_layout)
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()

        # 3. Hard Reset para 4-Up (Esvaziar Telas)
        if tipo_layout in ["MPR", "Normal", "4-Up"]:
            print("[TELEMETRIA-UI] Executando Hard Reset para o layout padrão...", flush=True)
            # 1. Descarrega as séries da memória
            self.coordenador_navegacao = None
            self.vtk_image_ativa = None
            
            # 2. Deixa as 4 telas limpas (Pretas/Vazias)
            if hasattr(self, 'coordenador_exibicao') and hasattr(self.coordenador_exibicao, 'widget_layout_ativo'):
                if hasattr(self.coordenador_exibicao.widget_layout_ativo, 'visoes'):
                    for visao_nome, widget_vtk in self.coordenador_exibicao.widget_layout_ativo.visoes.items():
                        try:
                            if hasattr(widget_vtk, 'renderer') and widget_vtk.renderer:
                                widget_vtk.renderer.RemoveAllViewProps()
                                widget_vtk.renderer.SetBackground(0.05, 0.05, 0.05)
                            if hasattr(widget_vtk, 'interactor') and widget_vtk.interactor.GetRenderWindow():
                                widget_vtk.interactor.GetRenderWindow().Render()
                        except Exception:
                            pass
                            
            # 3. Informa o usuário e aguarda
            self.statusBar().showMessage("Múltiplas telas fechadas. Selecione uma série na lista para carregar no 4-Up.")
            return

        # 4. Lógica para transição para os layouts de Comparação (Múltiplas Telas)
        self.statusBar().showMessage(f"Layout alterado para: {tipo_layout}")
        if hasattr(self.coordenador_exibicao, 'widget_layout_ativo') and hasattr(self.coordenador_exibicao.widget_layout_ativo, 'visoes'):
            print(f"[TELEMETRIA-UI] Chaves de visões ativas enviadas: {list(self.coordenador_exibicao.widget_layout_ativo.visoes.keys())}", flush=True)
            
        if hasattr(self, 'coordenador_navegacao') and self.coordenador_navegacao and hasattr(self, 'vtk_image_ativa') and self.vtk_image_ativa:
            print(f"[TELEMETRIA-UI] Re-inicializando navegação para o novo layout: {tipo_layout}", flush=True)
            self.coordenador_navegacao.inicializar_visualizacao(
                self.vtk_image_ativa,
                self.coordenador_exibicao.widget_layout_ativo.visoes,
                janelamento_callback=self.on_mouse_janelamento_changed,
                espessura_callback=self.on_mouse_espessura_changed
            )

"""

lines = lines[:start_idx] + [new_method] + lines[end_idx:]

with open('interface.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Patch applied successfully.")
