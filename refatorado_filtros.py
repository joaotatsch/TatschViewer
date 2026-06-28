# -*- coding: utf-8 -*-
from __future__ import annotations
from PyQt6.QtCore import QObject, QEvent, Qt
import vtk

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .navegacao_2d import Navegador2D
    from .navegacao_3d import Navegador3D

class FiltroEventosDicom(QObject):
    """
    Filtro de eventos PyQt6 para os visualizadores 2D.
    Instala o vtkInteractorStyleImage nativo e escuta seus eventos de janelamento,
    enquanto consome o scroll da roda do mouse para avanço de fatias e Ctrl+Left para roll 2D.
    """
    def __init__(self, nome_visao: str, navegador_2d: Navegador2D, interactor: vtk.vtkRenderWindowInteractor, operador_interacao_reslice=None, janelamento_callback=None, espessura_callback=None, parent=None):
        super().__init__(parent)
        self.ativo = True
        self.nome_visao = nome_visao
        self.navegador_2d = navegador_2d
        self.interactor = interactor
        self.operador_interacao_reslice = operador_interacao_reslice
        self.janelamento_callback = janelamento_callback
        self.espessura_callback = espessura_callback
        
        self.arrastando_janelamento = False
        self.arrastando_zoom = False
        self.arrastando_pan = False
        self.arrastando_crosshair = False
        self.arrastando_rotacao = False
        
        self.alvo_arraste = None
        self.alvo_reslice = None
        self.interactor.setMouseTracking(True)
        self.modo_crosshair = False
        self.ferramenta_ativa = "Normal"
        from .ferramentas import (
            FerramentaNormal, FerramentaSemente, FerramentaSementeDSA,
            FerramentaRegua, FerramentaElipse, FerramentaCropBox,
            FerramentaCrosshair, FerramentaReslice, FerramentaBisturi
        )
        self.ferramentas = {
            'Normal': FerramentaNormal(),
            'Semente': FerramentaSemente(),
            'SementeDSA': FerramentaSementeDSA(),
            'Regua': FerramentaRegua(),
            'Elipse': FerramentaElipse(),
            'CropBox': FerramentaCropBox(),
            'Crosshair': FerramentaCrosshair(),
            'Reslice': FerramentaReslice(),
            'Bisturi': FerramentaBisturi()
        }
        self.ferramenta_atual = self.ferramentas['Normal']
        self.arrastando_regua = False
        self.medida_selecionada = None
        self.arrastando_medida = False
        self._ultimo_pick_mundo = None
        self.ultima_posicao_medida = None
        self.drag_crop_index = None
        self.ultimo_pick_mundo = None
        self.picker = vtk.vtkCellPicker()
        self.picker.SetTolerance(0.005)
        
        # Cria o interactor style nativo 2D do VTK
        self.style = vtk.vtkInteractorStyleImage()
        self.style = vtk.vtkInteractorStyleImage()
        self.interactor.SetInteractorStyle(self.style)
                
    def _renderizar_seguro(self):
        if "TELA" in self.nome_visao:
            rnd = self.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
            if rnd: rnd.ResetCameraClippingRange()
            self.interactor.GetRenderWindow().Render()
        else:
            for v in ["Axial", "Coronal", "Sagital"]:
                if hasattr(self.parent(), 'filtros_eventos') and v in self.parent().filtros_eventos:
                    interactor = self.parent().filtros_eventos[v].interactor
                    if interactor.GetRenderWindow():
                        rnd = interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
                        if rnd: rnd.ResetCameraClippingRange()
                        interactor.GetRenderWindow().Render()

    def _hit_test(self, pos):
        if "Sagital" not in self.navegador_2d.planos or "Coronal" not in self.navegador_2d.planos or "Axial" not in self.navegador_2d.planos:
            return None
        cx = self.navegador_2d.planos["Sagital"].GetOrigin()[0]
        cy = self.navegador_2d.planos["Coronal"].GetOrigin()[1]
        cz = self.navegador_2d.planos["Axial"].GetOrigin()[2]
        centros = {"Sagital": cx, "Coronal": cy, "Axial": cz}
        idx_map = {"Sagital": 0, "Coronal": 1, "Axial": 2}

        visoes_cruzadas = []
        if self.nome_visao == "Axial": visoes_cruzadas = ["Sagital", "Coronal"]
        elif self.nome_visao == "Coronal": visoes_cruzadas = ["Sagital", "Axial"]
        elif self.nome_visao == "Sagital": visoes_cruzadas = ["Coronal", "Axial"]
        
        proj = self.parent().operador_projecao if hasattr(self.parent(), 'operador_projecao') else None
        
        # Se a projeção estiver em modo Normal, ignora completamente as linhas
        if not proj or proj.modos.get(self.nome_visao, "Normal") == "Normal":
            return None
            
        tol = 5.0
        
        v1, v2 = visoes_cruzadas[0], visoes_cruzadas[1]
        if abs(pos[idx_map[v1]] - centros[v1]) < tol and abs(pos[idx_map[v2]] - centros[v2]) < tol:
            return "Centro"
            
        for v_alvo in visoes_cruzadas:
            esp = proj.espessuras.get(v_alvo, 0)
            if esp > 0 and abs(abs(pos[idx_map[v_alvo]] - centros[v_alvo]) - (esp / 2.0)) < tol:
                return "Espessura_" + v_alvo
                
        for v_alvo in visoes_cruzadas:
            if abs(pos[idx_map[v_alvo]] - centros[v_alvo]) < tol:
                return v_alvo
                
        return None

    def eventFilter(self, obj, event):
        if not getattr(self, 'ativo', True):
            return True
        if not hasattr(self, 'interactor') or self.interactor is None:
            return super().eventFilter(obj, event)
        try:
            if obj == self.interactor:
                if event.type() == QEvent.Type.Wheel:
                    try:
                        delta = event.angleDelta().y()
                        if delta != 0:
                            inc = 1 if delta > 0 else -1
                            nav = self.navegador_2d
                            
                            # Obtém o plano correspondente ou usa o primeiro disponível (fallback seguro)
                            plane = nav.planos.get(self.nome_visao)
                            if plane is None and len(nav.planos) > 0:
                                plane = list(nav.planos.values())[0]
                                
                            if plane and nav.volume_ativo:
                                spacing = nav.volume_ativo.GetSpacing()
                                normal = plane.GetNormal()
                                esp = abs(normal[0]*spacing[0]) + abs(normal[1]*spacing[1]) + abs(normal[2]*spacing[2])
                                delta_mm = inc * esp
                                
                                # 1. Empurra o plano de origem local
                                plane.Push(delta_mm)
                                
                                # Atualiza as linhas do MIP apenas se todos os planos padrão existirem no navegador
                                if hasattr(self.parent(), 'operador_projecao') and self.parent().operador_projecao:
                                    if "Sagital" in nav.planos and "Coronal" in nav.planos and "Axial" in nav.planos:
                                        cx = nav.planos["Sagital"].GetOrigin()[0]
                                        cy = nav.planos["Coronal"].GetOrigin()[1]
                                        cz = nav.planos["Axial"].GetOrigin()[2]
                                        self.parent().operador_projecao.atualizar_linhas(cx, cy, cz, nav.planos)
                                        
                                # --- FILTRO DE VISIBILIDADE ATIVA E SINCRONIA DE QSCROLLBAR ---
                                # Busca segura pela MainWindow para extrair as visões ativas na tela agora
                                win = self.parent()
                                while win is not None and not hasattr(win, "coordenador_exibicao"):
                                    win = win.parent() if hasattr(win, "parent") else None
                                    
                                visoes_visiveis = []
                                sync_active = False
                                if win and hasattr(win, "coordenador_exibicao") and win.coordenador_exibicao.widget_layout_ativo:
                                    visoes = win.coordenador_exibicao.widget_layout_ativo.visoes
                                    visoes_visiveis = list(visoes.keys())
                                    if self.nome_visao in visoes:
                                        quadrante = visoes[self.nome_visao]
                                        if hasattr(quadrante, "sincronizar_scrollbar") and nav.volume_ativo:
                                            quadrante.sincronizar_scrollbar(plane, nav.volume_ativo)
                                            
                                    if hasattr(win, "is_sincronizacao_ativa"):
                                        sync_active = win.is_sincronizacao_ativa()
                                
                                # --- SINCRONIA INTERNA DOS PLANOS-IRMÃOS ---
                                if sync_active:
                                    # Se a sincronia estiver ativa, empurra os planos das OUTRAS telas visíveis deste mesmo coordenador
                                    for v_nome in visoes_visiveis:
                                        if v_nome != self.nome_visao:
                                            p_alvo = nav.planos.get(v_nome)
                                            if p_alvo and hasattr(p_alvo, "Push"):
                                                p_alvo.Push(delta_mm)
                                # --------------------------------------------
                                
                                # Notifica APENAS as fatias que estão fisicamente visíveis no layout ativo
                                for visao_nome, rnd in nav.renderers_2d.items():
                                    if visao_nome in visoes_visiveis:  # Filtro rígido
                                        if rnd and rnd.GetRenderWindow():
                                            try:
                                                rnd.ResetCameraClippingRange()
                                                rnd.GetRenderWindow().Render()
                                            except Exception:
                                                pass
                                        
                                # Sincronização de rolagem global (Sync Scroll)
                                from PyQt6.QtWidgets import QApplication
                                win_sync = None
                                for widget in QApplication.topLevelWidgets():
                                    if hasattr(widget, "sincronizar_rolagem_global"):
                                        win_sync = widget
                                        break
                                        
                                if win_sync is not None:
                                    sync_active = False
                                    if hasattr(win_sync, "is_sincronizacao_ativa"):
                                        sync_active = win_sync.is_sincronizacao_ativa()
                                    elif getattr(win_sync, "sincronizacao_ativa", False):
                                        sync_active = True
                                        
                                    if sync_active:
                                        win_sync.sincronizar_rolagem_global(self.parent(), self.nome_visao, delta_mm)
                    except Exception as e:
                        print(f"[Aviso] Erro capturado no scroll da fatia: {e}")
                    return True
                    
                elif event.type() == QEvent.Type.MouseButtonPress:
                    if hasattr(self, 'ferramenta_atual'):
                        if self.ferramenta_atual.on_mouse_press(event, self):
                            return True
                elif event.type() == QEvent.Type.MouseButtonDblClick:
                    # Impede que o duplo clique ative funções nativas do C++ do VTK 
                    # (como window/level nativo) que poderiam ficar com o mouse preso
                    return True
                    
                elif event.type() == QEvent.Type.MouseMove:
                    if hasattr(self, 'ferramenta_atual'):
                        if self.ferramenta_atual.on_mouse_move(event, self):
                            return True
                elif event.type() == QEvent.Type.MouseButtonRelease:
                    if hasattr(self, 'ferramenta_atual'):
                        if self.ferramenta_atual.on_mouse_release(event, self):
                            return True
                    # Consome releases perdidos se alguma flag ficou ativada
                    if getattr(self, 'arrastando_janelamento', False) or getattr(self, 'arrastando_zoom', False) or getattr(self, 'arrastando_pan', False):
                        self.arrastando_janelamento = self.arrastando_zoom = self.arrastando_pan = False
                        self.interactor.setCursor(Qt.CursorShape.ArrowCursor)
                        return True
        self.ferramenta_ativa = "Normal"
        from .ferramentas import (
            FerramentaNormal, FerramentaSemente, FerramentaSementeDSA,
            FerramentaRegua, FerramentaElipse, FerramentaCropBox,
            FerramentaCrosshair, FerramentaReslice, FerramentaBisturi
        )
        self.ferramentas = {
            'Normal': FerramentaNormal(),
            'Semente': FerramentaSemente(),
            'SementeDSA': FerramentaSementeDSA(),
            'Regua': FerramentaRegua(),
            'Elipse': FerramentaElipse(),
            'CropBox': FerramentaCropBox(),
            'Crosshair': FerramentaCrosshair(),
            'Reslice': FerramentaReslice(),
            'Bisturi': FerramentaBisturi()
        }
        self.ferramenta_atual = self.ferramentas['Normal']
                if event.type() == QEvent.Type.MouseButtonPress:
                    if hasattr(self, 'ferramenta_atual'):
                        if self.ferramenta_atual.on_mouse_press(event, self):
                            return True
                elif event.type() == QEvent.Type.MouseButtonDblClick:
                    # Impede que o duplo clique ative funções nativas do C++ do VTK
                    return True
                        
                elif event.type() == QEvent.Type.MouseMove:
                    if hasattr(self, 'ferramenta_atual'):
                        if self.ferramenta_atual.on_mouse_move(event, self):
                            return True
                elif event.type() == QEvent.Type.MouseButtonRelease:
                    if hasattr(self, 'ferramenta_atual'):
                        if self.ferramenta_atual.on_mouse_release(event, self):
                            return True
                    # Consome releases perdidos se alguma flag ficou ativada
                    if getattr(self, 'arrastando_janelamento', False) or getattr(self, 'arrastando_zoom', False) or getattr(self, 'arrastando_pan', False):
                        self.arrastando_janelamento = self.arrastando_zoom = self.arrastando_pan = False
                        self.interactor.setCursor(Qt.CursorShape.ArrowCursor)
                        return True
