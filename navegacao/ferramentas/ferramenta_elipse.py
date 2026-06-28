# -*- coding: utf-8 -*-
from PyQt6.QtCore import Qt
import vtk
from ..ferramentas_base import FerramentaBase

class FerramentaElipse(FerramentaBase):
    def on_mouse_press(self, event, filtro) -> bool:
        if event.button() == Qt.MouseButton.LeftButton:
            dpr = filtro.interactor.devicePixelRatioF()
            x_vtk = event.position().x() * dpr
            y_vtk = (filtro.interactor.height() - event.position().y()) * dpr
            
            renderer = filtro.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
            if renderer:
                filtro.picker.SetTolerance(0.005)
                filtro.picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                pos_world = filtro.picker.GetPickPosition()
                
                origem_plano = filtro.navegador_2d.planos[filtro.nome_visao].GetOrigin()
                
                filtro.arrastando_regua = True # O filtro usa arrastando_regua para ambas
                medidas_coord = filtro.parent().coordenador_medidas
                medidas_coord.iniciar_elipse(renderer, pos_world, filtro.nome_visao, origem_plano, filtro.navegador_2d.volume_ativo)
                return True
        return False

    def on_mouse_move(self, event, filtro) -> bool:
        if not event.buttons() & Qt.MouseButton.LeftButton:
            filtro.interactor.setCursor(Qt.CursorShape.CrossCursor)
            return False
            
        if getattr(filtro, 'arrastando_regua', False):
            dpr = filtro.interactor.devicePixelRatioF()
            x_vtk = event.position().x() * dpr
            y_vtk = (filtro.interactor.height() - event.position().y()) * dpr
            renderer = filtro.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
            if renderer:
                filtro.picker.SetTolerance(0.005)
                filtro.picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                pos_world = filtro.picker.GetPickPosition()
                
                medidas_coord = filtro.parent().coordenador_medidas
                if medidas_coord.medidas:
                    medida_atual = medidas_coord.medidas[-1]
                    medidas_coord.atualizar_medida(medida_atual, pos_world)
                    filtro._renderizar_seguro()
            return True
        return False

    def on_mouse_release(self, event, filtro) -> bool:
        if getattr(filtro, 'arrastando_regua', False):
            filtro.arrastando_regua = False
            filtro.interactor.setCursor(Qt.CursorShape.ArrowCursor)
            # Opcional: Atualizar área da elipse aqui caso a classe Medida já não o faça
            return True
        return False
