"""
Módulo de coordenação de navegação bidimensional (MPR).
"""
from PyQt6.QtCore import QObject
import vtk
import math
import time

# Mapa de eixo dominante para letra anatômica RAS
# O VTK usa o sistema RAS (Right, Anterior, Superior) para coordenadas positivas
_EIXOS_RAS = [
    (+1, 0, 0, "R"),  # +X = Right
    (-1, 0, 0, "L"),  # -X = Left
    (0, +1, 0, "A"),  # +Y = Anterior
    (0, -1, 0, "P"),  # -Y = Posterior
    (0, 0, +1, "S"),  # +Z = Superior
    (0, 0, -1, "I"),  # -Z = Inferior
]

def _letra_anatomica(vetor):
    """
    Retorna a letra RAS da direção anatômica predominante do vetor dado.
    Usa o maior produto escalar para encontrar o eixo mais alinhado.
    """
    vx, vy, vz = vetor
    mag = math.sqrt(vx*vx + vy*vy + vz*vz)
    if mag < 1e-9:
        return "?"
    vx, vy, vz = vx/mag, vy/mag, vz/mag
    melhor_dot = -2.0
    melhor_letra = "?"
    for ax, ay, az, letra in _EIXOS_RAS:
        dot = vx * ax + vy * ay + vz * az
        if dot > melhor_dot:
            melhor_dot = dot
            melhor_letra = letra
    return melhor_letra


class Navegador2D(QObject):
    """
    Coordenará como o usuário navegará e interagirá com a visualização 2D (Multiplanar Reconstruction),
    gerenciando troca de fatias (scrolling), pan, zoom e seleção de plano.
    """
    def __init__(self):
        super().__init__()
        # Guarda referências dos mappers, planos e atores para interações futuras
        self.mappers = {}
        self.planos = {}
        self.atores = {}
        self.volume_ativo = None
        self.operador_reslice = None
        self.indicadores = {}
        self.meta_actors = {}
        self.border_actors = {}
        self.quadrados_atores = {}
        # Bússola: dicionário de {nome_plano: {direcao: vtkTextActor}}
        self.bussola_actors = {}
        # Referências aos renderers 2D para atualizações de bússola
        self.renderers_2d = {}
        # Observers VTK para atualização dinâmica de bússola
        self._observadores = []

    def atualizar_volume(self, novo_vtk_image):
        self.volume_ativo = novo_vtk_image
        self.operador_reslice.dados = novo_vtk_image
        center = novo_vtk_image.GetCenter()
        
        for visao, mapper in self.mappers.items():
            mapper.SetInputData(novo_vtk_image)
            plane = self.planos[visao]
            plane.SetOrigin(center)
            mapper.SetSlicePlane(plane)
            mapper.Update()
            
            # Recalibra Câmera sem destruir atores de forma dinâmica e segura
            cam = self.renderers_2d[visao].GetActiveCamera()
            cam.SetFocalPoint(center)
            
            # Trata orientações padrões ou personalizadas (que assumem Axial como padrão)
            if visao == "Sagital":
                cam.SetPosition(center[0] - 500, center[1], center[2])
            elif visao == "Coronal":
                cam.SetPosition(center[0], center[1] + 500, center[2])
            else:
                # Axial e qualquer outra tela de comparação (como Tela_1, Tela_2, etc.)
                cam.SetPosition(center[0], center[1], center[2] - 500)
                
            self.renderers_2d[visao].ResetCamera()
            cam = self.renderers_2d[visao].GetActiveCamera()
            cam.Zoom(1.6)
            self.renderers_2d[visao].ResetCameraClippingRange()

    def configurar_mpr(self, vtk_image: vtk.vtkImageData, renderers_2d: dict) -> dict:
        """
        Recebe o volume carregado e os renderizadores do Layout 4-Up (Axial, Sagital, Coronal).
        Instancia vtkImageResliceMapper e vtkImageSlice para cada plano, configurando as câmeras.
        """
        self.volume_ativo = vtk_image
        
        # 1. Remover observadores antigos da memória C++
        if hasattr(self, '_observadores') and self._observadores:
            for renderer, obs_id in self._observadores:
                try:
                    if renderer:
                        renderer.RemoveObserver(obs_id)
                except Exception:
                    pass
        self._observadores = []
        
        # 2. Remover atores do contexto dos renderizadores antigos
        if hasattr(self, 'renderers_2d') and self.renderers_2d:
            for nome_plano, renderer in self.renderers_2d.items():
                try:
                    if renderer:
                        if hasattr(self, 'atores') and nome_plano in self.atores:
                            renderer.RemoveActor(self.atores[nome_plano])
                        if hasattr(self, 'meta_actors') and nome_plano in self.meta_actors:
                            renderer.RemoveActor(self.meta_actors[nome_plano])
                        if hasattr(self, 'bussola_actors') and nome_plano in self.bussola_actors:
                            for act in self.bussola_actors[nome_plano].values():
                                renderer.RemoveActor(act)
                except Exception:
                    pass
                    
        self.renderers_2d = renderers_2d
        
        # Limpa referências locais do Python
        self.mappers.clear()
        self.planos.clear()
        self.atores.clear()
        self.indicadores.clear()
        self.meta_actors.clear()
        self.bussola_actors.clear()

        # Importação local das classes de manipulação de imagem
        from manipulacao_da_imagem.reslice import OperadorReslice
        from manipulacao_da_imagem.janelamento.janelamento_2d.indicador_janelamento_2d import IndicadorJanelamento2D

        self.operador_reslice = OperadorReslice(vtk_image)
        self.indicadores = {}
        self.meta_actors = {}
        self.bussola_actors = {}

        center = vtk_image.GetCenter()

        config_planos = {
            "Axial": {
                "normal": (0, 0, 1),
                "view_up": (0, 1, 0),
                "camera_pos": (0, 0, -1),
                "focal_point": (0, 0, 0)
            },
            "Sagital": {
                "normal": (1, 0, 0),
                "view_up": (0, 0, 1),
                "camera_pos": (-1, 0, 0),
                "focal_point": (0, 0, 0)
            },
            "Coronal": {
                "normal": (0, 1, 0),
                "view_up": (0, 0, 1),
                "camera_pos": (0, 1, 0),
                "focal_point": (0, 0, 0)
            }
        }

        for nome_plano, renderer in renderers_2d.items():
            # Se for uma tela de comparação ou personalizada, herda o preset de orientação da Axial
            config = config_planos.get(nome_plano, config_planos["Axial"])

            # 1. Criação do Mapper de Fatiamento Verdadeiro (vtkImageResliceMapper)
            mapper = vtk.vtkImageResliceMapper()
            mapper.SetInputData(vtk_image)
            
            plane = vtk.vtkPlane()
            cx, cy, cz = center
            plane.SetOrigin(cx, cy, cz)
            
            cam = renderer.GetActiveCamera()
            cam.SetFocalPoint(cx, cy, cz)
            
            if nome_plano == "Coronal":
                plane.SetNormal(0, 1, 0)
                cam.SetPosition(cx, cy + 500, cz)
                cam.SetViewUp(0, 0, 1)
            elif nome_plano == "Sagital":
                plane.SetNormal(1, 0, 0)
                cam.SetPosition(cx - 500, cy, cz)
                cam.SetViewUp(0, 0, 1)
            else:
                plane.SetNormal(0, 0, 1)
                cam.SetPosition(cx, cy, cz - 500)
                cam.SetViewUp(0, 1, 0)
                
            mapper.SetSlicePlane(plane)
            self.mappers[nome_plano] = mapper
            self.planos[nome_plano] = plane
            
            mapper.Update()
            renderer.ResetCameraClippingRange()
            renderer.ResetCamera()
            cam.Zoom(1.6)
            
            # Força o enquadramento perfeito (Zoom exato) ignorando a heurística do VTK
            dim_y = vtk_image.GetDimensions()[1]
            cam.SetParallelScale(dim_y / 2.0)
            cam.ParallelProjectionOn()

            # 2. Criação do Ator de Fatiamento (vtkImageSlice)
            ator = vtk.vtkImageSlice()
            ator.SetMapper(mapper)
            ator.GetProperty().SetColorWindow(2000)
            ator.GetProperty().SetColorLevel(400)
            self.atores[nome_plano] = ator
            renderer.AddActor(ator)

            # Indicador HUD de janelamento 2D
            indicador = IndicadorJanelamento2D(renderer)
            self.indicadores[nome_plano] = indicador
            indicador.atualizar_valores(2000, 400)

            # HUD de metadados clínicos
            meta_act = vtk.vtkTextActor()
            prop_txt = meta_act.GetTextProperty()
            prop_txt.SetFontFamilyToArial()
            prop_txt.SetFontSize(11)
            prop_txt.BoldOn()
            prop_txt.SetColor(0.7, 0.7, 0.7)
            prop_txt.SetVerticalJustificationToTop()
            meta_act.GetPositionCoordinate().SetCoordinateSystemToNormalizedViewport()
            meta_act.GetPositionCoordinate().SetValue(0.02, 0.92)
            renderer.AddActor2D(meta_act)
            self.meta_actors[nome_plano] = meta_act

            # 4. Bússola de bordas: 4 vtkTextActor (Topo/Base/Esq/Dir)
            bussola = {}
            posicoes_bussola = {
                "topo": (0.50, 0.93),
                "base": (0.50, 0.02),
                "esq":  (0.01, 0.50),
                "dir":  (0.93, 0.50),
            }
            for lado, pos in posicoes_bussola.items():
                act = vtk.vtkTextActor()
                act.SetInput("?")
                tp = act.GetTextProperty()
                tp.SetFontFamilyToArial()
                tp.SetFontSize(14)
                tp.BoldOn()
                tp.SetColor(1.0, 0.85, 0.2)  # amarelo dourado
                tp.SetJustificationToCentered()
                act.GetPositionCoordinate().SetCoordinateSystemToNormalizedViewport()
                act.GetPositionCoordinate().SetValue(*pos)
                renderer.AddActor2D(act)
                bussola[lado] = act
            self.bussola_actors[nome_plano] = bussola

            renderer.ResetCameraClippingRange()

        # Calcula bússola inicial
        self.atualizar_bussola()
        return self.atores

    def adicionar_visao_independente(self, nome_visao, vtk_image, renderer):
        t0 = time.perf_counter()
        renderer.RemoveAllViewProps()
        
        self.mappers.pop(nome_visao, None)
        self.planos.pop(nome_visao, None)
        self.atores.pop(nome_visao, None)
        self.indicadores.pop(nome_visao, None)
        self.meta_actors.pop(nome_visao, None)
        self.bussola_actors.pop(nome_visao, None)
        
        from manipulacao_da_imagem.janelamento.janelamento_2d.indicador_janelamento_2d import IndicadorJanelamento2D
        self.renderers_2d[nome_visao] = renderer
        
        mapper = vtk.vtkImageResliceMapper()
        mapper.SetInputData(vtk_image)
        
        plane = vtk.vtkPlane()
        center = vtk_image.GetCenter()
        cx, cy, cz = center
        plane.SetOrigin(cx, cy, cz)
        plane.SetNormal(0, 0, 1) # Axial by default
        mapper.SetSlicePlane(plane)
        
        self.mappers[nome_visao] = mapper
        self.planos[nome_visao] = plane
        
        ator = vtk.vtkImageSlice()
        ator.SetMapper(mapper)
        ator.GetProperty().SetColorWindow(2000)
        ator.GetProperty().SetColorLevel(400)
        self.atores[nome_visao] = ator
        renderer.AddActor(ator)
        
        cam = renderer.GetActiveCamera()
        cam.SetFocalPoint(cx, cy, cz)
        cam.SetPosition(cx, cy, cz - 500)
        cam.SetViewUp(0, 1, 0)
        
        mapper.Update()
        renderer.ResetCameraClippingRange()
        renderer.ResetCamera()
        
        dim_y = vtk_image.GetDimensions()[1]
        cam.SetParallelScale(dim_y / 2.0)
        cam.ParallelProjectionOn()
        
        indicador = IndicadorJanelamento2D(renderer)
        self.indicadores[nome_visao] = indicador
        indicador.atualizar_valores(2000, 400)
        
        meta_act = vtk.vtkTextActor()
        prop_txt = meta_act.GetTextProperty()
        prop_txt.SetFontFamilyToArial()
        prop_txt.SetFontSize(11)
        prop_txt.BoldOn()
        prop_txt.SetColor(0.7, 0.7, 0.7)
        prop_txt.SetVerticalJustificationToTop()
        meta_act.GetPositionCoordinate().SetCoordinateSystemToNormalizedViewport()
        meta_act.GetPositionCoordinate().SetValue(0.02, 0.92)
        renderer.AddActor2D(meta_act)
        self.meta_actors[nome_visao] = meta_act
        
        bussola = {}
        posicoes_bussola = {
            "topo": (0.50, 0.93),
            "base": (0.50, 0.02),
            "esq":  (0.01, 0.50),
            "dir":  (0.93, 0.50),
        }
        for lado, pos in posicoes_bussola.items():
            act = vtk.vtkTextActor()
            act.SetInput("?")
            tp = act.GetTextProperty()
            tp.SetFontFamilyToArial()
            tp.SetFontSize(14)
            tp.BoldOn()
            tp.SetColor(1.0, 0.85, 0.2)
            tp.SetJustificationToCentered()
            act.GetPositionCoordinate().SetCoordinateSystemToNormalizedViewport()
            act.GetPositionCoordinate().SetValue(*pos)
            renderer.AddActor2D(act)
            bussola[lado] = act
        self.bussola_actors[nome_visao] = bussola
        
        renderer.ResetCameraClippingRange()
        self.atualizar_bussola()
        

    def inicializar_orientadores(self, interactor, nome_plano: str):
        """
        Chamado pelo CoordenadorNavegacao quando o interactor Qt estiver ativo.
        Instala um Observer de RenderEvent para atualizar a bússola dinamicamente
        sempre que a câmera se mover (rotação 2D).
        """
        if nome_plano not in self.renderers_2d:
            return

        renderer = self.renderers_2d[nome_plano]

        # Observer de RenderEvent: dispara atualizar_bussola a cada frame renderizado
        obs_id = renderer.AddObserver("ModifiedEvent", lambda obj, evt: self.atualizar_bussola())
        self._observadores.append((renderer, obs_id))

    def atualizar_bussola(self):
        """
        Recalcula as letras anatômicas das 4 bordas para cada plano 2D
        de acordo com a orientação atual da câmera (ViewUp e Right vector).

        Convenção radiológica:
          - Topo da tela → letra do vetor ViewUp da câmera projetado no RAS
          - Base da tela → oposto do topo
          - Direita da tela → proj × up (vetor Right)
          - Esquerda da tela → oposto da direita
        """
        for nome_plano, renderer in self.renderers_2d.items():
            if nome_plano not in self.bussola_actors:
                continue

            camera = renderer.GetActiveCamera()
            pos = camera.GetPosition()
            foc = camera.GetFocalPoint()
            up  = camera.GetViewUp()

            # Vetor de projeção normalizado: câmera → focal (aponta para dentro da tela)
            proj = (foc[0] - pos[0], foc[1] - pos[1], foc[2] - pos[2])
            mag_proj = math.sqrt(proj[0]**2 + proj[1]**2 + proj[2]**2)
            if mag_proj < 1e-9:
                continue
            proj = (proj[0]/mag_proj, proj[1]/mag_proj, proj[2]/mag_proj)

            # ViewUp normalizado → aponta para TOPO da tela
            mag_up = math.sqrt(up[0]**2 + up[1]**2 + up[2]**2)
            if mag_up < 1e-9:
                continue
            up_n = (up[0]/mag_up, up[1]/mag_up, up[2]/mag_up)

            # Right = proj × up_n → aponta para DIREITA da tela
            rx = proj[1]*up_n[2] - proj[2]*up_n[1]
            ry = proj[2]*up_n[0] - proj[0]*up_n[2]
            rz = proj[0]*up_n[1] - proj[1]*up_n[0]
            right = (rx, ry, rz)

            # Letras anatômicas por projeção de eixo dominante
            letra_topo  = _letra_anatomica(up_n)
            letra_base  = _letra_anatomica((-up_n[0], -up_n[1], -up_n[2]))
            letra_esq   = _letra_anatomica((-right[0], -right[1], -right[2]))
            letra_dir   = _letra_anatomica(right)

            bussola = self.bussola_actors[nome_plano]
            bussola["topo"].SetInput(letra_topo)
            bussola["base"].SetInput(letra_base)
            bussola["esq"].SetInput(letra_esq)
            bussola["dir"].SetInput(letra_dir)

    def navegar_fatia(self, visao: str, incremento: int):
        """
        Navega o plano ortogonal independente empurrando (Push) o vtkPlane espacialmente.
        """
        if visao in self.planos and self.operador_reslice:
            plane = self.planos[visao]
            spacing = self.operador_reslice.dados.GetSpacing()
            normal = plane.GetNormal()
            
            # Espaçamento ao longo da normal do plano
            esp = abs(normal[0]*spacing[0]) + abs(normal[1]*spacing[1]) + abs(normal[2]*spacing[2])
            plane.Push(incremento * esp)
            return None

    def atualizar_janelamento(self, visao: str, ww: float, wl: float):
        """
        Atualiza o janelamento (ColorWindow e ColorLevel) do ator de uma visão específica,
        atualizando também o texto do indicador visual.
        """
        if visao in self.atores and visao in self.indicadores:
            ator = self.atores[visao]
            ator.GetProperty().SetColorWindow(ww)
            ator.GetProperty().SetColorLevel(wl)
            self.indicadores[visao].atualizar_valores(ww, wl)

    def aplicar_preset(self, ww: float, wl: float):
        """
        Aplica os valores de WW e WL em todas as visões 2D ativas simultaneamente.
        """
        for visao in list(self.atores.keys()):
            self.atualizar_janelamento(visao, ww, wl)

    def atualizar_metadados_hud(self, texto: str):
        """
        Atualiza o texto dos metadados clínicos HUD em todos os renderizadores 2D.
        """
        for visao, actor in self.meta_actors.items():
            actor.SetInput(texto)

    def rotacionar_plano(self, visao_base, visao_alvo, p1, p2):
        """
        Rotaciona o plano alvo em torno da normal do plano base, calculando o
        ângulo incremental entre dois pontos de mundo capturados pelo mouse.
        """
        import numpy as np

        plane_base = self.planos[visao_base]
        plane_alvo = self.planos[visao_alvo]
        centro = np.array(plane_base.GetOrigin())

        v1 = np.array(p1) - centro
        v2 = np.array(p2) - centro

        axis = np.array(plane_base.GetNormal())

        cross_prod = np.cross(v1, v2)
        dot_prod   = np.dot(v1, v2)
        angle_rad  = math.atan2(np.dot(axis, cross_prod), dot_prod)
        angle_deg  = math.degrees(angle_rad)

        if abs(angle_deg) < 0.1:
            return

        transform = vtk.vtkTransform()
        transform.RotateWXYZ(angle_deg, axis[0], axis[1], axis[2])

        # Gira a Normal do plano alvo
        new_normal = transform.TransformDoubleVector(plane_alvo.GetNormal())
        plane_alvo.SetNormal(new_normal)

        # Gira a câmera do renderer alvo para manter a imagem em pé
        renderer_alvo = self.renderers_2d[visao_alvo]
        cam_alvo = renderer_alvo.GetActiveCamera()
        new_up = transform.TransformDoubleVector(cam_alvo.GetViewUp())
        cam_alvo.SetPosition(
            centro[0] - new_normal[0] * 500,
            centro[1] - new_normal[1] * 500,
            centro[2] - new_normal[2] * 500
        )
        cam_alvo.SetViewUp(new_up)

        # Recalcula letras do HUD para refletir o novo ângulo
        self.atualizar_bussola()

    def update_volume_data(self, novo_vtk_image):
        self.volume_ativo = novo_vtk_image
        self.operador_reslice.dados = novo_vtk_image
        center = novo_vtk_image.GetCenter()
        
        for visao, mapper in self.mappers.items():
            mapper.SetInputData(novo_vtk_image)
            plane = self.planos[visao]
            plane.SetOrigin(center)
            mapper.SetSlicePlane(plane)
            
            try:
                # Atualiza apenas o FocalPoint para o novo centro geométrico
                if visao in self.renderers_2d and self.renderers_2d[visao]:
                    cam = self.renderers_2d[visao].GetActiveCamera()
                    if cam:
                        cam.SetFocalPoint(center)
                # Removemos os ResetCamera() para manter a posição anterior travada!
            except RuntimeError:
                continue
