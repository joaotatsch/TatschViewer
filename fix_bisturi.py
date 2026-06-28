import os

code = '''# -*- coding: utf-8 -*-
from PyQt6.QtCore import Qt
import vtk
from ..ferramentas_base import FerramentaBase

class FerramentaBisturi(FerramentaBase):
    def on_mouse_press(self, event, filtro) -> bool:
        if event.button() == Qt.MouseButton.LeftButton:
            filtro.arrastando_bisturi = True
            
            dpr = filtro.interactor.devicePixelRatioF()
            x_vtk = event.position().x() * dpr
            y_vtk = (filtro.interactor.height() - event.position().y()) * dpr
            
            filtro.bisturi_pontos = [(x_vtk, y_vtk)]
            
            renderer = filtro.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
            if renderer:
                if not renderer.HasViewProp(filtro.bisturi_actor):
                    renderer.AddActor(filtro.bisturi_actor)
            filtro.interactor.GetRenderWindow().Render()
            return True
        return False

    def on_mouse_move(self, event, filtro) -> bool:
        if getattr(filtro, 'arrastando_bisturi', False):
            dpr = filtro.interactor.devicePixelRatioF()
            x_vtk = event.position().x() * dpr
            y_vtk = (filtro.interactor.height() - event.position().y()) * dpr
            
            filtro.bisturi_pontos.append((x_vtk, y_vtk))
            
            pts = vtk.vtkPoints()
            polyLine = vtk.vtkPolyLine()
            polyLine.GetPointIds().SetNumberOfIds(len(filtro.bisturi_pontos))
            for i, p in enumerate(filtro.bisturi_pontos):
                pts.InsertNextPoint(p[0], p[1], 0.0)
                polyLine.GetPointIds().SetId(i, i)
            
            cells = vtk.vtkCellArray()
            cells.InsertNextCell(polyLine)
            
            filtro.bisturi_poly.SetPoints(pts)
            filtro.bisturi_poly.SetLines(cells)
            
            filtro.interactor.GetRenderWindow().Render()
            return True
        return False

    def on_mouse_release(self, event, filtro) -> bool:
        if getattr(filtro, 'arrastando_bisturi', False) and event.button() == Qt.MouseButton.LeftButton:
            filtro.arrastando_bisturi = False
            
            renderer = filtro.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
            if renderer and renderer.HasViewProp(filtro.bisturi_actor):
                renderer.RemoveActor(filtro.bisturi_actor)
            
            if len(filtro.bisturi_pontos) > 2:
                filtro.bisturi_pontos.append(filtro.bisturi_pontos[0])
                pts = vtk.vtkPoints()
                polyLine = vtk.vtkPolyLine()
                polyLine.GetPointIds().SetNumberOfIds(len(filtro.bisturi_pontos))
                for i, p in enumerate(filtro.bisturi_pontos):
                    pts.InsertNextPoint(p[0], p[1], 0.0)
                    polyLine.GetPointIds().SetId(i, i)
                cells = vtk.vtkCellArray()
                cells.InsertNextCell(polyLine)
                filtro.bisturi_poly.SetPoints(pts)
                filtro.bisturi_poly.SetLines(cells)
                
                if hasattr(filtro.parent(), 'realizar_corte_3d'):
                    filtro.parent().pontos_bisturi = filtro.bisturi_pontos
                    filtro.parent().pontos_corte = filtro.bisturi_pontos
                    filtro.parent().realizar_corte_3d(filtro.bisturi_poly, renderer)
                elif filtro.parent() and hasattr(filtro.parent().parent(), 'realizar_corte_3d'):
                    filtro.parent().parent().pontos_bisturi = filtro.bisturi_pontos
                    filtro.parent().parent().pontos_corte = filtro.bisturi_pontos
                    filtro.parent().parent().realizar_corte_3d(filtro.bisturi_poly, renderer)
                    
            filtro.interactor.GetRenderWindow().Render()
            return True
        return False
'''

with open(r'd:\Desktop\Projetos\TatschViewer\navegacao\ferramentas\ferramenta_bisturi.py', 'w', encoding='utf-8') as f:
    f.write(code)
