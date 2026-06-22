# -*- coding: utf-8 -*-
import traceback

class GerenciadorFerramentas:
    def __init__(self, main_window):
        self.main_window = main_window

    def on_preset_changed(self, chave_preset):
        try:
            if not isinstance(chave_preset, str):
                return
                
            if not hasattr(self.main_window, 'presets_clinicos') or chave_preset not in self.main_window.presets_clinicos:
                return
                
            preset = self.main_window.presets_clinicos[chave_preset]
            ww = preset["ww"]
            wl = preset["wl"]
            nome = preset["nome"]
            
            if chave_preset == "customizado":
                self.main_window.btn_presets.setToolTip("Preset: Customizado")
                return
                
            self.main_window.btn_presets.setToolTip(f"Preset: {nome}")
            self.aplicar_ww_wl(ww, wl)
            
        except Exception as e:
            traceback.print_exc()
            self.main_window.statusBar().showMessage("Falha ao aplicar preset em múltiplas telas.")

    def aplicar_ww_wl(self, ww: float, wl: float):
        try:
            if hasattr(self.main_window, 'coordenador_navegacao') and self.main_window.coordenador_navegacao:
                if hasattr(self.main_window.coordenador_navegacao, 'navegador_2d') and self.main_window.coordenador_navegacao.navegador_2d:
                    self.main_window.coordenador_navegacao.navegador_2d.aplicar_preset(ww, wl)

            if hasattr(self.main_window, 'coordenador_exibicao') and hasattr(self.main_window.coordenador_exibicao, 'widget_layout_ativo'):
                layout_ativo = self.main_window.coordenador_exibicao.widget_layout_ativo
                
                if layout_ativo and hasattr(layout_ativo, 'visoes'):
                    is_layout_4_up = (layout_ativo.__class__.__name__ == "Layout4Up")
                    
                    for nome_visao, quadrante in layout_ativo.visoes.items():
                        if hasattr(quadrante, 'interactor') and quadrante.interactor:
                            if is_layout_4_up and nome_visao == "3D":
                                continue
                            quadrante.interactor.GetRenderWindow().Render()

        except Exception as e:
            traceback.print_exc()
            self.main_window.statusBar().showMessage("Falha ao propagar preset nas telas ativas.")

    def aplicar_preset_por_nome(self, nome_preset: str):
        try:
            if not hasattr(self.main_window, 'presets_clinicos'):
                return
                
            if nome_preset not in self.main_window.presets_clinicos:
                return
                
            preset = self.main_window.presets_clinicos[nome_preset]
            self.main_window.btn_presets.setToolTip(f"Preset: {preset['nome']}")
            self.aplicar_ww_wl(preset["ww"], preset["wl"])
            
        except Exception as e:
            traceback.print_exc()
            self.main_window.statusBar().showMessage("Falha ao aplicar preset em múltiplas telas.")

    def on_mouse_janelamento_changed(self, ww, wl):
        if not hasattr(self.main_window, 'presets_clinicos'):
            return
            
        preset_encontrado = None
        for chave, preset in self.main_window.presets_clinicos.items():
            if chave == "customizado":
                continue
            if int(ww) == int(preset["ww"]) and int(wl) == int(preset["wl"]):
                preset_encontrado = preset
                break
                
        if preset_encontrado:
            self.main_window.btn_presets.setToolTip(f"Preset: {preset_encontrado['nome']}")
        else:
            self.main_window.btn_presets.setToolTip("Preset: Customizado")

    def on_mouse_espessura_changed(self, esp_val):
        self.main_window.spin_espessura.blockSignals(True)
        self.main_window.spin_espessura.setValue(int(esp_val))
        self.main_window.spin_espessura.blockSignals(False)

    def on_projecao_changed(self, modo=None):
        if modo is not None:
            self.main_window.modo_projecao_atual = modo
        else:
            modo = self.main_window.modo_projecao_atual

        esp = self.main_window.spin_espessura.value()
        
        if modo != "Normal" and esp == 0:
            self.main_window.spin_espessura.blockSignals(True)
            self.main_window.spin_espessura.setValue(20)
            self.main_window.spin_espessura.blockSignals(False)
            esp = 20
        elif modo == "Normal" and esp != 0:
            self.main_window.spin_espessura.blockSignals(True)
            self.main_window.spin_espessura.setValue(0)
            self.main_window.spin_espessura.blockSignals(False)
            esp = 0
            
        if hasattr(self.main_window, 'coordenador_navegacao') and hasattr(self.main_window.coordenador_navegacao, 'operador_projecao'):
            self.main_window.coordenador_navegacao.operador_projecao.aplicar_projecao_global(modo, esp)
            
            if hasattr(self.main_window.coordenador_navegacao, 'navegador_2d'):
                planos = self.main_window.coordenador_navegacao.navegador_2d.planos
                if 'Sagital' in planos and 'Coronal' in planos and 'Axial' in planos:
                    cx = planos['Sagital'].GetOrigin()[0]
                    cy = planos['Coronal'].GetOrigin()[1]
                    cz = planos['Axial'].GetOrigin()[2]
                    self.main_window.coordenador_navegacao.operador_projecao.atualizar_linhas(cx, cy, cz, planos)

            if hasattr(self.main_window, 'coordenador_exibicao') and hasattr(self.main_window.coordenador_exibicao, 'widget_layout_ativo') and self.main_window.coordenador_exibicao.widget_layout_ativo:
                if hasattr(self.main_window.coordenador_exibicao.widget_layout_ativo, 'visoes'):
                    for nome, quadrante in self.main_window.coordenador_exibicao.widget_layout_ativo.visoes.items():
                        quadrante.interactor.GetRenderWindow().Render()

    def _desativar_outras_ferramentas(self, ignorar=None):
        ferramentas = {
            'btn_crosshair': self.main_window.btn_crosshair,
            'btn_regua': self.main_window.btn_regua,
            'btn_elipse': self.main_window.btn_elipse,
            'btn_reslice': self.main_window.btn_reslice,
            'action_adicionar_semente': getattr(self.main_window, 'action_adicionar_semente', None),
            'action_caixa_recorte': getattr(self.main_window, 'action_caixa_recorte', None),
            'action_bisturi_desenhar': getattr(self.main_window, 'action_bisturi_desenhar', None)
        }
        for nome, btn in ferramentas.items():
            if btn and nome != ignorar and hasattr(btn, 'isChecked') and btn.isChecked():
                btn.setChecked(False)
                if nome == 'action_caixa_recorte':
                    self.on_box_adjust_toggled(False)
                elif nome == 'action_bisturi_desenhar':
                    self.on_bisturi_toggled(False)

    def on_crosshair_toggled(self, checked):
        if checked:
            self._desativar_outras_ferramentas('btn_crosshair')
        if hasattr(self.main_window, 'coordenador_navegacao') and self.main_window.coordenador_navegacao:
            if hasattr(self.main_window.coordenador_navegacao, 'operador_crosshair'):
                if hasattr(self.main_window.coordenador_navegacao.operador_crosshair, 'ator'):
                    self.main_window.coordenador_navegacao.operador_crosshair.ator.SetVisibility(checked)
                for nome, filtro in self.main_window.coordenador_navegacao.filtros_eventos.items():
                    if hasattr(filtro, 'modo_crosshair'):
                        filtro.modo_crosshair = checked
                if hasattr(self.main_window, 'coordenador_exibicao') and hasattr(self.main_window.coordenador_exibicao, 'widget_layout_ativo') and self.main_window.coordenador_exibicao.widget_layout_ativo:
                    if hasattr(self.main_window.coordenador_exibicao.widget_layout_ativo, 'visoes'):
                        for nome, quadrante in self.main_window.coordenador_exibicao.widget_layout_ativo.visoes.items():
                            quadrante.interactor.GetRenderWindow().Render()

    def on_regua_toggled(self, checked):
        if checked:
            self._desativar_outras_ferramentas('btn_regua')
        if hasattr(self.main_window, 'coordenador_navegacao') and self.main_window.coordenador_navegacao:
            for nome, filtro in self.main_window.coordenador_navegacao.filtros_eventos.items():
                if hasattr(filtro, 'ferramenta_ativa'):
                    filtro.ferramenta_ativa = "Regua" if checked else "Normal"
                
    def on_elipse_toggled(self, checked):
        if checked:
            self._desativar_outras_ferramentas('btn_elipse')
        if hasattr(self.main_window, 'coordenador_navegacao') and self.main_window.coordenador_navegacao:
            for nome, filtro in self.main_window.coordenador_navegacao.filtros_eventos.items():
                if hasattr(filtro, 'ferramenta_ativa'):
                    filtro.ferramenta_ativa = "Elipse" if checked else "Normal"

    def on_reslice_toggled(self, checked):
        if checked:
            self._desativar_outras_ferramentas('btn_reslice')
        if hasattr(self.main_window, 'coordenador_navegacao') and self.main_window.coordenador_navegacao:
            for nome, filtro in self.main_window.coordenador_navegacao.filtros_eventos.items():
                if hasattr(filtro, 'ferramenta_ativa'):
                    filtro.ferramenta_ativa = "Reslice" if checked else "Normal"
                    
            if hasattr(self.main_window.coordenador_navegacao, 'operador_projecao'):
                self.main_window.coordenador_navegacao.operador_projecao.set_reslice_ativo(checked)
                
            if hasattr(self.main_window, 'coordenador_exibicao') and hasattr(self.main_window.coordenador_exibicao, 'widget_layout_ativo') and hasattr(self.main_window.coordenador_exibicao.widget_layout_ativo, 'visoes'):
                for quadrante in self.main_window.coordenador_exibicao.widget_layout_ativo.visoes.values():
                    quadrante.interactor.GetRenderWindow().Render()

    def on_semente_toggled(self, checked):
        if checked:
            self._desativar_outras_ferramentas('action_adicionar_semente')
        if hasattr(self.main_window, 'coordenador_navegacao') and self.main_window.coordenador_navegacao:
            for nome, filtro in self.main_window.coordenador_navegacao.filtros_eventos.items():
                if hasattr(filtro, 'ferramenta_ativa'):
                    filtro.ferramenta_ativa = "Semente" if checked else "Normal"

    def on_box_adjust_toggled(self, checked):
        try:
            import vtk
            if checked:
                self._desativar_outras_ferramentas('action_caixa_recorte')
                
            if not hasattr(self.main_window, 'coordenador_navegacao') or getattr(self.main_window, 'coordenador_navegacao') is None:
                return
            nav = self.main_window.coordenador_navegacao
            
            if hasattr(nav, 'filtros_eventos'):
                for filtro in nav.filtros_eventos.values():
                    if hasattr(filtro, 'ferramenta_ativa'):
                        if checked:
                            filtro.ferramenta_ativa = "CropBox"
                        else:
                            if filtro.ferramenta_ativa == "CropBox":
                                filtro.ferramenta_ativa = "Normal"
            
            if hasattr(nav, 'navegador_3d') and getattr(nav, 'navegador_3d') is not None:
                if hasattr(nav.navegador_3d, 'mostrar_caixa_recorte'):
                    nav.navegador_3d.mostrar_caixa_recorte(checked)
                    
                rep_compartilhada = getattr(nav.navegador_3d, 'crop_representation', None)
                if rep_compartilhada is None:
                    return
                    
                layout_ativo = getattr(self.main_window.coordenador_exibicao, 'widget_layout_ativo', None)
                visoes = getattr(layout_ativo, 'visoes', {}) if layout_ativo else {}
                
                def renderizar_todas_as_telas(obj, event):
                    for visao in visoes.values():
                        if hasattr(visao, 'interactor') and visao.interactor and visao.interactor.GetRenderWindow():
                            visao.interactor.GetRenderWindow().Render()
                            
                if not hasattr(nav.navegador_3d, 'crop_obs_id'):
                    if hasattr(nav.navegador_3d, 'crop_widget') and nav.navegador_3d.crop_widget:
                        nav.navegador_3d.crop_obs_id = nav.navegador_3d.crop_widget.AddObserver("InteractionEvent", renderizar_todas_as_telas)
                        
                nav2d = getattr(nav, 'navegador_2d', None)
                if nav2d:
                    if not hasattr(nav2d, 'crop_widgets'):
                        nav2d.crop_widgets = {}
                        
                    for nome in ["Axial", "Coronal", "Sagital"]:
                        if nome in visoes:
                            if nome not in nav2d.crop_widgets:
                                bw = vtk.vtkBoxWidget2()
                                translator = bw.GetEventTranslator()
                                translator.SetTranslation(vtk.vtkCommand.RightButtonPressEvent, vtk.vtkWidgetEvent.NoEvent)
                                translator.SetTranslation(vtk.vtkCommand.RightButtonReleaseEvent, vtk.vtkWidgetEvent.NoEvent)
                                
                                bw.SetInteractor(visoes[nome].interactor)
                                bw.SetRepresentation(rep_compartilhada)
                                bw.SetRotationEnabled(False)
                                bw.AddObserver("InteractionEvent", renderizar_todas_as_telas)
                                nav2d.crop_widgets[nome] = bw
                                
                            if checked:
                                nav2d.crop_widgets[nome].EnabledOn()
                            else:
                                nav2d.crop_widgets[nome].EnabledOff()
                                
                renderizar_todas_as_telas(None, None)
                
        except Exception as e:
            print(f"[CROP 3D] Erro ao ajustar caixa: {e}")

    def on_box_apply_clicked(self):
        try:
            if not hasattr(self.main_window, 'coordenador_navegacao') or getattr(self.main_window, 'coordenador_navegacao') is None:
                return
            nav = self.main_window.coordenador_navegacao
            if hasattr(nav, 'navegador_3d') and getattr(nav, 'navegador_3d') is not None:
                if hasattr(nav.navegador_3d, 'aplicar_recorte_caixa'):
                    nav.navegador_3d.aplicar_recorte_caixa()
                    
            self.on_box_adjust_toggled(False)
            if hasattr(self.main_window, 'action_caixa_recorte'):
                self.main_window.action_caixa_recorte.setChecked(False)
        except Exception as e:
            print(f"[CROP 3D] Erro ao aplicar recorte: {e}")

    def on_box_reset_clicked(self):
        try:
            if not hasattr(self.main_window, 'coordenador_navegacao') or getattr(self.main_window, 'coordenador_navegacao') is None:
                return
            nav = self.main_window.coordenador_navegacao
            if hasattr(nav, 'navegador_3d') and getattr(nav, 'navegador_3d') is not None:
                if hasattr(nav.navegador_3d, 'resetar_recorte'):
                    nav.navegador_3d.resetar_recorte()
                    
            self.on_box_adjust_toggled(False)
            if hasattr(self.main_window, 'action_caixa_recorte'):
                self.main_window.action_caixa_recorte.setChecked(False)
        except Exception as e:
            print(f"[CROP 3D] Erro ao resetar recorte: {e}")

    def on_bisturi_toggled(self, checked):
        try:
            if checked:
                self._desativar_outras_ferramentas('action_bisturi_desenhar')
                    
            if not hasattr(self.main_window, 'coordenador_navegacao') or getattr(self.main_window, 'coordenador_navegacao') is None:
                return
            nav = self.main_window.coordenador_navegacao
            
            if hasattr(nav, 'filtros_eventos'):
                for filtro in nav.filtros_eventos.values():
                    if hasattr(filtro, 'ferramenta_ativa'):
                        if checked:
                            filtro.ferramenta_ativa = "Bisturi"
                        else:
                            if filtro.ferramenta_ativa == "Bisturi":
                                filtro.ferramenta_ativa = "Normal"
                                if hasattr(filtro, 'limpar_bisturi_tela'):
                                    filtro.limpar_bisturi_tela()
                                    
        except Exception as e:
            print(f"[BISTURI] Erro ao alternar bisturi: {e}")

    def on_bisturi_aplicar_clicked(self, cortar_fora=False):
        try:
            if not hasattr(self.main_window, 'coordenador_navegacao') or getattr(self.main_window, 'coordenador_navegacao') is None:
                return
            nav = self.main_window.coordenador_navegacao
            if hasattr(nav, 'aplicar_bisturi'):
                nav.aplicar_bisturi(cortar_fora)
            if hasattr(self.main_window, 'action_bisturi_desenhar'):
                self.main_window.action_bisturi_desenhar.setChecked(False)
                self.on_bisturi_toggled(False)
        except Exception as e:
            print(f"[BISTURI] Erro ao aplicar corte: {e}")

    def on_bisturi_reset_clicked(self):
        try:
            if not hasattr(self.main_window, 'coordenador_navegacao') or getattr(self.main_window, 'coordenador_navegacao') is None:
                return
            nav = self.main_window.coordenador_navegacao
            if hasattr(nav, 'resetar_bisturi'):
                nav.resetar_bisturi()
        except Exception as e:
            print(f"[BISTURI] Erro ao resetar corte original: {e}")
