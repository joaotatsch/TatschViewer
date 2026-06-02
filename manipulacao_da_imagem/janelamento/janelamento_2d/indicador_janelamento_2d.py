"""
Módulo indicador visual de janelamento 2D em tempo real integrado ao VTK.
"""
import vtk

class IndicadorJanelamento2D:
    """
    Monitora e exibe em tempo real qual o Window Width (WW) e o Window Level (WL)
    do janelamento de cada tela plana do layout, utilizando um vtkTextActor sobreposto.
    """
    def __init__(self, renderer: vtk.vtkRenderer):
        self.renderer = renderer
        self.text_actor = vtk.vtkTextActor()
        
        # Configura as propriedades visuais do texto (cinza-claro minimalista)
        prop = self.text_actor.GetTextProperty()
        prop.SetFontFamilyToArial()
        prop.SetFontSize(12)
        prop.BoldOn()
        prop.SetColor(0.75, 0.75, 0.75)  # Cinza-claro
        
        # Configura posicionamento dinâmico no canto inferior esquerdo da tela (2% de margem)
        self.text_actor.GetPositionCoordinate().SetCoordinateSystemToNormalizedViewport()
        self.text_actor.GetPositionCoordinate().SetValue(0.02, 0.02)
        
        # Adiciona o ator de texto à visualização 2D
        self.renderer.AddActor2D(self.text_actor)
        self.atualizar_valores(2000, 400)  # Valores iniciais padrão

    def atualizar_valores(self, largura: float, nivel: float):
        """
        Atualiza o vtkTextActor exibindo a largura (WW) e o nível (WL) da janela ativa.
        """
        self.text_actor.SetInput(f"W: {int(largura)} L: {int(nivel)}")
        
        # Solicita re-renderização imediata da janela correspondente para atualizar a tela
        if self.renderer.GetRenderWindow():
            self.renderer.GetRenderWindow().Render()
