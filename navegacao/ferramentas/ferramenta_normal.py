# -*- coding: utf-8 -*-
from PyQt6.QtCore import Qt
import vtk
from ..ferramentas_base import FerramentaBase

class FerramentaNormal(FerramentaBase):
    def on_mouse_press(self, event, filtro) -> bool:
        if event.button() == Qt.MouseButton.LeftButton:
            # Seleção de medidas existentes
            if hasattr(filtro.parent(), 'coordenador_medidas') and filtro.parent().coordenador_medidas.medidas:
                dpr = filtro.interactor.devicePixelRatioF()
                x_vtk = event.position().x() * dpr
                y_vtk = (filtro.interactor.height() - event.position().y()) * dpr
                renderer = filtro.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
                if renderer:
                    prop_picker = vtk.vtkPropPicker()
                    prop_picker.PickProp(x_vtk, y_vtk, renderer)
                    prop_hit = prop_picker.GetViewProp()
                    medida_acertada = None
                    for med in filtro.parent().coordenador_medidas.medidas:
                        if prop_hit is med.actor or prop_hit is med.text_actor:
                            medida_acertada = med
                            break
                    if medida_acertada:
                        if filtro.medida_selecionada and filtro.medida_selecionada is not medida_acertada:
                            filtro.medida_selecionada.selecionar(False)
                        filtro.medida_selecionada = medida_acertada
                        medida_acertada.selecionar(True)
                        filtro.interactor.setCursor(Qt.CursorShape.ClosedHandCursor)
                        cell_picker = vtk.vtkCellPicker()
                        cell_picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                        filtro.ultima_posicao_medida = cell_picker.GetPickPosition()
                        filtro.arrastando_medida = True
                        filtro.interactor.GetRenderWindow().Render()
                        return True
                    else:
                        if getattr(filtro, 'medida_selecionada', None):
                            filtro.medida_selecionada.selecionar(False)
                            filtro.medida_selecionada = None
                            filtro.interactor.GetRenderWindow().Render()

            # Hit test normal para arrastar planos
            dpr = filtro.interactor.devicePixelRatioF()
            x_vtk = event.position().x() * dpr
            y_vtk = (filtro.interactor.height() - event.position().y()) * dpr
            renderer = filtro.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
            if renderer:
                filtro.picker.SetTolerance(0.0)
                filtro.picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                pos = filtro.picker.GetPickPosition()
                filtro.alvo_arraste = filtro._hit_test(pos)
                if filtro.alvo_arraste:
                    filtro.interactor.setCursor(Qt.CursorShape.ClosedHandCursor)
                    return True
            
            # Janelamento ou rotação 2D
            filtro.ultimo_pos_x = event.position().x()
            filtro.ultimo_pos_y = event.position().y()
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                filtro.arrastando_rotacao = True
                return True
            else:
                filtro.arrastando_janelamento = True
                return True
                
        return False

    def on_mouse_move(self, event, filtro) -> bool:
        if event.buttons() == Qt.MouseButton.NoButton:
            # Hover sobre medidas
            renderer = filtro.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
            if renderer and hasattr(filtro.parent(), 'coordenador_medidas') and filtro.parent().coordenador_medidas.medidas:
                dpr = filtro.interactor.devicePixelRatioF()
                x_vtk = event.position().x() * dpr
                y_vtk = (filtro.interactor.height() - event.position().y()) * dpr
                prop_picker = vtk.vtkPropPicker()
                prop_picker.PickProp(x_vtk, y_vtk, renderer)
                prop_hit = prop_picker.GetViewProp()
                for med in filtro.parent().coordenador_medidas.medidas:
                    if prop_hit is med.actor or prop_hit is med.text_actor:
                        filtro.interactor.setCursor(Qt.CursorShape.OpenHandCursor)
                        return False

            # Hover sobre hit targets
            dpr = filtro.interactor.devicePixelRatioF()
            x_vtk = event.position().x() * dpr
            y_vtk = (filtro.interactor.height() - event.position().y()) * dpr
            if renderer:
                filtro.picker.SetTolerance(0.0)
                filtro.picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                pos = filtro.picker.GetPickPosition()
                alvo = filtro._hit_test(pos)
                if alvo == "Centro":
                    filtro.interactor.setCursor(Qt.CursorShape.SizeAllCursor)
                elif alvo in ["Sagital", "Coronal", "Axial"]:
                    filtro.interactor.setCursor(Qt.CursorShape.OpenHandCursor)
                elif alvo and alvo.startswith("Espessura_"):
                    v_alvo = alvo.split("_")[1]
                    if v_alvo == "Sagital" or (v_alvo == "Coronal" and filtro.nome_visao == "Sagital"):
                        filtro.interactor.setCursor(Qt.CursorShape.SizeHorCursor)
                    else:
                        filtro.interactor.setCursor(Qt.CursorShape.SizeVerCursor)
                else:
                    filtro.interactor.setCursor(Qt.CursorShape.ArrowCursor)
            return False

        # Arrastando medida
        if getattr(filtro, 'arrastando_medida', False):
            dpr = filtro.interactor.devicePixelRatioF()
            x_vtk = event.position().x() * dpr
            y_vtk = (filtro.interactor.height() - event.position().y()) * dpr
            renderer = filtro.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
            if renderer:
                cell_picker = vtk.vtkCellPicker()
                cell_picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                pos_atual = cell_picker.GetPickPosition()
                filtro.medida_selecionada.mover(
                    pos_atual[0] - filtro.ultima_posicao_medida[0],
                    pos_atual[1] - filtro.ultima_posicao_medida[1],
                    pos_atual[2] - filtro.ultima_posicao_medida[2]
                )
                filtro.ultima_posicao_medida = pos_atual
                filtro.interactor.GetRenderWindow().Render()
            return True

        # Arrastando Hit Target
        if getattr(filtro, 'alvo_arraste', None) and event.buttons() & Qt.MouseButton.LeftButton:
            dpr = filtro.interactor.devicePixelRatioF()
            x_vtk = event.position().x() * dpr
            y_vtk = (filtro.interactor.height() - event.position().y()) * dpr
            renderer = filtro.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
            if renderer:
                filtro.picker.SetTolerance(0.0)
                filtro.picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                pos = filtro.picker.GetPickPosition()
                cx = filtro.navegador_2d.planos["Sagital"].GetOrigin()[0]
                cy = filtro.navegador_2d.planos["Coronal"].GetOrigin()[1]
                cz = filtro.navegador_2d.planos["Axial"].GetOrigin()[2]
                centros = {"Sagital": cx, "Coronal": cy, "Axial": cz}
                idx_map = {"Sagital": 0, "Coronal": 1, "Axial": 2}
                
                if filtro.alvo_arraste.startswith("Espessura_"):
                    v_alvo = filtro.alvo_arraste.split("_")[1]
                    proj = filtro.parent().operador_projecao
                    if proj:
                        nova_esp = abs(pos[idx_map[v_alvo]] - centros[v_alvo]) * 2.0
                        proj.aplicar_projecao_individual(v_alvo, proj.modos[v_alvo], nova_esp)
                        if filtro.espessura_callback:
                            filtro.espessura_callback(nova_esp)
                        filtro._renderizar_seguro()
                elif filtro.alvo_arraste == "Centro":
                    visoes_cruzadas = []
                    if filtro.nome_visao == "Axial": visoes_cruzadas = ["Sagital", "Coronal"]
                    elif filtro.nome_visao == "Coronal": visoes_cruzadas = ["Sagital", "Axial"]
                    elif filtro.nome_visao == "Sagital": visoes_cruzadas = ["Coronal", "Axial"]
                    v1, v2 = visoes_cruzadas[0], visoes_cruzadas[1]
                    plano1 = filtro.navegador_2d.planos[v1]
                    plano2 = filtro.navegador_2d.planos[v2]
                    origem1 = list(plano1.GetOrigin())
                    origem2 = list(plano2.GetOrigin())
                    i1 = idx_map[v1]
                    i2 = idx_map[v2]
                    origem1[i1] = pos[i1]
                    origem2[i2] = pos[i2]
                    plano1.SetOrigin(origem1)
                    plano2.SetOrigin(origem2)
                    p = filtro.navegador_2d.planos
                    if "Sagital" in p and "Coronal" in p and "Axial" in p:
                        nx = p["Sagital"].GetOrigin()[0]
                        ny = p["Coronal"].GetOrigin()[1]
                        nz = p["Axial"].GetOrigin()[2]
                        if hasattr(filtro.parent(), 'operador_projecao') and filtro.parent().operador_projecao:
                            filtro.parent().operador_projecao.atualizar_linhas(nx, ny, nz, p)
                        filtro._sincronizar_janelas(nx, ny, nz)
                        if hasattr(filtro.parent(), 'operador_crosshair') and filtro.parent().operador_crosshair:
                            filtro.parent().operador_crosshair.atualizar_posicao([nx, ny, nz], p)
                    filtro._renderizar_seguro()
                else:
                    v_arrastada = filtro.alvo_arraste
                    plano = filtro.navegador_2d.planos[v_arrastada]
                    origem = list(plano.GetOrigin())
                    i = idx_map[v_arrastada]
                    origem[i] = pos[i]
                    plano.SetOrigin(origem)
                    p = filtro.navegador_2d.planos
                    if "Sagital" in p and "Coronal" in p and "Axial" in p:
                        nx = p["Sagital"].GetOrigin()[0]
                        ny = p["Coronal"].GetOrigin()[1]
                        nz = p["Axial"].GetOrigin()[2]
                        if hasattr(filtro.parent(), 'operador_projecao') and filtro.parent().operador_projecao:
                            filtro.parent().operador_projecao.atualizar_linhas(nx, ny, nz, p)
                        filtro._sincronizar_janelas(nx, ny, nz)
                        if hasattr(filtro.parent(), 'operador_crosshair') and filtro.parent().operador_crosshair:
                            filtro.parent().operador_crosshair.atualizar_posicao([nx, ny, nz], p)
                    filtro._renderizar_seguro()
            return True

        if getattr(filtro, 'arrastando_janelamento', False):
            dx = event.position().x() - filtro.ultimo_pos_x
            dy = event.position().y() - filtro.ultimo_pos_y
            ator = filtro.navegador_2d.atores.get(filtro.nome_visao)
            if ator:
                ww_atual = ator.GetProperty().GetColorWindow()
                wl_atual = ator.GetProperty().GetColorLevel()
                sensibilidade = 2.0
                novo_ww = max(1.0, ww_atual + dx * sensibilidade)
                novo_wl = wl_atual - dy * sensibilidade
                filtro.navegador_2d.atualizar_janelamento(filtro.nome_visao, novo_ww, novo_wl)
                filtro.interactor.GetRenderWindow().Render()
                if filtro.janelamento_callback: filtro.janelamento_callback(novo_ww, novo_wl)
            filtro.ultimo_pos_x = event.position().x()
            filtro.ultimo_pos_y = event.position().y()
            return True
        elif getattr(filtro, 'arrastando_rotacao', False):
            dx = event.position().x() - filtro.ultimo_pos_x
            renderer = filtro.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
            if renderer:
                camera = renderer.GetActiveCamera()
                if camera:
                    camera.Roll(dx * 0.5)
                    filtro.navegador_2d.atualizar_bussola()
                    filtro.interactor.GetRenderWindow().Render()
            filtro.ultimo_pos_x = event.position().x()
            filtro.ultimo_pos_y = event.position().y()
            return True
            
        if getattr(filtro, 'arrastando_janelamento', False):
            ator = filtro.navegador_2d.atores.get(filtro.nome_visao)
            if ator:
                ww_atual = ator.GetProperty().GetColorWindow()
                wl_atual = ator.GetProperty().GetColorLevel()
                sensibilidade = 2.0
                novo_ww = max(1.0, ww_atual + dx * sensibilidade)
                novo_wl = wl_atual - dy * sensibilidade
                filtro.navegador_2d.atualizar_janelamento(filtro.nome_visao, novo_ww, novo_wl)
                filtro.interactor.GetRenderWindow().Render()
                if filtro.janelamento_callback: filtro.janelamento_callback(novo_ww, novo_wl)
            filtro.ultimo_pos_x = event.position().x()
            filtro.ultimo_pos_y = event.position().y()
            return True
        return False

    def on_mouse_release(self, event, filtro) -> bool:
        if event.button() == Qt.MouseButton.LeftButton:
            if getattr(filtro, 'arrastando_medida', False):
                filtro.arrastando_medida = False
                filtro.ultima_posicao_medida = None
                filtro.interactor.setCursor(Qt.CursorShape.OpenHandCursor)
                return True
            
            filtro.arrastando_janelamento = False
            filtro.arrastando_rotacao = False
            if getattr(filtro, 'alvo_arraste', None):
                filtro.alvo_arraste = None
                filtro.interactor.setCursor(Qt.CursorShape.ArrowCursor)
            return True
        return False
