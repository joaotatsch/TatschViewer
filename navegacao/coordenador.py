# -*- coding: utf-8 -*-
from PyQt6.QtCore import QObject
import vtk

from .navegacao_2d import Navegador2D
from .navegacao_3d import Navegador3D
from .filtros_eventos import FiltroEventosDicom, FiltroEventosDicom3D

class CoordenadorNavegacao(QObject):
    """
    Coordenará as interações globais de navegação, mapeando os inputs de teclado/mouse
    para direcionar as atualizações nos modos 2D (MPR) e 3D do visualizador.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        # Conecta as classes de navegação subalternas
        self.navegador_2d = Navegador2D()
        self.navegador_3d = Navegador3D()
        self.filtros_eventos = {}
        self.lista_sementes = []
        self.atores_sementes = []

        
        from medidas import CoordenadorMedidas
        self.coordenador_medidas = CoordenadorMedidas()
        
        from manipulacao_da_imagem.reslice import OperadorInteracaoReslice
        self.operador_interacao_reslice = OperadorInteracaoReslice(self.navegador_2d)

    def inicializar_visualizacao(self, vtk_image: vtk.vtkImageData, quadrantes_interactors: dict, janelamento_callback=None, espessura_callback=None):
        """
        Distribui o volume para os quadrantes corretos, adiciona os atores
        aos renderizadores e atualiza as janelas de exibição imediatamente.
        """
        if hasattr(self, 'filtros_eventos') and self.filtros_eventos:
            for nome, filtro in list(self.filtros_eventos.items()):
                try:
                    if filtro and hasattr(filtro, 'interactor') and filtro.interactor:
                        filtro.interactor.removeEventFilter(filtro)
                except Exception:
                    pass
        self.filtros_eventos = {}

        # 1. Filtra os renderizadores 2D/3D dinamicamente
        renderers_2d = {}
        renderer_3d = None
        
        for nome, quadrante in quadrantes_interactors.items():
            if nome == "3D":
                renderer_3d = quadrante.renderer
            else:
                renderers_2d[nome] = quadrante.renderer

        self.navegador_2d.configurar_mpr(vtk_image, renderers_2d)
        
        # 2. Direciona o renderizador 3D para o Navegador3D
        if renderer_3d is not None:
            self.navegador_3d.configurar_3d(vtk_image, renderer_3d)
        
        # 3. Instala o filtro de eventos de mouse nos interactors de forma dinâmica
        self.filtros_eventos = {}
        for nome, quadrante in quadrantes_interactors.items():
            if nome != "3D":  # Garante que todas as telas 2D (incluindo Tela_1, Tela_2, etc.) herdem o filtro
                filtro = FiltroEventosDicom(
                    nome, 
                    self.navegador_2d, 
                    quadrante.interactor, 
                    self.operador_interacao_reslice, 
                    janelamento_callback, 
                    espessura_callback, 
                    parent=self
                )
                quadrante.interactor.installEventFilter(filtro)
                self.filtros_eventos[nome] = filtro
                
                # --- ANCORAGEM FÍSICA CONTRA GARBAGE COLLECTION ---
                quadrante.interactor.filtro_dicom = filtro
                quadrante.filtro_dicom = filtro
                quadrante.interactor.coordenador_local = self
                quadrante.coordenador_local = self

                # Inicializa o cubo direcional para a tela correspondente
                self.navegador_2d.inicializar_orientadores(quadrante.interactor, nome)
                
        if "3D" in quadrantes_interactors:
            quadrante_3d = quadrantes_interactors["3D"]
            
            # Instala o estilo TrackballCamera nativo para a visão 3D
            style_3d = vtk.vtkInteractorStyleTrackballCamera()
            quadrante_3d.interactor.SetInteractorStyle(style_3d)
            
            filtro_3d = FiltroEventosDicom3D(self.navegador_3d, quadrante_3d.interactor, janelamento_callback, parent=self)
            quadrante_3d.interactor.installEventFilter(filtro_3d)
            self.filtros_eventos["3D"] = filtro_3d
            
            # Inicializa o cubo direcional 3D
            self.navegador_3d.inicializar_orientadores(quadrante_3d.interactor)
            
        # 4. Inicializa o Operador de MIP e o Crosshair
        from manipulacao_da_imagem.mip import OperadorProjecao
        from manipulacao_da_imagem.crosshair import OperadorCrosshair
        
        self.operador_projecao = OperadorProjecao(self.navegador_2d.mappers, renderers_2d, vtk_image.GetBounds())
        cx, cy, cz = vtk_image.GetCenter()
        self.operador_projecao.atualizar_linhas(cx, cy, cz, self.navegador_2d.planos)
        
        todos_renderers = {}
        for nome, quad in quadrantes_interactors.items():
            todos_renderers[nome] = quad.renderer
            
        self.operador_crosshair = OperadorCrosshair()
        self.operador_crosshair.inicializar(todos_renderers)
        
        # 5. Força a atualização imediata das janelas de renderização do VTK
        for nome, quadrante in quadrantes_interactors.items():
            quadrante.interactor.GetRenderWindow().Render()

    def alternar_modo_navegacao(self, modo: str):
        """
        Alterna as ferramentas e interações do usuário de acordo com o modo ativo.
        """
        pass

    def inicializar_tela_dinamica(self, nome_visao, vtk_image, quadrante, janelamento_cb, espessura_cb):
        self.navegador_2d.adicionar_visao_independente(nome_visao, vtk_image, quadrante.renderer)
        filtro = FiltroEventosDicom(nome_visao, self.navegador_2d, quadrante.interactor, self.operador_interacao_reslice, janelamento_cb, espessura_cb, parent=self)
        quadrante.interactor.installEventFilter(filtro)
        self.filtros_eventos[nome_visao] = filtro
        
        self.navegador_2d.inicializar_orientadores(quadrante.interactor, nome_visao)
        quadrante.interactor.GetRenderWindow().Render()

    def aplicar_bisturi(self, cortar_fora=False):
        """Coleta os pontos, repassa ao OperadorBisturi e atualiza mappers."""
        if not hasattr(self, 'pontos_corte') or len(self.pontos_corte) < 3:
            return
            
        if not hasattr(self, 'volume_original_bisturi'):
            import vtk
            self.volume_original_bisturi = vtk.vtkImageData()
            self.volume_original_bisturi.DeepCopy(self.navegador_3d.volume_ator.GetMapper().GetInput())
            
        from manipulacao_da_imagem.bisturi import OperadorBisturi
        volume_atual = self.navegador_3d.volume_ator.GetMapper().GetInput()
        operador = OperadorBisturi(volume_atual)
        
        # Executa o corte
        manter_interior = cortar_fora
        novo_volume = operador.cortar(
            self.pontos_corte, 
            self.renderer_corte, 
            manter_interior
        )
        
        import time
        t_inicio = time.time()
        
        # Atualiza todos os renderizadores
        self.navegador_2d.update_volume_data(novo_volume)
        self.navegador_3d.update_volume_data(novo_volume)
        
        # Oculta o ator do bisturi e renderiza
        for filtro in self.filtros_eventos.values():
            if hasattr(filtro, 'bisturi_actor'):
                if hasattr(filtro, 'interactor') and filtro.interactor:
                    renderer = filtro.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
                    if renderer and renderer.HasViewProp(filtro.bisturi_actor):
                        renderer.RemoveActor(filtro.bisturi_actor)
                    filtro.interactor.GetRenderWindow().Render()
                    
        t_fim = time.time()
        print(f"[PROFILING BISTURI] 5. Atualização da Engine 3D (GPU Rebuild): {t_fim - t_inicio:.4f}s")
        
    def resetar_bisturi(self):
        """Restaura o volume original do exame."""
        if hasattr(self, 'volume_original_bisturi'):
            import vtk
            volume_restaurado = vtk.vtkImageData()
            volume_restaurado.DeepCopy(self.volume_original_bisturi)
            
            self.navegador_2d.update_volume_data(volume_restaurado)
            self.navegador_3d.update_volume_data(volume_restaurado)
            
            for filtro in self.filtros_eventos.values():
                if hasattr(filtro, 'bisturi_actor'):
                    if hasattr(filtro, 'interactor') and filtro.interactor:
                        renderer = filtro.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
                        if renderer and renderer.HasViewProp(filtro.bisturi_actor):
                            renderer.RemoveActor(filtro.bisturi_actor)
                        filtro.interactor.GetRenderWindow().Render()

    def disparar_extracao_semente(self, pos):
        if self.parent() and hasattr(self.parent(), 'disparar_extracao_semente'):
            self.parent().disparar_extracao_semente(pos)

    def adicionar_semente(self, pos, actor):
        self.lista_sementes.append(pos)
        self.atores_sementes.append(actor)

    def limpar_sementes(self, renderers_2d=None):
        if renderers_2d is None:
            renderers_2d = list(self.navegador_2d.renderers_2d.values())
        elif isinstance(renderers_2d, dict):
            renderers_2d = list(renderers_2d.values())
        elif not isinstance(renderers_2d, list):
            renderers_2d = [renderers_2d]

        for renderer in renderers_2d:
            if renderer:
                for actor in self.atores_sementes:
                    if renderer.HasViewProp(actor):
                        renderer.RemoveActor(actor)
        
        self.lista_sementes.clear()
        self.atores_sementes.clear()
        
        for visao in self.navegador_2d.renderers_2d.values():
            if visao and visao.GetRenderWindow():
                visao.GetRenderWindow().Render()

