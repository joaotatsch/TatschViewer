from .regua import MedidaRegua
from .elipse import MedidaElipse

class CoordenadorMedidas:
    def __init__(self):
        self.medidas = []
        self.medida_ativa = None
        
    def iniciar_regua(self, renderer, pos_world, view_name, origin_plane):
        self.medida_ativa = MedidaRegua(renderer, pos_world, view_name, origin_plane)
        self.medidas.append(self.medida_ativa)
        
    def iniciar_elipse(self, renderer, pos_world, view_name, origin_plane, vtk_image):
        self.medida_ativa = MedidaElipse(renderer, pos_world, view_name, origin_plane, vtk_image)
        self.medidas.append(self.medida_ativa)
        
    def atualizar_regua(self, pos_world):
        if self.medida_ativa:
            self.medida_ativa.atualizar_ponto2(pos_world)
            
    def atualizar_medida(self, medida, pos_world):
        if medida:
            medida.atualizar_ponto2(pos_world)
        
    def finalizar_regua(self):
        self.medida_ativa = None
        
    def remover_medida(self, medida):
        if medida in self.medidas:
            medida.remover()
            self.medidas.remove(medida)
            
    def verificar_visibilidade(self, view_name, current_origin, tol=0.5):
        idx_map = {"Sagital": 0, "Coronal": 1, "Axial": 2}
        if view_name not in idx_map: return
        eixo = idx_map[view_name]
        pos_atual = current_origin[eixo]
        for med in self.medidas:
            if med.view_name == view_name:
                med.set_visivel(abs(pos_atual - med.slice_coord[eixo]) <= tol)
