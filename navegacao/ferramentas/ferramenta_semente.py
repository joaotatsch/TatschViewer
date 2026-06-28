# -*- coding: utf-8 -*-
from PyQt6.QtCore import Qt
import vtk
from ..ferramentas_base import FerramentaBase

class FerramentaSemente(FerramentaBase):
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
                
                # Conversão matemática imaculada VTK -> Index (Voxel)
                idx = [0.0, 0.0, 0.0]
                filtro.navegador_2d.volume_ativo.TransformPhysicalPointToContinuousIndex(pos, idx)
                ix, iy, iz = int(round(idx[0])), int(round(idx[1])), int(round(idx[2]))
                
                dims = filtro.navegador_2d.volume_ativo.GetDimensions()
                if 0 <= ix < dims[0] and 0 <= iy < dims[1] and 0 <= iz < dims[2]:
                    # Desenha a esfera tática
                    sphere = vtk.vtkSphereSource()
                    sphere.SetCenter(pos)
                    sphere.SetRadius(3.0)
                    mapper = vtk.vtkPolyDataMapper()
                    mapper.SetInputConnection(sphere.GetOutputPort())
                    actor = vtk.vtkActor()
                    actor.SetMapper(mapper)
                    actor.GetProperty().SetColor(0.0, 1.0, 0.0)
                    renderer.AddActor(actor)
                    filtro.interactor.GetRenderWindow().Render()
                    
                    if hasattr(filtro.parent(), 'adicionar_semente'):
                        filtro.parent().adicionar_semente([ix, iy, iz], actor)
            return True
        return False

    def on_mouse_move(self, event, filtro) -> bool:
        filtro.interactor.setCursor(Qt.CursorShape.CrossCursor)
        return True

class FerramentaSementeDSA(FerramentaBase):
    def on_mouse_press(self, event, filtro) -> bool:
        if event.button() == Qt.MouseButton.LeftButton:
            dpr = filtro.interactor.devicePixelRatioF()
            x_vtk = event.position().x() * dpr
            y_vtk = (filtro.interactor.height() - event.position().y()) * dpr
            renderer = filtro.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
            if renderer:
                filtro.picker.SetTolerance(0.0)
                filtro.picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                pos_world = filtro.picker.GetPickPosition()
                
                main_window = filtro.parent().parent() if hasattr(filtro.parent(), 'parent') else None
                vtk_img = filtro.navegador_2d.volume_ativo
                
                if main_window and vtk_img:
                    try:
                        idx = [0.0, 0.0, 0.0]
                        vtk_img.TransformPhysicalPointToContinuousIndex(pos_world, idx)
                        index_itk = (int(round(idx[0])), int(round(idx[1])), int(round(idx[2])))
                        main_window.gerenciador_processamento.iniciar_subtracao_semente(index_itk)
                    except Exception as e:
                        main_window.statusBar().showMessage(f"Erro ao converter semente: {str(e)}")
                
                # Para transição de estado, precisamos chamar pelo filtro
                filtro.ferramenta_atual = filtro.ferramentas.get("Normal", filtro.ferramenta_atual)
                filtro.interactor.setCursor(Qt.CursorShape.ArrowCursor)
                return True
        return False

    def on_mouse_move(self, event, filtro) -> bool:
        filtro.interactor.setCursor(Qt.CursorShape.CrossCursor)
        return False
