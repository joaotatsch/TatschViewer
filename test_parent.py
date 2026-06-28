import sys
import os
sys.path.append(r'd:\Desktop\Projetos\TatschViewer')

from PyQt6.QtWidgets import QApplication
from main import MainWindow

app = QApplication(sys.argv)
window = MainWindow()
print("Window loaded!")

coord = window.coordenador_navegacao
filtro = list(coord.filtros_eventos.values())[0]
print("Filtro:", filtro)
print("Filtro parent:", filtro.parent())
print("Coordenador medidas:", getattr(filtro.parent(), 'coordenador_medidas', None))
