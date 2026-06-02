from PyQt6.QtCore import QObject
import vtk

class OperadorProjecao(QObject):
    def __init__(self, mappers_2d: dict, renderers_2d: dict, bounds: tuple):
        super().__init__()
        self.mappers_2d = mappers_2d
        self.renderers_2d = renderers_2d
        self.bounds = bounds
        self.espessuras = {"Axial": 0.0, "Coronal": 0.0, "Sagital": 0.0}
        self.modos = {"Axial": "Normal", "Coronal": "Normal", "Sagital": "Normal"}
        self.ultimos_centros = (0.0, 0.0, 0.0)
        self.ultimos_planos = {}
        
        self.linhas = {"Axial": {}, "Coronal": {}, "Sagital": {}}
        
        cor_vermelha = (1.0, 0.0, 0.0) # Axial
        cor_azul = (0.0, 0.0, 1.0)     # Coronal
        cor_amarela = (1.0, 1.0, 0.0)  # Sagital
        
        # Visão Axial: exibe Coronal e Sagital
        if "Axial" in self.renderers_2d and self.renderers_2d["Axial"]:
            rnd = self.renderers_2d["Axial"]
            self.linhas["Axial"]["Coronal"] = self._criar_linha(rnd, cor_azul)
            self.linhas["Axial"]["Coronal_Tr1"] = self._criar_linha(rnd, cor_azul, True)
            self.linhas["Axial"]["Coronal_Tr2"] = self._criar_linha(rnd, cor_azul, True)
            self.linhas["Axial"]["Sagital"] = self._criar_linha(rnd, cor_amarela)
            self.linhas["Axial"]["Sagital_Tr1"] = self._criar_linha(rnd, cor_amarela, True)
            self.linhas["Axial"]["Sagital_Tr2"] = self._criar_linha(rnd, cor_amarela, True)

        # Visão Coronal: exibe Axial e Sagital
        if "Coronal" in self.renderers_2d and self.renderers_2d["Coronal"]:
            rnd = self.renderers_2d["Coronal"]
            self.linhas["Coronal"]["Axial"] = self._criar_linha(rnd, cor_vermelha)
            self.linhas["Coronal"]["Axial_Tr1"] = self._criar_linha(rnd, cor_vermelha, True)
            self.linhas["Coronal"]["Axial_Tr2"] = self._criar_linha(rnd, cor_vermelha, True)
            self.linhas["Coronal"]["Sagital"] = self._criar_linha(rnd, cor_amarela)
            self.linhas["Coronal"]["Sagital_Tr1"] = self._criar_linha(rnd, cor_amarela, True)
            self.linhas["Coronal"]["Sagital_Tr2"] = self._criar_linha(rnd, cor_amarela, True)

        # Visão Sagital: exibe Axial e Coronal
        if "Sagital" in self.renderers_2d and self.renderers_2d["Sagital"]:
            rnd = self.renderers_2d["Sagital"]
            self.linhas["Sagital"]["Axial"] = self._criar_linha(rnd, cor_vermelha)
            self.linhas["Sagital"]["Axial_Tr1"] = self._criar_linha(rnd, cor_vermelha, True)
            self.linhas["Sagital"]["Axial_Tr2"] = self._criar_linha(rnd, cor_vermelha, True)
            self.linhas["Sagital"]["Coronal"] = self._criar_linha(rnd, cor_azul)
            self.linhas["Sagital"]["Coronal_Tr1"] = self._criar_linha(rnd, cor_azul, True)
            self.linhas["Sagital"]["Coronal_Tr2"] = self._criar_linha(rnd, cor_azul, True)
        self.reslice_ativo = False

    def _criar_linha(self, renderer, cor, tracejado=False):
        source = vtk.vtkLineSource()
        if tracejado: source.SetResolution(50) # Cria 50 pontos espaçados
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(source.GetOutputPort())
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(cor)
        actor.GetProperty().SetLineWidth(1.5)
        actor.PickableOff()
        if tracejado:
            actor.GetProperty().SetRepresentationToPoints()
            actor.GetProperty().SetPointSize(3)
            actor.SetVisibility(False)
        renderer.AddActor(actor)
        return source, actor

    def aplicar_projecao_individual(self, visao: str, modo: str, esp: float):
        self.espessuras[visao] = esp
        self.modos[visao] = modo
        mapper = self.mappers_2d.get(visao)
        if mapper:
            mapper.SetSlabThickness(esp)
            if modo == "MIP":
                mapper.SetSlabTypeToMax()
            elif modo == "MinIP":
                mapper.SetSlabTypeToMin()
            elif modo == "Average":
                mapper.SetSlabTypeToMean()
            elif modo == "Normal":
                mapper.SetSlabThickness(0)
                
        self.atualizar_visibilidade()
        self.atualizar_linhas(*self.ultimos_centros)

    def set_reslice_ativo(self, ativo: bool):
        self.reslice_ativo = ativo
        self.atualizar_visibilidade()

    def atualizar_visibilidade(self):
        reslice_on = getattr(self, 'reslice_ativo', False)
        for visao_base, linhas_view in self.linhas.items():
            for nome_linha, (source, actor) in linhas_view.items():
                visao_alvo = nome_linha.split("_")[0]
                modo = self.modos.get(visao_alvo, "Normal")
                esp = self.espessuras.get(visao_alvo, 0)
                
                if "Tr" in nome_linha:
                    actor.SetVisibility(modo != "Normal" and esp > 0)
                else:
                    # Visível se tiver MIP OU se o Reslice estiver ligado
                    actor.SetVisibility(modo != "Normal" or reslice_on)

    def aplicar_projecao_global(self, modo: str, esp: float):
        for visao in ["Axial", "Coronal", "Sagital"]:
            self.aplicar_projecao_individual(visao, modo, esp)

    def atualizar_linhas(self, cx, cy, cz, planos_dict=None):
        self.ultimos_centros = (cx, cy, cz)
        if planos_dict is not None:
            self.ultimos_planos = planos_dict
            
        if not hasattr(self, 'ultimos_planos') or not self.ultimos_planos:
            return
            
        if "Axial" not in self.ultimos_planos or "Coronal" not in self.ultimos_planos or "Sagital" not in self.ultimos_planos:
            return
            
        import numpy as np
        centro = np.array([cx, cy, cz])
        normais = {
            "Axial": np.array(self.ultimos_planos["Axial"].GetNormal()),
            "Coronal": np.array(self.ultimos_planos["Coronal"].GetNormal()),
            "Sagital": np.array(self.ultimos_planos["Sagital"].GetNormal())
        }
        
        def atualizar_grupo(visao_base, visao_alvo, nome_linha):
            n_base = normais[visao_base]
            n_alvo = normais[visao_alvo]
            dir_linha = np.cross(n_base, n_alvo)
            norm_dir = np.linalg.norm(dir_linha)
            if norm_dir < 1e-6: return
            dir_linha = dir_linha / norm_dir
            
            p1 = centro - dir_linha * 500.0
            p2 = centro + dir_linha * 500.0
            
            # --- LÓGICA ANTI Z-FIGHTING (Puxa a linha 1.0mm para a câmera) ---
            cam = self.renderers_2d[visao_base].GetActiveCamera()
            cam_pos = np.array(cam.GetPosition())
            focal_pos = np.array(cam.GetFocalPoint())
            vetor_camera = cam_pos - focal_pos
            norm_cam = np.linalg.norm(vetor_camera)
            dir_camera = vetor_camera / norm_cam if norm_cam > 0 else np.array([0, 0, 0])
            
            offset_zfighting = dir_camera * 1.0
            p1_off = p1 + offset_zfighting
            p2_off = p2 + offset_zfighting
            # -----------------------------------------------------------------
            
            l = self.linhas[visao_base]
            l[nome_linha][0].SetPoint1(p1_off)
            l[nome_linha][0].SetPoint2(p2_off)
            
            d = self.espessuras.get(visao_alvo, 0) / 2.0
            if d > 0:
                offset = n_alvo * d
                l[f"{nome_linha}_Tr1"][0].SetPoint1(p1_off - offset)
                l[f"{nome_linha}_Tr1"][0].SetPoint2(p2_off - offset)
                l[f"{nome_linha}_Tr2"][0].SetPoint1(p1_off + offset)
                l[f"{nome_linha}_Tr2"][0].SetPoint2(p2_off + offset)

        if self.linhas["Axial"]:
            atualizar_grupo("Axial", "Coronal", "Coronal")
            atualizar_grupo("Axial", "Sagital", "Sagital")
        if self.linhas["Coronal"]:
            atualizar_grupo("Coronal", "Axial", "Axial")
            atualizar_grupo("Coronal", "Sagital", "Sagital")
        if self.linhas["Sagital"]:
            atualizar_grupo("Sagital", "Axial", "Axial")
            atualizar_grupo("Sagital", "Coronal", "Coronal")
            
        for linhas_view in self.linhas.values():
            for source, actor in linhas_view.values():
                source.Update()
