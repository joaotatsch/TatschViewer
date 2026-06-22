import vtk
from PyQt6.QtCore import Qt

class FerramentaInteracao:
    """Classe base para ferramentas de interação."""
    def __init__(self, filtro):
        self.filtro = filtro

    def on_mouse_press(self, event, x_vtk, y_vtk, pos_world, renderer):
        return False

    def on_mouse_move(self, event, x_vtk, y_vtk, pos_world, renderer):
        return False

    def on_mouse_release(self, event, x_vtk, y_vtk, pos_world, renderer):
        return False

    def on_wheel(self, delta_mm):
        return False


class FerramentaNormal(FerramentaInteracao):
    """Lida com janelamento manual, hover em medidas, e click para arrastar/selecionar."""
    def on_mouse_press(self, event, x_vtk, y_vtk, pos_world, renderer):
        # Selecionar medida existente
        if hasattr(self.filtro.parent(), 'coordenador_medidas') and self.filtro.parent().coordenador_medidas.medidas:
            prop_picker = vtk.vtkPropPicker()
            prop_picker.PickProp(x_vtk, y_vtk, renderer)
            prop_hit = prop_picker.GetViewProp()
            medida_acertada = None
            for med in self.filtro.parent().coordenador_medidas.medidas:
                if prop_hit is med.actor or prop_hit is med.text_actor:
                    medida_acertada = med
                    break
            if medida_acertada:
                if self.filtro.medida_selecionada and self.filtro.medida_selecionada is not medida_acertada:
                    self.filtro.medida_selecionada.selecionar(False)
                self.filtro.medida_selecionada = medida_acertada
                medida_acertada.selecionar(True)
                self.filtro.interactor.setCursor(Qt.CursorShape.ClosedHandCursor)
                
                cell_picker = vtk.vtkCellPicker()
                cell_picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                self.filtro.ultima_posicao_medida = cell_picker.GetPickPosition()
                self.filtro.arrastando_medida = True
                self.filtro.interactor.GetRenderWindow().Render()
                return True
            else:
                if self.filtro.medida_selecionada:
                    self.filtro.medida_selecionada.selecionar(False)
                    self.filtro.medida_selecionada = None
                    self.filtro.interactor.GetRenderWindow().Render()

        # Hit test arrastável (ex: espessuras ou centro de projeção)
        self.filtro.alvo_arraste = self.filtro._hit_test(pos_world)
        if self.filtro.alvo_arraste:
            self.filtro.interactor.setCursor(Qt.CursorShape.ClosedHandCursor)
            return True
            
        self.filtro.ultimo_pos_x = event.position().x()
        self.filtro.ultimo_pos_y = event.position().y()
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.filtro.arrastando_rotacao = True
            return True
        else:
            self.filtro.arrastando_janelamento = True
            return True

    def on_mouse_move(self, event, x_vtk, y_vtk, pos_world, renderer):
        # Hover sobre medidas
        if event.buttons() == Qt.MouseButton.NoButton:
            if hasattr(self.filtro.parent(), 'coordenador_medidas') and self.filtro.parent().coordenador_medidas.medidas:
                prop_picker = vtk.vtkPropPicker()
                prop_picker.PickProp(x_vtk, y_vtk, renderer)
                prop_hit = prop_picker.GetViewProp()
                for med in self.filtro.parent().coordenador_medidas.medidas:
                    if prop_hit is med.actor or prop_hit is med.text_actor:
                        self.filtro.interactor.setCursor(Qt.CursorShape.OpenHandCursor)
                        return False
            
            alvo = self.filtro._hit_test(pos_world)
            if alvo == "Centro":
                self.filtro.interactor.setCursor(Qt.CursorShape.SizeAllCursor)
            elif alvo in ["Sagital", "Coronal", "Axial"]:
                self.filtro.interactor.setCursor(Qt.CursorShape.OpenHandCursor)
            elif alvo and alvo.startswith("Espessura_"):
                v_alvo = alvo.split("_")[1]
                if v_alvo == "Sagital" or (v_alvo == "Coronal" and self.filtro.nome_visao == "Sagital"):
                    self.filtro.interactor.setCursor(Qt.CursorShape.SizeHorCursor)
                else:
                    self.filtro.interactor.setCursor(Qt.CursorShape.SizeVerCursor)
            else:
                self.filtro.interactor.setCursor(Qt.CursorShape.ArrowCursor)
            return False

        if self.filtro.arrastando_janelamento and event.buttons() & Qt.MouseButton.LeftButton:
            dx = event.position().x() - self.filtro.ultimo_pos_x
            dy = event.position().y() - self.filtro.ultimo_pos_y
            self.filtro.ultimo_pos_x = event.position().x()
            self.filtro.ultimo_pos_y = event.position().y()
            
            ator = self.filtro.navegador_2d.atores.get(self.filtro.nome_visao)
            if ator:
                ww_atual = ator.GetProperty().GetColorWindow()
                wl_atual = ator.GetProperty().GetColorLevel()
                fator = 2.0
                novo_ww = max(1.0, ww_atual + dx * fator)
                novo_wl = wl_atual - dy * fator
                ator.GetProperty().SetColorWindow(novo_ww)
                ator.GetProperty().SetColorLevel(novo_wl)
                if self.filtro.janelamento_callback:
                    self.filtro.janelamento_callback(novo_ww, novo_wl)
                self.filtro._renderizar_seguro()
            return True
            
        elif self.filtro.arrastando_rotacao and event.buttons() & Qt.MouseButton.LeftButton:
            dx = event.position().x() - self.filtro.ultimo_pos_x
            self.filtro.ultimo_pos_x = event.position().x()
            camera = renderer.GetActiveCamera()
            if camera:
                camera.Roll(dx * 0.5)
                self.filtro.navegador_2d.atualizar_bussola()
                self.filtro.interactor.GetRenderWindow().Render()
            return True

        elif self.filtro.alvo_arraste and event.buttons() & Qt.MouseButton.LeftButton:
            cx = self.filtro.navegador_2d.planos["Sagital"].GetOrigin()[0]
            cy = self.filtro.navegador_2d.planos["Coronal"].GetOrigin()[1]
            cz = self.filtro.navegador_2d.planos["Axial"].GetOrigin()[2]
            centros = {"Sagital": cx, "Coronal": cy, "Axial": cz}
            idx_map = {"Sagital": 0, "Coronal": 1, "Axial": 2}
            
            if self.filtro.alvo_arraste.startswith("Espessura_"):
                v_alvo = self.filtro.alvo_arraste.split("_")[1]
                proj = self.filtro.parent().operador_projecao
                if proj:
                    nova_esp = abs(pos_world[idx_map[v_alvo]] - centros[v_alvo]) * 2.0
                    proj.aplicar_projecao_individual(v_alvo, proj.modos[v_alvo], nova_esp)
                    if self.filtro.espessura_callback:
                        self.filtro.espessura_callback(nova_esp)
                    self.filtro._renderizar_seguro()
            elif self.filtro.alvo_arraste == "Centro":
                visoes_cruzadas = []
                if self.filtro.nome_visao == "Axial": visoes_cruzadas = ["Sagital", "Coronal"]
                elif self.filtro.nome_visao == "Coronal": visoes_cruzadas = ["Sagital", "Axial"]
                elif self.filtro.nome_visao == "Sagital": visoes_cruzadas = ["Coronal", "Axial"]
                
                v1, v2 = visoes_cruzadas[0], visoes_cruzadas[1]
                plano1 = self.filtro.navegador_2d.planos[v1]
                plano2 = self.filtro.navegador_2d.planos[v2]
                origem1 = list(plano1.GetOrigin())
                origem2 = list(plano2.GetOrigin())
                
                i1, i2 = idx_map[v1], idx_map[v2]
                origem1[i1] = pos_world[i1]
                origem2[i2] = pos_world[i2]
                plano1.SetOrigin(origem1)
                plano2.SetOrigin(origem2)
                
                p = self.filtro.navegador_2d.planos
                if "Sagital" in p and "Coronal" in p and "Axial" in p:
                    nx, ny, nz = p["Sagital"].GetOrigin()[0], p["Coronal"].GetOrigin()[1], p["Axial"].GetOrigin()[2]
                    if hasattr(self.filtro.parent(), 'operador_projecao') and self.filtro.parent().operador_projecao:
                        self.filtro.parent().operador_projecao.atualizar_linhas(nx, ny, nz, p)
                self.filtro._renderizar_seguro()
            elif self.filtro.alvo_arraste in ["Axial", "Coronal", "Sagital"]:
                plano_alvo = self.filtro.navegador_2d.planos[self.filtro.alvo_arraste]
                nova_origem = list(plano_alvo.GetOrigin())
                i_alvo = idx_map[self.filtro.alvo_arraste]
                nova_origem[i_alvo] = pos_world[i_alvo]
                plano_alvo.SetOrigin(nova_origem)
                
                p = self.filtro.navegador_2d.planos
                if "Sagital" in p and "Coronal" in p and "Axial" in p:
                    nx, ny, nz = p["Sagital"].GetOrigin()[0], p["Coronal"].GetOrigin()[1], p["Axial"].GetOrigin()[2]
                    if hasattr(self.filtro.parent(), 'operador_projecao') and self.filtro.parent().operador_projecao:
                        self.filtro.parent().operador_projecao.atualizar_linhas(nx, ny, nz, p)
                self.filtro._renderizar_seguro()
            return True
            
        elif self.filtro.arrastando_medida and self.filtro.medida_selecionada and self.filtro.ultima_posicao_medida and event.buttons() & Qt.MouseButton.LeftButton:
            cell_picker = vtk.vtkCellPicker()
            cell_picker.Pick(x_vtk, y_vtk, 0.0, renderer)
            pos = cell_picker.GetPickPosition()
            dx = pos[0] - self.filtro.ultima_posicao_medida[0]
            dy = pos[1] - self.filtro.ultima_posicao_medida[1]
            dz = pos[2] - self.filtro.ultima_posicao_medida[2]
            if dx != 0 or dy != 0 or dz != 0:
                self.filtro.medida_selecionada.mover(dx, dy, dz)
                self.filtro.ultima_posicao_medida = pos
                self.filtro.interactor.GetRenderWindow().Render()
            return True
        return False

    def on_mouse_release(self, event, x_vtk, y_vtk, pos_world, renderer):
        self.filtro.arrastando_janelamento = False
        self.filtro.arrastando_rotacao = False
        self.filtro.alvo_arraste = None
        self.filtro.arrastando_medida = False
        return False
class FerramentaSemente(FerramentaInteracao):
    def on_mouse_press(self, event, x_vtk, y_vtk, pos_world, renderer):
        self.filtro.picker.SetTolerance(0.0)
        self.filtro.picker.Pick(x_vtk, y_vtk, 0.0, renderer)
        pos = self.filtro.picker.GetPickPosition()
        idx = [0.0, 0.0, 0.0]
        self.filtro.navegador_2d.volume_ativo.TransformPhysicalPointToContinuousIndex(pos, idx)
        ix, iy, iz = int(round(idx[0])), int(round(idx[1])), int(round(idx[2]))
        dims = self.filtro.navegador_2d.volume_ativo.GetDimensions()
        if 0 <= ix < dims[0] and 0 <= iy < dims[1] and 0 <= iz < dims[2]:
            sphere = vtk.vtkSphereSource()
            sphere.SetCenter(pos)
            sphere.SetRadius(3.0)
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputConnection(sphere.GetOutputPort())
            actor = vtk.vtkActor()
            actor.SetMapper(mapper)
            actor.GetProperty().SetColor(0.0, 1.0, 0.0)
            renderer.AddActor(actor)
            self.filtro.interactor.GetRenderWindow().Render()
            if hasattr(self.filtro.parent(), 'adicionar_semente'):
                self.filtro.parent().adicionar_semente([ix, iy, iz], actor)
        return True

    def on_mouse_move(self, event, x_vtk, y_vtk, pos_world, renderer):
        self.filtro.interactor.setCursor(Qt.CursorShape.CrossCursor)
        return True

class FerramentaSementeDSA(FerramentaInteracao):
    def on_mouse_press(self, event, x_vtk, y_vtk, pos_world, renderer):
        main_window = self.filtro.parent().parent() if hasattr(self.filtro.parent(), 'parent') else None
        vtk_img = self.filtro.navegador_2d.volume_ativo
        if main_window and vtk_img:
            try:
                idx = [0.0, 0.0, 0.0]
                vtk_img.TransformPhysicalPointToContinuousIndex(pos_world, idx)
                index_itk = (int(round(idx[0])), int(round(idx[1])), int(round(idx[2])))
                main_window.gerenciador_processamento.iniciar_subtracao_semente(index_itk)
            except Exception as e:
                main_window.statusBar().showMessage(f"Erro ao converter semente: {str(e)}")
        self.filtro.ferramenta_ativa = "Normal"
        self.filtro.interactor.setCursor(Qt.CursorShape.ArrowCursor)
        return True

    def on_mouse_move(self, event, x_vtk, y_vtk, pos_world, renderer):
        if event.buttons() == Qt.MouseButton.NoButton:
            self.filtro.interactor.setCursor(Qt.CursorShape.CrossCursor)
            return False
        return False

class FerramentaReslice(FerramentaInteracao):
    def on_mouse_press(self, event, x_vtk, y_vtk, pos_world, renderer):
        self.filtro.alvo_reslice = self.filtro.operador_interacao_reslice.hit_test(self.filtro.nome_visao, pos_world)
        if self.filtro.alvo_reslice is not None:
            cell_picker = vtk.vtkCellPicker()
            cell_picker.Pick(x_vtk, y_vtk, 0.0, renderer)
            self.filtro.ultima_posicao_medida = cell_picker.GetPickPosition()
            return True
        self.filtro.ultimo_pos_x = event.position().x()
        self.filtro.ultimo_pos_y = event.position().y()
        self.filtro.arrastando_janelamento = True
        return True

    def on_mouse_move(self, event, x_vtk, y_vtk, pos_world, renderer):
        if event.buttons() == Qt.MouseButton.NoButton:
            alvo = self.filtro.operador_interacao_reslice.hit_test(self.filtro.nome_visao, pos_world)
            if alvo == "Centro":
                self.filtro.interactor.setCursor(Qt.CursorShape.SizeAllCursor)
            elif alvo is not None:
                self.filtro.interactor.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.filtro.interactor.setCursor(Qt.CursorShape.ArrowCursor)
            return True

        if self.filtro.alvo_reslice and event.buttons() & Qt.MouseButton.LeftButton:
            cell_picker = vtk.vtkCellPicker()
            cell_picker.Pick(x_vtk, y_vtk, 0.0, renderer)
            pos = cell_picker.GetPickPosition()
            if self.filtro.alvo_reslice == "Centro":
                for visao, plane in self.filtro.navegador_2d.planos.items():
                    plane.SetOrigin(pos[0], pos[1], pos[2])
                self.filtro.ultima_posicao_medida = pos
                p = self.filtro.navegador_2d.planos
                if "Sagital" in p and "Coronal" in p and "Axial" in p:
                    nx, ny, nz = p["Sagital"].GetOrigin()[0], p["Coronal"].GetOrigin()[1], p["Axial"].GetOrigin()[2]
                    if hasattr(self.filtro.parent(), 'operador_projecao') and self.filtro.parent().operador_projecao:
                        self.filtro.parent().operador_projecao.atualizar_linhas(nx, ny, nz, p)
            else:
                self.filtro.operador_interacao_reslice.rotacionar(self.filtro.nome_visao, self.filtro.alvo_reslice, self.filtro.ultima_posicao_medida, pos)
                self.filtro.ultima_posicao_medida = pos
                p = self.filtro.navegador_2d.planos
                if "Sagital" in p and "Coronal" in p and "Axial" in p:
                    nx, ny, nz = p["Sagital"].GetOrigin()[0], p["Coronal"].GetOrigin()[1], p["Axial"].GetOrigin()[2]
                    if hasattr(self.filtro.parent(), 'operador_projecao') and self.filtro.parent().operador_projecao:
                        self.filtro.parent().operador_projecao.atualizar_linhas(nx, ny, nz, p)
            self.filtro._renderizar_seguro()
            return True
        return False

    def on_mouse_release(self, event, x_vtk, y_vtk, pos_world, renderer):
        self.filtro.alvo_reslice = None
        self.filtro.arrastando_janelamento = False
        return False

class FerramentaMedida(FerramentaInteracao):
    def __init__(self, filtro, tipo="Regua"):
        super().__init__(filtro)
        self.tipo = tipo

    def on_mouse_press(self, event, x_vtk, y_vtk, pos_world, renderer):
        origem_plano = self.filtro.navegador_2d.planos[self.filtro.nome_visao].GetOrigin()
        self.filtro.arrastando_regua = True
        medidas_coord = self.filtro.parent().coordenador_medidas
        if self.tipo == "Regua":
            medidas_coord.iniciar_regua(renderer, pos_world, self.filtro.nome_visao, origem_plano)
        elif self.tipo == "Elipse":
            medidas_coord.iniciar_elipse(renderer, pos_world, self.filtro.nome_visao, origem_plano, self.filtro.navegador_2d.volume_ativo)
        return True

    def on_mouse_move(self, event, x_vtk, y_vtk, pos_world, renderer):
        if event.buttons() == Qt.MouseButton.NoButton:
            self.filtro.interactor.setCursor(Qt.CursorShape.CrossCursor)
            return False

        if self.filtro.arrastando_regua:
            picker = vtk.vtkCellPicker()
            picker.Pick(x_vtk, y_vtk, 0.0, renderer)
            pos = picker.GetPickPosition()
            if self.tipo == "Regua":
                self.filtro.parent().coordenador_medidas.atualizar_regua(pos)
            elif self.tipo == "Elipse":
                self.filtro.parent().coordenador_medidas.atualizar_elipse(pos)
            self.filtro.interactor.GetRenderWindow().Render()
            return True
        return False

    def on_mouse_release(self, event, x_vtk, y_vtk, pos_world, renderer):
        self.filtro.arrastando_regua = False
        if self.tipo == "Elipse":
            # Conclui elipse
            if hasattr(self.filtro.parent(), 'coordenador_medidas'):
                self.filtro.parent().coordenador_medidas.concluir_elipse()
        return False
class FerramentaCropBox(FerramentaInteracao):
    def on_mouse_press(self, event, x_vtk, y_vtk, pos_world, renderer):
        nav2d = self.filtro.navegador_2d
        if hasattr(nav2d, 'crop_widgets') and self.filtro.nome_visao in nav2d.crop_widgets:
            widget = nav2d.crop_widgets[self.filtro.nome_visao]
            if widget.GetEnabled():
                self.filtro.picker.SetTolerance(0.0)
                self.filtro.picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                pos = self.filtro.picker.GetPickPosition()
                bounds = list(widget.GetRepresentation().GetBounds())
                tol = 6.0
                self.filtro.drag_crop_index = None
                
                if self.filtro.nome_visao == "Axial":
                    if abs(pos[0] - bounds[0]) < tol: self.filtro.drag_crop_index = 0
                    elif abs(pos[0] - bounds[1]) < tol: self.filtro.drag_crop_index = 1
                    elif abs(pos[1] - bounds[2]) < tol: self.filtro.drag_crop_index = 2
                    elif abs(pos[1] - bounds[3]) < tol: self.filtro.drag_crop_index = 3
                elif self.filtro.nome_visao == "Coronal":
                    if abs(pos[0] - bounds[0]) < tol: self.filtro.drag_crop_index = 0
                    elif abs(pos[0] - bounds[1]) < tol: self.filtro.drag_crop_index = 1
                    elif abs(pos[2] - bounds[4]) < tol: self.filtro.drag_crop_index = 4
                    elif abs(pos[2] - bounds[5]) < tol: self.filtro.drag_crop_index = 5
                elif self.filtro.nome_visao == "Sagital":
                    if abs(pos[1] - bounds[2]) < tol: self.filtro.drag_crop_index = 2
                    elif abs(pos[1] - bounds[3]) < tol: self.filtro.drag_crop_index = 3
                    elif abs(pos[2] - bounds[4]) < tol: self.filtro.drag_crop_index = 4
                    elif abs(pos[2] - bounds[5]) < tol: self.filtro.drag_crop_index = 5
                    
                if self.filtro.drag_crop_index is not None:
                    self.filtro.ultimo_pick_mundo = pos
                    return True
        return False

    def on_mouse_move(self, event, x_vtk, y_vtk, pos_world, renderer):
        nav2d = self.filtro.navegador_2d
        if hasattr(nav2d, 'crop_widgets') and self.filtro.nome_visao in nav2d.crop_widgets:
            widget = nav2d.crop_widgets[self.filtro.nome_visao]
            if getattr(self.filtro, 'drag_crop_index', None) is not None:
                self.filtro.picker.SetTolerance(0.0)
                self.filtro.picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                pos = self.filtro.picker.GetPickPosition()
                dx = pos[0] - self.filtro.ultimo_pick_mundo[0]
                dy = pos[1] - self.filtro.ultimo_pick_mundo[1]
                dz = pos[2] - self.filtro.ultimo_pick_mundo[2]
                rep = widget.GetRepresentation()
                bounds = list(rep.GetBounds())
                idx = self.filtro.drag_crop_index
                if idx in [0, 1]: bounds[idx] += dx
                elif idx in [2, 3]: bounds[idx] += dy
                elif idx in [4, 5]: bounds[idx] += dz
                if bounds[1] - bounds[0] < 5.0: bounds[idx] -= dx
                elif bounds[3] - bounds[2] < 5.0: bounds[idx] -= dy
                elif bounds[5] - bounds[4] < 5.0: bounds[idx] -= dz
                else:
                    rep.PlaceWidget(bounds)
                    self.filtro.ultimo_pick_mundo = pos
                    self.filtro._renderizar_seguro()
                return True
            elif event.buttons() == Qt.MouseButton.NoButton:
                if widget.GetEnabled():
                    self.filtro.picker.SetTolerance(0.0)
                    self.filtro.picker.Pick(x_vtk, y_vtk, 0.0, renderer)
                    pos = self.filtro.picker.GetPickPosition()
                    bounds = widget.GetRepresentation().GetBounds()
                    tol = 6.0
                    cursor = Qt.CursorShape.ArrowCursor
                    if self.filtro.nome_visao == "Axial":
                        on_x = abs(pos[0] - bounds[0]) < tol or abs(pos[0] - bounds[1]) < tol
                        on_y = abs(pos[1] - bounds[2]) < tol or abs(pos[1] - bounds[3]) < tol
                        if on_x and on_y: cursor = Qt.CursorShape.SizeAllCursor
                        elif on_x: cursor = Qt.CursorShape.SizeHorCursor
                        elif on_y: cursor = Qt.CursorShape.SizeVerCursor
                    elif self.filtro.nome_visao == "Coronal":
                        on_x = abs(pos[0] - bounds[0]) < tol or abs(pos[0] - bounds[1]) < tol
                        on_z = abs(pos[2] - bounds[4]) < tol or abs(pos[2] - bounds[5]) < tol
                        if on_x and on_z: cursor = Qt.CursorShape.SizeAllCursor
                        elif on_x: cursor = Qt.CursorShape.SizeHorCursor
                        elif on_z: cursor = Qt.CursorShape.SizeVerCursor
                    elif self.filtro.nome_visao == "Sagital":
                        on_y = abs(pos[1] - bounds[2]) < tol or abs(pos[1] - bounds[3]) < tol
                        on_z = abs(pos[2] - bounds[4]) < tol or abs(pos[2] - bounds[5]) < tol
                        if on_y and on_z: cursor = Qt.CursorShape.SizeAllCursor
                        elif on_y: cursor = Qt.CursorShape.SizeHorCursor
                        elif on_z: cursor = Qt.CursorShape.SizeVerCursor
                    self.filtro.interactor.setCursor(cursor)
        return False

    def on_mouse_release(self, event, x_vtk, y_vtk, pos_world, renderer):
        self.filtro.drag_crop_index = None
        return False

class FerramentaCrosshair(FerramentaInteracao):
    def on_mouse_press(self, event, x_vtk, y_vtk, pos_world, renderer):
        self.filtro.arrastando_crosshair = True
        if hasattr(self.filtro.parent(), 'operador_crosshair') and self.filtro.parent().operador_crosshair:
            planos = self.filtro.navegador_2d.planos
            self.filtro.parent().operador_crosshair.atualizar_posicao(pos_world, planos)
            p = self.filtro.navegador_2d.planos
            if "Sagital" in p and "Coronal" in p and "Axial" in p:
                nx, ny, nz = p["Sagital"].GetOrigin()[0], p["Coronal"].GetOrigin()[1], p["Axial"].GetOrigin()[2]
                if hasattr(self.filtro.parent(), 'operador_projecao') and self.filtro.parent().operador_projecao:
                    self.filtro.parent().operador_projecao.atualizar_linhas(nx, ny, nz, p)
            self.filtro._renderizar_seguro()
        return True

    def on_mouse_move(self, event, x_vtk, y_vtk, pos_world, renderer):
        if self.filtro.arrastando_crosshair and event.buttons() & Qt.MouseButton.LeftButton:
            if hasattr(self.filtro.parent(), 'operador_crosshair') and self.filtro.parent().operador_crosshair:
                planos = self.filtro.navegador_2d.planos
                self.filtro.parent().operador_crosshair.atualizar_posicao(pos_world, planos)
                p = self.filtro.navegador_2d.planos
                if "Sagital" in p and "Coronal" in p and "Axial" in p:
                    nx, ny, nz = p["Sagital"].GetOrigin()[0], p["Coronal"].GetOrigin()[1], p["Axial"].GetOrigin()[2]
                    if hasattr(self.filtro.parent(), 'operador_projecao') and self.filtro.parent().operador_projecao:
                        self.filtro.parent().operador_projecao.atualizar_linhas(nx, ny, nz, p)
                self.filtro._renderizar_seguro()
            return True
        return False

    def on_mouse_release(self, event, x_vtk, y_vtk, pos_world, renderer):
        self.filtro.arrastando_crosshair = False
        return False

class FerramentaBisturi(FerramentaInteracao):
    def on_mouse_press(self, event, x_vtk, y_vtk, pos_world, renderer):
        self.filtro.arrastando_bisturi = True
        self.filtro.bisturi_pontos = [(x_vtk, y_vtk)]
        if renderer and not renderer.HasViewProp(self.filtro.bisturi_actor):
            renderer.AddActor(self.filtro.bisturi_actor)
        return True

    def on_mouse_move(self, event, x_vtk, y_vtk, pos_world, renderer):
        if self.filtro.arrastando_bisturi and event.buttons() & Qt.MouseButton.LeftButton:
            if hasattr(self.filtro, 'bisturi_pontos'):
                self.filtro.bisturi_pontos.append((x_vtk, y_vtk))
                # Atualizar linha visual
                points = vtk.vtkPoints()
                lines = vtk.vtkCellArray()
                for i, p in enumerate(self.filtro.bisturi_pontos):
                    points.InsertNextPoint(p[0], p[1], 0.0)
                    if i > 0:
                        line = vtk.vtkLine()
                        line.GetPointIds().SetId(0, i - 1)
                        line.GetPointIds().SetId(1, i)
                        lines.InsertNextCell(line)
                polydata = vtk.vtkPolyData()
                polydata.SetPoints(points)
                polydata.SetLines(lines)
                
                mapper = vtk.vtkPolyDataMapper2D()
                mapper.SetInputData(polydata)
                self.filtro.bisturi_actor.SetMapper(mapper)
                self.filtro.interactor.GetRenderWindow().Render()
            return True
        return False

    def on_mouse_release(self, event, x_vtk, y_vtk, pos_world, renderer):
        if self.filtro.arrastando_bisturi:
            self.filtro.arrastando_bisturi = False
            if hasattr(self.filtro, 'bisturi_pontos') and len(self.filtro.bisturi_pontos) > 2:
                if renderer and renderer.HasViewProp(self.filtro.bisturi_actor):
                    renderer.RemoveActor(self.filtro.bisturi_actor)
                self.filtro.aplicar_bisturi(cortar_fora=False)
            self.filtro.bisturi_pontos = []
            self.filtro.interactor.GetRenderWindow().Render()
            return True
        return False
