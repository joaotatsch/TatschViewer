import os

file_path = os.path.join('navegacao', '__init__.py')

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

start_marker = "            if event.type() == QEvent.Type.Wheel:"
end_marker = "            elif event.type() == QEvent.Type.MouseButtonPress:"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print("Markers not found!")
    exit(1)

new_block = """            if event.type() == QEvent.Type.Wheel:
                # BLINDAGEM ANTI-SEGFAULT
                # [BLINDAGEM DE VOLUME]
                volume_ativo = self.navegador_2d.volume_ativo
                if volume_ativo is None:
                    return False

                delta = event.angleDelta().y()
                if delta != 0:
                    inc = 1 if delta > 0 else -1
                    if self.nome_visao in self.navegador_2d.planos:
                        plane = self.navegador_2d.planos[self.nome_visao]
                        
                        if self.nome_visao not in self.navegador_2d.mappers or self.navegador_2d.mappers[self.nome_visao] is None:
                            return False
                            
                        spacing = self.navegador_2d.mappers[self.nome_visao].GetInput().GetSpacing()
                        normal = plane.GetNormal()
                        esp = abs(normal[0]*spacing[0]) + abs(normal[1]*spacing[1]) + abs(normal[2]*spacing[2])
                        deslocamento_mm = inc * esp
                        plane.Push(deslocamento_mm)
                        
                        # [BLINDAGEM MIP]
                        if hasattr(self.parent(), 'operador_projecao'):
                            planos = self.navegador_2d.planos
                            if "Sagital" in planos and "Coronal" in planos and "Axial" in planos:
                                cx = planos["Sagital"].GetOrigin()[0]
                                cy = planos["Coronal"].GetOrigin()[1]
                                cz = planos["Axial"].GetOrigin()[2]
                                self.parent().operador_projecao.atualizar_linhas(cx, cy, cz, planos)
                                
                        if hasattr(self.parent(), 'coordenador_medidas'):
                            self.parent().coordenador_medidas.verificar_visibilidade(self.nome_visao, plane.GetOrigin())
                            
                        # [BLINDAGEM RENDER]
                        if hasattr(self.navegador_2d, 'renderers_2d'):
                            for nome, rnd in self.navegador_2d.renderers_2d.items():
                                try:
                                    if rnd is not None and rnd.GetRenderWindow() is not None:
                                        rnd.GetRenderWindow().Render()
                                except Exception:
                                    pass
                        else:
                            self._renderizar_seguro()

                        # [NOVO] Integração Sync Scroll
                        try:
                            if hasattr(self.parent(), 'parent'):
                                main_window = self.parent().parent()
                                if main_window and hasattr(main_window, 'btn_sync_scroll') and main_window.btn_sync_scroll.isChecked():
                                    if hasattr(main_window, 'sincronizar_scroll_global'):
                                        main_window.sincronizar_scroll_global(self.nome_visao, deslocamento_mm, self.parent())
                        except Exception:
                            pass

                return True
                
"""

new_content = content[:start_idx] + new_block + content[end_idx:]

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Modification successful.")
