import os

file_path = r'd:\Desktop\Projetos\TatschViewer\navegacao\ferramentas\ferramenta_bisturi.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

import re

# Find the if hasattr(filtro.parent()...) block and replace it
new_block = """            if len(filtro.bisturi_pontos) > 2:
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
                
                if hasattr(filtro.parent(), 'lista_sementes'): # A duck-typing way to check if it's CoordenadorNavegacao
                    filtro.parent().pontos_corte = filtro.bisturi_pontos
                    filtro.parent().renderer_corte = renderer
                elif hasattr(filtro.parent(), 'parent') and hasattr(filtro.parent().parent(), 'lista_sementes'):
                    filtro.parent().parent().pontos_corte = filtro.bisturi_pontos
                    filtro.parent().parent().renderer_corte = renderer
                    
            filtro.interactor.GetRenderWindow().Render()
            return True"""

# We replace everything from "if len(filtro.bisturi_pontos) > 2:" to the end of the file
content = re.sub(r'if len\(filtro\.bisturi_pontos\) > 2:.*', new_block, content, flags=re.DOTALL)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
