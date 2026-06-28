import os

file_path = r'd:\Desktop\Projetos\TatschViewer\medidas\__init__.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
"""    def atualizar_regua(self, pos_world):
        if self.medida_ativa:
            self.medida_ativa.atualizar_ponto2(pos_world)
        
    def finalizar_regua(self):
        self.medida_ativa = None""",
"""    def atualizar_regua(self, pos_world):
        if self.medida_ativa:
            self.medida_ativa.atualizar_ponto2(pos_world)
            
    def atualizar_medida(self, medida, pos_world):
        if medida:
            medida.atualizar_ponto2(pos_world)
        
    def finalizar_regua(self):
        self.medida_ativa = None"""
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
