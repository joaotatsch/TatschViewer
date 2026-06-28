import os

file_filtros = r'd:\Desktop\Projetos\TatschViewer\navegacao\filtros_eventos.py'
with open(file_filtros, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
"""        self._ferramenta_ativa = "Normal"
        from .ferramentas import FerramentaNormal, FerramentaBisturi
        from .ferramentas_base import FerramentaBase
        self.ferramentas = {
            'Normal': FerramentaNormal(),
            'Bisturi': FerramentaBisturi()
        }""",
"""        self._ferramenta_ativa = "Normal"
        from .ferramentas import FerramentaBisturi
        from .ferramentas_base import FerramentaBase
        self.ferramentas = {
            'Normal': FerramentaBase(),
            'Bisturi': FerramentaBisturi()
        }"""
)

with open(file_filtros, 'w', encoding='utf-8') as f:
    f.write(content)
