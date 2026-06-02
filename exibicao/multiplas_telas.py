from PyQt6.QtWidgets import QWidget, QGridLayout
from exibicao.layout_4_up import QuadranteVisualizador

class LayoutDinamico(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout_grade = QGridLayout(self)
        self.layout_grade.setContentsMargins(2, 2, 2, 2)
        self.layout_grade.setSpacing(2)
        
        self.todas_telas = []
        for i in range(1, 7):
            nome_tela = f"TELA {i}"
            tela = QuadranteVisualizador(nome_tela, self)
            tela.hide()
            self.todas_telas.append(tela)
            
        self.visoes = {}

    def configurar_grade(self, linhas: int, colunas: int):
        # Esconde e remove todas as telas atuais do layout
        for tela in self.todas_telas:
            tela.hide()
            self.layout_grade.removeWidget(tela)
            
        self.visoes = {}
        
        # Adiciona as telas necessárias na grade
        total_necessario = linhas * colunas
        idx_tela = 0
        
        for r in range(linhas):
            for c in range(colunas):
                if idx_tela < len(self.todas_telas) and idx_tela < total_necessario:
                    tela = self.todas_telas[idx_tela]
                    self.layout_grade.addWidget(tela, r, c)
                    tela.show()
                    
                    if tela.renderer.GetActors().GetNumberOfItems() == 0:
                        tela.renderer.RemoveAllViewProps()
                        tela.interactor.GetRenderWindow().Render()
                    
                    nome = f"TELA {idx_tela + 1}"
                    self.visoes[nome] = tela
                    idx_tela += 1
