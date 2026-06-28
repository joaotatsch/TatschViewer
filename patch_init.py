import os

file_path = r'd:\Desktop\Projetos\TatschViewer\navegacao\filtros_eventos.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

import re

# Patch 2D init
if "self.picker = vtk.vtkCellPicker()" not in content:
    content = content.replace("self.alvo_reslice = None\n",
                              "self.alvo_reslice = None\n"
                              "        self.picker = vtk.vtkCellPicker()\n"
                              "        self.picker.SetTolerance(0.005)\n"
                              "        self.medida_selecionada = None\n"
                              "        self.arrastando_medida = False\n"
                              "        self.ultima_posicao_medida = None\n")

# Patch 3D init
if "self.bisturi_poly = vtk.vtkPolyData()" not in content:
    replacement = """        self.alvo_arraste = None
        self.bisturi_pontos = vtk.vtkPoints()
        self.bisturi_poly = vtk.vtkPolyData()
        mapper2d = vtk.vtkPolyDataMapper2D()
        mapper2d.SetInputData(self.bisturi_poly)
        coord = vtk.vtkCoordinate()
        coord.SetCoordinateSystemToDisplay()
        mapper2d.SetTransformCoordinate(coord)
        self.bisturi_actor = vtk.vtkActor2D()
        self.bisturi_actor.SetMapper(mapper2d)
        self.bisturi_actor.GetProperty().SetColor(1.0, 1.0, 0.0)
        self.bisturi_actor.GetProperty().SetLineWidth(2.0)
"""
    # Find the init of FiltroEventosDicom3D
    # It has self.alvo_arraste = None
    # Wait, does FiltroEventosDicom3D have self.alvo_arraste? Let's check original content.
    pass

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
