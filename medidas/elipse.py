import vtk, math
import numpy as np
from vtkmodules.util.numpy_support import vtk_to_numpy

class MedidaElipse:
    def _offset_pos(self, pos):
        x, y, z = pos
        if self.view_name == "Axial": return (x, y, z - 0.5)
        elif self.view_name == "Coronal": return (x, y + 0.5, z)
        elif self.view_name == "Sagital": return (x - 0.5, y, z)
        return (x, y, z - 0.5)

    def __init__(self, renderer, pos1, view_name, slice_coord, vtk_image):
        self.renderer = renderer
        self.view_name = view_name
        self.slice_coord = slice_coord
        self.vtk_image = vtk_image
        self.pos1 = pos1
        self.cor_padrao = (0.9, 0.6, 0.1)

        self.pos1_off = self._offset_pos(pos1)

        self.source = vtk.vtkRegularPolygonSource()
        self.source.SetNumberOfSides(50) # Círculo suave
        self.source.SetRadius(0.1)
        self.source.SetCenter(self.pos1_off)

        if view_name == "Axial": self.source.SetNormal(0, 0, 1)
        elif view_name == "Coronal": self.source.SetNormal(0, 1, 0)
        elif view_name == "Sagital": self.source.SetNormal(1, 0, 0)

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(self.source.GetOutputPort())

        self.actor = vtk.vtkActor()
        self.actor.SetMapper(mapper)
        self.actor.GetProperty().SetColor(self.cor_padrao) # Laranja
        self.actor.GetProperty().SetLineWidth(2.0)
        self.actor.GetProperty().SetRepresentationToWireframe()

        self.text_actor = vtk.vtkCaptionActor2D()
        self.text_actor.GetTextActor().SetTextScaleMode(vtk.vtkTextActor.TEXT_SCALE_MODE_NONE)
        self.text_actor.SetCaption("Calculando...")
        self.text_actor.SetAttachmentPoint(self.pos1_off)
        self.text_actor.BorderOff()
        self.text_actor.LeaderOff()
        self.text_actor.GetCaptionTextProperty().SetColor(self.cor_padrao)
        self.text_actor.GetCaptionTextProperty().SetFontSize(14)
        self.text_actor.GetCaptionTextProperty().ShadowOff()

        self.renderer.AddActor(self.actor)
        self.renderer.AddActor(self.text_actor)

    def atualizar_ponto2(self, pos2):
        pos2_off = self._offset_pos(pos2)
        r = math.sqrt((pos2_off[0]-self.pos1_off[0])**2 + (pos2_off[1]-self.pos1_off[1])**2 + (pos2_off[2]-self.pos1_off[2])**2)
        if r < 0.5: return
        self.source.SetRadius(r)
        self.source.Update()
        self.text_actor.SetAttachmentPoint((self.pos1_off[0]+r*0.7, self.pos1_off[1]+r*0.7, self.pos1_off[2]))

        try:
            dims = self.vtk_image.GetDimensions()
            spacing = self.vtk_image.GetSpacing()

            # Transformação perfeita respeitando a Direção RAS
            idx = [0.0, 0.0, 0.0]
            self.vtk_image.TransformPhysicalPointToContinuousIndex(self.pos1, idx)
            vx, vy, vz = int(round(idx[0])), int(round(idx[1])), int(round(idx[2]))

            rx, ry, rz = r/spacing[0], r/spacing[1], r/spacing[2]

            vtk_data = self.vtk_image.GetPointData().GetScalars()
            volume_np = vtk_to_numpy(vtk_data).reshape(dims[2], dims[1], dims[0])

            if self.view_name == "Axial":
                min_x, max_x = max(0, int(vx-rx)), min(dims[0], int(vx+rx+1))
                min_y, max_y = max(0, int(vy-ry)), min(dims[1], int(vy+ry+1))
                vz_c = max(0, min(vz, dims[2]-1))
                Y, X = np.ogrid[min_y:max_y, min_x:max_x]
                mask = ((X - vx)**2 / rx**2) + ((Y - vy)**2 / ry**2) <= 1
                roi = volume_np[vz_c, min_y:max_y, min_x:max_x][mask]
            elif self.view_name == "Coronal":
                min_x, max_x = max(0, int(vx-rx)), min(dims[0], int(vx+rx+1))
                min_z, max_z = max(0, int(vz-rz)), min(dims[2], int(vz+rz+1))
                vy_c = max(0, min(vy, dims[1]-1))
                Z, X = np.ogrid[min_z:max_z, min_x:max_x]
                mask = ((X - vx)**2 / rx**2) + ((Z - vz)**2 / rz**2) <= 1
                roi = volume_np[min_z:max_z, vy_c, min_x:max_x][mask]
            else: # Sagital
                min_y, max_y = max(0, int(vy-ry)), min(dims[1], int(vy+ry+1))
                min_z, max_z = max(0, int(vz-rz)), min(dims[2], int(vz+rz+1))
                vx_c = max(0, min(vx, dims[0]-1))
                Z, Y = np.ogrid[min_z:max_z, min_y:max_y]
                mask = ((Y - vy)**2 / ry**2) + ((Z - vz)**2 / rz**2) <= 1
                roi = volume_np[min_z:max_z, min_y:max_y, vx_c][mask]

            if len(roi) > 0:
                area = math.pi * (r**2)
                texto = f"Area: {area:.1f} mm²\nMean: {np.mean(roi):.1f} HU\nMin: {np.min(roi)} HU\nMax: {np.max(roi)} HU"
                self.text_actor.SetCaption(texto)
        except Exception as e:
            self.text_actor.SetCaption("Erro Calc")

    def set_visivel(self, visivel):
        self.actor.SetVisibility(visivel)
        self.text_actor.SetVisibility(visivel)

    def selecionar(self, selecionado: bool):
        cor = (1.0, 1.0, 0.0) if selecionado else self.cor_padrao
        self.actor.GetProperty().SetColor(cor)
        self.text_actor.GetCaptionTextProperty().SetColor(cor)

    def mover(self, dx, dy, dz):
        self.pos1 = (self.pos1[0]+dx, self.pos1[1]+dy, self.pos1[2]+dz)
        self.pos1_off = self._offset_pos(self.pos1)
        self.source.SetCenter(self.pos1_off)
        self.source.Update()
        self.slice_coord = (self.slice_coord[0]+dx, self.slice_coord[1]+dy, self.slice_coord[2]+dz)

        r = self.source.GetRadius()
        novo_p2_virtual = (self.pos1[0] + r, self.pos1[1], self.pos1[2])
        # Força o recálculo da área e dos Hounsfield Units na nova posição
        self.atualizar_ponto2(novo_p2_virtual)

    def remover(self):
        self.renderer.RemoveActor(self.actor)
        self.renderer.RemoveActor(self.text_actor)
