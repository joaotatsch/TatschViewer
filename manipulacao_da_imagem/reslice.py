"""
Módulo para funcionalidade de Re-fatiamento Oblíquo (Reslice).
"""
from PyQt6.QtCore import QObject
import vtk

class OperadorReslice(QObject):
    """
    Organiza como funciona a função de scroll de fatias, utilizando nativamente
    o vtkImageSliceMapper e isolando as atualizações para cada visão.
    """
    def __init__(self, volume_dados: vtk.vtkImageData):
        super().__init__()
        self.dados = volume_dados

    def deslocar_fatia(self, orientacao: str, incremento: int,
                       mapper: vtk.vtkImageSliceMapper) -> int:
        """
        Adiciona o incremento (scroll) na fatia atual suportada pelo mapper.
        Garante que o índice não exceda os limites da imagem original.
        """
        fatia_atual = mapper.GetSliceNumber()
        nova_fatia = fatia_atual + incremento
        
        # Limites exatos extraídos pelo próprio mapper do vtkImageData
        min_fatia = mapper.GetSliceNumberMinValue()
        max_fatia = mapper.GetSliceNumberMaxValue()
        
        nova_fatia = max(min_fatia, min(nova_fatia, max_fatia))
        
        mapper.SetSliceNumber(nova_fatia)
        return nova_fatia


import numpy as np
import math

class OperadorInteracaoReslice:
    def __init__(self, navegador_2d):
        self.nav = navegador_2d
        
    def hit_test(self, visao_atual, pos):
        planos = self.nav.planos
        if visao_atual not in planos: return None
        
        centro = np.array(planos[visao_atual].GetOrigin())
        p_mouse = np.array(pos)
        dist_centro = np.linalg.norm(p_mouse - centro)
        
        if dist_centro < 15.0: return "Centro"
        if dist_centro < 20.0: return None # Zona morta para evitar erros
        
        # Identifica os 2 planos ortogonais que aparecem como linhas na vista atual
        visoes_alvo = [v for v in ["Axial", "Coronal", "Sagital"] if v != visao_atual]
        
        melhor_alvo = None
        menor_dist = 12.0 # Margem de clique de 12mm
        
        n_base = np.array(planos[visao_atual].GetNormal())
        for alvo in visoes_alvo:
            n_alvo = np.array(planos[alvo].GetNormal())
            dir_linha = np.cross(n_base, n_alvo)
            norm = np.linalg.norm(dir_linha)
            if norm < 1e-6: continue
            dir_linha = dir_linha / norm
            
            # Distância do ponto à reta
            v_ponto = p_mouse - centro
            dist_linha = np.linalg.norm(np.cross(v_ponto, dir_linha))
            if dist_linha < menor_dist:
                menor_dist = dist_linha
                melhor_alvo = alvo
                
        return melhor_alvo
        
    def rotacionar(self, visao_atual, visao_alvo, p1, p2):
        plane_base = self.nav.planos[visao_atual]
        plane_alvo = self.nav.planos[visao_alvo]
        centro = np.array(plane_base.GetOrigin())
        
        v1 = np.array(p1) - centro
        v2 = np.array(p2) - centro
        axis = np.array(plane_base.GetNormal())
        
        cross_prod = np.cross(v1, v2)
        dot_prod = np.dot(v1, v2)
        angle_rad = math.atan2(np.dot(axis, cross_prod), dot_prod)
        angle_deg = math.degrees(angle_rad)
        
        if abs(angle_deg) < 0.1: return
        
        transform = vtk.vtkTransform()
        transform.Translate(centro[0], centro[1], centro[2])
        transform.RotateWXYZ(angle_deg, axis[0], axis[1], axis[2])
        transform.Translate(-centro[0], -centro[1], -centro[2])
        
        visoes_alvo_rotacao = [v for v in ["Axial", "Coronal", "Sagital"] if v != visao_atual]
        
        for alvo in visoes_alvo_rotacao:
            plane_alvo_iter = self.nav.planos[alvo]
            
            # Gira a Normal do plano alvo
            new_normal = transform.TransformDoubleVector(plane_alvo_iter.GetNormal())
            plane_alvo_iter.SetNormal(new_normal)

            # Gira a Origem (ponto âncora) do plano alvo
            new_origin = transform.TransformDoublePoint(plane_alvo_iter.GetOrigin())
            plane_alvo_iter.SetOrigin(new_origin)

            # Atualiza a Câmera
            renderer_alvo_iter = self.nav.renderers_2d[alvo]
            cam = renderer_alvo_iter.GetActiveCamera()
            new_up = transform.TransformDoubleVector(cam.GetViewUp())

            # A câmera deve olhar para a nova origem e se afastar na direção da nova normal
            cam.SetFocalPoint(new_origin[0], new_origin[1], new_origin[2])
            cam.SetPosition(new_origin[0] - new_normal[0]*500.0, 
                            new_origin[1] - new_normal[1]*500.0, 
                            new_origin[2] - new_normal[2]*500.0)
            cam.SetViewUp(new_up)

            # CRÍTICO: Evita que o plano saia do campo de visão da câmera gerando tela preta
            renderer_alvo_iter.ResetCameraClippingRange()

        self.nav.atualizar_bussola()

