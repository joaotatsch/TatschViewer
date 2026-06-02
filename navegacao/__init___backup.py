# -*- coding: utf-8 -*-
"""
Módulo de coordenação geral de navegação do usuário.
"""
from PyQt6.QtCore import QObject, QEvent, Qt
import vtk

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
        if obj == self.interactor:
            if event.type() == QEvent.Type.Wheel:
                delta = event.angleDelta().y()
                if delta != 0:
                    inc = 1 if delta > 0 else -1
                    if self.nome_visao in self.navegador_2d.planos:
                        plane = self.navegador_2d.planos[self.nome_visao]
                        spacing = self.navegador_2d.mappers[self.nome_visao].GetInput().GetSpacing()
                        normal = plane.GetNormal()
                        esp = abs(normal[0]*spacing[0]) + abs(normal[1]*spacing[1]) + abs(normal[2]*spacing[2])
                        deslocamento_mm = inc * esp
                        plane.Push(deslocamento_mm)
                        
                        # Se o MIP estiver ativo, atualiza as linhas projetadas
                        if hasattr(self.parent(), 'operador_projecao'):
                            cx = self.navegador_2d.planos["Sagital"].GetOrigin()[0]
                            cy = self.navegador_2d.planos["Coronal"].GetOrigin()[1]
                            cz = self.navegador_2d.planos["Axial"].GetOrigin()[2]
                            self.parent().operador_projecao.atualizar_linhas(cx, cy, cz, self.navegador_2d.planos)
                            
                        if hasattr(self.parent(), 'coordenador_medidas'):
                            self.parent().coordenador_medidas.verificar_visibilidade(self.nome_visao, plane.GetOrigin())
                            
                        # Atualiza apenas a janela e as linhas
                        self._renderizar_seguro()

                        # ── SYNC SCROLL ──────────────────────────────────────
                        # Propaga o deslocamento físico para as demais telas se
                        # o botão de sincronização estiver ativado na MainWindow.
                        try:
                            from PyQt6.QtWidgets import QApplication
                            app = QApplication.instance()
                            if app:
                                for widget in app.topLevelWidgets():
                                    if hasattr(widget, 'btn_sync_scroll') and hasattr(widget, 'sincronizar_scroll_global'):
                                        if widget.btn_sync_scroll.isChecked():
                                            widget.sincronizar_scroll_global(
                                                self.nome_visao,
                                                deslocamento_mm,
                                                self.parent()
                                            )
                                        break   # só há uma MainWindow
                        except Exception as _e_sync:
                            pass   # sync opcional — nunca trava o scroll nativo
                        # ─────────────────────────────────────────────────────

                return True
                
            elif event.type() == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    if self.ferramenta_ativa == "Semente":
                        dpr = self.interactor.devicePixelRatioF()
                        x_vtk = event.position().x() * dpr
                        y_vtk = (self.interactor.height() - event.position().y()) * dpr
                        renderer = self.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
                        if renderer:
                            self.picker.SetTolerance(0.0)
                            self.picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                            pos = self.picker.GetPickPosition()
                            
                            # Conversão matemática imaculada VTK -> Index (Voxel)
                            idx = [0.0, 0.0, 0.0]
                            self.navegador_2d.volume_ativo.TransformPhysicalPointToContinuousIndex(pos, idx)
                            ix, iy, iz = int(round(idx[0])), int(round(idx[1])), int(round(idx[2]))
                            
                            dims = self.navegador_2d.volume_ativo.GetDimensions()
                            if 0 <= ix < dims[0] and 0 <= iy < dims[1] and 0 <= iz < dims[2]:
                                # Desenha a esfera tática
                                sphere = vtk.vtkSphereSource()
                                sphere.SetCenter(pos)
                                sphere.SetRadius(3.0)
                                mapper = vtk.vtkPolyDataMapper()
                                mapper.SetInputConnection(sphere.GetOutputPort())
                                actor = vtk.vtkActor()
                                actor.SetMapper(mapper)
                                actor.GetProperty().SetColor(0.0, 1.0, 0.0)
                                renderer.AddActor(actor)
                                self.interactor.GetRenderWindow().Render()
                                
                                if hasattr(self.parent(), 'adicionar_semente'):
                                    self.parent().adicionar_semente([ix, iy, iz], actor) # Passamos o Index!
                        return True

                    if getattr(self, 'ferramenta_ativa', 'Normal') == "CropBox":
                        nav2d = self.navegador_2d
                        if hasattr(nav2d, 'crop_widgets') and self.nome_visao in nav2d.crop_widgets:
                            widget = nav2d.crop_widgets[self.nome_visao]
                            if widget.GetEnabled():
                                dpr = self.interactor.devicePixelRatioF()
                                x_vtk = event.position().x() * dpr
                                y_vtk = (self.interactor.height() - event.position().y()) * dpr
                                renderer = self.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
                                if renderer:
                                    self.picker.SetTolerance(0.0)
                                    self.picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                                    pos = self.picker.GetPickPosition()
                                    
                                    bounds = list(widget.GetRepresentation().GetBounds())
                                    tol = 6.0
                                    
                                    self.drag_crop_index = None
                                    if self.nome_visao == "Axial":
                                        if abs(pos[0] - bounds[0]) < tol: self.drag_crop_index = 0
                                        elif abs(pos[0] - bounds[1]) < tol: self.drag_crop_index = 1
                                        elif abs(pos[1] - bounds[2]) < tol: self.drag_crop_index = 2
                                        elif abs(pos[1] - bounds[3]) < tol: self.drag_crop_index = 3
                                    elif self.nome_visao == "Coronal":
                                        if abs(pos[0] - bounds[0]) < tol: self.drag_crop_index = 0
                                        elif abs(pos[0] - bounds[1]) < tol: self.drag_crop_index = 1
                                        elif abs(pos[2] - bounds[4]) < tol: self.drag_crop_index = 4
                                        elif abs(pos[2] - bounds[5]) < tol: self.drag_crop_index = 5
                                    elif self.nome_visao == "Sagital":
                                        if abs(pos[1] - bounds[2]) < tol: self.drag_crop_index = 2
                                        elif abs(pos[1] - bounds[3]) < tol: self.drag_crop_index = 3
                                        elif abs(pos[2] - bounds[4]) < tol: self.drag_crop_index = 4
                                        elif abs(pos[2] - bounds[5]) < tol: self.drag_crop_index = 5
                                        
                                    if self.drag_crop_index is not None:
                                        self.ultimo_pick_mundo = pos
                                        
                        self.arrastando_janelamento = False
                        return True # Engole o clique garantindo exclusividade
                        
                    if self.ferramenta_ativa in ["Regua", "Elipse", "SementeDSA"]:
                        dpr = self.interactor.devicePixelRatioF()
                        x_vtk, y_vtk = event.position().x() * dpr, (self.interactor.height() - event.position().y()) * dpr
                        picker = vtk.vtkCellPicker()
                        picker.SetTolerance(0.005)
                        renderer = self.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
                        
                        if renderer:
                            picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                            pos_world = picker.GetPickPosition()
                            
                            origem_plano = self.navegador_2d.planos[self.nome_visao].GetOrigin()
                            
                            # --- LÓGICA DA SEMENTE DSA AQUI ---
                            if self.ferramenta_ativa == "SementeDSA":
                                main_window = self.parent().parent() if hasattr(self.parent(), 'parent') else None
                                
                                # Usa o volume_ativo diretamente do navegador_2d que já está neste escopo
                                vtk_img = self.navegador_2d.volume_ativo
                                
                                if main_window and vtk_img:
                                    try:
                                        # Converte a coordenada 3D física diretamente para o Índice Voxel da Matriz
                                        idx = [0.0, 0.0, 0.0]
                                        vtk_img.TransformPhysicalPointToContinuousIndex(pos_world, idx)
                                        
                                        # Arredonda para inteiros exatos da grade
                                        index_itk = (int(round(idx[0])), int(round(idx[1])), int(round(idx[2])))
                                        
                                        print(f"\n[SENSOR CORRIGIDO] Coordenada de Mundo (VTK): {pos_world}")
                                        print(f"[SENSOR CORRIGIDO] Índice Voxel (Matriz): {index_itk}")
                                        
                                        # Dispara a Thread na MainWindow
                                        main_window.iniciar_subtracao_semente(index_itk)
                                    except Exception as e:
                                        main_window.statusBar().showMessage(f"Erro ao converter semente: {str(e)}")

                                # Desativa a ferramenta e volta o cursor ao normal
                                self.ferramenta_ativa = "Normal"
                                self.interactor.setCursor(Qt.CursorShape.ArrowCursor)
                                return True
                            # -----------------------------------
                            
                            self.arrastando_regua = True
                            medidas_coord = self.parent().coordenador_medidas
                            if self.ferramenta_ativa == "Regua":
                                medidas_coord.iniciar_regua(renderer, pos_world, self.nome_visao, origem_plano)
                            elif self.ferramenta_ativa == "Elipse":
                                medidas_coord.iniciar_elipse(renderer, pos_world, self.nome_visao, origem_plano, self.navegador_2d.volume_ativo)
                            return True
                        
                    elif self.modo_crosshair:
                        self.arrastando_crosshair = True
                        
                        # Fator de escala do monitor (ex: 1.25 para 125% no Windows)
                        dpr = self.interactor.devicePixelRatioF()
                        
                        # Coordenadas físicas exatas para o VTK
                        x_vtk = event.position().x() * dpr
                        # Inversão do Y considerando a altura lógica multiplicada pelo DPR
                        y_vtk = (self.interactor.height() - event.position().y()) * dpr
                        
                        renderer = self.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
                        if renderer:
                            self.picker.SetTolerance(0.0)
                            self.picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                            pos = self.picker.GetPickPosition()
                            
                            if hasattr(self.parent(), 'operador_crosshair') and self.parent().operador_crosshair:
                                planos = self.navegador_2d.planos
                                self.parent().operador_crosshair.atualizar_posicao(pos, planos)
                                if hasattr(self.parent(), 'operador_projecao') and self.parent().operador_projecao:
                                    self.parent().operador_projecao.atualizar_linhas(pos[0], pos[1], pos[2], self.navegador_2d.planos)
                                self._renderizar_seguro()
                        return True
                        
                    # Hit test de Reslice (antes do MIP normal)
                    if self.ferramenta_ativa == "Reslice":
                        dpr = self.interactor.devicePixelRatioF()
                        x_vtk = event.position().x() * dpr
                        y_vtk = (self.interactor.height() - event.position().y()) * dpr
                        renderer = self.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
                        if renderer:
                            self.picker.SetTolerance(0.0)
                            self.picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                            pos = self.picker.GetPickPosition()
                            self.alvo_reslice = self.operador_interacao_reslice.hit_test(self.nome_visao, pos)
                            if self.alvo_reslice is not None:
                                cell_picker = vtk.vtkCellPicker()
                                cell_picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                                self.ultima_posicao_medida = cell_picker.GetPickPosition()
                                return True
                        # Clique no vazio em modo Reslice → janelamento normal
                        self.ultimo_pos_x = event.position().x()
                        self.ultimo_pos_y = event.position().y()
                        self.arrastando_janelamento = True
                        return True

                    # Lógica de arrasto de linhas (Navegação Interativa)
                    # Primeiro: tenta selecionar medidas existentes (modo Normal)
                    if self.ferramenta_ativa == "Normal" and hasattr(self.parent(), 'coordenador_medidas') and self.parent().coordenador_medidas.medidas:
                        dpr = self.interactor.devicePixelRatioF()
                        x_vtk = event.position().x() * dpr
                        y_vtk = (self.interactor.height() - event.position().y()) * dpr
                        renderer = self.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
                        if renderer:
                            prop_picker = vtk.vtkPropPicker()
                            prop_picker.PickProp(x_vtk, y_vtk, renderer)
                            prop_hit = prop_picker.GetViewProp()
                            medida_acertada = None
                            for med in self.parent().coordenador_medidas.medidas:
                                if prop_hit is med.actor or prop_hit is med.text_actor:
                                    medida_acertada = med
                                    break
                            if medida_acertada:
                                # Deselecionar anterior
                                if self.medida_selecionada and self.medida_selecionada is not medida_acertada:
                                    self.medida_selecionada.selecionar(False)
                                self.medida_selecionada = medida_acertada
                                medida_acertada.selecionar(True)
                                self.interactor.setCursor(Qt.CursorShape.ClosedHandCursor)
                                # Captura segura da posição de mundo para calcular deltas
                                cell_picker = vtk.vtkCellPicker()
                                cell_picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                                self.ultima_posicao_medida = cell_picker.GetPickPosition()
                                self.arrastando_medida = True
                                self.interactor.GetRenderWindow().Render()
                                return True
                            else:
                                # Clicou no vazio - deseleciona
                                if self.medida_selecionada:
                                    self.medida_selecionada.selecionar(False)
                                    self.medida_selecionada = None
                                    self.interactor.GetRenderWindow().Render()

                    dpr = self.interactor.devicePixelRatioF()
                    x_vtk = event.position().x() * dpr
                    y_vtk = (self.interactor.height() - event.position().y()) * dpr
                    renderer = self.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
                    if renderer:
                        self.picker.SetTolerance(0.0)
                        self.picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                        pos = self.picker.GetPickPosition()
                        
                        self.alvo_arraste = self._hit_test(pos)
                        if self.alvo_arraste:
                            self.interactor.setCursor(Qt.CursorShape.ClosedHandCursor)
                            return True
                    
                    self.ultimo_pos_x = event.position().x()
                    self.ultimo_pos_y = event.position().y()
                    if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                        self.arrastando_rotacao = True
                        return True  # Consome para rotação 2D
                    else:
                        self.arrastando_janelamento = True
                        return True  # Consome para janelamento manual
                # Deixa cliques normais fluírem para a engine do VTK
                return False
                
            elif event.type() == QEvent.Type.MouseMove:
                if self.ferramenta_ativa == "Semente":
                    self.interactor.setCursor(Qt.CursorShape.CrossCursor)
                    return True

                if getattr(self, 'ferramenta_ativa', 'Normal') == "CropBox":
                    nav2d = self.navegador_2d
                    if hasattr(nav2d, 'crop_widgets') and self.nome_visao in nav2d.crop_widgets:
                        widget = nav2d.crop_widgets[self.nome_visao]
                        
                        if getattr(self, 'drag_crop_index', None) is not None:
                            dpr = self.interactor.devicePixelRatioF()
                            x_vtk = event.position().x() * dpr
                            y_vtk = (self.interactor.height() - event.position().y()) * dpr
                            renderer = self.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
                            if renderer:
                                self.picker.SetTolerance(0.0)
                                self.picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                                pos = self.picker.GetPickPosition()
                                
                                dx = pos[0] - self.ultimo_pick_mundo[0]
                                dy = pos[1] - self.ultimo_pick_mundo[1]
                                dz = pos[2] - self.ultimo_pick_mundo[2]
                                
                                rep = widget.GetRepresentation()
                                bounds = list(rep.GetBounds())
                                
                                idx = self.drag_crop_index
                                if idx in [0, 1]: bounds[idx] += dx
                                elif idx in [2, 3]: bounds[idx] += dy
                                elif idx in [4, 5]: bounds[idx] += dz
                                
                                if bounds[1] - bounds[0] < 5.0: bounds[idx] -= dx
                                elif bounds[3] - bounds[2] < 5.0: bounds[idx] -= dy
                                elif bounds[5] - bounds[4] < 5.0: bounds[idx] -= dz
                                else:
                                    rep.PlaceWidget(bounds)
                                    self.ultimo_pick_mundo = pos
                                    self._renderizar_seguro()
                            return True
                            
                        elif event.buttons() == Qt.MouseButton.NoButton:
                            if widget.GetEnabled():
                                dpr = self.interactor.devicePixelRatioF()
                                x_vtk = event.position().x() * dpr
                                y_vtk = (self.interactor.height() - event.position().y()) * dpr
                                renderer = self.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
                                if renderer:
                                    self.picker.SetTolerance(0.0)
                                    self.picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                                    pos = self.picker.GetPickPosition()
                                    
                                    bounds = widget.GetRepresentation().GetBounds()
                                    tol = 6.0
                                    cursor = Qt.CursorShape.ArrowCursor
                                    
                                    if self.nome_visao == "Axial":
                                        on_x = abs(pos[0] - bounds[0]) < tol or abs(pos[0] - bounds[1]) < tol
                                        on_y = abs(pos[1] - bounds[2]) < tol or abs(pos[1] - bounds[3]) < tol
                                        if on_x and on_y: cursor = Qt.CursorShape.SizeAllCursor
                                        elif on_x: cursor = Qt.CursorShape.SizeHorCursor
                                        elif on_y: cursor = Qt.CursorShape.SizeVerCursor
                                    elif self.nome_visao == "Coronal":
                                        on_x = abs(pos[0] - bounds[0]) < tol or abs(pos[0] - bounds[1]) < tol
                                        on_z = abs(pos[2] - bounds[4]) < tol or abs(pos[2] - bounds[5]) < tol
                                        if on_x and on_z: cursor = Qt.CursorShape.SizeAllCursor
                                        elif on_x: cursor = Qt.CursorShape.SizeHorCursor
                                        elif on_z: cursor = Qt.CursorShape.SizeVerCursor
                                    elif self.nome_visao == "Sagital":
                                        on_y = abs(pos[1] - bounds[2]) < tol or abs(pos[1] - bounds[3]) < tol
                                        on_z = abs(pos[2] - bounds[4]) < tol or abs(pos[2] - bounds[5]) < tol
                                        if on_y and on_z: cursor = Qt.CursorShape.SizeAllCursor
                                        elif on_y: cursor = Qt.CursorShape.SizeHorCursor
                                        elif on_z: cursor = Qt.CursorShape.SizeVerCursor
                                    
                                    self.interactor.setCursor(cursor)
                    return False
                    
                if event.buttons() == Qt.MouseButton.NoButton:
                    if self.ferramenta_ativa in ["Regua", "Elipse", "SementeDSA"]:
                        self.interactor.setCursor(Qt.CursorShape.CrossCursor)
                        return False
                    
                    if self.ferramenta_ativa == "Reslice":
                        dpr = self.interactor.devicePixelRatioF()
                        x_vtk = event.position().x() * dpr
                        y_vtk = (self.interactor.height() - event.position().y()) * dpr
                        renderer = self.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
                        if renderer:
                            self.picker.SetTolerance(0.0)
                            self.picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                            pos = self.picker.GetPickPosition()
                            alvo = self.operador_interacao_reslice.hit_test(self.nome_visao, pos)
                            if alvo == "Centro":
                                self.interactor.setCursor(Qt.CursorShape.SizeAllCursor)
                            elif alvo is not None:
                                self.interactor.setCursor(Qt.CursorShape.PointingHandCursor)
                            else:
                                self.interactor.setCursor(Qt.CursorShape.ArrowCursor)
                        return True
                        
                    # Hover sobre medidas existentes (ferramenta Normal)
                    renderer = self.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
                    if renderer and hasattr(self.parent(), 'coordenador_medidas') and self.parent().coordenador_medidas.medidas:
                        dpr = self.interactor.devicePixelRatioF()
                        x_vtk = event.position().x() * dpr
                        y_vtk = (self.interactor.height() - event.position().y()) * dpr
                        prop_picker = vtk.vtkPropPicker()
                        prop_picker.PickProp(x_vtk, y_vtk, renderer)
                        prop_hit = prop_picker.GetViewProp()
                        for med in self.parent().coordenador_medidas.medidas:
                            if prop_hit is med.actor or prop_hit is med.text_actor:
                                self.interactor.setCursor(Qt.CursorShape.OpenHandCursor)
                                return False
                        
                    dpr = self.interactor.devicePixelRatioF()
                    x_vtk = event.position().x() * dpr
                    y_vtk = (self.interactor.height() - event.position().y()) * dpr
                    renderer = self.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
                    if renderer:
                        self.picker.SetTolerance(0.0)
                        self.picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                        pos = self.picker.GetPickPosition()
                        
                        alvo = self._hit_test(pos)
                        if alvo == "Centro":
                            self.interactor.setCursor(Qt.CursorShape.SizeAllCursor)
                        elif alvo in ["Sagital", "Coronal", "Axial"]:
                            self.interactor.setCursor(Qt.CursorShape.OpenHandCursor)
                        elif alvo and alvo.startswith("Espessura_"):
                            v_alvo = alvo.split("_")[1]
                            if v_alvo == "Sagital" or (v_alvo == "Coronal" and self.nome_visao == "Sagital"):
                                self.interactor.setCursor(Qt.CursorShape.SizeHorCursor)
                            else:
                                self.interactor.setCursor(Qt.CursorShape.SizeVerCursor)
                        else:
                            self.interactor.setCursor(Qt.CursorShape.ArrowCursor)

                elif self.alvo_arraste and event.buttons() & Qt.MouseButton.LeftButton:
                    dpr = self.interactor.devicePixelRatioF()
                    x_vtk = event.position().x() * dpr
                    y_vtk = (self.interactor.height() - event.position().y()) * dpr
                    renderer = self.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
                    if renderer:
                        self.picker.SetTolerance(0.0)
                        self.picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                        pos = self.picker.GetPickPosition()
                        
                        cx = self.navegador_2d.planos["Sagital"].GetOrigin()[0]
                        cy = self.navegador_2d.planos["Coronal"].GetOrigin()[1]
                        cz = self.navegador_2d.planos["Axial"].GetOrigin()[2]
                        centros = {"Sagital": cx, "Coronal": cy, "Axial": cz}
                        idx_map = {"Sagital": 0, "Coronal": 1, "Axial": 2}
                        
                        if self.alvo_arraste.startswith("Espessura_"):
                            v_alvo = self.alvo_arraste.split("_")[1]
                            proj = self.parent().operador_projecao
                            if proj:
                                nova_esp = abs(pos[idx_map[v_alvo]] - centros[v_alvo]) * 2.0
                                proj.aplicar_projecao_individual(v_alvo, proj.modos[v_alvo], nova_esp)
                                if self.espessura_callback:
                                    self.espessura_callback(nova_esp)
                                self._renderizar_seguro()
                        elif self.alvo_arraste == "Centro":
                            visoes_cruzadas = []
                            if self.nome_visao == "Axial": visoes_cruzadas = ["Sagital", "Coronal"]
                            elif self.nome_visao == "Coronal": visoes_cruzadas = ["Sagital", "Axial"]
                            elif self.nome_visao == "Sagital": visoes_cruzadas = ["Coronal", "Axial"]
                            
                            v1, v2 = visoes_cruzadas[0], visoes_cruzadas[1]
                            plano1 = self.navegador_2d.planos[v1]
                            plano2 = self.navegador_2d.planos[v2]
                            origem1 = list(plano1.GetOrigin())
                            origem2 = list(plano2.GetOrigin())
                            
                            i1 = idx_map[v1]
                            i2 = idx_map[v2]
                            origem1[i1] = pos[i1]
                            origem2[i2] = pos[i2]
                            
                            plano1.SetOrigin(origem1)
                            plano2.SetOrigin(origem2)
                            
                            nx = self.navegador_2d.planos["Sagital"].GetOrigin()[0]
                            ny = self.navegador_2d.planos["Coronal"].GetOrigin()[1]
                            nz = self.navegador_2d.planos["Axial"].GetOrigin()[2]
                            if hasattr(self.parent(), 'operador_projecao') and self.parent().operador_projecao:
                                self.parent().operador_projecao.atualizar_linhas(nx, ny, nz, self.navegador_2d.planos)
                            
                            self._renderizar_seguro()
                        elif self.alvo_arraste in ["Axial", "Coronal", "Sagital"]:
                            plano_alvo = self.navegador_2d.planos[self.alvo_arraste]
                            nova_origem = list(plano_alvo.GetOrigin())
                            i_alvo = idx_map[self.alvo_arraste]
                            nova_origem[i_alvo] = pos[i_alvo]
                            plano_alvo.SetOrigin(nova_origem)
                            
                            nx = self.navegador_2d.planos["Sagital"].GetOrigin()[0]
                            ny = self.navegador_2d.planos["Coronal"].GetOrigin()[1]
                            nz = self.navegador_2d.planos["Axial"].GetOrigin()[2]
                            if hasattr(self.parent(), 'operador_projecao') and self.parent().operador_projecao:
                                self.parent().operador_projecao.atualizar_linhas(nx, ny, nz, self.navegador_2d.planos)
                            
                            self._renderizar_seguro()
                    return True
                elif self.alvo_reslice and event.buttons() & Qt.MouseButton.LeftButton:
                    dpr = self.interactor.devicePixelRatioF()
                    x_vtk, y_vtk = event.position().x() * dpr, (self.interactor.height() - event.position().y()) * dpr
                    renderer = self.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
                    if renderer and self.ultima_posicao_medida:
                        cell_picker = vtk.vtkCellPicker()
                        cell_picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                        pos = cell_picker.GetPickPosition()
                        
                        if self.alvo_reslice == "Centro":
                            for visao, plane in self.navegador_2d.planos.items():
                                plane.SetOrigin(pos[0], pos[1], pos[2])
                            self.ultima_posicao_medida = pos
                            if hasattr(self.parent(), 'operador_projecao'):
                                self.parent().operador_projecao.atualizar_linhas(pos[0], pos[1], pos[2], self.navegador_2d.planos)
                        else:
                            self.operador_interacao_reslice.rotacionar(self.nome_visao, self.alvo_reslice, self.ultima_posicao_medida, pos)
                            self.ultima_posicao_medida = pos
                            
                            cx = self.navegador_2d.planos["Sagital"].GetOrigin()[0]
                            cy = self.navegador_2d.planos["Coronal"].GetOrigin()[1]
                            cz = self.navegador_2d.planos["Axial"].GetOrigin()[2]
                            if hasattr(self.parent(), 'operador_projecao'):
                                self.parent().operador_projecao.atualizar_linhas(cx, cy, cz, self.navegador_2d.planos)
                                
                        self._renderizar_seguro()
                    return True
                elif self.arrastando_regua:
                    dpr = self.interactor.devicePixelRatioF()
                    x_vtk, y_vtk = event.position().x() * dpr, (self.interactor.height() - event.position().y()) * dpr
                    picker = vtk.vtkCellPicker()
                    picker.Pick(x_vtk, y_vtk, 0.0, self.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer())
                    self.parent().coordenador_medidas.atualizar_regua(picker.GetPickPosition())
                    self.interactor.GetRenderWindow().Render()
                    return True
                elif self.arrastando_medida and self.medida_selecionada and self.ultima_posicao_medida and event.buttons() & Qt.MouseButton.LeftButton:
                    dpr = self.interactor.devicePixelRatioF()
                    x_vtk, y_vtk = event.position().x() * dpr, (self.interactor.height() - event.position().y()) * dpr
                    renderer = self.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
                    if renderer:
                        cell_picker = vtk.vtkCellPicker()
                        cell_picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                        pos = cell_picker.GetPickPosition()
                        dx = pos[0] - self.ultima_posicao_medida[0]
                        dy = pos[1] - self.ultima_posicao_medida[1]
                        dz = pos[2] - self.ultima_posicao_medida[2]
                        
                        if dx != 0 or dy != 0 or dz != 0:
                            self.medida_selecionada.mover(dx, dy, dz)
                            self.ultima_posicao_medida = pos
                            self.interactor.GetRenderWindow().Render()
                    return True
                elif self.arrastando_crosshair and event.buttons() & Qt.MouseButton.LeftButton:
                    # Fator de escala do monitor (ex: 1.25 para 125% no Windows)
                    dpr = self.interactor.devicePixelRatioF()
                    
                    # Coordenadas físicas exatas para o VTK
                    x_vtk = event.position().x() * dpr
                    # Inversão do Y considerando a altura lógica multiplicada pelo DPR
                    y_vtk = (self.interactor.height() - event.position().y()) * dpr
                    
                    renderer = self.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
                    if renderer:
                        self.picker.SetTolerance(0.0)
                        self.picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                        pos = self.picker.GetPickPosition()
                        
                        if hasattr(self.parent(), 'operador_crosshair') and self.parent().operador_crosshair:
                            planos = self.navegador_2d.planos
                            self.parent().operador_crosshair.atualizar_posicao(pos, planos)
                            if hasattr(self.parent(), 'operador_projecao') and self.parent().operador_projecao:
                                self.parent().operador_projecao.atualizar_linhas(pos[0], pos[1], pos[2], self.navegador_2d.planos)
                            self._renderizar_seguro()
                    return True
                elif self.arrastando_rotacao and event.buttons() & Qt.MouseButton.LeftButton:
                    dx = event.position().x() - self.ultimo_pos_x
                    self.ultimo_pos_x = event.position().x()
                    
                    renderer = self.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
                    if renderer:
                        camera = renderer.GetActiveCamera()
                        if camera:
                            camera.Roll(dx * 0.5)
                            # Atualiza a bússola anatômica após a rotação
                            self.navegador_2d.atualizar_bussola()
                            self.interactor.GetRenderWindow().Render()
                    return True
                    
                elif self.arrastando_janelamento and event.buttons() & Qt.MouseButton.LeftButton:
                    dx = event.position().x() - self.ultimo_pos_x
                    dy = event.position().y() - self.ultimo_pos_y
                    self.ultimo_pos_x = event.position().x()
                    self.ultimo_pos_y = event.position().y()
                    
                    ator = self.navegador_2d.atores.get(self.nome_visao)
                    if ator:
                        ww_atual = ator.GetProperty().GetColorWindow()
                        wl_atual = ator.GetProperty().GetColorLevel()
                        
                        sensibilidade = 2.0
                        novo_ww = max(1.0, ww_atual + dx * sensibilidade)
                        novo_wl = wl_atual - dy * sensibilidade
                        
                        self.navegador_2d.atualizar_janelamento(self.nome_visao, novo_ww, novo_wl)
                        self.interactor.GetRenderWindow().Render()
                        
                        if self.janelamento_callback:
                            self.janelamento_callback(novo_ww, novo_wl)
                    return True
                return False
                
            elif event.type() == QEvent.Type.MouseButtonRelease:
                if event.button() == Qt.MouseButton.LeftButton:
                    if getattr(self, 'ferramenta_ativa', 'Normal') == "CropBox":
                        if getattr(self, 'drag_crop_index', None) is not None:
                            self.drag_crop_index = None
                            self.ultimo_pick_mundo = None
                            
                            self._renderizar_seguro()
                            return True
                        return False
                        
                    if getattr(self, 'arrastando_regua', False):
                        if hasattr(self.parent(), 'coordenador_medidas'):
                            self.parent().coordenador_medidas.finalizar_regua()
                        self.arrastando_regua = False
                        return True
                    
                    if getattr(self, 'arrastando_medida', False):
                        self.arrastando_medida = False
                        self.ultima_posicao_medida = None
                        self.interactor.setCursor(Qt.CursorShape.OpenHandCursor)
                        return True
                        
                    self.arrastando_janelamento = False
                    self.arrastando_crosshair = False
                    self.arrastando_rotacao = False
                    self.alvo_reslice = None
                    if self.alvo_arraste:
                        self.alvo_arraste = None
                        self.interactor.setCursor(Qt.CursorShape.ArrowCursor)
                    return True
                return False
                
            elif event.type() == QEvent.Type.KeyPress:
                # Pega a tecla 'C' (ignorando a repetição automática do teclado)
                if event.key() == Qt.Key.Key_C and not event.isAutoRepeat():
                    self.modo_crosshair = True
                    if hasattr(self.parent(), 'operador_crosshair'):
                        self.parent().operador_crosshair.ator.SetVisibility(True)
                        for n, f in self.parent().filtros_eventos.items():
                            f.interactor.GetRenderWindow().Render()
                    return True
                    
                if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                    if self.medida_selecionada and hasattr(self.parent(), 'coordenador_medidas'):
                        self.parent().coordenador_medidas.remover_medida(self.medida_selecionada)
                        self.medida_selecionada = None
                        self.arrastando_medida = False
                        self.ultima_posicao_medida = None
                        self.interactor.GetRenderWindow().Render()
                        return True

            elif event.type() == QEvent.Type.KeyRelease:
                if event.key() == Qt.Key.Key_C and not event.isAutoRepeat():
                    self.modo_crosshair = False
                    if hasattr(self.parent(), 'operador_crosshair'):
                        self.parent().operador_crosshair.ator.SetVisibility(False)
                        for n, f in self.parent().filtros_eventos.items():
                            f.interactor.GetRenderWindow().Render()
                    return True
                
        return super().eventFilter(obj, event)


class FiltroEventosDicom3D(QObject):
    """
    Filtro de eventos PyQt6 para a visualização 3D.
    Intercepta Shift + Clique Esquerdo para ajustar o janelamento 3D,
    deixando rotação nativa (Left Click comum), Pan (Middle) e Zoom (Right) fluírem.
    """
    def __init__(self, navegador_3d: Navegador3D, interactor, janelamento_callback=None, parent=None):
        super().__init__(parent)
        self.navegador_3d = navegador_3d
        self.interactor = interactor
        self.janelamento_callback = janelamento_callback
        
        self.picker = vtk.vtkPointPicker()
        self.picker.PickFromListOn()
        self.ultimo_pos_x = 0
        self.ultimo_pos_y = 0
        self.arrastando_janelamento = False
        
        self.ferramenta_ativa = "Normal"
        self.bisturi_pontos = []
        self.bisturi_poly = vtk.vtkPolyData()
        mapper2d = vtk.vtkPolyDataMapper2D()
        mapper2d.SetInputData(self.bisturi_poly)
        
        coord = vtk.vtkCoordinate()
        coord.SetCoordinateSystemToDisplay()
        mapper2d.SetTransformCoordinate(coord)
        
        self.bisturi_actor = vtk.vtkActor2D()
        self.bisturi_actor.SetMapper(mapper2d)
        self.bisturi_actor.GetProperty().SetColor(1.0, 1.0, 0.0) # Amarelo
        self.bisturi_actor.GetProperty().SetLineWidth(2.0)

    def eventFilter(self, obj, event):
        if obj == self.interactor:
            if event.type() == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    if getattr(self, 'ferramenta_ativa', 'Normal') == "Bisturi":
                        self.arrastando_bisturi = True
                        dpr = self.interactor.devicePixelRatioF()
                        x_vtk = event.position().x() * dpr
                        y_vtk = (self.interactor.height() - event.position().y()) * dpr
                        
                        # Inicia a lista com o primeiro ponto do clique
                        self.bisturi_pontos = [(x_vtk, y_vtk)]
                        
                        renderer = self.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
                        if renderer and not renderer.HasViewProp(self.bisturi_actor):
                            renderer.AddActor(self.bisturi_actor)
                        return True
                        
                    if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                        self.arrastando_janelamento = True
                        self.ultimo_pos_x = event.position().x()
                        self.ultimo_pos_y = event.position().y()
                        return True  # Consome para evitar rotação nativa
                    
            elif event.type() == QEvent.Type.MouseMove:
                if getattr(self, 'arrastando_bisturi', False) and event.buttons() & Qt.MouseButton.LeftButton:
                    dpr = self.interactor.devicePixelRatioF()
                    x_vtk = event.position().x() * dpr
                    y_vtk = (self.interactor.height() - event.position().y()) * dpr
                    self.bisturi_pontos.append((x_vtk, y_vtk))
                    
                    # Recria o vtkPolyLine completo para evitar bugs de estado do CellArray
                    pts = vtk.vtkPoints()
                    polyLine = vtk.vtkPolyLine()
                    polyLine.GetPointIds().SetNumberOfIds(len(self.bisturi_pontos))
                    
                    for i, p in enumerate(self.bisturi_pontos):
                        pts.InsertNextPoint(p[0], p[1], 0.0)
                        polyLine.GetPointIds().SetId(i, i)
                        
                    cells = vtk.vtkCellArray()
                    cells.InsertNextCell(polyLine)
                    
                    self.bisturi_poly.SetPoints(pts)
                    self.bisturi_poly.SetLines(cells)
                    self.interactor.GetRenderWindow().Render()
                    return True
                    
                if self.arrastando_janelamento and event.buttons() & Qt.MouseButton.LeftButton:
                    dx = event.position().x() - self.ultimo_pos_x
                    dy = event.position().y() - self.ultimo_pos_y
                    
                    self.ultimo_pos_x = event.position().x()
                    self.ultimo_pos_y = event.position().y()
                    
                    ww_atual = self.navegador_3d.ww_3d
                    wl_atual = self.navegador_3d.wl_3d
                    
                    sensibilidade = 2.0
                    novo_ww = max(10.0, ww_atual + dx * sensibilidade)
                    novo_wl = wl_atual - dy * sensibilidade
                    
                    self.navegador_3d.atualizar_transfer_functions(novo_ww, novo_wl)
                    
                    if self.janelamento_callback:
                        self.janelamento_callback(novo_ww, novo_wl)
                        
                    return True
                    
            elif event.type() == QEvent.Type.MouseButtonRelease:
                if event.button() == Qt.MouseButton.LeftButton:
                    if getattr(self, 'arrastando_bisturi', False):
                        self.arrastando_bisturi = False
                        
                        if len(self.bisturi_pontos) > 2:
                            # Repete o primeiro ponto no final para fechar o laço visualmente
                            self.bisturi_pontos.append(self.bisturi_pontos[0])
                            
                            pts = vtk.vtkPoints()
                            polyLine = vtk.vtkPolyLine()
                            polyLine.GetPointIds().SetNumberOfIds(len(self.bisturi_pontos))
                            
                            for i, p in enumerate(self.bisturi_pontos):
                                pts.InsertNextPoint(p[0], p[1], 0.0)
                                polyLine.GetPointIds().SetId(i, i)
                                
                            cells = vtk.vtkCellArray()
                            cells.InsertNextCell(polyLine)
                            
                            self.bisturi_poly.SetPoints(pts)
                            self.bisturi_poly.SetLines(cells)
                            self.interactor.GetRenderWindow().Render()
                            
                        # Armazena os dados no coordenador pai para que os botões do menu possam acessá-los
                        if hasattr(self.parent(), 'coordenador_navegacao'):
                            self.parent().pontos_bisturi = self.bisturi_pontos
                            self.parent().renderer_bisturi = self.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
                            self.parent().pontos_corte = self.bisturi_pontos
                            self.parent().renderer_corte = self.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
                        elif self.parent():
                            self.parent().pontos_corte = self.bisturi_pontos
                            self.parent().renderer_corte = self.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
                            
                        return True
                        
                    if self.arrastando_janelamento:
                        self.arrastando_janelamento = False
                        return True
                        
        return super().eventFilter(obj, event)

class CoordenadorNavegacao(QObject):
    """
    Coordenará as interações globais de navegação, mapeando os inputs de teclado/mouse
    para direcionar as atualizações nos modos 2D (MPR) e 3D do visualizador.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        # Conecta as classes de navegação subalternas
        self.navegador_2d = Navegador2D()
        self.navegador_3d = Navegador3D()
        self.filtros_eventos = {}
        self.lista_sementes = []
        self.atores_sementes = []

        
        from medidas import CoordenadorMedidas
        self.coordenador_medidas = CoordenadorMedidas()
        
        from manipulacao_da_imagem.reslice import OperadorInteracaoReslice
        self.operador_interacao_reslice = OperadorInteracaoReslice(self.navegador_2d)

    def inicializar_visualizacao(self, vtk_image: vtk.vtkImageData, quadrantes_interactors: dict, janelamento_callback=None, espessura_callback=None):
        """
        Distribui o volume para os quadrantes corretos, adiciona os atores
        aos renderizadores e atualiza as janelas de exibição imediatamente.
        """
        # 1. Filtra os renderizadores 2D para o Navegador2D
        renderers_2d = {
            "Axial": quadrantes_interactors["Axial"].renderer,
            "Sagital": quadrantes_interactors["Sagital"].renderer,
            "Coronal": quadrantes_interactors["Coronal"].renderer
        }
        self.navegador_2d.configurar_mpr(vtk_image, renderers_2d)
        
        # 2. Direciona o renderizador 3D para o Navegador3D
        renderer_3d = quadrantes_interactors["3D"].renderer
        self.navegador_3d.configurar_3d(vtk_image, renderer_3d)
        
        # 3. Instala o filtro de eventos de mouse nos interactors
        self.filtros_eventos = {}
        for nome in ["Axial", "Sagital", "Coronal"]:
            if nome in quadrantes_interactors:
                quadrante = quadrantes_interactors[nome]
                filtro = FiltroEventosDicom(nome, self.navegador_2d, quadrante.interactor, self.operador_interacao_reslice, janelamento_callback, espessura_callback, parent=self)
                quadrante.interactor.installEventFilter(filtro)
                self.filtros_eventos[nome] = filtro
                
                # Inicializa o cubo direcional agora que o interactor tem contexto físico
                self.navegador_2d.inicializar_orientadores(quadrante.interactor, nome)
                
        if "3D" in quadrantes_interactors:
            quadrante_3d = quadrantes_interactors["3D"]
            
            # Instala o estilo TrackballCamera nativo para a visão 3D
            style_3d = vtk.vtkInteractorStyleTrackballCamera()
            quadrante_3d.interactor.SetInteractorStyle(style_3d)
            
            filtro_3d = FiltroEventosDicom3D(self.navegador_3d, quadrante_3d.interactor, janelamento_callback, parent=self)
            quadrante_3d.interactor.installEventFilter(filtro_3d)
            self.filtros_eventos["3D"] = filtro_3d
            
            # Inicializa o cubo direcional 3D
            self.navegador_3d.inicializar_orientadores(quadrante_3d.interactor)
            
        # 4. Inicializa o Operador de MIP e o Crosshair
        from manipulacao_da_imagem.mip import OperadorProjecao
        from manipulacao_da_imagem.crosshair import OperadorCrosshair
        
        self.operador_projecao = OperadorProjecao(self.navegador_2d.mappers, renderers_2d, vtk_image.GetBounds())
        cx, cy, cz = vtk_image.GetCenter()
        self.operador_projecao.atualizar_linhas(cx, cy, cz, self.navegador_2d.planos)
        
        todos_renderers = {}
        for nome, quad in quadrantes_interactors.items():
            todos_renderers[nome] = quad.renderer
            
        self.operador_crosshair = OperadorCrosshair()
        self.operador_crosshair.inicializar(todos_renderers)
        
        # 5. Força a atualização imediata das janelas de renderização do VTK
        for nome, quadrante in quadrantes_interactors.items():
            quadrante.interactor.GetRenderWindow().Render()

    def alternar_modo_navegacao(self, modo: str):
        """
        Alterna as ferramentas e interações do usuário de acordo com o modo ativo.
        """
        pass

    def inicializar_tela_dinamica(self, nome_visao, vtk_image, quadrante, janelamento_cb, espessura_cb):
        self.navegador_2d.adicionar_visao_independente(nome_visao, vtk_image, quadrante.renderer)
        filtro = FiltroEventosDicom(nome_visao, self.navegador_2d, quadrante.interactor, self.operador_interacao_reslice, janelamento_cb, espessura_cb, parent=self)
        quadrante.interactor.installEventFilter(filtro)
        self.filtros_eventos[nome_visao] = filtro
        
        self.navegador_2d.inicializar_orientadores(quadrante.interactor, nome_visao)
        quadrante.interactor.GetRenderWindow().Render()

    def aplicar_bisturi(self, cortar_fora=False):
        """Coleta os pontos, repassa ao OperadorBisturi e atualiza mappers."""
        if not hasattr(self, 'pontos_corte') or len(self.pontos_corte) < 3:
            return
            
        if not hasattr(self, 'volume_original_bisturi'):
            import vtk
            self.volume_original_bisturi = vtk.vtkImageData()
            self.volume_original_bisturi.DeepCopy(self.navegador_3d.volume_ator.GetMapper().GetInput())
            
        from manipulacao_da_imagem.bisturi import OperadorBisturi
        volume_atual = self.navegador_3d.volume_ator.GetMapper().GetInput()
        operador = OperadorBisturi(volume_atual)
        
        # Executa o corte
        manter_interior = cortar_fora
        novo_volume = operador.cortar(
            self.pontos_corte, 
            self.renderer_corte, 
            manter_interior
        )
        
        import time
        t_inicio = time.time()
        
        # Atualiza todos os renderizadores
        self.navegador_2d.update_volume_data(novo_volume)
        self.navegador_3d.update_volume_data(novo_volume)
        
        # Oculta o ator do bisturi e renderiza
        for filtro in self.filtros_eventos.values():
            if hasattr(filtro, 'bisturi_actor'):
                if hasattr(filtro, 'interactor') and filtro.interactor:
                    renderer = filtro.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
                    if renderer and renderer.HasViewProp(filtro.bisturi_actor):
                        renderer.RemoveActor(filtro.bisturi_actor)
                    filtro.interactor.GetRenderWindow().Render()
                    
        t_fim = time.time()
        print(f"[PROFILING BISTURI] 5. Atualização da Engine 3D (GPU Rebuild): {t_fim - t_inicio:.4f}s")
        
    def resetar_bisturi(self):
        """Restaura o volume original do exame."""
        if hasattr(self, 'volume_original_bisturi'):
            import vtk
            volume_restaurado = vtk.vtkImageData()
            volume_restaurado.DeepCopy(self.volume_original_bisturi)
            
            self.navegador_2d.update_volume_data(volume_restaurado)
            self.navegador_3d.update_volume_data(volume_restaurado)
            
            for filtro in self.filtros_eventos.values():
                if hasattr(filtro, 'bisturi_actor'):
                    if hasattr(filtro, 'interactor') and filtro.interactor:
                        renderer = filtro.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
                        if renderer and renderer.HasViewProp(filtro.bisturi_actor):
                            renderer.RemoveActor(filtro.bisturi_actor)
                        filtro.interactor.GetRenderWindow().Render()

    def disparar_extracao_semente(self, pos):
        if self.parent() and hasattr(self.parent(), 'disparar_extracao_semente'):
            self.parent().disparar_extracao_semente(pos)

    def adicionar_semente(self, pos, actor):
        self.lista_sementes.append(pos)
        self.atores_sementes.append(actor)

    def limpar_sementes(self, renderers_2d=None):
        if renderers_2d is None:
            renderers_2d = list(self.navegador_2d.renderers_2d.values())
        elif isinstance(renderers_2d, dict):
            renderers_2d = list(renderers_2d.values())
        elif not isinstance(renderers_2d, list):
            renderers_2d = [renderers_2d]

        for renderer in renderers_2d:
            if renderer:
                for actor in self.atores_sementes:
                    if renderer.HasViewProp(actor):
                        renderer.RemoveActor(actor)
        
        self.lista_sementes.clear()
        self.atores_sementes.clear()
        
        for visao in self.navegador_2d.renderers_2d.values():
            if visao and visao.GetRenderWindow():
                visao.GetRenderWindow().Render()

