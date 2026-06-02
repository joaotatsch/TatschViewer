from PyQt6.QtCore import QObject
import vtk

class OperadorCrosshair(QObject):
    """
    Controla o cursor de sincronização 3D (Crosshair), renderizado
    simultaneamente em todas as vistas MPR e 3D, restrito a uma cruz pequena.
    """
    def __init__(self):
        super().__init__()
        self.cursor = vtk.vtkCursor3D()
        self.cursor.SetFocalPoint(0, 0, 0)
        self.cursor.AllOff()
        self.cursor.AxesOn()
        self.cursor.SetModelBounds(-15, 15, -15, 15, -15, 15)

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(self.cursor.GetOutputPort())

        self.ator = vtk.vtkActor()
        self.ator.SetMapper(mapper)
        self.ator.GetProperty().SetColor(1.0, 0.0, 0.0) # Vermelho
        self.ator.VisibilityOff()
        self.ator.PickableOff()

    def inicializar(self, renderers_dict: dict):
        for renderer in renderers_dict.values():
            if renderer:
                renderer.AddActor(self.ator)

    def atualizar_posicao(self, pos, planos: dict):
        x, y, z = pos
        self.cursor.SetModelBounds(x-15, x+15, y-15, y+15, z-15, z+15)
        self.cursor.SetFocalPoint(x, y, z)
        self.cursor.Update()

        # Mover a origem dos 3 vtkPlane
        for plane in planos.values():
            plane.SetOrigin(x, y, z)
