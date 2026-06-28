# -*- coding: utf-8 -*-
from PyQt6.QtCore import Qt
import vtk
from ..ferramentas_base import FerramentaBase

class FerramentaCropBox(FerramentaBase):
    def on_mouse_press(self, event, filtro) -> bool:
        if event.button() == Qt.MouseButton.LeftButton:
            nav2d = filtro.navegador_2d
            if hasattr(nav2d, 'crop_widgets') and filtro.nome_visao in nav2d.crop_widgets:
                widget = nav2d.crop_widgets[filtro.nome_visao]
                if widget.GetEnabled():
                    dpr = filtro.interactor.devicePixelRatioF()
                    x_vtk = event.position().x() * dpr
                    y_vtk = (filtro.interactor.height() - event.position().y()) * dpr
                    renderer = filtro.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
                    if renderer:
                        filtro.picker.SetTolerance(0.0)
                        filtro.picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                        pos = filtro.picker.GetPickPosition()
                        
                        bounds = list(widget.GetRepresentation().GetBounds())
                        tol = 6.0
                        
                        filtro.drag_crop_index = None
                        if filtro.nome_visao == "Axial":
                            if abs(pos[0] - bounds[0]) < tol: filtro.drag_crop_index = 0
                            elif abs(pos[0] - bounds[1]) < tol: filtro.drag_crop_index = 1
                            elif abs(pos[1] - bounds[2]) < tol: filtro.drag_crop_index = 2
                            elif abs(pos[1] - bounds[3]) < tol: filtro.drag_crop_index = 3
                        elif filtro.nome_visao == "Coronal":
                            if abs(pos[0] - bounds[0]) < tol: filtro.drag_crop_index = 0
                            elif abs(pos[0] - bounds[1]) < tol: filtro.drag_crop_index = 1
                            elif abs(pos[2] - bounds[4]) < tol: filtro.drag_crop_index = 4
                            elif abs(pos[2] - bounds[5]) < tol: filtro.drag_crop_index = 5
                        elif filtro.nome_visao == "Sagital":
                            if abs(pos[1] - bounds[2]) < tol: filtro.drag_crop_index = 2
                            elif abs(pos[1] - bounds[3]) < tol: filtro.drag_crop_index = 3
                            elif abs(pos[2] - bounds[4]) < tol: filtro.drag_crop_index = 4
                            elif abs(pos[2] - bounds[5]) < tol: filtro.drag_crop_index = 5
                            
                        if filtro.drag_crop_index is not None:
                            filtro.ultimo_pick_mundo = pos
            return True
        return False

    def on_mouse_move(self, event, filtro) -> bool:
        nav2d = filtro.navegador_2d
        if hasattr(nav2d, 'crop_widgets') and filtro.nome_visao in nav2d.crop_widgets:
            widget = nav2d.crop_widgets[filtro.nome_visao]
            
            if getattr(filtro, 'drag_crop_index', None) is not None:
                dpr = filtro.interactor.devicePixelRatioF()
                x_vtk = event.position().x() * dpr
                y_vtk = (filtro.interactor.height() - event.position().y()) * dpr
                renderer = filtro.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
                if renderer:
                    filtro.picker.SetTolerance(0.0)
                    filtro.picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                    pos = filtro.picker.GetPickPosition()
                    
                    dx = pos[0] - filtro.ultimo_pick_mundo[0]
                    dy = pos[1] - filtro.ultimo_pick_mundo[1]
                    dz = pos[2] - filtro.ultimo_pick_mundo[2]
                    
                    rep = widget.GetRepresentation()
                    bounds = list(rep.GetBounds())
                    
                    idx = filtro.drag_crop_index
                    if idx in [0, 1]: bounds[idx] += dx
                    elif idx in [2, 3]: bounds[idx] += dy
                    elif idx in [4, 5]: bounds[idx] += dz
                    
                    if bounds[1] - bounds[0] < 5.0: bounds[idx] -= dx
                    elif bounds[3] - bounds[2] < 5.0: bounds[idx] -= dy
                    elif bounds[5] - bounds[4] < 5.0: bounds[idx] -= dz
                    else:
                        rep.PlaceWidget(bounds)
                        filtro.ultimo_pick_mundo = pos
                        filtro._renderizar_seguro()
                return True
                
            elif event.buttons() == Qt.MouseButton.NoButton:
                if widget.GetEnabled():
                    dpr = filtro.interactor.devicePixelRatioF()
                    x_vtk = event.position().x() * dpr
                    y_vtk = (filtro.interactor.height() - event.position().y()) * dpr
                    renderer = filtro.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
                    if renderer:
                        filtro.picker.SetTolerance(0.0)
                        filtro.picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                        pos = filtro.picker.GetPickPosition()
                        
                        bounds = widget.GetRepresentation().GetBounds()
                        tol = 6.0
                        cursor = Qt.CursorShape.ArrowCursor
                        
                        if filtro.nome_visao == "Axial":
                            on_x = abs(pos[0] - bounds[0]) < tol or abs(pos[0] - bounds[1]) < tol
                            on_y = abs(pos[1] - bounds[2]) < tol or abs(pos[1] - bounds[3]) < tol
                            if on_x and on_y: cursor = Qt.CursorShape.SizeAllCursor
                            elif on_x: cursor = Qt.CursorShape.SizeHorCursor
                            elif on_y: cursor = Qt.CursorShape.SizeVerCursor
                        elif filtro.nome_visao == "Coronal":
                            on_x = abs(pos[0] - bounds[0]) < tol or abs(pos[0] - bounds[1]) < tol
                            on_z = abs(pos[2] - bounds[4]) < tol or abs(pos[2] - bounds[5]) < tol
                            if on_x and on_z: cursor = Qt.CursorShape.SizeAllCursor
                            elif on_x: cursor = Qt.CursorShape.SizeHorCursor
                            elif on_z: cursor = Qt.CursorShape.SizeVerCursor
                        elif filtro.nome_visao == "Sagital":
                            on_y = abs(pos[1] - bounds[2]) < tol or abs(pos[1] - bounds[3]) < tol
                            on_z = abs(pos[2] - bounds[4]) < tol or abs(pos[2] - bounds[5]) < tol
                            if on_y and on_z: cursor = Qt.CursorShape.SizeAllCursor
                            elif on_y: cursor = Qt.CursorShape.SizeHorCursor
                            elif on_z: cursor = Qt.CursorShape.SizeVerCursor
                        
                        filtro.interactor.setCursor(cursor)
        return False

    def on_mouse_release(self, event, filtro) -> bool:
        if getattr(filtro, 'drag_crop_index', None) is not None:
            filtro.drag_crop_index = None
            if hasattr(filtro.parent(), 'sincronizar_cropbox_3d'):
                filtro.parent().sincronizar_cropbox_3d(filtro.navegador_2d.crop_widgets)
            return True
        return False
