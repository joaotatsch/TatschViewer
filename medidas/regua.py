import vtk
import math

class MedidaRegua:
    def _offset_pos(self, pos):
        x, y, z = pos
        if self.view_name == "Axial": return (x, y, z - 0.5) # Câmera no -Z
        elif self.view_name == "Coronal": return (x, y + 0.5, z) # Câmera no +Y
        elif self.view_name == "Sagital": return (x - 0.5, y, z) # Câmera no -X
        return (x, y, z - 0.5)

    def __init__(self, renderer, pos1, view_name, slice_coord):
        self.renderer = renderer
        self.view_name = view_name
        self.slice_coord = slice_coord # Tupla (cx, cy, cz) da fatia
        self.cor_padrao = (0.2, 0.8, 0.2)
        self._ponto2_atual = None
        
        pos1_off = self._offset_pos(pos1)
        
        self.source = vtk.vtkLineSource()
        self.source.SetPoint1(pos1_off)
        self.source.SetPoint2(pos1_off)
        
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(self.source.GetOutputPort())
        
        self.actor = vtk.vtkActor()
        self.actor.SetMapper(mapper)
        self.actor.GetProperty().SetColor(0.2, 0.8, 0.2) # Verde
        self.actor.GetProperty().SetLineWidth(2.0)
        
        self.text_actor = vtk.vtkCaptionActor2D()
        self.text_actor.GetTextActor().SetTextScaleMode(vtk.vtkTextActor.TEXT_SCALE_MODE_NONE)
        self.text_actor.SetCaption("0.0 mm")
        self.text_actor.SetAttachmentPoint(pos1_off)
        self.text_actor.BorderOff()
        self.text_actor.LeaderOff()
        self.text_actor.GetCaptionTextProperty().SetColor(0.2, 0.8, 0.2)
        self.text_actor.GetCaptionTextProperty().SetFontSize(14)
        self.text_actor.GetCaptionTextProperty().ShadowOff()
        
        self.renderer.AddActor(self.actor)
        self.renderer.AddActor(self.text_actor)
        
    def atualizar_ponto2(self, pos2):
        pos2_off = self._offset_pos(pos2)
        self._ponto2_atual = pos2_off
        self.source.SetPoint2(pos2_off)
        self.source.Update() # Força o VTK a redesenhar a linha
        
        p1 = self.source.GetPoint1()
        dist = math.sqrt((pos2_off[0]-p1[0])**2 + (pos2_off[1]-p1[1])**2 + (pos2_off[2]-p1[2])**2)
        meio = ((p1[0]+pos2_off[0])/2, (p1[1]+pos2_off[1])/2, (p1[2]+pos2_off[2])/2)
        
        self.text_actor.SetAttachmentPoint(meio)
        self.text_actor.SetCaption(f"{dist:.1f} mm")
        
    def set_visivel(self, visivel):
        self.actor.SetVisibility(visivel)
        self.text_actor.SetVisibility(visivel)

    def selecionar(self, selecionado: bool):
        cor = (1.0, 1.0, 0.0) if selecionado else self.cor_padrao
        self.actor.GetProperty().SetColor(cor)
        self.text_actor.GetCaptionTextProperty().SetColor(cor)

    def mover(self, dx, dy, dz):
        p1 = self.source.GetPoint1()
        p2 = self.source.GetPoint2()
        novo_p1 = (p1[0]+dx, p1[1]+dy, p1[2]+dz)
        novo_p2 = (p2[0]+dx, p2[1]+dy, p2[2]+dz)
        
        self.source.SetPoint1(novo_p1)
        self.source.SetPoint2(novo_p2)
        self.source.Update()
        
        meio = ((novo_p1[0]+novo_p2[0])/2, (novo_p1[1]+novo_p2[1])/2, (novo_p1[2]+novo_p2[2])/2)
        self.text_actor.SetAttachmentPoint(meio)
        self.slice_coord = (self.slice_coord[0]+dx, self.slice_coord[1]+dy, self.slice_coord[2]+dz)

    def remover(self):
        self.renderer.RemoveActor(self.actor)
        self.renderer.RemoveActor(self.text_actor)
