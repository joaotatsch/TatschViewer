# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import QMessageBox, QProgressDialog, QDialog, QVBoxLayout, QLabel, QComboBox, QDialogButtonBox, QListWidgetItem
from PyQt6.QtCore import Qt
import SimpleITK as sitk
import vtk
import numpy as np
from core.utils_profiling import profiler_time

from processamento_imagem.threads_subtracao import (
    ThreadSubtracaoLenta, ThreadSubtracaoRapida, ThreadSubtracaoSemente, 
    ThreadSubtracaoOssea, ThreadExtracaoVascularRMRapida
)

class GerenciadorProcessamento:
    @profiler_time
    def __init__(self, main_window):
        self.main_window = main_window

    def processar_sementes(self):
        if self.main_window._sitk_img_ref is None:
            QMessageBox.warning(self.main_window, "Aviso", "Nenhuma série carregada para processamento.")
            return

        lista_seeds = self.main_window.coordenador_navegacao.lista_sementes
        if not lista_seeds:
            QMessageBox.warning(self.main_window, "Aviso", "Por favor, adicione pelo menos uma semente antes de processar.")
            return

        self.main_window.progresso_subtracao = QProgressDialog("Extraindo Vasos por Sementes (Region Growing)...", None, 0, 0, self.main_window)
        self.main_window.progresso_subtracao.setWindowModality(Qt.WindowModality.WindowModal)
        self.main_window.progresso_subtracao.setCancelButton(None)
        self.main_window.progresso_subtracao.show()

        if hasattr(self.main_window, 'action_processar_sementes'):
            self.main_window.action_processar_sementes.setEnabled(False)

        self.main_window.thread_semente = ThreadSubtracaoSemente(self.main_window._sitk_img_ref, lista_seeds)
        self.main_window.thread_semente.resultado.connect(self.on_semente_concluida)
        self.main_window.thread_semente.erro.connect(self.on_erro_semente)
        self.main_window.thread_manager.active_threads.append(self.main_window.thread_semente)
        self.main_window.thread_semente.finished.connect(lambda t=self.main_window.thread_semente: self.main_window.thread_manager.cleanup_thread(t))
        self.main_window.thread_semente.finished.connect(self.main_window.thread_semente.deleteLater)
        self.main_window.thread_semente.start()

    def on_semente_concluida(self, sitk_img_result):
        if hasattr(self.main_window, 'progresso_subtracao') and self.main_window.progresso_subtracao:
            self.main_window.progresso_subtracao.close()

        if hasattr(self.main_window, 'action_processar_sementes'):
            self.main_window.action_processar_sementes.setEnabled(True)
        
        if hasattr(self.main_window, 'action_adicionar_semente') and self.main_window.action_adicionar_semente.isChecked():
            self.main_window.action_adicionar_semente.setChecked(False)

        if hasattr(self.main_window, 'coordenador_navegacao'):
            self.main_window.coordenador_navegacao.limpar_sementes()

        self.on_subtracao_concluida(sitk_img_result)

    def on_erro_semente(self, mensagem):
        if hasattr(self.main_window, 'progresso_subtracao') and self.main_window.progresso_subtracao:
            self.main_window.progresso_subtracao.close()
        if hasattr(self.main_window, 'action_processar_sementes'):
            self.main_window.action_processar_sementes.setEnabled(True)
        QMessageBox.critical(self.main_window, "Erro de Processamento", f"Falha na extração por semente: {mensagem}")

    def limpar_sementes(self):
        if hasattr(self.main_window, 'coordenador_navegacao'):
            self.main_window.coordenador_navegacao.limpar_sementes()

    def iniciar_subtracao_lenta(self):
        if not hasattr(self.main_window, "series_carregadas") or not self.main_window.series_carregadas:
            QMessageBox.warning(self.main_window, "Aviso", "Nenhuma série carregada. Abra uma pasta DICOM primeiro.")
            return

        dialog = QDialog(self.main_window)
        dialog.setWindowTitle("Subtração Óssea Lenta (Registration)")
        dialog.setMinimumWidth(400)
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel("Selecione a Fase Angio-TC (Com Contraste):"))
        combo_angio = QComboBox()
        layout.addWidget(combo_angio)

        layout.addWidget(QLabel("Selecione a Fase Pré-Contraste (Sem Contraste):"))
        combo_sem_contraste = QComboBox()
        layout.addWidget(combo_sem_contraste)

        for s in self.main_window.series_carregadas:
            s_id = s.get("SeriesID")
            dir_serie = s.get("Directory")
            num_slices = len(s.get("Files", []))
            desc_serie = s.get("Description", "Desconhecida")
            num_serie = s.get("Number", "N/A")
            
            texto_item = f"Série {num_serie}: {desc_serie} ({num_slices} fatias)"
            
            dados_serie = {"id": s_id, "dir": dir_serie, "files": s.get("Files", [])}
            combo_angio.addItem(texto_item, userData=dados_serie)
            combo_sem_contraste.addItem(texto_item, userData=dados_serie)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        layout.addWidget(btn_box)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            serie_angio = combo_angio.currentData()
            serie_sem = combo_sem_contraste.currentData()

            if serie_angio["id"] == serie_sem["id"]:
                QMessageBox.warning(self.main_window, "Aviso", "Por favor, selecione séries diferentes para o Registro.")
                return

            def get_sitk_img(serie_dados):
                s_id = serie_dados["id"]
                if hasattr(self.main_window, "cache_series") and s_id in self.main_window.cache_series:
                    return self.main_window.cache_series[s_id][1]
                reader = sitk.ImageSeriesReader()
                reader.SetFileNames(serie_dados["files"])
                return reader.Execute()

            try:
                img_angio = get_sitk_img(serie_angio)
                img_sem = get_sitk_img(serie_sem)
            except Exception as e:
                QMessageBox.critical(self.main_window, "Erro", f"Erro ao ler imagem: {str(e)}")
                return

            self.main_window.progresso_dsa = QProgressDialog("Inicializando Registro 3D...", None, 0, 0, self.main_window)
            self.main_window.progresso_dsa.setWindowTitle("Subtração Lenta")
            self.main_window.progresso_dsa.setWindowModality(Qt.WindowModality.WindowModal)
            self.main_window.progresso_dsa.setCancelButton(None)
            self.main_window.progresso_dsa.show()

            self.main_window.thread_dsa = ThreadSubtracaoLenta(img_sem, img_angio)
            self.main_window.thread_dsa.progresso_sinal.connect(
                lambda it, val: self.main_window.progresso_dsa.setLabelText(f"Iteração {it} | Métrica: {val:.5f}")
            )
            self.main_window.thread_dsa.log_sinal.connect(self.main_window.progresso_dsa.setLabelText)
            self.main_window.thread_dsa.virtual_sinal.connect(self.on_serie_virtual_criada)
            self.main_window.thread_dsa.erro_sinal.connect(self.on_subtracao_erro)
            self.main_window.thread_manager.active_threads.append(self.main_window.thread_dsa)
            self.main_window.thread_dsa.finished.connect(lambda t=self.main_window.thread_dsa: self.main_window.thread_manager.cleanup_thread(t))
            self.main_window.thread_dsa.finished.connect(self.main_window.thread_dsa.deleteLater)
            self.main_window.thread_dsa.start()

    def ativar_ferramenta_semente_dsa(self):
        if not hasattr(self.main_window, 'coordenador_navegacao') or not self.main_window.coordenador_navegacao: return
        self.main_window.statusBar().showMessage("Semente Vascular ativada: Clique na Aorta na visão 2D.")
        
        QMessageBox.information(self.main_window, "Subtração Rápida", "Clique no vaso de interesse na visão 2D.")
        
        for nome, filtro in self.main_window.coordenador_navegacao.filtros_eventos.items():
            if hasattr(filtro, 'ferramenta_ativa'):
                filtro.ferramenta_ativa = "SementeDSA"

    def atualizar_progresso_dsa(self, valor, mensagem):
        if hasattr(self.main_window, 'progress_dsa'):
            self.main_window.progress_dsa.setValue(valor)
            self.main_window.progress_dsa.setLabelText(mensagem)

    def iniciar_subtracao_semente(self, index_itk):
        if not hasattr(self.main_window, '_sitk_img_ref') or self.main_window._sitk_img_ref is None:
            QMessageBox.warning(self.main_window, "Aviso", "Nenhuma série carregada para subtração.")
            return
            
        is_mr = hasattr(self.main_window, '_prop_dicom_ref') and self.main_window._prop_dicom_ref.get("Modality", "") == "MR"
            
        self.main_window.statusBar().showMessage("Inundando árvore vascular...")
        
        if hasattr(self.main_window, 'btn_subtracao_ossea') and self.main_window.btn_subtracao_ossea:
            self.main_window.btn_subtracao_ossea.setEnabled(False)
        
        msg_progresso = "Isolamento Vascular MR (White Top-Hat)..." if is_mr else "Iniciando subtração..."
        self.main_window.progress_dsa = QProgressDialog(msg_progresso, "Cancelar", 0, 100, self.main_window)
        self.main_window.progress_dsa.setWindowTitle("Subtração Óssea Guiada")
        self.main_window.progress_dsa.setWindowModality(Qt.WindowModality.WindowModal)
        self.main_window.progress_dsa.setAutoClose(True)
        self.main_window.progress_dsa.show()
        if is_mr:
            self.main_window.thread_semente_dsa = ThreadExtracaoVascularRMRapida(self.main_window._sitk_img_ref, index_itk)
        else:
            self.main_window.thread_semente_dsa = ThreadSubtracaoSemente(self.main_window._sitk_img_ref, index_itk)
            
        self.main_window.thread_semente_dsa.progresso_sinal.connect(self.atualizar_progresso_dsa)
        self.main_window.thread_semente_dsa.virtual_sinal.connect(self.on_serie_virtual_criada)
        self.main_window.thread_semente_dsa.log_sinal.connect(self.main_window.statusBar().showMessage)
        self.main_window.thread_semente_dsa.erro_sinal.connect(self.on_subtracao_erro)
        self.main_window.thread_manager.active_threads.append(self.main_window.thread_semente_dsa)
        self.main_window.thread_semente_dsa.finished.connect(lambda t=self.main_window.thread_semente_dsa: self.main_window.thread_manager.cleanup_thread(t))
        self.main_window.thread_semente_dsa.finished.connect(self.main_window.thread_semente_dsa.deleteLater)
        self.main_window.thread_semente_dsa.start()

    def iniciar_subtracao_rapida(self):
        if not hasattr(self.main_window, '_sitk_img_ref') or self.main_window._sitk_img_ref is None:
            QMessageBox.warning(self.main_window, "Aviso", "Nenhuma série carregada para subtração.")
            return
            
        self.ativar_ferramenta_semente_dsa()

    def on_serie_virtual_criada(self, vtk_image, sitk_image, nome):
        if hasattr(self.main_window, "progresso_dsa"):
            self.main_window.progresso_dsa.close()
            
        if hasattr(self.main_window, 'coordenador_navegacao') and self.main_window.coordenador_navegacao:
            for n, filtro in self.main_window.coordenador_navegacao.filtros_eventos.items():
                filtro.ferramenta_ativa = "Normal"
                if hasattr(filtro, 'interactor') and filtro.interactor:
                    filtro.interactor.setCursor(Qt.CursorShape.ArrowCursor)
                    filtro.interactor.GetRenderWindow().Render()
                    
        item = QListWidgetItem(nome)
        dados = {
            "virtual": True, 
            "vtk_image": vtk_image, 
            "sitk_image": sitk_image,
            "np_array": getattr(vtk_image, "_np_ref", None)
        }
        
        if hasattr(vtk_image, '_mr_windowing'):
            ww, wl = vtk_image._mr_windowing
            if hasattr(self.main_window, '_prop_dicom_ref'):
                novo_prop_dicom = dict(self.main_window._prop_dicom_ref)
                novo_prop_dicom["WindowWidth"] = str(ww)
                novo_prop_dicom["WindowCenter"] = str(wl)
                dados["prop_dicom"] = novo_prop_dicom
                
        item.setData(Qt.ItemDataRole.UserRole, dados)
        item.setToolTip(f"Série gerada virtualmente em RAM.")
        self.main_window.list_series.addItem(item)
        
        self.main_window.list_series.setCurrentItem(item)
        self.main_window.gerenciador_arquivos.carregar_serie_selecionada(item)
        
        QMessageBox.information(self.main_window, "Sucesso", f"{nome} processada e anexada na lista com sucesso!")

    def on_subtracao_erro(self, erro):
        if hasattr(self.main_window, "progresso_dsa"):
            self.main_window.progresso_dsa.close()
        self.main_window.statusBar().showMessage("Erro no processamento da subtração.")
        QMessageBox.critical(self.main_window, "Erro", f"Ocorreu um erro durante a subtração:\n{erro}")
        if hasattr(self.main_window, 'btn_subtracao_ossea') and self.main_window.btn_subtracao_ossea:
            self.main_window.btn_subtracao_ossea.setEnabled(True)

    def aplicar_subtracao_ossea_legada(self):
        pass

    def on_erro_subtracao(self, mensagem):
        if hasattr(self.main_window, 'progresso_subtracao') and self.main_window.progresso_subtracao:
            self.main_window.progresso_subtracao.close()
        if hasattr(self.main_window, 'btn_subtracao_ossea') and self.main_window.btn_subtracao_ossea:
            self.main_window.btn_subtracao_ossea.setEnabled(True)
        QMessageBox.critical(self.main_window, "Erro de Processamento", f"Falha na subtração óssea: {mensagem}")

    def on_subtracao_concluida(self, sitk_img_result):
        if hasattr(self.main_window, 'progresso_subtracao') and self.main_window.progresso_subtracao:
            self.main_window.progresso_subtracao.close()
        
        if hasattr(self.main_window, 'btn_subtracao_ossea') and self.main_window.btn_subtracao_ossea:
            self.main_window.btn_subtracao_ossea.setEnabled(True)

        self.main_window._sitk_img_ref = sitk_img_result
        np_array = sitk.GetArrayFromImage(sitk_img_result)
        
        if not np_array.flags["C_CONTIGUOUS"]:
            np_array = np.ascontiguousarray(np_array)
        self.main_window._np_view_ref = np_array
        
        is_mr = hasattr(self.main_window, '_prop_dicom_ref') and self.main_window._prop_dicom_ref.get("Modality", "") == "MR"
        if is_mr:
            min_val = float(np.min(np_array))
            p99_9 = float(np.percentile(np_array, 99.9))
            if p99_9 > min_val:
                ww = p99_9 - min_val
                wl = min_val + (ww / 2.0)
                self.main_window._prop_dicom_ref["WindowWidth"] = str(ww)
                self.main_window._prop_dicom_ref["WindowCenter"] = str(wl)
                import logging
                logging.getLogger(__name__).info(f"[MR WINDOWING - PÓS-EXTRAÇÃO] WW={ww:.1f} WL={wl:.1f}")

        spacing = sitk_img_result.GetSpacing()
        origin = sitk_img_result.GetOrigin()
        direction = sitk_img_result.GetDirection()
        
        dims = np_array.shape # Z, Y, X
        nx, ny, nz = dims[2], dims[1], dims[0]

        if len(origin) >= 3:
            origin_vtk = [-origin[0], -origin[1], origin[2]]
        else:
            origin_vtk = [0.0, 0.0, 0.0]

        import_vtk = vtk.vtkImageImport()
        import_vtk.SetImportVoidPointer(np_array)
        import_vtk.SetDataScalarTypeToShort()
        import_vtk.SetNumberOfScalarComponents(1)
        import_vtk.SetDataExtent(0, nx-1, 0, ny-1, 0, nz-1)
        import_vtk.SetWholeExtent(0, nx-1, 0, ny-1, 0, nz-1)
        import_vtk.SetDataSpacing(*spacing)
        import_vtk.SetDataOrigin(*origin_vtk)
        import_vtk.Update()
        
        vtk_image = import_vtk.GetOutput()
        
        mat = vtk.vtkMatrix3x3()
        for r in range(3):
            for c in range(3):
                val = direction[r*3 + c]
                mat.SetElement(r, c, -val if r in (0,1) else val)
        vtk_image.SetDirectionMatrix(mat)
        
        vtk_image.ComputeBounds()
        vtk_image.GetScalarRange()

        self.main_window.coordenador_navegacao.navegador_2d.atualizar_volume(vtk_image)
        self.main_window.coordenador_navegacao.navegador_3d.atualizar_volume(vtk_image)
        
        if hasattr(self.main_window.coordenador_navegacao, 'operador_projecao'):
            self.main_window.coordenador_navegacao.operador_projecao.bounds = vtk_image.GetBounds()
            
        if hasattr(self.main_window.coordenador_exibicao.widget_layout_ativo, "visoes"):
            for quadrante in self.main_window.coordenador_exibicao.widget_layout_ativo.visoes.values():
                if hasattr(quadrante, "interactor") and quadrante.interactor:
                    quadrante.interactor.GetRenderWindow().Render()
