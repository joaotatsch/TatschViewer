import sys
sys.path.append(r'd:\Desktop\Projetos\TatschViewer')
from navegacao.filtros_eventos import FiltroEventosDicom

class MockInt:
    def setMouseTracking(self, v): pass
    def SetInteractorStyle(self, s): pass

f = FiltroEventosDicom(None, None, MockInt())
print("Before:", type(f.ferramenta_atual).__name__)
f.ferramenta_ativa = 'Regua'
print("After:", type(f.ferramenta_atual).__name__)
