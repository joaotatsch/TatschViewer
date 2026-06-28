# -*- coding: utf-8 -*-
import os
import time
import traceback
import gc
import pydicom
from PyQt6.QtCore import Qt, QTimer, QThread, QObject, pyqtSignal
from carregamento.controlador_arquivos import ControladorArquivos
from carregamento.threads_carregamento import ThreadCarregamento
from carregamento import CoordenadorCarregamento
from ui.custom_widgets import LabelImagemResponsiva
from traducoes import tr
from core.utils_profiling import profiler_time

class GerenciadorEventosArquivos(QObject):
    sinal_progresso_escanear = pyqtSignal(int, int)
    sinal_progresso_exportar = pyqtSignal(int, int)
    sinal_status_mensagem = pyqtSignal(str)
    sinal_erro = pyqtSignal(str, str)
    sinal_fim_progresso = pyqtSignal()
    sinal_cursor_espera = pyqtSignal(bool)

    @profiler_time
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.controlador_arquivos = ControladorArquivos(main_window)
        self._cancelar_operacao = False

    def carregar_diretorio_dicom(self, diretorio: str):
        if not diretorio:
            return
            
        self.sinal_status_mensagem.emit(f"Escaneando diretório: {diretorio}...")
        try:
            self._cancelar_operacao = False

            def update_progress(atual, total):
                self.sinal_progresso_escanear.emit(atual, total)
                return not self._cancelar_operacao

            series = self.controlador_arquivos.escanear_dicom(diretorio, progress_callback=update_progress)
            
            self.sinal_fim_progresso.emit()
            
            if self._cancelar_operacao:
                self.sinal_status_mensagem.emit("Escaneamento cancelado pelo usuário.")
                return
            
            if not series:
                self.sinal_status_mensagem.emit("Nenhuma série DICOM válida encontrada no diretório.")
                return
            
            self.main_window.diretorio_ativo = diretorio
            self.main_window.series_carregadas = series
            
            self._popular_lista_series(series)
            
            self.sinal_status_mensagem.emit("Carregando série DICOM em alta velocidade...")
            
            primeira_serie_id = series[0]["SeriesID"]
            coordenador = CoordenadorCarregamento()
            
            self.main_window.thread_carregamento = ThreadCarregamento(coordenador, series[0]["Files"], primeira_serie_id)
            self.main_window.thread_carregamento.resultado.connect(lambda res: self.on_carregamento_concluido(res, primeira_serie_id))
            self.main_window.thread_carregamento.erro_carregamento.connect(self.on_carregamento_erro)
            self.main_window.thread_manager.active_threads.append(self.main_window.thread_carregamento)
            self.main_window.thread_carregamento.finished.connect(lambda t=self.main_window.thread_carregamento: self.main_window.thread_manager.cleanup_thread(t))
            self.main_window.thread_carregamento.finished.connect(self.main_window.thread_carregamento.deleteLater)
            self.main_window.thread_carregamento.start()
            
        except Exception as e:
            self.sinal_status_mensagem.emit(f"Erro ao analisar diretório DICOM: {str(e)}")
            traceback.print_exc()

    def carregar_arquivo_zip(self, caminho_zip: str):
        if not caminho_zip or not os.path.exists(caminho_zip):
            return
            
        self.sinal_status_mensagem.emit(f"Extraindo e escaneando arquivo ZIP: {caminho_zip}...")
        try:
            series, temp_dir = self.controlador_arquivos.descompactar_zip(caminho_zip)
            
            if not series or not temp_dir:
                self.sinal_status_mensagem.emit("Nenhuma série DICOM válida encontrada no arquivo ZIP.")
                return
                
            if not hasattr(self.main_window, "temp_dirs"):
                self.main_window.temp_dirs = []
            self.main_window.temp_dirs.append(temp_dir)
            
            self.main_window.diretorio_ativo = temp_dir.name
            self.main_window.series_carregadas = series
            
            self._popular_lista_series(series)
            
            self.sinal_status_mensagem.emit("Carregando série DICOM extraída do ZIP...")
            self.sinal_cursor_espera.emit(True)
            
            primeira_serie_id = series[0]["SeriesID"]
            coordenador = CoordenadorCarregamento()
            
            self.main_window.thread_carregamento = ThreadCarregamento(coordenador, series[0]["Files"], primeira_serie_id)
            self.main_window.thread_carregamento.resultado.connect(lambda res: self.on_carregamento_concluido(res, primeira_serie_id))
            self.main_window.thread_carregamento.erro_carregamento.connect(self.on_carregamento_erro)
            self.main_window.thread_manager.active_threads.append(self.main_window.thread_carregamento)
            self.main_window.thread_carregamento.finished.connect(lambda t=self.main_window.thread_carregamento: self.main_window.thread_manager.cleanup_thread(t))
            self.main_window.thread_carregamento.finished.connect(self.main_window.thread_carregamento.deleteLater)
            self.main_window.thread_carregamento.start()
            
        except Exception as e:
            self.sinal_status_mensagem.emit(f"Erro ao carregar arquivo ZIP: {str(e)}")
            traceback.print_exc()

    def carregar_arquivo_nrrd(self, caminho_nrrd: str):
        if not caminho_nrrd or not os.path.exists(caminho_nrrd):
            return
            
        self.sinal_status_mensagem.emit(f"Carregando volume: {caminho_nrrd}...")
        try:
            sitk_img = self.controlador_arquivos.carregar_nrrd(caminho_nrrd)
            self.main_window.gerenciador_processamento.on_subtracao_concluida(sitk_img)
            self.sinal_status_mensagem.emit(f"Volume carregado com sucesso: {caminho_nrrd}")
        except Exception as e:
            self.sinal_status_mensagem.emit(f"Erro ao carregar volume: {str(e)}")
            traceback.print_exc()

    def _popular_lista_series(self, series):
        if hasattr(self.main_window, 'popular_lista_series_ui'):
            self.main_window.popular_lista_series_ui(series)

    def anonimizar_e_exportar(self, series_alvo, diretorio_destino, exportar_todas):
        try:
            total_arquivos = 0
            for s in series_alvo:
                if s and "Files" in s:
                    total_arquivos += len(s["Files"])

            self._cancelar_operacao = False

            def progress_callback(valor):
                self.sinal_progresso_exportar.emit(valor, total_arquivos)

            def check_canceled():
                return self._cancelar_operacao

            sucesso = self.controlador_arquivos.anonimizar_e_exportar(
                series_alvo=series_alvo,
                diretorio_ativo=getattr(self.main_window, 'diretorio_ativo', ''),
                diretorio_destino=diretorio_destino,
                exportar_todas=exportar_todas,
                progress_callback=progress_callback,
                check_canceled=check_canceled
            )

            self.sinal_fim_progresso.emit()

            if self._cancelar_operacao:
                self.sinal_status_mensagem.emit("Anonimização cancelada pelo usuário.")
                return

            if sucesso:
                msg = f"Anonimização concluída com sucesso em: {diretorio_destino}"
                self.sinal_status_mensagem.emit(msg)
            else:
                self.sinal_status_mensagem.emit("Falha parcial ao anonimizar os arquivos.")

        except Exception as e:
            traceback.print_exc()
            self.sinal_status_mensagem.emit(f"Erro no processo de anonimização: {str(e)}")

    def on_carregamento_erro(self, msg):
        self.sinal_erro.emit("Aviso de Carregamento", f"Falha ao carregar a série:\n{msg}")
        self.sinal_status_mensagem.emit(f"Erro durante carregamento multithread.")

    def on_carregamento_concluido(self, resultado_tupla, series_id):
        self.sinal_cursor_espera.emit(False)
        vtk_image, sitk_image, np_view, prop_dicom = resultado_tupla
        
        self.main_window._sitk_img_ref = sitk_image
        self.main_window._np_view_ref = np_view
        self.main_window.vtk_image_ativa = vtk_image
        self.main_window._prop_dicom_ref = prop_dicom
        
        if not hasattr(self.main_window, "buffers_vivos"):
            self.main_window.buffers_vivos = {}
        self.main_window.buffers_vivos[series_id] = (sitk_image, np_view, vtk_image)
        
        try:
            from carregamento.carregamento_dicom import verificar_integridade_fase
            from vtk.util import numpy_support
            
            is_mr = prop_dicom.get("Modality", "") == "MR"

            if is_mr:
                log_auditoria = f"[AUDITORIA] Série: {series_id} | >>> MR_FIX_APLICADO <<< Ressonância (MR) detectada. HU ignorado."
                print(log_auditoria)
                self.sinal_status_mensagem.emit(log_auditoria)
            else:
                scalars = vtk_image.GetPointData().GetScalars()
                media_hu = 0.0
                if scalars is not None:
                    import numpy as np
                    np_arr = numpy_support.vtk_to_numpy(scalars)
                    dims = vtk_image.GetDimensions()
                    np_vol = np_arr.reshape((dims[2], dims[1], dims[0]))
                    cz, cy, cx = dims[2] // 2, dims[1] // 2, dims[0] // 2
                    rz, ry, rx = 5, 5, 5
                    sample = np_vol[
                        max(0, cz-rz):min(dims[2], cz+rz+1),
                        max(0, cy-ry):min(dims[1], cy+ry+1),
                        max(0, cx-rx):min(dims[0], cx+rx+1)
                    ]
                    if sample.size > 0:
                        media_hu = float(np.mean(sample))

                log_auditoria = f"[AUDITORIA] Série: {series_id} | >>> MR_FIX_APLICADO <<< Fase Estimada: {media_hu:.2f} HU"
                print(log_auditoria)
                self.sinal_status_mensagem.emit(log_auditoria)

                nome_fase_esperada = "Pré-Contraste" if "_PRE" in series_id or "PRE" in series_id.upper() else "Outra"

                alerta = verificar_integridade_fase(vtk_image, nome_fase_esperada, series_id)
                if alerta:
                    print(alerta)
                    self.sinal_status_mensagem.emit(f"⚠️ {alerta}")
                    self.sinal_erro.emit("Alerta de Auditoria Médica", alerta)
        except Exception as e_aud:
            pass
            
        if hasattr(self.main_window, 'coordenador_navegacao') and self.main_window.coordenador_navegacao is not None:
            self.main_window.coordenador_navegacao.navegador_2d.update_volume_data(vtk_image)
            self.main_window.coordenador_navegacao.navegador_3d.update_volume_data(vtk_image)
            
            if hasattr(self.main_window.coordenador_navegacao, 'operador_projecao'):
                self.main_window.coordenador_navegacao.operador_projecao.bounds = vtk_image.GetBounds()
        else:
            from navegacao import CoordenadorNavegacao
            self.main_window.coordenador_navegacao = CoordenadorNavegacao(self.main_window)
            self.main_window.coordenador_navegacao.inicializar_visualizacao(
                vtk_image,
                self.main_window.coordenador_exibicao.widget_layout_ativo.visoes,
                janelamento_callback=self.main_window.gerenciador_ferramentas.on_mouse_janelamento_changed,
                espessura_callback=self.main_window.gerenciador_ferramentas.on_mouse_espessura_changed
            )
        
        from exibicao.formatador_hud import formatar_texto_hud
        hud_texto = formatar_texto_hud(prop_dicom)
        self.main_window.coordenador_navegacao.navegador_2d.atualizar_metadados_hud(hud_texto)
        self.main_window.coordenador_navegacao.navegador_3d.atualizar_metadados_hud(hud_texto)

        try:
            if hasattr(self.main_window, 'label_boas_vindas') and self.main_window.label_boas_vindas is not None:
                self.main_window.label_boas_vindas.hide()
                self.main_window.label_boas_vindas.deleteLater()
                self.main_window.label_boas_vindas = None
        except RuntimeError:
            self.main_window.label_boas_vindas = None

        if hasattr(self.main_window, 'coordenador_exibicao'):
            self.main_window.coordenador_exibicao.show()

        self.main_window.modo_projecao_atual = "Normal"
        self.main_window.spin_espessura.blockSignals(True)
        self.main_window.spin_espessura.setValue(0)
        self.main_window.spin_espessura.blockSignals(False)
        if hasattr(self.main_window, 'coordenador_navegacao') and hasattr(self.main_window.coordenador_navegacao, 'operador_projecao'):
            self.main_window.coordenador_navegacao.operador_projecao.aplicar_projecao_global("Normal", 0.0)

        if hasattr(self.main_window, 'coordenador_exibicao') and hasattr(self.main_window.coordenador_exibicao, 'widget_layout_ativo'):
            self.main_window.coordenador_exibicao.show()
            self.main_window.setCentralWidget(self.main_window.coordenador_exibicao)
            
            if getattr(self.main_window, '_layout_explicitamente_escolhido', False):
                self.main_window.gerenciador_layouts.on_visualizacao_changed("4-up")
            else:
                self.main_window.gerenciador_layouts.on_visualizacao_changed("1-up")

        modalidade = prop_dicom.get("Modality", "")
        is_mr_ui = (modalidade == "MR")
        ww_3d, wl_3d = 500.0, 150.0
        if "WindowWidth" in prop_dicom and "WindowCenter" in prop_dicom:
            ww_3d = float(prop_dicom["WindowWidth"])
            wl_3d = float(prop_dicom["WindowCenter"])
            QTimer.singleShot(200, lambda w=ww_3d, l=wl_3d: self.main_window.gerenciador_ferramentas.aplicar_ww_wl(w, l))
        elif not is_mr_ui:
            self.main_window.gerenciador_ferramentas.aplicar_preset_por_nome("angio_tc")

        if hasattr(self.main_window, 'coordenador_navegacao') and hasattr(self.main_window.coordenador_navegacao, 'navegador_3d'):
            self.main_window.coordenador_navegacao.navegador_3d.atualizar_transfer_functions(ww_3d, wl_3d, is_mr=is_mr_ui)
        
        if hasattr(self.main_window.coordenador_exibicao.widget_layout_ativo, "visoes"):
            for visao_nome, widget_vtk in self.main_window.coordenador_exibicao.widget_layout_ativo.visoes.items():
                if hasattr(widget_vtk, "GetRenderWindow") and widget_vtk.GetRenderWindow():
                    widget_vtk.GetRenderWindow().Render()
        
        dim = vtk_image.GetDimensions()
        info_msg = f"Série carregada: {series_id} | Resolução: {dim[0]}x{dim[1]}x{dim[2]}"
        self.sinal_status_mensagem.emit(info_msg)

        def _deferred_update_3d():
            if hasattr(self.main_window, 'coordenador_navegacao') and hasattr(self.main_window.coordenador_navegacao, 'navegador_3d'):
                if self.main_window.coordenador_navegacao.navegador_3d.volume_ator:
                    mapper_3d = self.main_window.coordenador_navegacao.navegador_3d.volume_ator.GetMapper()
                    if mapper_3d:
                        mapper_3d.Update()
            if hasattr(self.main_window, 'coordenador_exibicao') and hasattr(self.main_window.coordenador_exibicao, 'widget_layout_ativo'):
                if hasattr(self.main_window.coordenador_exibicao.widget_layout_ativo, "visoes"):
                    if "3D" in self.main_window.coordenador_exibicao.widget_layout_ativo.visoes:
                        widget_3d = self.main_window.coordenador_exibicao.widget_layout_ativo.visoes["3D"]
                        if hasattr(widget_3d, "GetRenderWindow") and widget_3d.GetRenderWindow():
                            widget_3d.GetRenderWindow().Render()

        QTimer.singleShot(100, _deferred_update_3d)

        if series_id in getattr(self.main_window, 'cache_series', {}):
            del self.main_window.cache_series[series_id]
        if not hasattr(self.main_window, 'cache_series'):
            self.main_window.cache_series = {}
        self.main_window.cache_series[series_id] = resultado_tupla
        if len(self.main_window.cache_series) > 3:
            del self.main_window.cache_series[next(iter(self.main_window.cache_series))]
            
        self._iniciar_cache_preditivo(series_id)

    def carregar_serie_selecionada(self, item):
        if not item or not hasattr(self.main_window, "series_carregadas") or not self.main_window.series_carregadas:
            return
 
        dados = item.data(Qt.ItemDataRole.UserRole)
        if not dados or not isinstance(dados, dict):
            return
            
        # Reset para visualização Axial 1-up ao dar duplo clique se estiver em Múltiplas Telas
        if hasattr(self.main_window, 'coordenador_exibicao') and hasattr(self.main_window.coordenador_exibicao, 'widget_layout_ativo'):
            class_name = type(self.main_window.coordenador_exibicao.widget_layout_ativo).__name__
            if class_name == "LayoutDinamico":
                # Força o reset completo para MPR/1-up antes de prosseguir com o carregamento da nova imagem
                self.main_window._layout_explicitamente_escolhido = False
                if hasattr(self.main_window, 'gerenciador_layouts'):
                    self.main_window.gerenciador_layouts.on_layout_selecionado("MPR")
                    self.main_window.gerenciador_layouts.on_visualizacao_changed("1-up")
            
        if dados.get("virtual"):
            self.sinal_status_mensagem.emit("Carregando Série Virtual instantaneamente...")
            self.main_window.gerenciador_processamento.on_subtracao_concluida(dados["sitk_image"])
            
            nome_serie = item.text()
            if "[SUB]" in nome_serie:
                if hasattr(self.main_window, 'coordenador_navegacao') and hasattr(self.main_window.coordenador_navegacao, 'navegador_3d'):
                    self.main_window.coordenador_navegacao.navegador_3d.aplicar_preset_angio()
            
            return

        series_id = dados.get("id")
        diretorio_serie = dados.get("dir")

        if not series_id or not diretorio_serie:
            self.sinal_status_mensagem.emit("Erro: Dados da série inválidos no item.")
            return

        if series_id in getattr(self.main_window, 'cache_series', {}):
            self.sinal_status_mensagem.emit("⚡ Série em CACHE! Troca instantânea.")
            self.on_carregamento_concluido(self.main_window.cache_series[series_id], series_id)
            return

        if series_id in self.main_window.thread_manager.threads_prefetch:
            thread_bg = self.main_window.thread_manager.threads_prefetch[series_id]
            if thread_bg.isRunning():
                thread_bg.setPriority(QThread.Priority.HighPriority)
                self.sinal_status_mensagem.emit("🔄 Acelerando carregamento em background...")
                self.sinal_cursor_espera.emit(True)

                thread_bg.prefetch_concluido.disconnect()
                thread_bg.prefetch_concluido.connect(
                    lambda res, sid=series_id: self._on_prefetch_promovido(res, sid)
                )
                return

        self.sinal_status_mensagem.emit("Carregando série...")
        self.sinal_cursor_espera.emit(True)

        if hasattr(self.main_window, 'coordenador_navegacao') and self.main_window.coordenador_navegacao is not None:
            if hasattr(self.main_window.coordenador_navegacao, 'navegador_2d'):
                self.main_window.coordenador_navegacao.navegador_2d.atualizar_metadados_hud("CARREGANDO SÉRIE ALTA RESOLUÇÃO...")
            if hasattr(self.main_window.coordenador_navegacao, 'navegador_3d'):
                self.main_window.coordenador_navegacao.navegador_3d.atualizar_metadados_hud("CARREGANDO SÉRIE ALTA RESOLUÇÃO...")

        coordenador = CoordenadorCarregamento()
        arquivos = dados.get("files")
        self.main_window.thread_carregamento = ThreadCarregamento(coordenador, arquivos, series_id)
        self.main_window.thread_carregamento.resultado.connect(lambda res: self.on_carregamento_concluido(res, series_id))
        self.main_window.thread_carregamento.erro_carregamento.connect(self.on_carregamento_erro)
        self.main_window.thread_manager.active_threads.append(self.main_window.thread_carregamento)
        self.main_window.thread_carregamento.finished.connect(lambda t=self.main_window.thread_carregamento: self.main_window.thread_manager.cleanup_thread(t))
        self.main_window.thread_carregamento.finished.connect(self.main_window.thread_carregamento.deleteLater)
        self.main_window.thread_carregamento.start()

    def _iniciar_cache_preditivo(self, series_id_atual):
        if not hasattr(self.main_window, 'list_series'): return

        prox_item = None
        for i in range(self.main_window.list_series.count()):
            item = self.main_window.list_series.item(i)
            dados = item.data(Qt.ItemDataRole.UserRole)
            if dados and dados.get("id") == series_id_atual:
                if i + 1 < self.main_window.list_series.count():
                    prox_item = self.main_window.list_series.item(i + 1)
                break

        if not prox_item:
            return

        dados_prox = prox_item.data(Qt.ItemDataRole.UserRole)
        if not dados_prox:
            return

        prox_id  = dados_prox.get("id")
        arquivos = dados_prox.get("files")

        if not prox_id or not arquivos:
            return
        if prox_id in getattr(self.main_window, 'cache_series', {}):
            return
        if prox_id in self.main_window.thread_manager.threads_prefetch:
            return

        coordenador = CoordenadorCarregamento()
        thread = ThreadCarregamento(coordenador, arquivos, prox_id, prefetch=True)
        thread.prefetch_concluido.connect(self._on_prefetch_concluido)
        self.main_window.thread_manager.active_threads.append(thread)
        thread.finished.connect(lambda t=thread: self.main_window.thread_manager.cleanup_thread(t))
        thread.finished.connect(thread.deleteLater)

        self.main_window.thread_manager.threads_prefetch[prox_id] = thread
        thread.start(QThread.Priority.IdlePriority)

    def _on_prefetch_concluido(self, resultado_tupla, series_id):
        if not hasattr(self.main_window, 'cache_series'):
            self.main_window.cache_series = {}
        if series_id in self.main_window.cache_series:
            del self.main_window.cache_series[series_id]
        self.main_window.cache_series[series_id] = resultado_tupla
        if len(self.main_window.cache_series) > 3:
            del self.main_window.cache_series[next(iter(self.main_window.cache_series))]
        self.main_window.thread_manager.threads_prefetch.pop(series_id, None)

    def _on_prefetch_promovido(self, resultado_tupla, series_id):
        self.sinal_cursor_espera.emit(False)
        self._on_prefetch_concluido(resultado_tupla, series_id)
        self.on_carregamento_concluido(resultado_tupla, series_id)

    def carregar_serie_no_quadrante(self, dados_serie, quadrante):
        series_id = dados_serie.get("id")
        
        if series_id in getattr(self.main_window, 'cache_series', {}):
            tupla = self.main_window.cache_series[series_id]
            vtk_image = tupla[0]
            prop_dicom = tupla[3]
            nome_visao = quadrante.label.text()
            
            if getattr(self.main_window, 'coordenador_navegacao', None) is None:
                from navegacao import CoordenadorNavegacao
                self.main_window.coordenador_navegacao = CoordenadorNavegacao(self.main_window)
                self.main_window.coordenador_navegacao.inicializar_visualizacao(
                    vtk_image,
                    self.main_window.coordenador_exibicao.widget_layout_ativo.visoes,
                    janelamento_callback=self.main_window.gerenciador_ferramentas.on_mouse_janelamento_changed,
                    espessura_callback=self.main_window.gerenciador_ferramentas.on_mouse_espessura_changed
                )
                if hasattr(self.main_window.coordenador_navegacao, 'navegador_3d'):
                    self.main_window.coordenador_navegacao.navegador_3d.atualizar_transfer_functions(500.0, 150.0)
                
                if not hasattr(self.main_window, "buffers_vivos"):
                    self.main_window.buffers_vivos = {}
                self.main_window.buffers_vivos[nome_visao] = (tupla[1], tupla[2], vtk_image)
                return
                
            self.main_window.coordenador_navegacao.inicializar_tela_dinamica(nome_visao, vtk_image, quadrante, self.main_window.gerenciador_ferramentas.on_mouse_janelamento_changed, self.main_window.gerenciador_ferramentas.on_mouse_espessura_changed)
            
            from exibicao.formatador_hud import formatar_texto_hud
            self.main_window.coordenador_navegacao.navegador_2d.meta_actors[nome_visao].SetInput(formatar_texto_hud(prop_dicom))

            if not hasattr(self.main_window, "buffers_vivos"):
                self.main_window.buffers_vivos = {}
            self.main_window.buffers_vivos[nome_visao] = (tupla[1], tupla[2], vtk_image)
            
            QTimer.singleShot(100, gc.collect)
            return
            
        arquivos = dados_serie.get("files")
        if not arquivos:
            return
            
        coordenador = CoordenadorCarregamento()
        
        thread_isolada = ThreadCarregamento(coordenador, arquivos, series_id)
        self.main_window.thread_manager.threads_isoladas.append(thread_isolada)
        
        def on_loaded(res, q=quadrante):
            nome_visao = q.label.text()
            vtk_image, sitk_image, np_view, prop_dicom = res
            
            if getattr(self.main_window, 'coordenador_navegacao', None) is None:
                from navegacao import CoordenadorNavegacao
                self.main_window.coordenador_navegacao = CoordenadorNavegacao(self.main_window)
                self.main_window.coordenador_navegacao.inicializar_visualizacao(
                    vtk_image,
                    self.main_window.coordenador_exibicao.widget_layout_ativo.visoes,
                    janelamento_callback=self.main_window.gerenciador_ferramentas.on_mouse_janelamento_changed,
                    espessura_callback=self.main_window.gerenciador_ferramentas.on_mouse_espessura_changed
                )
                if hasattr(self.main_window.coordenador_navegacao, 'navegador_3d'):
                    self.main_window.coordenador_navegacao.navegador_3d.atualizar_transfer_functions(500.0, 150.0)
                
                if not hasattr(self.main_window, "buffers_vivos"):
                    self.main_window.buffers_vivos = {}
                self.main_window.buffers_vivos[nome_visao] = (sitk_image, np_view, vtk_image)
                return
                
            self.main_window.coordenador_navegacao.inicializar_tela_dinamica(nome_visao, vtk_image, q, self.main_window.gerenciador_ferramentas.on_mouse_janelamento_changed, self.main_window.gerenciador_ferramentas.on_mouse_espessura_changed)
            
            from exibicao.formatador_hud import formatar_texto_hud
            self.main_window.coordenador_navegacao.navegador_2d.meta_actors[nome_visao].SetInput(formatar_texto_hud(prop_dicom))
            
            if not hasattr(self.main_window, "buffers_vivos"):
                self.main_window.buffers_vivos = {}
            self.main_window.buffers_vivos[nome_visao] = (sitk_image, np_view, vtk_image)
                
            QTimer.singleShot(100, gc.collect)
            
        thread_isolada.resultado.connect(on_loaded)
        self.main_window.thread_manager.active_threads.append(thread_isolada)
        thread_isolada.finished.connect(lambda t=thread_isolada: self.main_window.thread_manager.cleanup_thread(t))
        thread_isolada.finished.connect(thread_isolada.deleteLater)
        thread_isolada.start()
