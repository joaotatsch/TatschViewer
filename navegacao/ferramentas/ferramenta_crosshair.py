# -*- coding: utf-8 -*-
from PyQt6.QtCore import Qt
import vtk
from ..ferramentas_base import FerramentaBase

class FerramentaCrosshair(FerramentaBase):
    def on_mouse_press(self, event, filtro) -> bool:
        if event.button() == Qt.MouseButton.LeftButton:
            filtro.arrastando_crosshair = True
            
            # Fator de escala do monitor (ex: 1.25 para 125% no Windows)
            dpr = filtro.interactor.devicePixelRatioF()
            
            # Coordenadas físicas exatas para o VTK
            x_vtk = event.position().x() * dpr
            # Inversão do Y considerando a altura lógica multiplicada pelo DPR
            y_vtk = (filtro.interactor.height() - event.position().y()) * dpr
            
            renderer = filtro.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
            if renderer:
                filtro.picker.SetTolerance(0.0)
                filtro.picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                pos = filtro.picker.GetPickPosition()
                
                if hasattr(filtro.parent(), 'operador_crosshair') and filtro.parent().operador_crosshair:
                    planos = filtro.navegador_2d.planos
                    filtro.parent().operador_crosshair.atualizar_posicao(pos, planos)
                    p = filtro.navegador_2d.planos
                    if "Sagital" in p and "Coronal" in p and "Axial" in p:
                        nx = p["Sagital"].GetOrigin()[0]
                        ny = p["Coronal"].GetOrigin()[1]
                        nz = p["Axial"].GetOrigin()[2]
                        if hasattr(filtro.parent(), 'operador_projecao') and filtro.parent().operador_projecao:
                            filtro.parent().operador_projecao.atualizar_linhas(nx, ny, nz, p)
                    filtro._renderizar_seguro()
            return True
        return False

    def on_mouse_move(self, event, filtro) -> bool:
        if getattr(filtro, 'arrastando_crosshair', False):
            dpr = filtro.interactor.devicePixelRatioF()
            x_vtk = event.position().x() * dpr
            y_vtk = (filtro.interactor.height() - event.position().y()) * dpr
            
            renderer = filtro.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
            if renderer:
                filtro.picker.SetTolerance(0.0)
                filtro.picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                pos = filtro.picker.GetPickPosition()
                
                if hasattr(filtro.parent(), 'operador_crosshair') and filtro.parent().operador_crosshair:
                    planos = filtro.navegador_2d.planos
                    filtro.parent().operador_crosshair.atualizar_posicao(pos, planos)
                    p = filtro.navegador_2d.planos
                    if "Sagital" in p and "Coronal" in p and "Axial" in p:
                        nx = p["Sagital"].GetOrigin()[0]
                        ny = p["Coronal"].GetOrigin()[1]
                        nz = p["Axial"].GetOrigin()[2]
                        if hasattr(filtro.parent(), 'operador_projecao') and filtro.parent().operador_projecao:
                            filtro.parent().operador_projecao.atualizar_linhas(nx, ny, nz, p)
                    filtro._renderizar_seguro()
            return True
        return False

    def on_mouse_release(self, event, filtro) -> bool:
        if getattr(filtro, 'arrastando_crosshair', False):
            filtro.arrastando_crosshair = False
            return True
        return False
