"""
Módulo de coordenação de navegação tridimensional.
"""
from PyQt6.QtCore import QObject
import vtk

class Navegador3D(QObject):
    """
    Coordenará as interações tridimensionais do usuário na reconstrução 3D,
    lidando com operações de rotação de câmera, pan, zoom e cortes de volume.
    """
    def __init__(self, renderizador_3d: vtk.vtkRenderer = None):
        super().__init__()
        self.renderizador = renderizador_3d
        self.volume_ator = None
        self.meta_actor = None
        self.ww_3d = 1000.0  # WW 3D padrão inicial
        self.wl_3d = 400.0   # WL 3D padrão inicial
        self.marcador_orientacao = None

    def atualizar_volume(self, novo_vtk_image):
        if self.volume_ator:
            mapper = self.volume_ator.GetMapper()
            mapper.SetInputData(novo_vtk_image)
            mapper.Update()
            
            bounds = novo_vtk_image.GetBounds()
            cx = (bounds[0] + bounds[1]) / 2.0
            cy = (bounds[2] + bounds[3]) / 2.0
            cz = (bounds[4] + bounds[5]) / 2.0
            
            cam = self.renderizador.GetActiveCamera()
            cam.SetFocalPoint(cx, cy, cz)
            self.renderizador.ResetCamera()
            self.renderizador.ResetCameraClippingRange()

    def configurar_3d(self, vtk_image: vtk.vtkImageData, renderer_3d: vtk.vtkRenderer) -> vtk.vtkVolume:
        """
        Configura o pipeline de Volume Rendering 3D usando aceleração por hardware (vtkSmartVolumeMapper),
        definindo as funções de transferência padrão de cor e opacidade, e adiciona o volume ao renderizador.
        """
        self.renderizador = renderer_3d
        
        # 1. Criação do Mapper Inteligente — blindado com try/except para compatibilidade de GPU
        volume_mapper = vtk.vtkSmartVolumeMapper()
        volume_mapper.SetInputData(vtk_image)
        volume_mapper.Update()  # Força limites 3D absolutos do novo volume

        try:
            # GPU ray-casting de alta fidelidade (OpenGL 3.3+)
            volume_mapper.SetRequestedRenderModeToGPU()

            # Desativa ajuste automático de distância de amostragem
            # (evita que o VTK degrade qualidade em volumes grandes)
            volume_mapper.SetAutoAdjustSampleDistances(False)

            # 0.2 = Distância de amostragem ultrafina (vs padrão 1.0–1.5)
            # Elimina faixas (banding) e artefatos de amostragem em tecidos suaves
            volume_mapper.SetSampleDistance(0.2)

        except AttributeError as e:
            # Fallback seguro: se a GPU/versão VTK não suportar, usa modo padrão
            print(f"[RENDER 3D] Fallback de mapper: {e}")
            volume_mapper.SetRequestedRenderModeToDefault()
        
        # 2. Propriedades do Volume (vtkVolumeProperty)
        propriedades = vtk.vtkVolumeProperty()
        propriedades.ShadeOn()  # Sombreamento de Lambert — dá profundidade, brilho e sombras reais
        propriedades.SetInterpolationTypeToLinear()

        # Normaliza a opacidade pela distância real entre voxels (resolve banding de cor)
        # 0.5 mm é um valor clínico excelente para Angio-TC com slice de ~0.5–1 mm
        propriedades.SetScalarOpacityUnitDistance(0.5)
        
        # Iluminação premium: Ambiente suave + Difuso forte + Especular brilhante
        # Amplifica o vermelho dos vasos angio e o branco crisção dos ossos
        propriedades.SetAmbient(0.15)
        propriedades.SetDiffuse(0.9)
        propriedades.SetSpecular(0.5)
        propriedades.SetSpecularPower(60.0)
        
        # 3. Instanciação e adição do Ator de Volume (vtkVolume)
        volume = vtk.vtkVolume()
        volume.SetMapper(volume_mapper)
        volume.SetProperty(propriedades)
        
        # Remove volumes anteriores para evitar sobreposição se carregados múltiplos arquivos
        renderer_3d.RemoveAllViewProps()
        
        # Adiciona o volume à cena
        renderer_3d.AddViewProp(volume)
        self.volume_ator = volume

        # 4. Aplica o preset visual "Atlas Anatômico" como renderização padrão
        self.aplicar_preset_3d_anatomico()
        
        # 5. Configuração e Adição do HUD vtkTextActor para Metadados do Paciente
        self.meta_actor = vtk.vtkTextActor()
        prop_txt = self.meta_actor.GetTextProperty()
        prop_txt.SetFontFamilyToArial()
        prop_txt.SetFontSize(11)
        prop_txt.BoldOn()
        prop_txt.SetColor(0.7, 0.7, 0.7)  # cinza claro
        self.meta_actor.GetPositionCoordinate().SetCoordinateSystemToNormalizedViewport()
        self.meta_actor.GetPositionCoordinate().SetValue(0.02, 0.85)
        renderer_3d.AddActor2D(self.meta_actor)
        
        # 5.5. Configuração do Cubo de Orientação Interativo 3D
        cubo = vtk.vtkAnnotatedCubeActor()
        cubo.SetXPlusFaceText("R")
        cubo.SetXMinusFaceText("L")
        cubo.SetYPlusFaceText("A")
        cubo.SetYMinusFaceText("P")
        cubo.SetZPlusFaceText("S")
        cubo.SetZMinusFaceText("I")
        cubo.SetFaceTextScale(0.65)
        prop_cubo = cubo.GetCubeProperty()
        prop_cubo.SetColor(0.2, 0.2, 0.2)
        
        marcador = vtk.vtkOrientationMarkerWidget()
        marcador.SetOrientationMarker(cubo)
        self.marcador_orientacao = marcador

        # 6. Configura a câmera com projeção perspectiva (desativa projeção paralela)
        camera = renderer_3d.GetActiveCamera()
        if camera:
            camera.ParallelProjectionOff()
            # Força o ponto focal no centro geométrico do volume para evitar rotação fora do centro
            bounds = vtk_image.GetBounds()  # (xmin, xmax, ymin, ymax, zmin, zmax)
            cx = (bounds[0] + bounds[1]) / 2.0
            cy = (bounds[2] + bounds[3]) / 2.0
            cz = (bounds[4] + bounds[5]) / 2.0
            camera.SetFocalPoint(cx, cy, cz)
            camera.SetPosition(cx, cy + 500, cz)
            camera.SetViewUp(0, 0, 1)

        # Ajusta a câmera tridimensional para enquadrar perfeitamente o volume
        renderer_3d.ResetCamera()

        # Ilumina a cena adequadamente
        renderer_3d.ResetCameraClippingRange()

        render_window = renderer_3d.GetRenderWindow()
        if render_window:
            try:
                # Anti-Aliasing temporal de 8 quadros:
                # VTK acumula 8 sub-amostras por pixel enquanto a cena está em repouso
                # Remove serrilhados nas bordas vasculares sem custo de GPU durante rotação
                render_window.SetAAFrames(8)
            except AttributeError:
                pass  # Graceful: sem AA se a versão VTK não suportar
            
            # DesiredUpdateRate aplicado na RenderWindow (local correto — NÃO no mapper)
            # 1.0 = qualidade máxima em idle; o interactor elevará para ~30 durante movimento
            render_window.SetDesiredUpdateRate(1.0)

        # 7. Configuração da Ferramenta de Dissecção (Box Cropping)
        self.crop_widget = vtk.vtkBoxWidget2()
        
        # Desvincula o Botão Direito para permitir Zoom In/Out nativo do interactor
        translator = self.crop_widget.GetEventTranslator()
        translator.SetTranslation(vtk.vtkCommand.RightButtonPressEvent, vtk.vtkWidgetEvent.NoEvent)
        translator.SetTranslation(vtk.vtkCommand.RightButtonReleaseEvent, vtk.vtkWidgetEvent.NoEvent)
        
        self.crop_representation = vtk.vtkBoxRepresentation()
        self.crop_representation.SetPlaceFactor(1.0)
        self.crop_widget.SetRepresentation(self.crop_representation)
        self.crop_widget.SetRotationEnabled(False)
        self.crop_widget.SetTranslationEnabled(True)
        self.crop_widget.SetScalingEnabled(True)

        return volume

    def inicializar_orientadores(self, interactor):
        """
        Associa o marcador ao interactor quando este estiver ativado pela UI.
        """
        if self.marcador_orientacao:
            self.marcador_orientacao.SetInteractor(interactor)
            self.marcador_orientacao.SetViewport(0.8, 0.0, 1.0, 0.2)
            self.marcador_orientacao.InteractiveOff()
            self.marcador_orientacao.EnabledOn()

        if hasattr(self, 'crop_widget') and getattr(self, 'crop_widget') is not None:
            self.crop_widget.SetInteractor(interactor)

    def mostrar_caixa_recorte(self, mostrar: bool):
        """
        Exibe ou oculta o gabarito interativo de recorte 3D (Box Widget).
        Não aplica o recorte ao volume ainda.
        """
        if not hasattr(self, 'crop_widget') or getattr(self, 'crop_widget') is None:
            return
            
        if mostrar:
            if hasattr(self, 'volume_ator') and getattr(self, 'volume_ator') is not None:
                self.crop_representation.PlaceWidget(self.volume_ator.GetBounds())
            self.crop_widget.EnabledOn()
        else:
            self.crop_widget.EnabledOff()
            
        if self.renderizador and self.renderizador.GetRenderWindow():
            self.renderizador.GetRenderWindow().Render()

    def aplicar_recorte_caixa(self):
        """
        Extrai os planos do Box Widget e aplica como Clipping Planes no Volume 3D.
        Corrige o bug InsideOut garantindo que o interior da caixa seja preservado.
        """
        if not hasattr(self, 'crop_representation') or getattr(self, 'crop_representation') is None:
            return
            
        planes = vtk.vtkPlanes()
        # CORREÇÃO CRÍTICA DO BUG: Garante que as normais apontem para fora (preservando o interior)
        self.crop_representation.SetInsideOut(True)
        self.crop_representation.GetPlanes(planes)
        
        if hasattr(self, 'volume_ator') and getattr(self, 'volume_ator') is not None:
            mapper = self.volume_ator.GetMapper()
            if mapper:
                mapper.SetClippingPlanes(planes)
                
        # Oculta o widget visual após aplicar
        if hasattr(self, 'crop_widget') and getattr(self, 'crop_widget') is not None:
            self.crop_widget.EnabledOff()
            
        if self.renderizador and self.renderizador.GetRenderWindow():
            self.renderizador.GetRenderWindow().Render()

    def resetar_recorte(self):
        """
        Limpa todos os recortes e restaura o volume 3D completo.
        """
        if hasattr(self, 'volume_ator') and getattr(self, 'volume_ator') is not None:
            mapper = self.volume_ator.GetMapper()
            if mapper:
                mapper.RemoveAllClippingPlanes()
                
        if hasattr(self, 'crop_widget') and getattr(self, 'crop_widget') is not None:
            self.crop_widget.EnabledOff()
            
        if self.renderizador and self.renderizador.GetRenderWindow():
            self.renderizador.GetRenderWindow().Render()

    def aplicar_preset_3d_anatomico(self):
        """
        Aplica o preset visual "Atlas Anatômico" ao volume 3D.

        Utiliza curvas de transferência calibradas em Hounsfield Units (HU) para
        produzir um efeito de Cinematic Volume Rendering:
          - Ar / Gordura           → totalmente transparentes
          - Tecido mole / Músculo  → translúcido pêssego/carne
          - Vasos com contraste    → vermelho vivo (padrão Angio-TC)
          - Osso esponjoso/cortical→ marfim opaco

        O VTK interpola suavemente entre todos os pontos, garantindo transições
        graduais sem artefatos visuais.
        """
        if not self.volume_ator:
            return

        # ── Função de Transferência de Opacidade (Escalar → Opacidade) ──────────
        # Cada ponto: (HU, opacidade 0‒1)
        funcao_opacidade = vtk.vtkPiecewiseFunction()
        funcao_opacidade.AddPoint(-1000,  0.000)  # Ar           → invisível
        funcao_opacidade.AddPoint( -200,  0.000)  # Pulmao/Ar    → invisível
        funcao_opacidade.AddPoint(  -50,  0.000)  # Gordura       → invisível
        funcao_opacidade.AddPoint(   20,  0.015)  # Tecido mole escuro → translúcido
        funcao_opacidade.AddPoint(   60,  0.060)  # Músculo/Parênquima
        funcao_opacidade.AddPoint(  140,  0.380)  # Vasos / Contraste leve
        funcao_opacidade.AddPoint(  220,  0.680)  # Vasos alto contraste / Angio
        funcao_opacidade.AddPoint(  400,  0.850)  # Osso esponjoso
        funcao_opacidade.AddPoint( 1000,  0.980)  # Osso cortical → quase opaco
        funcao_opacidade.AddPoint( 3071,  1.000)  # Máximo HU    → totalmente opaco

        # ── Função de Transferência de Cor (Escalar → RGB) ──────────────────────
        funcao_cor = vtk.vtkColorTransferFunction()
        # Ar e gordura: preto total
        funcao_cor.AddRGBPoint(-1000,  0.00, 0.00, 0.00)
        funcao_cor.AddRGBPoint(  -50,  0.00, 0.00, 0.00)
        # Tecido mole escuro: marrom escuro quente
        funcao_cor.AddRGBPoint(   20,  0.55, 0.25, 0.15)
        # Músculo / Parênquima: pêssego / carne
        funcao_cor.AddRGBPoint(   60,  0.90, 0.68, 0.55)
        # Vasos leves: laranja-avermelhado (transição)
        funcao_cor.AddRGBPoint(  140,  0.95, 0.28, 0.10)
        # Vasos com alto contraste Angio-TC: vermelho vivo
        funcao_cor.AddRGBPoint(  220,  0.92, 0.08, 0.08)
        # Osso esponjoso: bege/marfim
        funcao_cor.AddRGBPoint(  400,  0.88, 0.84, 0.72)
        # Osso cortical: branco límpido
        funcao_cor.AddRGBPoint( 1000,  0.97, 0.97, 0.93)
        funcao_cor.AddRGBPoint( 3071,  1.00, 1.00, 1.00)

        propriedades = self.volume_ator.GetProperty()
        propriedades.SetScalarOpacity(funcao_opacidade)
        propriedades.SetColor(funcao_cor)

        # Garante que o sombreamento está ativo (necessário para brilho e sombras)
        propriedades.ShadeOn()
        propriedades.SetAmbient(0.15)
        propriedades.SetDiffuse(0.9)
        propriedades.SetSpecular(0.5)
        propriedades.SetSpecularPower(60.0)

        if self.renderizador and self.renderizador.GetRenderWindow():
            self.renderizador.GetRenderWindow().Render()

    def aplicar_preset_dsa(self):
        """
        Aplica o preset 3D otimizado para DSA (Digital Subtraction Angiography).
        Remove tecidos moles residuais (opacidade 0 abaixo de 80 HU) e destaca
        a vasculatura iodada de forma opaca com gradiente vermelho/vinho até branco.
        """
        if not self.volume_ator:
            return

        # ── Função de Transferência de Opacidade (HU -> Opacidade) ──────────
        funcao_opacidade = vtk.vtkPiecewiseFunction()
        funcao_opacidade.AddPoint(-1000, 0.0)  # Ar -> invisível
        funcao_opacidade.AddPoint(80,    0.0)  # Até 80 HU -> estritamente invisível
        funcao_opacidade.AddPoint(150,   0.5)  # De 80 a 150 HU -> sobe para 0.5
        funcao_opacidade.AddPoint(200,   1.0)  # Acima de 200 HU -> totalmente opaca

        # ── Função de Transferência de Cor (HU -> RGB) ──────────────────────
        funcao_cor = vtk.vtkColorTransferFunction()
        # Tecidos escuros abaixo de 80: preto
        funcao_cor.AddRGBPoint(-1000, 0.0, 0.0, 0.0)
        funcao_cor.AddRGBPoint(79, 0.0, 0.0, 0.0)
        # De 80 (vermelho escuro/vinho) até 300 (vermelho vivo/branco)
        funcao_cor.AddRGBPoint(80,   0.35, 0.02, 0.05)  # Vermelho escuro/vinho
        funcao_cor.AddRGBPoint(150,  0.85, 0.05, 0.05)  # Vermelho vivo
        funcao_cor.AddRGBPoint(250,  0.95, 0.45, 0.15)  # Laranja brilhante
        funcao_cor.AddRGBPoint(300,  1.00, 0.95, 0.95)  # Branco/Vermelho muito claro

        propriedades = self.volume_ator.GetProperty()
        propriedades.SetScalarOpacity(funcao_opacidade)
        propriedades.SetColor(funcao_cor)

        # Configurações de iluminação para efeito Cinematic premium
        propriedades.ShadeOn()
        propriedades.SetAmbient(0.20)
        propriedades.SetDiffuse(0.85)
        propriedades.SetSpecular(0.6)
        propriedades.SetSpecularPower(50.0)

        if self.renderizador and self.renderizador.GetRenderWindow():
            self.renderizador.GetRenderWindow().Render()

    def aplicar_preset_angio(self):
        """
        Aplica o preset de 'Angio VR' de alta performance isolando o Polígono de Willis e
        vasos iodados, removendo totalmente o ruído de tecidos moles e pele.
        """
        if not self.volume_ator:
            return

        # ── Função de Transferência de Opacidade ──────────
        funcao_opacidade = vtk.vtkPiecewiseFunction()
        funcao_opacidade.AddPoint(-1024, 0.0)  # Totalmente invisível
        funcao_opacidade.AddPoint(120,   0.0)  # Totalmente invisível até 120 HU
        funcao_opacidade.AddPoint(150,   0.2)  # Transição suave para evitar artefato de borda
        funcao_opacidade.AddPoint(200,   0.8)  # Artérias finas brilhantes
        funcao_opacidade.AddPoint(400,   1.0)  # Contraste denso/Osso residual sólido

        # ── Função de Transferência de Cor ──────────────────────
        funcao_cor = vtk.vtkColorTransferFunction()
        funcao_cor.AddRGBPoint(120, 0.5, 0.0, 0.0)  # Vermelho escuro
        funcao_cor.AddRGBPoint(200, 1.0, 0.3, 0.0)  # Vermelho vivo / Laranja
        funcao_cor.AddRGBPoint(400, 1.0, 0.9, 0.5)  # Amarelo claro / Marfim

        propriedades = self.volume_ator.GetProperty()
        propriedades.SetScalarOpacity(funcao_opacidade)
        propriedades.SetColor(funcao_cor)

        propriedades.ShadeOn()
        propriedades.SetAmbient(0.20)
        propriedades.SetDiffuse(0.85)
        propriedades.SetSpecular(0.6)
        propriedades.SetSpecularPower(50.0)

        if self.renderizador and self.renderizador.GetRenderWindow():
            self.renderizador.GetRenderWindow().Render()

    def atualizar_transfer_functions(self, ww: float, wl: float, is_mr: bool = False):
        """
        Recalcula e atualiza as funções de transferência de cor e opacidade do volume 3D
        dinamicamente com base nos valores WW/WL fornecidos.
        """
        if not self.volume_ator:
            return
            
        self.ww_3d = ww
        self.wl_3d = wl
        
        # Calcula limites da rampa baseada em WW/WL
        min_val = wl - ww / 2.0
        max_val = wl + ww / 2.0
        
        if max_val <= min_val:
            max_val = min_val + 1.0
            
        funcao_opacidade = vtk.vtkPiecewiseFunction()
        funcao_cor = vtk.vtkColorTransferFunction()

        if is_mr:
            # Curva sigmoide para RM: fundo transparente, tecido semi-opaco
            # Evita o "paralelepipedo" da rampa linear
            low  = min_val + 0.05 * ww   # 5%: inicio do tecido
            mid  = min_val + 0.40 * ww   # 40%: tecido intermediario
            high = min_val + 0.85 * ww   # 85%: tecido de alto sinal

            funcao_opacidade.AddPoint(min_val, 0.00)  # fundo preto: transparente
            funcao_opacidade.AddPoint(low,     0.00)  # ruido: transparente
            funcao_opacidade.AddPoint(mid,     0.08)  # tecido mole
            funcao_opacidade.AddPoint(high,    0.35)  # alto sinal
            funcao_opacidade.AddPoint(max_val, 0.55)  # pico de sinal

            funcao_cor.AddRGBPoint(min_val, 0.00, 0.00, 0.00)  # preto
            funcao_cor.AddRGBPoint(low,     0.05, 0.05, 0.05)  # quase preto
            funcao_cor.AddRGBPoint(mid,     0.50, 0.50, 0.50)  # cinza
            funcao_cor.AddRGBPoint(high,    0.85, 0.85, 0.85)  # cinza claro
            funcao_cor.AddRGBPoint(max_val, 1.00, 1.00, 1.00)  # branco
        else:
            # Função de Transferência de Opacidade (CT)
            funcao_opacidade.AddPoint(min_val - 100, 0.00)
            funcao_opacidade.AddPoint(min_val, 0.00)
            funcao_opacidade.AddPoint(min_val + 0.2 * ww, 0.15)
            funcao_opacidade.AddPoint(min_val + 0.5 * ww, 0.50)
            funcao_opacidade.AddPoint(max_val, 0.85)
            
            # Função de Transferência de Cor (CT)
            funcao_cor.AddRGBPoint(min_val - 100, 0.0, 0.0, 0.0)      # Ar (Preto)
            funcao_cor.AddRGBPoint(min_val, 0.45, 0.25, 0.25)        # Tecido mole escuro
            funcao_cor.AddRGBPoint(min_val + 0.2 * ww, 0.85, 0.65, 0.55) # Tecido fibroso
            funcao_cor.AddRGBPoint(min_val + 0.5 * ww, 0.95, 0.90, 0.80) # Marfim
            funcao_cor.AddRGBPoint(max_val, 1.0, 1.0, 1.0)           # Branco puro
        
        propriedades = self.volume_ator.GetProperty()
        propriedades.SetColor(funcao_cor)
        propriedades.SetScalarOpacity(funcao_opacidade)
        funcao_opacidade.Modified()
        funcao_cor.Modified()
        propriedades.Modified()
        
        if self.renderizador and self.renderizador.GetRenderWindow():
            self.renderizador.GetRenderWindow().Render()

    def atualizar_metadados_hud(self, texto: str):
        """
        Atualiza o texto dos metadados clínicos HUD no renderizador 3D.
        """
        if self.meta_actor:
            self.meta_actor.SetInput(texto)
            if self.renderizador and self.renderizador.GetRenderWindow():
                self.renderizador.GetRenderWindow().Render()

    def resetar_camera(self):
        """
        Retorna a câmera para a posição padrão de visualização 3D anterior.
        """
        if self.renderizador:
            self.renderizador.ResetCamera()
            self.renderizador.GetRenderWindow().Render()

    def update_volume_data(self, novo_vtk_image):
        if self.volume_ator:
            mapper = self.volume_ator.GetMapper()
            mapper.SetInputData(novo_vtk_image)
            mapper.SetScalarModeToUsePointData()
            mapper.Update()
            
            bounds = novo_vtk_image.GetBounds()
            cx = (bounds[0] + bounds[1]) / 2.0
            cy = (bounds[2] + bounds[3]) / 2.0
            cz = (bounds[4] + bounds[5]) / 2.0
            
            cam = self.renderizador.GetActiveCamera()
            cam.SetFocalPoint(cx, cy, cz)
            # Removemos os ResetCamera() para manter a posição travada no Object Pool

