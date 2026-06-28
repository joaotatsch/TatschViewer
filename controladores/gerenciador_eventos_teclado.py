from PyQt6.QtCore import QObject, QEvent, Qt

class FiltroTeclado(QObject):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window

    def eventFilter(self, obj, event):
        # Rastreia o clique do mouse em qualquer lugar da aplicação para definir o quadrante ativo
        if event.type() == QEvent.Type.MouseButtonPress:
            parent_widget = obj
            while parent_widget:
                if type(parent_widget).__name__ == "QuadranteVisualizador":
                    if hasattr(self.main_window, 'active_quadrante'):
                        self.main_window.active_quadrante = parent_widget
                    break
                if hasattr(parent_widget, "parent"):
                    parent_widget = parent_widget.parent()
                else:
                    break

        if event.type() == QEvent.Type.MouseButtonRelease:
            if hasattr(self.main_window, 'coordenador_navegacao') and self.main_window.coordenador_navegacao:
                coord = self.main_window.coordenador_navegacao
                if hasattr(coord, 'filtros_eventos') and coord.filtros_eventos:
                    for filtro in coord.filtros_eventos.values():
                        filtro.arrastando_janelamento = False
                        filtro.arrastando_rotacao = False
                        filtro.arrastando_crosshair = False
                        filtro.alvo_reslice = None
                        if getattr(filtro, 'alvo_arraste', None):
                            filtro.alvo_arraste = None
                            if hasattr(filtro, 'interactor') and filtro.interactor:
                                try:
                                    filtro.interactor.setCursor(Qt.CursorShape.ArrowCursor)
                                except Exception:
                                    pass

        if event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
                try:
                    # Aceleração Balística: Passo normal 1, segurando a tecla salta mais rápido
                    step = 3 if event.isAutoRepeat() else 1
                    incremento = -1 if event.key() == Qt.Key.Key_Up else 1
                    
                    # Identifica viewport ativo focado pelo clique
                    if hasattr(self.main_window, 'active_quadrante') and self.main_window.active_quadrante:
                        quadrante = self.main_window.active_quadrante
                        if hasattr(self.main_window, 'coordenador_navegacao') and self.main_window.coordenador_navegacao:
                            nav = self.main_window.coordenador_navegacao.navegador_2d
                            
                            nome_visao_raw = quadrante.nome
                            nome_visao_cap = quadrante.nome.capitalize()
                            
                            plane = nav.planos.get(nome_visao_raw) or nav.planos.get(nome_visao_cap)
                            # Fallback robusto apenas se tudo falhar
                            if not plane and len(nav.planos) > 0:
                                plane = list(nav.planos.values())[0]
                                
                            if plane and nav.volume_ativo:
                                spacing = nav.volume_ativo.GetSpacing()
                                normal = plane.GetNormal()
                                esp = abs(normal[0]*spacing[0]) + abs(normal[1]*spacing[1]) + abs(normal[2]*spacing[2])
                                delta_mm = incremento * step * esp
                                
                                # Empurra o plano
                                plane.Push(delta_mm)
                                
                                # Atualiza as bússolas e indicadores
                                if hasattr(nav, 'atualizar_bussola'):
                                    nav.atualizar_bussola()
                                    
                                # Atualiza projeções cruzadas
                                if hasattr(self.main_window, 'operador_projecao') and self.main_window.operador_projecao:
                                    p = nav.planos
                                    if "Sagital" in p and "Coronal" in p and "Axial" in p:
                                        nx, ny, nz = p["Sagital"].GetOrigin()[0], p["Coronal"].GetOrigin()[1], p["Axial"].GetOrigin()[2]
                                        self.main_window.operador_projecao.atualizar_linhas(nx, ny, nz, p)
                                        
                                # Sincroniza o Scrollbar associado ao quadrante (Anti-loop já garantido lá dentro)
                                if hasattr(quadrante, "sincronizar_scrollbar"):
                                    quadrante.sincronizar_scrollbar(plane, nav.volume_ativo)
                                    
                                for q in self.main_window.coordenador_exibicao.widget_layout_ativo.visoes.values():
                                    if hasattr(q, 'interactor') and q.interactor and q.interactor.GetRenderWindow():
                                        q.interactor.GetRenderWindow().Render()
                                return True
                except RuntimeError:
                    # Ocorre se o QuadranteVisualizador ou seus widgets C++ tiverem sido destruídos
                    # (ex: mudança de layout antes de o usuário clicar novamente na nova tela)
                    self.main_window.active_quadrante = None
                    
        return super().eventFilter(obj, event)
