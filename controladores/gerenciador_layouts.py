# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import QApplication, QAbstractButton

class GerenciadorLayouts:
    def __init__(self, main_window):
        self.main_window = main_window
        self.sincronizacao_ativa = False

    def alterar_layout_modo(self, tipo_layout: str):
        if hasattr(self.main_window, 'coordenador_navegacao') and self.main_window.coordenador_navegacao:
            if hasattr(self.main_window.coordenador_navegacao, 'filtros_eventos'):
                for filtro in self.main_window.coordenador_navegacao.filtros_eventos.values():
                    if filtro:
                        filtro.ativo = False
            
            if hasattr(self.main_window, 'coordenador_exibicao') and hasattr(self.main_window.coordenador_exibicao, 'widget_layout_ativo'):
                if hasattr(self.main_window.coordenador_exibicao.widget_layout_ativo, 'visoes'):
                    for visao_nome, widget_vtk in self.main_window.coordenador_exibicao.widget_layout_ativo.visoes.items():
                        try:
                            if hasattr(widget_vtk, 'interactor') and widget_vtk.interactor:
                                widget_vtk.interactor.Disable()
                        except Exception:
                            pass

        self.main_window.coordenador_exibicao.definir_layout(tipo_layout)
        QApplication.processEvents()

        if tipo_layout in ["MPR", "Normal", "4-Up"]:
            if hasattr(self.main_window, 'coordenador_navegacao'):
                self.main_window.coordenador_navegacao = None
            if hasattr(self.main_window, 'vtk_image_ativa'):
                self.main_window.vtk_image_ativa = None
                
            self.main_window.statusBar().showMessage("Layout reiniciado. Selecione uma série na lista para carregar.")
            return

        self.main_window.statusBar().showMessage(f"Layout alterado para: {tipo_layout}")
        if hasattr(self.main_window, 'coordenador_navegacao') and self.main_window.coordenador_navegacao and hasattr(self.main_window, 'vtk_image_ativa') and self.main_window.vtk_image_ativa:
            self.main_window.coordenador_navegacao.inicializar_visualizacao(
                self.main_window.vtk_image_ativa,
                self.main_window.coordenador_exibicao.widget_layout_ativo.visoes,
                janelamento_callback=self.main_window.gerenciador_ferramentas.on_mouse_janelamento_changed,
                espessura_callback=self.main_window.gerenciador_ferramentas.on_mouse_espessura_changed
            )

    def on_visualizacao_changed(self, modo: str):
        if hasattr(self.main_window, 'coordenador_exibicao') and hasattr(self.main_window.coordenador_exibicao, 'widget_layout_ativo'):
            layout_ativo = self.main_window.coordenador_exibicao.widget_layout_ativo
            if hasattr(layout_ativo, 'aplicar_modo_visualizacao'):
                layout_ativo.aplicar_modo_visualizacao(modo)
                
                if hasattr(layout_ativo, 'visoes'):
                    for quadrante in layout_ativo.visoes.values():
                        if not quadrante.isHidden() and hasattr(quadrante, 'interactor') and quadrante.interactor:
                            try:
                                quadrante.interactor.GetRenderWindow().Render()
                            except Exception:
                                pass

    def on_layout_selecionado(self, modo: str):
        if not hasattr(self.main_window, 'coordenador_exibicao'):
            return
            
        self.main_window._layout_explicitamente_escolhido = True
        self.alterar_layout_modo(modo)
        
        if modo in ["MPR", "1x2", "1x3", "2x2", "2x3"]:
            self.on_visualizacao_changed("4-up")
        
        if hasattr(self.main_window.coordenador_exibicao.widget_layout_ativo, "visoes"):
            for visao_nome, widget_vtk in self.main_window.coordenador_exibicao.widget_layout_ativo.visoes.items():
                if hasattr(widget_vtk, "GetRenderWindow") and widget_vtk.GetRenderWindow():
                    widget_vtk.GetRenderWindow().Render()

    def on_sync_scroll_toggled(self, checked):
        self.sincronizacao_ativa = checked

    def is_sincronizacao_ativa(self):
        if getattr(self, "sincronizacao_ativa", False):
            return True
            
        for btn in self.main_window.findChildren(QAbstractButton):
            texto = btn.text() or ""
            nome_objeto = btn.objectName().lower() or ""
            if "🔗" in texto or "sync" in nome_objeto or "sinc" in nome_objeto:
                if btn.isCheckable() and btn.isChecked():
                    return True
        return False

    def sincronizar_rolagem_global(self, coordenador_origem, nome_visao, delta_mm):
        from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
        interactors = self.main_window.findChildren(QVTKRenderWindowInteractor)
        
        for idx, interactor in enumerate(interactors):
            tem_filtro = hasattr(interactor, "filtro_dicom")
            if tem_filtro:
                filtro = interactor.filtro_dicom
                if filtro and hasattr(filtro, "parent") and filtro.parent() == coordenador_origem:
                    continue
                    
                try:
                    nav = filtro.navegador_2d if filtro else None
                    if nav:
                        plano_alvo = None
                        if nome_visao in nav.planos:
                            plano_alvo = nav.planos[nome_visao]
                        elif len(nav.planos) > 0:
                            plano_alvo = list(nav.planos.values())[0]
                            
                        if plano_alvo:
                            plano_alvo.Push(delta_mm)
                            
                            for visao_nome, rnd in nav.renderers_2d.items():
                                if hasattr(self.main_window.coordenador_exibicao.widget_layout_ativo, "visoes"):
                                    if visao_nome in self.main_window.coordenador_exibicao.widget_layout_ativo.visoes:
                                        if rnd and rnd.GetRenderWindow():
                                            rnd.ResetCameraClippingRange()
                                            rnd.GetRenderWindow().Render()
                except Exception as e:
                    print(f"[SYNC-ERR] Falha ao sincronizar tela espelho: {e}", flush=True)
