import os

code = '''# -*- coding: utf-8 -*-
from PyQt6.QtCore import Qt
import vtk
from ..ferramentas_base import FerramentaBase

class FerramentaReslice(FerramentaBase):
    def on_mouse_press(self, event, filtro) -> bool:
        if event.button() == Qt.MouseButton.LeftButton:
            dpr = filtro.interactor.devicePixelRatioF()
            x_vtk = event.position().x() * dpr
            y_vtk = (filtro.interactor.height() - event.position().y()) * dpr
            renderer = filtro.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
            if renderer:
                filtro.picker.SetTolerance(0.0)
                filtro.picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                pos = filtro.picker.GetPickPosition()
                filtro.alvo_reslice = filtro.operador_interacao_reslice.hit_test(filtro.nome_visao, pos)
                if filtro.alvo_reslice is not None:
                    cell_picker = vtk.vtkCellPicker()
                    cell_picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                    filtro.ultima_posicao_medida = cell_picker.GetPickPosition()
                    return True
            # Clique no vazio em modo Reslice → janelamento normal
            filtro.ultimo_pos_x = event.position().x()
            filtro.ultimo_pos_y = event.position().y()
            filtro.arrastando_janelamento = True
            return True
        return False

    def on_mouse_move(self, event, filtro) -> bool:
        if event.buttons() == Qt.MouseButton.NoButton:
            dpr = filtro.interactor.devicePixelRatioF()
            x_vtk = event.position().x() * dpr
            y_vtk = (filtro.interactor.height() - event.position().y()) * dpr
            renderer = filtro.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
            if renderer:
                filtro.picker.SetTolerance(0.0)
                filtro.picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                pos = filtro.picker.GetPickPosition()
                alvo = filtro.operador_interacao_reslice.hit_test(filtro.nome_visao, pos)
                if alvo == "Centro":
                    filtro.interactor.setCursor(Qt.CursorShape.SizeAllCursor)
                elif alvo is not None:
                    filtro.interactor.setCursor(Qt.CursorShape.PointingHandCursor)
                else:
                    filtro.interactor.setCursor(Qt.CursorShape.ArrowCursor)
            return True
            
        elif getattr(filtro, 'alvo_reslice', None):
            dpr = filtro.interactor.devicePixelRatioF()
            x_vtk = event.position().x() * dpr
            y_vtk = (filtro.interactor.height() - event.position().y()) * dpr
            renderer = filtro.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
            if renderer and getattr(filtro, 'ultima_posicao_medida', None):
                cell_picker = vtk.vtkCellPicker()
                cell_picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                pos = cell_picker.GetPickPosition()
                
                if filtro.alvo_reslice == "Centro":
                    for visao, plane in filtro.navegador_2d.planos.items():
                        plane.SetOrigin(pos[0], pos[1], pos[2])
                    filtro.ultima_posicao_medida = pos
                    p = filtro.navegador_2d.planos
                    if "Sagital" in p and "Coronal" in p and "Axial" in p:
                        nx, ny, nz = p["Sagital"].GetOrigin()[0], p["Coronal"].GetOrigin()[1], p["Axial"].GetOrigin()[2]
                        if hasattr(filtro.parent(), 'operador_projecao') and filtro.parent().operador_projecao:
                            filtro.parent().operador_projecao.atualizar_linhas(nx, ny, nz, p)
                else:
                    filtro.operador_interacao_reslice.rotacionar(filtro.nome_visao, filtro.alvo_reslice, filtro.ultima_posicao_medida, pos)
                    filtro.ultima_posicao_medida = pos
                    p = filtro.navegador_2d.planos
                    if "Sagital" in p and "Coronal" in p and "Axial" in p:
                        nx, ny, nz = p["Sagital"].GetOrigin()[0], p["Coronal"].GetOrigin()[1], p["Axial"].GetOrigin()[2]
                        if hasattr(filtro.parent(), 'operador_projecao') and filtro.parent().operador_projecao:
                            filtro.parent().operador_projecao.atualizar_linhas(nx, ny, nz, p)
                            
                filtro._renderizar_seguro()
            return True
            
        elif getattr(filtro, 'arrastando_janelamento', False):
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
            
        return False

    def on_mouse_release(self, event, filtro) -> bool:
        if getattr(filtro, 'alvo_reslice', None):
            filtro.alvo_reslice = None
            if hasattr(filtro.parent(), 'finalizar_interacao_mpr'):
                filtro.parent().finalizar_interacao_mpr()
            return True
        elif getattr(filtro, 'arrastando_janelamento', False):
            filtro.arrastando_janelamento = False
            return True
        return False
'''

with open(r'd:\Desktop\Projetos\TatschViewer\navegacao\ferramentas\ferramenta_reslice.py', 'w', encoding='utf-8') as f:
    f.write(code)
