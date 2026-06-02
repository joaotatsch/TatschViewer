"""
Módulo principal de interface do usuário do Neuroviewer.
"""
import os
import sys
import time
from PyQt6.QtWidgets import (
    QMainWindow, QApplication, QToolBar, QFileDialog, QDockWidget, 
    QListWidget, QListWidgetItem, QComboBox, QSpinBox, QLabel, QToolButton, QMenu,
    QPushButton, QStyle, QProgressDialog, QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QAction, QIcon
import SimpleITK as sitk
import vtk
import traceback

from exibicao import CoordenadorExibicao

class ThreadCarregamento(QThread):
    resultado = pyqtSignal(object)
    erro_carregamento = pyqtSignal(str)
    resultado_cache_silencioso = pyqtSignal(object, str)
    prefetch_concluido = pyqtSignal(object, str)   # novo: sinal de pré-busca concluída

    def __init__(self, coordenador, diretorio, series_id, silencioso=False, prefetch=False):
        super().__init__()
        self.coordenador = coordenador
        self.diretorio = diretorio
        self.series_id = series_id
        self.silencioso = silencioso
        self.prefetch = prefetch

    def run(self):
        try:
            resultado = self.coordenador.carregar_serie(self.diretorio, self.series_id)
            if self.prefetch:
                self.prefetch_concluido.emit(resultado, self.series_id)
            elif self.silencioso:
                self.resultado_cache_silencioso.emit(resultado, self.series_id)
            else:
                self.resultado.emit(resultado)
        except Exception as e:
            if not self.silencioso and not self.prefetch:
                self.erro_carregamento.emit(str(e))
            else:
                print(f"[PREFETCH] Erro no background: {e}")

from processamento_imagem.subtracao_ossea import OperadorSubtracaoOssea

class ThreadSubtracaoLenta(QThread):
    progresso_sinal = pyqtSignal(int, float)
    log_sinal = pyqtSignal(str)
    virtual_sinal = pyqtSignal(object, object, str)  # vtk_image, sitk_image, nome_serie
    concluido_sinal = pyqtSignal(str)
    erro_sinal = pyqtSignal(str)

    def __init__(self, sitk_sem_contraste, sitk_angio):
        super().__init__()
        self.sitk_sem_contraste = sitk_sem_contraste
        self.sitk_angio = sitk_angio

    def run(self):
        try:
            self.log_sinal.emit("Carregando imagens da memória...")
            fixed_image = sitk.Cast(self.sitk_angio, sitk.sitkFloat32)
            moving_image = sitk.Cast(self.sitk_sem_contraste, sitk.sitkFloat32)

            self.log_sinal.emit("Configurando Registro de Imagem...")
            registration_method = sitk.ImageRegistrationMethod()
            
            # Métrica e Amostragem (Ajuste Fino)
            registration_method.SetMetricAsMeanSquares()
            registration_method.SetMetricSamplingStrategy(registration_method.RANDOM)
            registration_method.SetMetricSamplingPercentage(0.10)
            
            # Pirâmide de Múltiplas Resoluções (Obrigatório para Z assimétrico)
            registration_method.SetShrinkFactorsPerLevel(shrinkFactors=[4, 2, 1])
            registration_method.SetSmoothingSigmasPerLevel(smoothingSigmas=[2, 1, 0])
            registration_method.SmoothingSigmasAreSpecifiedInPhysicalUnitsOn()
            
            # Interpolador
            registration_method.SetInterpolator(sitk.sitkLinear)
            
            # Otimizador com Parameter Scaling
            registration_method.SetOptimizerAsRegularStepGradientDescent(
                learningRate=1.0, minStep=1e-4, numberOfIterations=100
            )
            registration_method.SetOptimizerScalesFromPhysicalShift()
            
            # Inicialização Baseada em Geometria (Exames da mesma máquina)
            initial_transform = sitk.CenteredTransformInitializer(
                fixed_image, moving_image, sitk.Euler3DTransform(), 
                sitk.CenteredTransformInitializerFilter.GEOMETRY
            )
            registration_method.SetInitialTransform(initial_transform, inPlace=False)

            def command_iteration():
                it = registration_method.GetOptimizerIteration()
                val = registration_method.GetMetricValue()
                self.progresso_sinal.emit(it, val)

            registration_method.AddCommand(sitk.sitkIterationEvent, command_iteration)

            self.log_sinal.emit("Iniciando Otimização (Alinhamento 3D)...")
            final_transform = registration_method.Execute(fixed_image, moving_image)

            self.log_sinal.emit("Realizando Resampling...")
            resampled_moving = sitk.Resample(
                moving_image, fixed_image, final_transform, sitk.sitkLinear, 0.0, moving_image.GetPixelID()
            )

            # --- Novo Algoritmo de Mascaramento Ósseo e Subtração ---
            self.log_sinal.emit("Criando Máscara Óssea (Threshold)...")
            mask_osso = sitk.BinaryThreshold(resampled_moving, lowerThreshold=150.0, upperThreshold=3000.0, insideValue=1, outsideValue=0)
            
            self.log_sinal.emit("Dilatando Máscara (Margem de Segurança)...")
            mask_osso_dilatada = sitk.BinaryDilate(mask_osso, [2, 2, 2])

            self.log_sinal.emit("Zerar Osso na Fase Angio-TC...")
            angio_sem_osso = sitk.MaskNegated(fixed_image, mask_osso_dilatada)

            self.log_sinal.emit("Zerar Osso na Fase Sem Contraste...")
            resampled_moving_sem_osso = sitk.MaskNegated(resampled_moving, mask_osso_dilatada)

            self.log_sinal.emit("Executando Subtração Final (Tecidos Moles)...")
            subtracted_image = sitk.Subtract(angio_sem_osso, resampled_moving_sem_osso)

            self.log_sinal.emit("Aplicando Limpeza Agressiva (Partes Moles)...")
            import sys
            dsa_result = sitk.Threshold(subtracted_image, lower=50.0, upper=sys.float_info.max, outsideValue=-1024.0)
            dsa_result = sitk.Cast(dsa_result, sitk.sitkInt16)
            
            self.log_sinal.emit("Convertendo para formato VTK...")
            import numpy as np
            import vtk
            np_array = sitk.GetArrayFromImage(dsa_result)
            if not np_array.flags["C_CONTIGUOUS"]:
                np_array = np.ascontiguousarray(np_array)
            
            spacing = dsa_result.GetSpacing()
            origin = dsa_result.GetOrigin()
            direction = dsa_result.GetDirection()
            
            dims = np_array.shape
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
            
            # Vincula o numpy array ao vtk_image para proteção de GC
            vtk_image._np_ref = np_array
            
            self.log_sinal.emit("Concluído!")
            self.virtual_sinal.emit(vtk_image, dsa_result, "Série Virtual: [SUB] Lenta (Gabarito)")
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.erro_sinal.emit(str(e))

class ThreadSubtracaoRapida(QThread):
    progresso_sinal = pyqtSignal(int, float)
    log_sinal = pyqtSignal(str)
    virtual_sinal = pyqtSignal(object, object, str)  # vtk_image, sitk_image, nome_serie
    erro_sinal = pyqtSignal(str)

    def __init__(self, sitk_image):
        super().__init__()
        self.sitk_image = sitk_image

    def run(self):
        try:
            self.log_sinal.emit("Iniciando Subtração Rápida (Core-Bone Shielding)...")
            import gc
            import sys
            import numpy as np
            import vtk
            from vtkmodules.util import numpy_support
            
            # 1. Recupera o volume original (já na RAM, zero leitura de disco)
            img_original = self.sitk_image
            
            # 2. Threshold do "Osso Duro" (Cortical)
            self.log_sinal.emit("Isolando núcleo de osso cortical (> 400 HU)...")
            mask_osso_duro = sitk.BinaryThreshold(
                img_original, 
                lowerThreshold=400.0, 
                upperThreshold=3000.0, 
                insideValue=1, 
                outsideValue=0
            )
            
            # 3. Dilatar o Osso Duro (Escudo)
            self.log_sinal.emit("Expandindo escudo ósseo (cobrindo esponjoso)...")
            mask_osso_dilatado = sitk.BinaryDilate(mask_osso_duro, [2, 2, 2])
            del mask_osso_duro
            gc.collect()
            
            # 4. Mascarar (Zerar o osso na imagem original)
            self.log_sinal.emit("Removendo ossos da imagem original...")
            img_sem_osso = sitk.MaskNegated(img_original, mask_osso_dilatado)
            del mask_osso_dilatado
            gc.collect()
            
            # 5. Limpeza de Tecidos Moles (Filtro DSA)
            self.log_sinal.emit("Limpando partes moles e ar (< 120 HU)...")
            resultado_sitk = sitk.Threshold(
                img_sem_osso, 
                lower=120.0, 
                upper=sys.float_info.max, 
                outsideValue=-1024.0
            )
            del img_sem_osso
            gc.collect()
            
            self.log_sinal.emit("Convertendo para formato VTK...")
            np_array = sitk.GetArrayFromImage(resultado_sitk)
            if not np_array.flags["C_CONTIGUOUS"]:
                np_array = np.ascontiguousarray(np_array)
            
            spacing = resultado_sitk.GetSpacing()
            origin = resultado_sitk.GetOrigin()
            direction = resultado_sitk.GetDirection()
            
            dims = np_array.shape
            nx, ny, nz = dims[2], dims[1], dims[0]
            
            if len(origin) >= 3:
                origin_vtk = [-origin[0], -origin[1], origin[2]]
            else:
                origin_vtk = [0.0, 0.0, 0.0]
                
            vtk_array = numpy_support.numpy_to_vtk(num_array=np_array.ravel(), deep=False, array_type=vtk.VTK_SHORT)
            
            vtk_image = vtk.vtkImageData()
            vtk_image.SetDimensions(nx, ny, nz)
            vtk_image.SetSpacing(*spacing)
            vtk_image.SetOrigin(*origin_vtk)
            vtk_image.GetPointData().SetScalars(vtk_array)
            
            mat = vtk.vtkMatrix3x3()
            for r in range(3):
                for c in range(3):
                    val = direction[r*3 + c]
                    mat.SetElement(r, c, -val if r in (0,1) else val)
            vtk_image.SetDirectionMatrix(mat)
            vtk_image.ComputeBounds()
            
            # Vincula o numpy array ao vtk_image para proteção de GC
            vtk_image._np_ref = np_array
            
            self.log_sinal.emit("Concluído!")
            self.virtual_sinal.emit(vtk_image, resultado_sitk, "Série Virtual: [SUB] Rápida (Máscara Cortical)")
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.erro_sinal.emit(str(e))


class ThreadSubtracaoSemente(QThread):
    progresso_sinal = pyqtSignal(int, str)
    log_sinal = pyqtSignal(str)
    virtual_sinal = pyqtSignal(object, object, str)
    erro_sinal = pyqtSignal(str)

    def __init__(self, sitk_image_input, seed_index):
        super().__init__()
        self.sitk_image_input = sitk_image_input
        self.seed_index = seed_index

    def run(self):
        try:
            self.log_sinal.emit("Iniciando Subtração Guiada por Semente...")
            import gc
            import sys
            import numpy as np
            import vtk
            from vtkmodules.util import numpy_support
            import SimpleITK as sitk

            img_original = self.sitk_image_input
            seed_x = max(0, int(self.seed_index[0]))
            seed_y = max(0, int(self.seed_index[1]))
            seed_z = max(0, int(self.seed_index[2]))

            self.progresso_sinal.emit(10, "Calculando escudo ósseo cortical...")
            self.log_sinal.emit("1. Criando escudo ósseo (Aceiro)...")
            # 1. Escudo de Osso (Aceiro contra a base do crânio)
            # Protege > 500 HU e dilata apenas 1 voxel para isolar o polígono de Willis
            mask_osso = sitk.BinaryThreshold(img_original, lowerThreshold=500.0, upperThreshold=3000.0)
            mask_osso_dil = sitk.BinaryDilate(mask_osso, [1, 1, 1])
            img_sem_osso = sitk.MaskNegated(img_original, mask_osso_dil)
            del mask_osso, mask_osso_dil
            gc.collect()

            self.log_sinal.emit("2. Suavização para rastreamento de vasos finos...")
            # 2. Suavização Rastreadora (O Segredo para Vasos Finos)
            # Aplica um leve blur gaussiano apenas para o algoritmo de rastreamento.
            # Isso cria "pontes" matemáticas sobre o ruído que quebra a continuidade dos vasos finos.
            img_suavizada = sitk.SmoothingRecursiveGaussian(img_sem_osso, sigma=0.5)

            self.progresso_sinal.emit(40, "Inundando árvore vascular a partir da semente...")
            self.log_sinal.emit("3. Inundação Vascular Guiada...")
            # 3. Inundação (Region Growing)
            rg_filter = sitk.ConnectedThresholdImageFilter()
            # Piso rebaixado para 90 HU para permitir que a tinta flua por capilares e colaterais
            rg_filter.SetLower(90.0) 
            rg_filter.SetUpper(500.0)
            rg_filter.SetReplaceValue(1)
            rg_filter.AddSeed((seed_x, seed_y, seed_z))

            # Executa a inundação na imagem suavizada
            mask_vasos = rg_filter.Execute(img_suavizada)
            del img_suavizada
            gc.collect()

            self.progresso_sinal.emit(70, "Refinando capilares e colaterais...")
            self.log_sinal.emit("4. Dilatação e Restauração de Bordas...")
            # 4. Dilatação de Restauração
            # Recupera a espessura calibrada das bordas dos vasos finos
            mask_vasos = sitk.BinaryDilate(mask_vasos, [1, 1, 1])

            self.log_sinal.emit("5. Aplicação da Máscara de Alta Resolução...")
            # 5. Aplicação da Máscara na Imagem ORIGINAL (Alta Resolução)
            img_final = sitk.Mask(img_original, mask_vasos)
            del mask_vasos
            gc.collect()

            self.log_sinal.emit("6. Limpeza do fundo para o Preset 3D...")
            # 6. Limpeza do fundo para o Preset 3D (Ar invisível)
            resultado_final = sitk.Threshold(
                img_final, 
                lower=50.0, 
                upper=sys.float_info.max, 
                outsideValue=-1024.0
            )
            del img_final
            gc.collect()

            self.progresso_sinal.emit(100, "Finalizando reconstrução 3D...")
            self.log_sinal.emit("Convertendo para VTK (Zero-Copy)...")
            np_array = sitk.GetArrayFromImage(resultado_final)
            if not np_array.flags["C_CONTIGUOUS"]:
                np_array = np.ascontiguousarray(np_array)
            
            spacing = resultado_final.GetSpacing()
            origin = resultado_final.GetOrigin()
            direction = resultado_final.GetDirection()
            
            dims = np_array.shape
            nx, ny, nz = dims[2], dims[1], dims[0]
            
            if len(origin) >= 3:
                origin_vtk = [-origin[0], -origin[1], origin[2]]
            else:
                origin_vtk = [0.0, 0.0, 0.0]
                
            vtk_array = numpy_support.numpy_to_vtk(num_array=np_array.ravel(), deep=False, array_type=vtk.VTK_SHORT)
            
            vtk_image = vtk.vtkImageData()
            vtk_image.SetDimensions(nx, ny, nz)
            vtk_image.SetSpacing(*spacing)
            vtk_image.SetOrigin(*origin_vtk)
            vtk_image.GetPointData().SetScalars(vtk_array)
            
            mat = vtk.vtkMatrix3x3()
            for r in range(3):
                for c in range(3):
                    val = direction[r*3 + c]
                    mat.SetElement(r, c, -val if r in (0,1) else val)
            vtk_image.SetDirectionMatrix(mat)
            vtk_image.ComputeBounds()
            
            vtk_image._np_ref = np_array
            
            self.log_sinal.emit("Subtração Guiada Concluída!")
            self.virtual_sinal.emit(vtk_image, resultado_final, "Série Virtual: [SUB] Guiada (Semente)")
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.erro_sinal.emit(str(e))


class ThreadSubtracaoOssea(QThread):
    resultado = pyqtSignal(object)
    erro = pyqtSignal(str)

    def __init__(self, sitk_image):
        super().__init__()
        self.sitk_image = sitk_image

    def run(self):
        try:
            operador = OperadorSubtracaoOssea()
            resultado_img = operador.executar_subtracao_rapida(self.sitk_image)
            self.resultado.emit(resultado_img)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.erro.emit(str(e))




class MainWindow(QMainWindow):
    """
    Classe principal responsável por organizar toda a interface do usuário (UI),
    incluindo menus, barras de ferramentas, painéis laterais e áreas de visualização.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Neuroviewer - Visualizador DICOM")
        self.resize(1200, 800)
        
        # Habilita Drag and Drop
        self.setAcceptDrops(True)
        
        # Referências de segurança de memória para o buffer DICOM
        self._sitk_img_ref = None
        self._np_view_ref = None
        self.temp_dirs = []
        self.modo_projecao_atual = "Normal"
        self.cache_series = {}
        # Dicionário de threads de pré-busca ativas: series_id -> ThreadCarregamento
        self._threads_prefetch: dict = {}
        
        
        self.inicializar_ui()

    def inicializar_ui(self):
        """
        Estrutura e carrega todos os componentes visuais principais da janela.
        """
        # 1. Configuração do Visual Clínico Dark Mode
        self.setStyleSheet("""
            QMainWindow {
                background-color: #121212;
            }
            QToolBar {
                background-color: #1a1a1a;
                border-bottom: 1px solid #2d2d2d;
                spacing: 12px;
                padding: 6px;
            }
            QStatusBar {
                background-color: #1a1a1a;
                color: #888888;
                border-top: 1px solid #2d2d2d;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 11px;
            }
        """)

        # 2. Barra de Status para feedback ao usuário
        self.statusBar().showMessage("Pronto")

        # 3. Criação da Barra de Ferramentas (QToolBar) no Topo
        self.toolbar = QToolBar("Barra de Ferramentas Principal", self)
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)
        self.toolbar.setIconSize(QSize(36, 36))
        
        # Ação: Abrir Pasta
        self.action_abrir = QAction("Abrir Pasta", self)
        self.action_abrir.setIcon(QIcon(os.path.join("icones", "abrir_pasta.png")))
        self.action_abrir.setStatusTip("Seleciona um diretório contendo arquivos DICOM")
        self.action_abrir.triggered.connect(self.abrir_pasta)
        
        # Ação: Anonimizar e Exportar
        self.action_anonimizar = QAction("Anonimizar", self)
        self.action_anonimizar.setIcon(QIcon(os.path.join("icones", "anonimizar.png")))
        self.action_anonimizar.setStatusTip("Anonimiza e exporta a série ativa para um novo diretório")
        self.action_anonimizar.triggered.connect(self.anonimizar_e_exportar)

        # (Botão de subtração foi movido para o final da toolbar)

        # Estilo padrão para botões da barra de ferramentas
        for action in [self.action_abrir, self.action_anonimizar]:
            widget = self.toolbar.widgetForAction(action)
            if widget:
                widget.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
                widget.setStyleSheet("""
                    QToolButton {
                        background-color: #2a2a2a;
                        color: #e0e0e0;
                        border: 1px solid #3d3d3d;
                        border-radius: 4px;
                        padding: 4px;
                        font-family: 'Segoe UI', Arial, sans-serif;
                        font-size: 12px;
                        font-weight: bold;
                    }
                    QToolButton:hover {
                        background-color: #353535;
                        border-color: #555555;
                        color: #ffffff;
                    }
                    QToolButton:pressed {
                        background-color: #121212;
                        border-color: #007acc;
                        color: #007acc;
                    }
                """)

        # Menu de Presets Unificado
        self.btn_presets = QToolButton(self)
        self.btn_presets.setIcon(QIcon(os.path.join("icones", "janelamento.png")))
        self.btn_presets.setIconSize(QSize(36, 36))
        self.btn_presets.setToolTip("Janelamento / Presets")
        self.btn_presets.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.menu_presets = QMenu(self.btn_presets)
        self.menu_presets.setStyleSheet("""
            QMenu {
                background-color: #1a1a1a;
                color: #e0e0e0;
                border: 1px solid #3d3d3d;
                padding: 4px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
                border-radius: 4px;
            }
            QMenu::item {
                padding: 8px 24px 8px 12px;
                border-radius: 4px;
                margin: 2px;
            }
            QMenu::item:selected {
                background-color: #007acc;
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background-color: #3d3d3d;
                margin: 4px 8px;
            }
        """)
        
        # Grupo Neuro
        self.action_header_neuro = self.menu_presets.addAction("[Grupo Neuro]")
        self.action_header_neuro.setEnabled(False)
        self.action_preset_angiotc = self.menu_presets.addAction("Angio-TC Vascular (WW: 600 / WL: 150)")
        self.action_preset_cerebro = self.menu_presets.addAction("Cérebro Genérico (WW: 80 / WL: 40)")
        self.action_preset_avc = self.menu_presets.addAction("AVC Isquêmico (WW: 35 / WL: 35)")
        self.action_preset_hemorragia = self.menu_presets.addAction("Hemorragia Aguda (WW: 160 / WL: 120)")
        
        self.menu_presets.addSeparator()
        
        # Grupo Corpo
        self.action_header_corpo = self.menu_presets.addAction("[Grupo Corpo]")
        self.action_header_corpo.setEnabled(False)
        self.action_preset_osso = self.menu_presets.addAction("Osso (WW: 2000 / WL: 500)")
        self.action_preset_pulmao = self.menu_presets.addAction("Pulmão (WW: 1500 / WL: -600)")
        self.action_preset_mediastino = self.menu_presets.addAction("Mediastino (WW: 350 / WL: 50)")
        self.action_preset_abdome = self.menu_presets.addAction("Abdome (WW: 400 / WL: 40)")
        
        self.menu_presets.addSeparator()
        
        # Outros
        self.action_header_outros = self.menu_presets.addAction("[Outros]")
        self.action_header_outros.setEnabled(False)
        self.action_preset_customizado = self.menu_presets.addAction("Customizado...")
        
        self.presets_clinicos = {
            "angio_tc": {"ww": 600, "wl": 150, "nome": "Angio-TC Vascular"},
            "cerebro": {"ww": 80, "wl": 40, "nome": "Cérebro Genérico"},
            "avc_isquemico": {"ww": 35, "wl": 35, "nome": "AVC Isquêmico"},
            "hemorragia": {"ww": 160, "wl": 120, "nome": "Hemorragia Aguda"},
            "osso": {"ww": 2000, "wl": 500, "nome": "Osso"},
            "pulmao": {"ww": 1500, "wl": -600, "nome": "Pulmão"},
            "mediastino": {"ww": 350, "wl": 50, "nome": "Mediastino"},
            "abdome": {"ww": 400, "wl": 40, "nome": "Abdome"},
            "customizado": {"ww": 0, "wl": 0, "nome": "Customizado"}
        }
        
        # CORREÇÃO: lambda com parâmetro `checked` explícito para blindar o booleano
        # que o PyQt6 envia automaticamente via QAction.triggered(checked: bool)
        self.action_preset_angiotc.triggered.connect(lambda checked, k="angio_tc": self.on_preset_changed(k))
        self.action_preset_cerebro.triggered.connect(lambda checked, k="cerebro": self.on_preset_changed(k))
        self.action_preset_avc.triggered.connect(lambda checked, k="avc_isquemico": self.on_preset_changed(k))
        self.action_preset_hemorragia.triggered.connect(lambda checked, k="hemorragia": self.on_preset_changed(k))
        self.action_preset_osso.triggered.connect(lambda checked, k="osso": self.on_preset_changed(k))
        self.action_preset_pulmao.triggered.connect(lambda checked, k="pulmao": self.on_preset_changed(k))
        self.action_preset_mediastino.triggered.connect(lambda checked, k="mediastino": self.on_preset_changed(k))
        self.action_preset_abdome.triggered.connect(lambda checked, k="abdome": self.on_preset_changed(k))
        self.action_preset_customizado.triggered.connect(lambda checked, k="customizado": self.on_preset_changed(k))
        
        self.btn_presets.setMenu(self.menu_presets)
        self.btn_presets.setStyleSheet("""
            QToolButton {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 4px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
                font-weight: bold;
            }
            QToolButton::menu-indicator { image: none; }
            QToolButton:hover { background-color: #353535; }
        """)
        
        
        self.btn_mip = QToolButton(self)
        self.btn_mip.setIcon(QIcon(os.path.join("icones", "mip.png")))
        self.btn_mip.setIconSize(QSize(36, 36))
        self.btn_mip.setToolTip("Modos de Projeção (MIP)")
        self.btn_mip.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_mip.setStyleSheet(self.btn_presets.styleSheet())
        
        self.menu_mip = QMenu(self.btn_mip)
        self.menu_mip.setStyleSheet(self.menu_presets.styleSheet())
        
        for modo in ["Normal", "MIP", "MinIP", "Average"]:
            action = self.menu_mip.addAction(modo)
            action.triggered.connect(lambda checked, m=modo: self.on_projecao_changed(m))
        self.btn_mip.setMenu(self.menu_mip)
        

        # Botão Layout Dinâmico
        self.btn_layout = QToolButton(self)
        self.btn_layout.setIcon(QIcon(os.path.join("icones", "multiplas_telas.png")))
        self.btn_layout.setIconSize(QSize(36, 36))
        self.btn_layout.setToolTip("Layouts de Exibição")
        self.btn_layout.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_layout.setStyleSheet(self.btn_presets.styleSheet())
        
        self.menu_layout = QMenu(self.btn_layout)
        self.menu_layout.setStyleSheet(self.menu_presets.styleSheet())
        
        layout_acoes = {
            "MPR Clássico (4-Up)": "MPR",
            "Comparação Lado a Lado (1x2)": "1x2",
            "Comparação Tripla (1x3)": "1x3",
            "Grade (2x2)": "2x2",
            "Grade (2x3)": "2x3"
        }
        for nome_acao, modo_acao in layout_acoes.items():
            action = self.menu_layout.addAction(nome_acao)
            action.triggered.connect(lambda checked, m=modo_acao: self.on_layout_selecionado(m))
        self.btn_layout.setMenu(self.menu_layout)
        
        # QSpinBox para Espessura
        self.spin_espessura = QSpinBox(self)
        self.spin_espessura.setSuffix(" mm")
        self.spin_espessura.setToolTip("Espessura do Slab (MIP)")
        self.spin_espessura.setRange(0, 50)
        self.spin_espessura.setValue(0)
        self.spin_espessura.setFixedWidth(85)
        self.spin_espessura.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spin_espessura.setStyleSheet("""
            QSpinBox {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 4px 6px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-weight: bold;
                font-size: 12px;
            }
        """)
        self.spin_espessura.valueChanged.connect(self.on_projecao_changed)
        
        
        # Botão Crosshair
        self.btn_crosshair = QPushButton("⌖", self)
        self.btn_crosshair.setToolTip("Ativar Mira 3D (Crosshair)")
        self.btn_crosshair.setCheckable(True)
        self.btn_crosshair.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a; color: #e0e0e0;
                border: 1px solid #3d3d3d; border-radius: 4px;
                padding: 4px; font-size: 22px; /* Transforma o caractere em ícone */
                min-width: 32px; max-width: 32px; min-height: 28px;
            }
            QPushButton:checked { background-color: #007acc; color: #ffffff; }
        """)
        self.btn_crosshair.toggled.connect(self.on_crosshair_toggled)
        
        self.btn_regua = QToolButton(self)
        self.btn_regua.setIcon(QIcon(os.path.join("icones", "regua.png")))
        self.btn_regua.setIconSize(QSize(36, 36))
        self.btn_regua.setToolTip("Medida (Régua 3D)")
        self.btn_regua.setCheckable(True)
        self.btn_regua.setStyleSheet("""
            QToolButton {
                background-color: #2a2a2a; border: 1px solid #3d3d3d;
                border-radius: 4px; padding: 4px;
            }
            QToolButton:hover { background-color: #353535; }
            QToolButton:checked { background-color: #007acc; border-color: #007acc; }
        """)
        self.btn_regua.toggled.connect(self.on_regua_toggled)
        
        self.btn_elipse = QToolButton(self)
        self.btn_elipse.setIcon(QIcon(os.path.join("icones", "elipse.png")))
        self.btn_elipse.setIconSize(QSize(36, 36))
        self.btn_elipse.setToolTip("ROI (Elipse 3D)")
        self.btn_elipse.setCheckable(True)
        self.btn_elipse.setStyleSheet("""
            QToolButton {
                background-color: #2a2a2a; border: 1px solid #3d3d3d;
                border-radius: 4px; padding: 4px;
            }
            QToolButton:hover { background-color: #353535; }
            QToolButton:checked { background-color: #007acc; border-color: #007acc; }
        """)
        self.btn_elipse.toggled.connect(self.on_elipse_toggled)

        self.btn_reslice = QToolButton(self)
        self.btn_reslice.setIcon(QIcon(os.path.join("icones", "reslice.png")))
        self.btn_reslice.setIconSize(QSize(36, 36))
        self.btn_reslice.setToolTip("Reslice Oblíquo")
        self.btn_reslice.setCheckable(True)
        self.btn_reslice.setStyleSheet("""
            QToolButton {
                background-color: #2a2a2a; border: 1px solid #3d3d3d;
                border-radius: 4px; padding: 4px;
            }
            QToolButton:hover { background-color: #353535; }
            QToolButton:checked { background-color: #007acc; border-color: #007acc; }
        """)
        self.btn_reslice.toggled.connect(self.on_reslice_toggled)

        
        self.btn_subtracao_ossea = QToolButton(self)
        self.btn_subtracao_ossea.setIcon(QIcon(os.path.join("icones", "subtracao_ossea.png")))
        self.btn_subtracao_ossea.setIconSize(QSize(36, 36))
        self.btn_subtracao_ossea.setToolTip("Subt. Óssea")
        self.btn_subtracao_ossea.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        
        self.menu_subtracao = QMenu(self.btn_subtracao_ossea)
        
        self.action_subtracao_rapida = QAction("Subt. rápida", self)
        self.action_subtracao_rapida.triggered.connect(self.ativar_ferramenta_semente_dsa)
        
        self.action_subtracao_lenta = QAction("Subt. lenta", self)
        self.action_subtracao_lenta.triggered.connect(self.iniciar_subtracao_lenta)
        
        self.menu_subtracao.addAction(self.action_subtracao_rapida)
        self.menu_subtracao.addAction(self.action_subtracao_lenta)
        self.btn_subtracao_ossea.setMenu(self.menu_subtracao)
        
        self.btn_subtracao_ossea.setStyleSheet("""
            QToolButton {
                background-color: #2a2a2a; border: 1px solid #3d3d3d;
                border-radius: 4px; padding: 4px;
            }
            QToolButton:hover { background-color: #353535; }
            QToolButton:pressed { background-color: #121212; border-color: #007acc; color: #007acc; }
        """)


        # Botão Sync Scroll
        self.btn_sync_scroll = QPushButton("🔗", self)
        self.btn_sync_scroll.setToolTip("Sincronizar Navegação (Scroll)")
        self.btn_sync_scroll.setCheckable(True)
        self.btn_sync_scroll.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a; color: #e0e0e0;
                border: 1px solid #3d3d3d; border-radius: 4px;
                padding: 4px; font-size: 18px;
                min-width: 32px; max-width: 32px; min-height: 28px;
            }
            QPushButton:checked { background-color: #27ae60; color: #ffffff; border-color: #27ae60; }
            QPushButton:hover   { background-color: #353535; }
        """)


        # Menu Dissecção 3D (Box Cropping)
        self.btn_disseccao = QToolButton(self)
        self.btn_disseccao.setText("Dissecção")
        self.btn_disseccao.setIcon(QIcon(os.path.join("icones", "disseccao.png")))
        self.btn_disseccao.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.btn_disseccao.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_disseccao.setStyleSheet(self.btn_presets.styleSheet())
        
        self.menu_disseccao = QMenu(self.btn_disseccao)
        self.menu_disseccao.setStyleSheet(self.menu_presets.styleSheet())
        
        self.menu_cubo = QMenu("Cubo de interesse", self.menu_disseccao)
        self.menu_cubo.setIcon(QIcon(os.path.join("icones", "cubo.png")))
        self.menu_cubo.setStyleSheet(self.menu_presets.styleSheet())
        
        self.action_caixa_recorte = QAction("Caixa de Recorte", self)
        self.action_caixa_recorte.setIcon(QIcon(os.path.join("icones", "tesoura.png")))
        self.action_caixa_recorte.setCheckable(True)
        self.action_caixa_recorte.triggered.connect(self.on_box_adjust_toggled)
        
        self.action_aplicar_recorte = QAction("Aplicar Recorte", self)
        self.action_aplicar_recorte.setIcon(QIcon(os.path.join("icones", "tesoura.png")))
        self.action_aplicar_recorte.triggered.connect(self.on_box_apply_clicked)
        
        self.action_resetar_3d = QAction("Resetar 3D", self)
        self.action_resetar_3d.setIcon(QIcon(os.path.join("icones", "reset.png")))
        self.action_resetar_3d.triggered.connect(self.on_box_reset_clicked)
        
        self.menu_cubo.addAction(self.action_caixa_recorte)
        self.menu_cubo.addAction(self.action_aplicar_recorte)
        self.menu_cubo.addAction(self.action_resetar_3d)
        
        self.menu_bisturi = QMenu("Bisturi de Mão Livre", self.menu_disseccao)
        self.menu_bisturi.setIcon(QIcon(os.path.join("icones", "bisturi.png")))
        self.menu_bisturi.setStyleSheet(self.menu_presets.styleSheet())
        
        self.action_bisturi_desenhar = QAction("Desenhar Contorno", self)
        self.action_bisturi_desenhar.setIcon(QIcon(os.path.join("icones", "elipse.png")))
        self.action_bisturi_desenhar.setCheckable(True)
        self.action_bisturi_desenhar.triggered.connect(self.on_bisturi_toggled)
        
        self.action_bisturi_cortar_interior = QAction("Cortar interior", self)
        self.action_bisturi_cortar_interior.setIcon(QIcon(os.path.join("icones", "tesoura.png")))
        self.action_bisturi_cortar_interior.triggered.connect(lambda: self.on_bisturi_aplicar_clicked(cortar_fora=False))
        
        self.action_bisturi_cortar_exterior = QAction("Cortar exterior", self)
        self.action_bisturi_cortar_exterior.setIcon(QIcon(os.path.join("icones", "tesoura.png")))
        self.action_bisturi_cortar_exterior.triggered.connect(lambda: self.on_bisturi_aplicar_clicked(cortar_fora=True))
        
        self.action_bisturi_reset = QAction("Restaurar Original", self)
        self.action_bisturi_reset.setIcon(QIcon(os.path.join("icones", "reset.png")))
        self.action_bisturi_reset.triggered.connect(self.on_bisturi_reset_clicked)
        
        self.menu_bisturi.addAction(self.action_bisturi_desenhar)
        self.menu_bisturi.addAction(self.action_bisturi_cortar_interior)
        self.menu_bisturi.addAction(self.action_bisturi_cortar_exterior)
        self.menu_bisturi.addAction(self.action_bisturi_reset)
        
        self.menu_disseccao.addMenu(self.menu_cubo)
        self.menu_disseccao.addMenu(self.menu_bisturi)
        self.btn_disseccao.setMenu(self.menu_disseccao)
        




        self.coordenador_exibicao = CoordenadorExibicao(self)
        self.coordenador_exibicao.hide()
        
        self.label_boas_vindas = QLabel(self)
        self.label_boas_vindas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_boas_vindas.setStyleSheet("color: #aaaaaa; font-family: 'Segoe UI'; font-size: 14px;")
        self.label_boas_vindas.setText(
            "<h2 align='center'>Bem-vindo ao Neuroviewer</h2>"
            "<p align='center'>Arraste e solte uma pasta DICOM ou arquivo .zip aqui para começar.</p>"
            "<br><br>"
            "<table width='80%' align='center' cellpadding='15' style='border-collapse: collapse;'>"
            "<tr>"
            "<td width='50%' valign='top' style='border-right: 1px solid #3d3d3d;'>"
            "<h3 align='center' style='color: #007acc;'>Navegação 2D (MPR)</h3>"
            "<ul style='line-height: 1.6;'>"
            "<li><b>Botão Esquerdo (Fundo):</b> Ajuste de Contraste</li>"
            "<li><b>Botão Esquerdo (Linhas):</b> Arrastar fatias / Espessura MIP</li>"
            "<li><b>Scroll (Roda):</b> Navegar entre Fatias</li>"
            "<li><b>Botão do Meio:</b> Mover a Imagem (Pan)</li>"
            "<li><b>Botão Direito:</b> Zoom In / Out</li>"
            "<li><b>Duplo-Clique:</b> Maximizar Tela</li>"
            "<li><b>Crosshair:</b> Sincronizar as 3 telas clicando num vaso</li>"
            "</ul>"
            "</td>"
            "<td width='50%' valign='top'>"
            "<h3 align='center' style='color: #e74c3c;'>Navegação 3D (Volume)</h3>"
            "<ul style='line-height: 1.6;'>"
            "<li><b>Botão Esquerdo:</b> Rotacionar o modelo 3D</li>"
            "<li><b style='color: #f1c40f;'>Shift + Esquerdo:</b> Janelamento 3D (Transparência)</li>"
            "<li><b>Botão do Meio:</b> Mover o modelo 3D (Pan)</li>"
            "<li><b>Botão Direito:</b> Zoom In / Out</li>"
            "<li><b>Duplo-Clique:</b> Maximizar Tela</li>"
            "</ul>"
            "</td>"
            "</tr>"
            "</table>"
        )
        self.setCentralWidget(self.label_boas_vindas)

        # 5. Barra Lateral de Séries de Imagens (QDockWidget)
        self.dock_series = QDockWidget("Séries de Imagens", self)
        self.dock_series.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.dock_series.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.dock_series.setStyleSheet("""
            QDockWidget {
                color: #e0e0e0;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
                font-weight: bold;
            }
            QDockWidget::title {
                background-color: #1a1a1a;
                padding: 6px;
                border-bottom: 1px solid #2d2d2d;
            }
        """)
        
        self.list_series = QListWidget(self)
        self.list_series.setStyleSheet("""
            QListWidget {
                background-color: #151515;
                color: #e0e0e0;
                border: 1px solid #2d2d2d;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 11px;
                outline: 0;
            }
            QListWidget::item {
                padding: 8px 12px;
                border-bottom: 1px solid #222222;
            }
            QListWidget::item:hover {
                background-color: #252525;
            }
            QListWidget::item:selected {
                background-color: #2a2a2a;
                color: #007acc;
                border-left: 3px solid #007acc;
            }
        """)
        self.list_series.itemDoubleClicked.connect(self.carregar_serie_selecionada)
        self.list_series.setDragEnabled(True)
        self.list_series.setDefaultDropAction(Qt.DropAction.CopyAction)
        
        from PyQt6.QtWidgets import QWidget, QVBoxLayout
        container_lateral = QWidget()
        layout_lateral = QVBoxLayout(container_lateral)
        layout_lateral.setContentsMargins(0, 0, 0, 0)
        layout_lateral.setSpacing(0)

        # Adiciona a lista de séries (expande para ocupar o espaço)
        layout_lateral.addWidget(self.list_series)

        # Cria o botão de dicas no rodapé
        self.btn_dicas = QPushButton("ℹ️ Dicas de Navegação")
        self.btn_dicas.setStyleSheet("""
            QPushButton {
                background-color: #1a1a1a; color: #888888;
                border-top: 1px solid #2d2d2d; border-bottom: none; border-left: none; border-right: none;
                padding: 10px; font-family: 'Segoe UI'; font-size: 12px; font-weight: bold;
                text-align: left;
            }
            QPushButton:hover { background-color: #252525; color: #ffffff; }
        """)
        self.btn_dicas.clicked.connect(self.mostrar_dicas_navegacao)
        layout_lateral.addWidget(self.btn_dicas)

        self.dock_series.setWidget(container_lateral)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock_series)

    def mostrar_dicas_navegacao(self):
        from PyQt6.QtWidgets import QMessageBox
        msg = QMessageBox(self)
        msg.setWindowTitle("Dicas de Navegação")
        msg.setText(
            "<table width='100%' align='center' cellpadding='15' style='border-collapse: collapse;'>"
            "<tr>"
            "<td width='50%' valign='top' style='border-right: 1px solid #3d3d3d;'>"
            "<h3 align='center' style='color: #007acc;'>Navegação 2D (MPR)</h3>"
            "<ul style='line-height: 1.6;'>"
            "<li><b>Botão Esquerdo (Fundo):</b> Ajuste de Contraste</li>"
            "<li><b>Botão Esquerdo (Linhas):</b> Arrastar fatias / Espessura MIP</li>"
            "<li><b>Scroll (Roda):</b> Navegar entre Fatias</li>"
            "<li><b>Botão do Meio:</b> Mover a Imagem (Pan)</li>"
            "<li><b>Botão Direito:</b> Zoom In / Out</li>"
            "<li><b>Duplo-Clique:</b> Maximizar Tela</li>"
            "<li><b>Crosshair:</b> Sincronizar as 3 telas clicando num vaso</li>"
            "</ul>"
            "</td>"
            "<td width='50%' valign='top'>"
            "<h3 align='center' style='color: #e74c3c;'>Navegação 3D (Volume)</h3>"
            "<ul style='line-height: 1.6;'>"
            "<li><b>Botão Esquerdo:</b> Rotacionar o modelo 3D</li>"
            "<li><b style='color: #f1c40f;'>Shift + Esquerdo:</b> Janelamento 3D (Transparência)</li>"
            "<li><b>Botão do Meio:</b> Mover o modelo 3D (Pan)</li>"
            "<li><b>Botão Direito:</b> Zoom In / Out</li>"
            "<li><b>Duplo-Clique:</b> Maximizar Tela</li>"
            "</ul>"
            "</td>"
            "</tr>"
            "</table>"
        )
        msg.setStyleSheet("QMessageBox { background-color: #1a1a1a; color: #e0e0e0; min-width: 650px; } QLabel { color: #e0e0e0; font-size: 12px; } QPushButton { background-color: #2a2a2a; color: white; padding: 6px 12px; border-radius: 4px; border: 1px solid #3d3d3d; }")
        msg.exec()

    def alterar_layout_modo(self, tipo_layout: str):
        """
        Chama o coordenador de exibição para reestruturar os widgets ativos na tela.
        """
        self.coordenador_exibicao.definir_layout(tipo_layout)
        self.statusBar().showMessage(f"Layout alterado para: {tipo_layout}")

    def on_preset_changed(self, chave_preset):
        """
        Callback acionado quando o preset clínico é alterado.
        Sincroniza os QSpinBoxes e aplica a calibração nas visões 2D.
        """
        try:
            # Guarda anti-crash: valida se a chave é uma string válida
            if not isinstance(chave_preset, str):
                print(f"[PRESET] Erro: argumento inválido recebido ({type(chave_preset).__name__}: {chave_preset!r}). Esperado str.")
                return
                
            if not hasattr(self, 'presets_clinicos') or chave_preset not in self.presets_clinicos:
                print(f"[PRESET] Erro: Preset '{chave_preset}' não encontrado no dicionário presets_clinicos.")
                return
                
            preset = self.presets_clinicos[chave_preset]
            ww = preset["ww"]
            wl = preset["wl"]
            nome = preset["nome"]
            
            if chave_preset == "customizado":
                self.btn_presets.setToolTip("Preset: Customizado")
                return
                
            self.btn_presets.setToolTip(f"Preset: {nome}")
            self.aplicar_ww_wl(ww, wl)
            
        except Exception as e:
            print("[ERRO CRÍTICO PRESET] Falha em on_preset_changed:")
            traceback.print_exc()
            self.statusBar().showMessage("Falha ao aplicar preset em múltiplas telas.")

    def aplicar_ww_wl(self, ww: float, wl: float):
        """
        Propaga WW/WL para TODAS as telas ativas no layout atual.

        Arquitetura de múltiplas telas:
        - Modo MPR (4-Up): aplica no coordenador_navegacao principal (visões Axial/Coronal/Sagital
          via navegador_2d.aplicar_preset) e no volume 3D via navegador_3d.
        - Modo Dinâmico (TELA 1..N): para cada tela visível, chama
          atualizar_janelamento por nome_visao no navegador_2d compartilhado.

        Toda chamada VTK é blindada com null-checks para evitar C++ segfaults
        ao acessar ponteiros de janelas já destruídas ou ocultas.
        """
        try:
            if not hasattr(self, 'coordenador_exibicao') or not self.coordenador_exibicao:
                return
            if not hasattr(self, 'coordenador_navegacao') or not self.coordenador_navegacao:
                return

            nav = self.coordenador_navegacao
            layout_ativo = self.coordenador_exibicao.widget_layout_ativo

            # ------------------------------------------------------------------
            # CASO 1: Layout MPR (4-Up clássico)
            # ------------------------------------------------------------------
            if layout_ativo is self.coordenador_exibicao.layout_4_up:
                # Aplica nas visões 2D (Axial, Coronal, Sagital)
                # navegador_2d.aplicar_preset itera sobre self.atores.keys()
                # — limitamos ao subconjunto MPR para não tocar nas TELAs
                visoes_mpr = {"Axial", "Sagital", "Coronal"}
                for nome_visao in list(nav.navegador_2d.atores.keys()):
                    if nome_visao in visoes_mpr:
                        try:
                            nav.navegador_2d.atualizar_janelamento(nome_visao, ww, wl)
                        except Exception as e_inner:
                            print(f"[PRESET] Erro ao aplicar WW/WL na visão 2D '{nome_visao}': {e_inner}")

                # Aplica no volume 3D
                if hasattr(nav, 'navegador_3d') and nav.navegador_3d is not None:
                    try:
                        nav.navegador_3d.atualizar_transfer_functions(ww, wl)
                    except Exception as e_3d:
                        print(f"[PRESET] Erro ao aplicar WW/WL no volume 3D: {e_3d}")

                # Renderiza somente as janelas MPR válidas
                for nome_visao, quadrante in layout_ativo.visoes.items():
                    try:
                        if not hasattr(quadrante, 'interactor') or quadrante.interactor is None:
                            continue
                        rw = quadrante.interactor.GetRenderWindow()
                        if rw:
                            rw.Render()
                    except Exception as e_render:
                        print(f"[PRESET] Erro ao renderizar quadrante '{nome_visao}': {e_render}")

            # ------------------------------------------------------------------
            # CASO 2: Layout Dinâmico (TELA 1..N)
            # ------------------------------------------------------------------
            else:
                for nome_visao, quadrante in layout_ativo.visoes.items():
                    # Aplica WW/WL apenas nas TELAs que têm um ator ativo
                    if nome_visao in nav.navegador_2d.atores:
                        try:
                            nav.navegador_2d.atualizar_janelamento(nome_visao, ww, wl)
                        except Exception as e_inner:
                            print(f"[PRESET] Erro ao aplicar WW/WL na tela '{nome_visao}': {e_inner}")

                    # Renderiza apenas se o interactor e a janela ainda existem
                    try:
                        if not hasattr(quadrante, 'interactor') or quadrante.interactor is None:
                            continue
                        rw = quadrante.interactor.GetRenderWindow()
                        if rw:
                            rw.Render()
                    except Exception as e_render:
                        print(f"[PRESET] Erro ao renderizar tela '{nome_visao}': {e_render}")

        except Exception as e:
            print("[ERRO CRÍTICO PRESET] Falha em aplicar_ww_wl:")
            traceback.print_exc()
            self.statusBar().showMessage("Falha ao propagar preset nas telas ativas.")


    def on_mouse_espessura_changed(self, esp_val):
        self.spin_espessura.blockSignals(True)
        self.spin_espessura.setValue(int(esp_val))
        self.spin_espessura.blockSignals(False)

    def on_projecao_changed(self, modo=None):
        if modo is not None:
            self.modo_projecao_atual = modo
        else:
            modo = self.modo_projecao_atual

        esp = self.spin_espessura.value()
        
        if modo != "Normal" and esp == 0:
            self.spin_espessura.blockSignals(True)
            self.spin_espessura.setValue(20)
            self.spin_espessura.blockSignals(False)
            esp = 20
        elif modo == "Normal" and esp != 0:
            self.spin_espessura.blockSignals(True)
            self.spin_espessura.setValue(0)
            self.spin_espessura.blockSignals(False)
            esp = 0
            
        if hasattr(self, 'coordenador_navegacao') and hasattr(self.coordenador_navegacao, 'operador_projecao'):
            self.coordenador_navegacao.operador_projecao.aplicar_projecao_global(modo, esp)
            
            if hasattr(self.coordenador_navegacao, 'navegador_2d'):
                planos = self.coordenador_navegacao.navegador_2d.planos
                if 'Sagital' in planos and 'Coronal' in planos and 'Axial' in planos:
                    cx = planos['Sagital'].GetOrigin()[0]
                    cy = planos['Coronal'].GetOrigin()[1]
                    cz = planos['Axial'].GetOrigin()[2]
                    self.coordenador_navegacao.operador_projecao.atualizar_linhas(cx, cy, cz, planos)

            if hasattr(self, 'coordenador_exibicao') and hasattr(self.coordenador_exibicao, 'widget_layout_ativo') and self.coordenador_exibicao.widget_layout_ativo:
                if hasattr(self.coordenador_exibicao.widget_layout_ativo, 'visoes'):
                    for nome, quadrante in self.coordenador_exibicao.widget_layout_ativo.visoes.items():
                        quadrante.interactor.GetRenderWindow().Render()

    def on_crosshair_toggled(self, checked):
        if checked:
            if hasattr(self, 'btn_regua') and self.btn_regua.isChecked(): self.btn_regua.setChecked(False)
            if hasattr(self, 'btn_elipse') and self.btn_elipse.isChecked(): self.btn_elipse.setChecked(False)
            if hasattr(self, 'btn_reslice') and self.btn_reslice.isChecked(): self.btn_reslice.setChecked(False)
            if hasattr(self, 'action_adicionar_semente') and self.action_adicionar_semente.isChecked(): self.action_adicionar_semente.setChecked(False)
            if hasattr(self, 'action_caixa_recorte') and self.action_caixa_recorte.isChecked():
                self.action_caixa_recorte.setChecked(False)
                self.on_box_adjust_toggled(False)
            if hasattr(self, 'action_bisturi_desenhar') and self.action_bisturi_desenhar.isChecked():
                self.action_bisturi_desenhar.setChecked(False)
                self.on_bisturi_toggled(False)
        if hasattr(self.coordenador_navegacao, 'operador_crosshair'):
            if hasattr(self.coordenador_navegacao.operador_crosshair, 'ator'):
                self.coordenador_navegacao.operador_crosshair.ator.SetVisibility(checked)
            for nome, filtro in self.coordenador_navegacao.filtros_eventos.items():
                if hasattr(filtro, 'modo_crosshair'):
                    filtro.modo_crosshair = checked
            if hasattr(self, 'coordenador_exibicao') and hasattr(self.coordenador_exibicao, 'widget_layout_ativo') and self.coordenador_exibicao.widget_layout_ativo:
                if hasattr(self.coordenador_exibicao.widget_layout_ativo, 'visoes'):
                    for nome, quadrante in self.coordenador_exibicao.widget_layout_ativo.visoes.items():
                        quadrante.interactor.GetRenderWindow().Render()
 
    def on_regua_toggled(self, checked):
        if checked:
            if hasattr(self, 'btn_crosshair') and self.btn_crosshair.isChecked(): self.btn_crosshair.setChecked(False)
            if hasattr(self, 'btn_elipse') and self.btn_elipse.isChecked(): self.btn_elipse.setChecked(False)
            if hasattr(self, 'btn_reslice') and self.btn_reslice.isChecked(): self.btn_reslice.setChecked(False)
            if hasattr(self, 'action_adicionar_semente') and self.action_adicionar_semente.isChecked(): self.action_adicionar_semente.setChecked(False)
            if hasattr(self, 'action_caixa_recorte') and self.action_caixa_recorte.isChecked():
                self.action_caixa_recorte.setChecked(False)
                self.on_box_adjust_toggled(False)
            if hasattr(self, 'action_bisturi_desenhar') and self.action_bisturi_desenhar.isChecked():
                self.action_bisturi_desenhar.setChecked(False)
                self.on_bisturi_toggled(False)
        for nome, filtro in self.coordenador_navegacao.filtros_eventos.items():
            if hasattr(filtro, 'ferramenta_ativa'):
                filtro.ferramenta_ativa = "Regua" if checked else "Normal"
                
    def on_elipse_toggled(self, checked):
        if checked:
            if hasattr(self, 'btn_crosshair') and self.btn_crosshair.isChecked(): self.btn_crosshair.setChecked(False)
            if hasattr(self, 'btn_regua') and self.btn_regua.isChecked(): self.btn_regua.setChecked(False)
            if hasattr(self, 'btn_reslice') and self.btn_reslice.isChecked(): self.btn_reslice.setChecked(False)
            if hasattr(self, 'action_adicionar_semente') and self.action_adicionar_semente.isChecked(): self.action_adicionar_semente.setChecked(False)
            if hasattr(self, 'action_caixa_recorte') and self.action_caixa_recorte.isChecked():
                self.action_caixa_recorte.setChecked(False)
                self.on_box_adjust_toggled(False)
        for nome, filtro in self.coordenador_navegacao.filtros_eventos.items():
            if hasattr(filtro, 'ferramenta_ativa'):
                filtro.ferramenta_ativa = "Elipse" if checked else "Normal"

    def on_reslice_toggled(self, checked):
        if checked:
            if hasattr(self, 'btn_crosshair') and self.btn_crosshair.isChecked(): self.btn_crosshair.setChecked(False)
            if hasattr(self, 'btn_regua') and self.btn_regua.isChecked(): self.btn_regua.setChecked(False)
            if hasattr(self, 'btn_elipse') and self.btn_elipse.isChecked(): self.btn_elipse.setChecked(False)
            if hasattr(self, 'action_adicionar_semente') and self.action_adicionar_semente.isChecked(): self.action_adicionar_semente.setChecked(False)
            if hasattr(self, 'action_caixa_recorte') and self.action_caixa_recorte.isChecked():
                self.action_caixa_recorte.setChecked(False)
                self.on_box_adjust_toggled(False)
            if hasattr(self, 'action_bisturi_desenhar') and self.action_bisturi_desenhar.isChecked():
                self.action_bisturi_desenhar.setChecked(False)
                self.on_bisturi_toggled(False)
        for nome, filtro in self.coordenador_navegacao.filtros_eventos.items():
            if hasattr(filtro, 'ferramenta_ativa'):
                filtro.ferramenta_ativa = "Reslice" if checked else "Normal"
                
        if hasattr(self.coordenador_navegacao, 'operador_projecao'):
            self.coordenador_navegacao.operador_projecao.set_reslice_ativo(checked)
            
        # Força a atualização da tela
        if hasattr(self.coordenador_exibicao.widget_layout_ativo, 'visoes'):
            for quadrante in self.coordenador_exibicao.widget_layout_ativo.visoes.values():
                quadrante.interactor.GetRenderWindow().Render()

    def on_semente_toggled(self, checked):
        if checked:
            if hasattr(self, 'btn_crosshair') and self.btn_crosshair.isChecked(): self.btn_crosshair.setChecked(False)
            if hasattr(self, 'btn_regua') and self.btn_regua.isChecked(): self.btn_regua.setChecked(False)
            if hasattr(self, 'btn_elipse') and self.btn_elipse.isChecked(): self.btn_elipse.setChecked(False)
            if hasattr(self, 'btn_reslice') and self.btn_reslice.isChecked(): self.btn_reslice.setChecked(False)
            if hasattr(self, 'action_caixa_recorte') and self.action_caixa_recorte.isChecked():
                self.action_caixa_recorte.setChecked(False)
                self.on_box_adjust_toggled(False)
            if hasattr(self, 'action_bisturi_desenhar') and self.action_bisturi_desenhar.isChecked():
                self.action_bisturi_desenhar.setChecked(False)
                self.on_bisturi_toggled(False)
        
        for nome, filtro in self.coordenador_navegacao.filtros_eventos.items():
            if hasattr(filtro, 'ferramenta_ativa'):
                filtro.ferramenta_ativa = "Semente" if checked else "Normal"

    def processar_sementes(self):
        if self._sitk_img_ref is None:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Aviso", "Nenhuma série carregada para processamento.")
            return

        lista_seeds = self.coordenador_navegacao.lista_sementes
        if not lista_seeds:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Aviso", "Por favor, adicione pelo menos uma semente antes de processar.")
            return

        from PyQt6.QtWidgets import QProgressDialog
        self.progresso_subtracao = QProgressDialog("Extraindo Vasos por Sementes (Region Growing)...", None, 0, 0, self)
        self.progresso_subtracao.setWindowModality(Qt.WindowModality.WindowModal)
        self.progresso_subtracao.setCancelButton(None)
        self.progresso_subtracao.show()

        # Desativa os botões
        if hasattr(self, 'action_processar_sementes'):
            self.action_processar_sementes.setEnabled(False)

        self.thread_semente = ThreadSubtracaoSemente(self._sitk_img_ref, lista_seeds)
        self.thread_semente.resultado.connect(self.on_semente_concluida)
        self.thread_semente.erro.connect(self.on_erro_semente)
        self.thread_semente.start()

    def on_semente_concluida(self, sitk_img_result):
        if hasattr(self, 'progresso_subtracao') and self.progresso_subtracao:
            self.progresso_subtracao.close()

        if hasattr(self, 'action_processar_sementes'):
            self.action_processar_sementes.setEnabled(True)
        
        # Desativa a ferramenta após concluir
        if hasattr(self, 'action_adicionar_semente') and self.action_adicionar_semente.isChecked():
            self.action_adicionar_semente.setChecked(False)

        # Limpa as sementes visuais da tela
        if hasattr(self, 'coordenador_navegacao'):
            self.coordenador_navegacao.limpar_sementes()

        self.on_subtracao_concluida(sitk_img_result)

    def on_erro_semente(self, mensagem):
        if hasattr(self, 'progresso_subtracao') and self.progresso_subtracao:
            self.progresso_subtracao.close()
        if hasattr(self, 'action_processar_sementes'):
            self.action_processar_sementes.setEnabled(True)
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(self, "Erro de Processamento", f"Falha na extração por semente: {mensagem}")

    def limpar_sementes(self):
        if hasattr(self, 'coordenador_navegacao'):
            self.coordenador_navegacao.limpar_sementes()



    def sincronizar_scroll_global(self, nome_visao: str, deslocamento_mm: float, coordenador_origem):
        """
        Propaga um deslocamento físico (em mm) para todas as telas ativas que NÃO
        sejam a tela de origem do evento de scroll.

        Parâmetros
        ----------
        nome_visao : str
            Nome do plano que foi rolado (ex: "Axial", "TELA 1", ...).
        deslocamento_mm : float
            Deslocamento físico calculado na tela de origem (inc * spacing).
        coordenador_origem : CoordenadorNavegacao
            Coordenador que disparou o evento; é excluído da propagação.
        """
        try:
            if not hasattr(self, 'coordenador_exibicao') or not self.coordenador_exibicao:
                return
            if not hasattr(self, 'coordenador_navegacao') or not self.coordenador_navegacao:
                return

            nav_principal = self.coordenador_navegacao
            layout_ativo  = self.coordenador_exibicao.widget_layout_ativo

            # Determina o conjunto de (nome_plano, nav, quadrante) a atualizar.
            # No layout MPR há um único CoordenadorNavegacao que gerencia Axial/Coronal/Sagital.
            # No layout dinâmico cada TELA usa o mesmo navegador_2d mas atores independentes.
            alvos = []   # lista de (nome_plano_alvo, nav, quadrante)

            if layout_ativo is self.coordenador_exibicao.layout_4_up:
                # Modo MPR: propaga para os 3 planos ortogonais exceto o de origem
                planos_mpr = ["Axial", "Sagital", "Coronal"]
                for nome_plano in planos_mpr:
                    if nome_plano == nome_visao:
                        continue   # pula a origem
                    if nome_plano in nav_principal.navegador_2d.planos and nome_plano in layout_ativo.visoes:
                        alvos.append((nome_plano, nav_principal, layout_ativo.visoes[nome_plano]))
            else:
                # Modo dinâmico: cada TELA tem seu próprio ator; o nome_visao é "TELA N"
                # Para sincronizar, empurra o MESMO deslocamento em todas as TELAs
                # que também tenham o plano nome_visao registrado.
                for nome_tela, quadrante in layout_ativo.visoes.items():
                    if nome_tela == nome_visao:
                        continue   # pula a origem
                    if nome_tela in nav_principal.navegador_2d.planos:
                        alvos.append((nome_tela, nav_principal, quadrante))

            for nome_plano_alvo, nav, quadrante in alvos:
                try:
                    plane = nav.navegador_2d.planos[nome_plano_alvo]
                    plane.Push(deslocamento_mm)

                    # Atualiza as linhas de projeção MIP se o coordenador tiver um
                    if hasattr(nav, 'operador_projecao') and nav.operador_projecao is not None:
                        try:
                            p = nav.navegador_2d.planos
                            if "Sagital" in p and "Coronal" in p and "Axial" in p:
                                cx = p["Sagital"].GetOrigin()[0]
                                cy = p["Coronal"].GetOrigin()[1]
                                cz = p["Axial"].GetOrigin()[2]
                                nav.operador_projecao.atualizar_linhas(cx, cy, cz, p)
                        except Exception:
                            pass   # Projeção opcional — nunca deve travar o scroll

                    # Render blindado
                    if hasattr(quadrante, 'interactor') and quadrante.interactor is not None:
                        rw = quadrante.interactor.GetRenderWindow()
                        if rw:
                            rw.Render()

                except Exception as e_alvo:
                    print(f"[SYNC SCROLL] Erro ao sincronizar plano '{nome_plano_alvo}': {e_alvo}")

        except Exception:
            # Nunca deixa o sync scroll travar o scroll nativo
            traceback.print_exc()

    def on_box_adjust_toggled(self, checked):
        try:
            import vtk
            
            if checked:
                if hasattr(self, 'btn_crosshair') and self.btn_crosshair.isChecked(): self.btn_crosshair.setChecked(False)
                if hasattr(self, 'btn_regua') and self.btn_regua.isChecked(): self.btn_regua.setChecked(False)
                if hasattr(self, 'btn_elipse') and self.btn_elipse.isChecked(): self.btn_elipse.setChecked(False)
                if hasattr(self, 'btn_reslice') and self.btn_reslice.isChecked(): self.btn_reslice.setChecked(False)
                if hasattr(self, 'action_adicionar_semente') and self.action_adicionar_semente.isChecked(): self.action_adicionar_semente.setChecked(False)
                if hasattr(self, 'action_bisturi_desenhar') and self.action_bisturi_desenhar.isChecked():
                    self.action_bisturi_desenhar.setChecked(False)
                    self.on_bisturi_toggled(False)
                
            if not hasattr(self, 'coordenador_navegacao') or getattr(self, 'coordenador_navegacao') is None:
                return
            nav = self.coordenador_navegacao
            
            # Atualiza o estado da ferramenta nos filtros de eventos
            if hasattr(nav, 'filtros_eventos'):
                for filtro in nav.filtros_eventos.values():
                    if hasattr(filtro, 'ferramenta_ativa'):
                        if checked:
                            filtro.ferramenta_ativa = "CropBox"
                        else:
                            if filtro.ferramenta_ativa == "CropBox":
                                filtro.ferramenta_ativa = "Normal"
            
            # 1. Ativa/Desativa o Box Widget no 3D
            if hasattr(nav, 'navegador_3d') and getattr(nav, 'navegador_3d') is not None:
                if hasattr(nav.navegador_3d, 'mostrar_caixa_recorte'):
                    nav.navegador_3d.mostrar_caixa_recorte(checked)
                    
                # 2. Recupera a representação compartilhada
                rep_compartilhada = getattr(nav.navegador_3d, 'crop_representation', None)
                if rep_compartilhada is None:
                    return
                    
                layout_ativo = getattr(self.coordenador_exibicao, 'widget_layout_ativo', None)
                visoes = getattr(layout_ativo, 'visoes', {}) if layout_ativo else {}
                
                # Sub-função para renderizar todas as janelas ao interagir com qualquer widget
                def renderizar_todas_as_telas(obj, event):
                    for visao in visoes.values():
                        if hasattr(visao, 'interactor') and visao.interactor and visao.interactor.GetRenderWindow():
                            visao.interactor.GetRenderWindow().Render()
                            
                # Adiciona observer no widget 3D para renderizar as telas 2D
                if not hasattr(nav.navegador_3d, 'crop_obs_id'):
                    if hasattr(nav.navegador_3d, 'crop_widget') and nav.navegador_3d.crop_widget:
                        nav.navegador_3d.crop_obs_id = nav.navegador_3d.crop_widget.AddObserver("InteractionEvent", renderizar_todas_as_telas)
                        
                # 3. Instanciar e sincronizar os widgets 2D
                nav2d = getattr(nav, 'navegador_2d', None)
                if nav2d:
                    if not hasattr(nav2d, 'crop_widgets'):
                        nav2d.crop_widgets = {}
                        
                    for nome in ["Axial", "Coronal", "Sagital"]:
                        if nome in visoes:
                            # Cria o widget para a visão se ainda não existir
                            if nome not in nav2d.crop_widgets:
                                bw = vtk.vtkBoxWidget2()
                                bw.SetInteractor(visoes[nome].interactor)
                                bw.SetRepresentation(rep_compartilhada)
                                bw.SetRotationEnabled(False)
                                bw.AddObserver("InteractionEvent", renderizar_todas_as_telas)
                                nav2d.crop_widgets[nome] = bw
                                
                            # Ativa ou desativa conforme o estado do botão
                            if checked:
                                nav2d.crop_widgets[nome].EnabledOn()
                                # Desliga o janelamento C++ nativo
                                visoes[nome].interactor.SetInteractorStyle(vtk.vtkInteractorStyleUser())
                            else:
                                nav2d.crop_widgets[nome].EnabledOff()
                                # Restaura o estilo de navegação nativo guardado no filtro
                                if hasattr(nav, 'filtros_eventos') and nome in nav.filtros_eventos:
                                    visoes[nome].interactor.SetInteractorStyle(nav.filtros_eventos[nome].style)
                                
                # Força a atualização da tela imediatamente
                renderizar_todas_as_telas(None, None)
                
        except Exception as e:
            print(f"[CROP 3D] Erro ao ajustar caixa: {e}")

    def on_box_apply_clicked(self):
        try:
            if not hasattr(self, 'coordenador_navegacao') or getattr(self, 'coordenador_navegacao') is None:
                return
            nav = self.coordenador_navegacao
            if hasattr(nav, 'navegador_3d') and getattr(nav, 'navegador_3d') is not None:
                if hasattr(nav.navegador_3d, 'aplicar_recorte_caixa'):
                    nav.navegador_3d.aplicar_recorte_caixa()
            if hasattr(self, 'action_caixa_recorte'):
                self.action_caixa_recorte.setChecked(False)
        except Exception as e:
            print(f"[CROP 3D] Erro ao aplicar recorte: {e}")

    def on_box_reset_clicked(self):
        try:
            if not hasattr(self, 'coordenador_navegacao') or getattr(self, 'coordenador_navegacao') is None:
                return
            nav = self.coordenador_navegacao
            if hasattr(nav, 'navegador_3d') and getattr(nav, 'navegador_3d') is not None:
                if hasattr(nav.navegador_3d, 'resetar_recorte'):
                    nav.navegador_3d.resetar_recorte()
        except Exception as e:
            print(f"[CROP 3D] Erro ao resetar recorte: {e}")

    def on_bisturi_toggled(self, checked):
        try:
            if checked:
                if hasattr(self, 'btn_crosshair') and self.btn_crosshair.isChecked(): self.btn_crosshair.setChecked(False)
                if hasattr(self, 'btn_regua') and self.btn_regua.isChecked(): self.btn_regua.setChecked(False)
                if hasattr(self, 'btn_elipse') and self.btn_elipse.isChecked(): self.btn_elipse.setChecked(False)
                if hasattr(self, 'btn_reslice') and self.btn_reslice.isChecked(): self.btn_reslice.setChecked(False)
                if hasattr(self, 'action_adicionar_semente') and self.action_adicionar_semente.isChecked(): self.action_adicionar_semente.setChecked(False)
                if hasattr(self, 'action_caixa_recorte') and self.action_caixa_recorte.isChecked():
                    self.action_caixa_recorte.setChecked(False)
                    self.on_box_adjust_toggled(False)
                    
            if not hasattr(self, 'coordenador_navegacao') or getattr(self, 'coordenador_navegacao') is None:
                return
            nav = self.coordenador_navegacao
            
            # Atualiza o estado nos filtros de eventos 3D e 2D
            if hasattr(nav, 'filtros_eventos'):
                for filtro in nav.filtros_eventos.values():
                    if hasattr(filtro, 'ferramenta_ativa'):
                        if checked:
                            filtro.ferramenta_ativa = "Bisturi"
                        else:
                            if filtro.ferramenta_ativa == "Bisturi":
                                filtro.ferramenta_ativa = "Normal"
                                if hasattr(filtro, 'limpar_bisturi_tela'):
                                    filtro.limpar_bisturi_tela()
                                    
        except Exception as e:
            print(f"[BISTURI] Erro ao alternar bisturi: {e}")

    def on_bisturi_aplicar_clicked(self, cortar_fora=False):
        try:
            if not hasattr(self, 'coordenador_navegacao') or getattr(self, 'coordenador_navegacao') is None:
                return
            nav = self.coordenador_navegacao
            # Chamada para o coordenador de navegação acionar os filtros e coletar os pontos
            if hasattr(nav, 'aplicar_bisturi'):
                nav.aplicar_bisturi(cortar_fora)
            if hasattr(self, 'action_bisturi_desenhar'):
                self.action_bisturi_desenhar.setChecked(False)
                self.on_bisturi_toggled(False)
        except Exception as e:
            print(f"[BISTURI] Erro ao aplicar corte: {e}")

    def on_bisturi_reset_clicked(self):
        try:
            if not hasattr(self, 'coordenador_navegacao') or getattr(self, 'coordenador_navegacao') is None:
                return
            nav = self.coordenador_navegacao
            if hasattr(nav, 'resetar_bisturi'):
                nav.resetar_bisturi()
        except Exception as e:
            print(f"[BISTURI] Erro ao resetar corte original: {e}")

    def on_mouse_janelamento_changed(self, ww, wl):
        """
        Callback acionado quando o usuário arrasta o mouse nos viewports 2D/3D.
        Verifica a lista de presets para atualizar o ToolTip.
        """
        if not hasattr(self, 'presets_clinicos'):
            return
            
        preset_encontrado = None
        for chave, preset in self.presets_clinicos.items():
            if chave == "customizado":
                continue
            if int(ww) == int(preset["ww"]) and int(wl) == int(preset["wl"]):
                preset_encontrado = preset
                break
                
        if preset_encontrado:
            self.btn_presets.setToolTip(f"Preset: {preset_encontrado['nome']}")
        else:
            self.btn_presets.setToolTip("Preset: Customizado")

    def extrair_texto_hud(self, prop_dicom: dict) -> str:
        linhas = []
        
        nome = prop_dicom.get("Nome", "").strip()
        nomes_ignorados = ["", "ANONIMO", "PACIENTE ANONIMIZADO", "DESCONHECIDO", "N/A"]
        if nome.upper() not in nomes_ignorados:
            linhas.append(f"Paciente: {nome}")
            
        inst = prop_dicom.get("Inst", "").strip()
        inst_ignoradas = ["", "ANONIMA", "INSTITUICAO ANONIMA", "HOSPITAL DE NEUROIMAGEM", "N/A"]
        if inst.upper() not in inst_ignoradas:
            linhas.append(f"Inst: {inst}")
            
        data = prop_dicom.get("Data", "").strip()
        if len(data) == 8 and data.isdigit():
            data = f"{data[6:8]}/{data[4:6]}/{data[0:4]}"

        hora = prop_dicom.get("Hora", "").strip()
        hora_limpa = hora.split(".")[0] if "." in hora else hora
        if len(hora_limpa) >= 4:
            hora = f"{hora_limpa[0:2]}:{hora_limpa[2:4]}"
        
        linha_data_hora = ""
        datas_ignoradas = ["", "N/A", "01/01/2000", "01/01/1900", "20000101", "19000101"]
        
        if data and data not in datas_ignoradas:
            linha_data_hora += f"Data: {data}"
            
        if hora and hora not in ["", "N/A"]:
            separador = "   " if linha_data_hora else ""
            linha_data_hora += f"{separador}Hora: {hora}"
            
        if linha_data_hora.strip():
            linhas.append(linha_data_hora.strip())
            
        return "\n".join(linhas)

    def aplicar_preset_por_nome(self, nome_preset: str):
        """
        Aplica as calibrações de presets atualizando os widgets da toolbar de forma limpa.
        """
        try:
            if not hasattr(self, 'presets_clinicos'):
                return
                
            if nome_preset not in self.presets_clinicos:
                print(f"[PRESET] Erro: Preset '{nome_preset}' não encontrado em presets_clinicos.")
                return
                
            preset = self.presets_clinicos[nome_preset]
            self.btn_presets.setToolTip(f"Preset: {preset['nome']}")
            self.aplicar_ww_wl(preset["ww"], preset["wl"])
            
        except Exception as e:
            print("[ERRO CRÍTICO PRESET] Falha em aplicar_preset_por_nome:")
            traceback.print_exc()
            self.statusBar().showMessage("Falha ao aplicar preset em múltiplas telas.")

    def dragEnterEvent(self, event):
        """
        Trata o evento de arrastar um diretório ou arquivo sobre a janela do aplicativo.
        """
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                path = url.toLocalFile()
                if os.path.isdir(path) or path.lower().endswith((".zip", ".nrrd", ".nii.gz")):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        """
        Trata o recebimento da pasta ou arquivo arrastado pelo usuário.
        """
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                path = url.toLocalFile()
                if os.path.isdir(path):
                    self.statusBar().showMessage(f"Diretório arrastado detectado: {path}")
                    self.carregar_diretorio_dicom(path)
                    break
                elif path.lower().endswith(".zip"):
                    self.statusBar().showMessage(f"Arquivo ZIP arrastado detectado: {path}")
                    self.carregar_arquivo_zip(path)
                    break
                elif path.lower().endswith((".nrrd", ".nii.gz")):
                    self.statusBar().showMessage(f"Volume Médico arrastado detectado: {path}")
                    self.carregar_arquivo_nrrd(path)
                    break
            event.acceptProposedAction()

    def carregar_arquivo_zip(self, caminho_zip: str):
        """
        Descompacta o arquivo zip temporariamente e carrega as séries encontradas.
        """
        if not caminho_zip or not os.path.exists(caminho_zip):
            return
            
        self.statusBar().showMessage(f"Extraindo e escaneando arquivo ZIP: {caminho_zip}...")
        try:
            from carregamento.carregamento_arquivos_zip import CarregadorArquivosZip
            carregador = CarregadorArquivosZip()
            series, temp_dir = carregador.extrair_e_carregar(caminho_zip)
            
            if not series or not temp_dir:
                self.statusBar().showMessage("Nenhuma série DICOM válida encontrada no arquivo ZIP.")
                return
                
            # Salva o diretório temporário para mantê-lo vivo na memória
            if not hasattr(self, "temp_dirs"):
                self.temp_dirs = []
            self.temp_dirs.append(temp_dir)
            
            # Popula as séries e carrega da mesma forma que carregar_diretorio_dicom
            self.diretorio_ativo = temp_dir.name
            self.series_carregadas = series
            
            # Popula o list widget com as séries encontradas
            self.list_series.clear()
            for s in series:
                s_id = s["SeriesID"]
                num_slices = len(s["Files"])
                
                desc_serie = s.get("Description", "Desconhecida")
                num_serie = s.get("Number", "N/A")
                if len(desc_serie) > 25:
                    desc_serie = desc_serie[:22] + "..."
                    
                texto_item = f"Série {num_serie}: {desc_serie} ({num_slices} fatias)"
                item = QListWidgetItem(texto_item)
                item.setData(Qt.ItemDataRole.UserRole, s_id)
                item.setToolTip(f"ID Completo: {s_id}\nDescrição: {s.get('Description', 'N/A')}\nNúmero: {num_serie}\nFatias: {num_slices}")
                self.list_series.addItem(item)
            
            # Seleciona visualmente a primeira série na barra lateral
            if self.list_series.count() > 0:
                self.list_series.setCurrentRow(0)
            
            # Carrega a primeira série do diretório de forma padrão (Zero-Copy)
            self.statusBar().showMessage("Carregando série DICOM extraída do ZIP...")
            
            from carregamento import CoordenadorCarregamento
            coordenador = CoordenadorCarregamento()
            primeira_serie_id = series[0]["SeriesID"]
            primeira_serie_dir = series[0]["Directory"]
            vtk_image, sitk_image, np_view, prop_dicom = coordenador.carregar_serie(primeira_serie_dir, primeira_serie_id)
            
            # Salva referências para evitar Garbage Collector do buffer C++
            self._sitk_img_ref = sitk_image
            self._np_view_ref = np_view
            
            # Inicializa a renderização 2D (MPR) e 3D (Volume Rendering)
            from navegacao import CoordenadorNavegacao
            self.coordenador_navegacao = CoordenadorNavegacao(self)

            
            if hasattr(self.coordenador_exibicao.widget_layout_ativo, "visoes"):
                self.coordenador_navegacao.inicializar_visualizacao(
                    vtk_image, 
                    self.coordenador_exibicao.widget_layout_ativo.visoes,
                    janelamento_callback=self.on_mouse_janelamento_changed
                )
            
            # Extração dos Metadados para o HUD
            hud_texto = self.extrair_texto_hud(prop_dicom)
            self.coordenador_navegacao.navegador_2d.atualizar_metadados_hud(hud_texto)
            self.coordenador_navegacao.navegador_3d.atualizar_metadados_hud(hud_texto)
            
            # Aplica o preset padrão Angio-TC Vascular (WW: 600 / WL: 150)
            self.aplicar_preset_por_nome("angio_tc")
            
            dim = vtk_image.GetDimensions()
            info_msg = f"Série carregada do ZIP: {primeira_serie_id} | Resolução: {dim[0]}x{dim[1]}x{dim[2]}"
            self.statusBar().showMessage(info_msg)
            
        except Exception as e:
            self.statusBar().showMessage(f"Erro ao carregar arquivo ZIP: {str(e)}")
            import traceback
            traceback.print_exc()

    def iniciar_subtracao_lenta(self):
        if not hasattr(self, "series_carregadas") or not self.series_carregadas:
            QMessageBox.warning(self, "Aviso", "Nenhuma série carregada. Abra uma pasta DICOM primeiro.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Subtração Óssea Lenta (Registration)")
        dialog.setMinimumWidth(400)
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel("Selecione a Fase Angio-TC (Com Contraste):"))
        combo_angio = QComboBox()
        layout.addWidget(combo_angio)

        layout.addWidget(QLabel("Selecione a Fase Pré-Contraste (Sem Contraste):"))
        combo_sem_contraste = QComboBox()
        layout.addWidget(combo_sem_contraste)

        for s in self.series_carregadas:
            s_id = s.get("SeriesID")
            dir_serie = s.get("Directory")
            num_slices = len(s.get("Files", []))
            desc_serie = s.get("Description", "Desconhecida")
            num_serie = s.get("Number", "N/A")
            
            # Formatação amigável para o médico
            texto_item = f"Série {num_serie}: {desc_serie} ({num_slices} fatias)"
            
            # Adicionando nos dois ComboBoxes (guardando os dados necessários no userData)
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
                QMessageBox.warning(self, "Aviso", "Por favor, selecione séries diferentes para o Registro.")
                return

            def get_sitk_img(serie_dados):
                s_id = serie_dados["id"]
                if hasattr(self, "cache_series") and s_id in self.cache_series:
                    return self.cache_series[s_id][1]
                reader = sitk.ImageSeriesReader()
                reader.SetFileNames(serie_dados["files"])
                return reader.Execute()

            try:
                img_angio = get_sitk_img(serie_angio)
                img_sem = get_sitk_img(serie_sem)
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao ler imagem: {str(e)}")
                return

            # Cria dialog de progresso
            self.progresso_dsa = QProgressDialog("Inicializando Registro 3D...", None, 0, 0, self)
            self.progresso_dsa.setWindowTitle("Subtração Lenta")
            self.progresso_dsa.setWindowModality(Qt.WindowModality.WindowModal)
            self.progresso_dsa.setCancelButton(None)
            self.progresso_dsa.show()

            self.thread_dsa = ThreadSubtracaoLenta(img_sem, img_angio)
            self.thread_dsa.progresso_sinal.connect(
                lambda it, val: self.progresso_dsa.setLabelText(f"Iteração {it} | Métrica: {val:.5f}")
            )
            self.thread_dsa.log_sinal.connect(self.progresso_dsa.setLabelText)
            self.thread_dsa.virtual_sinal.connect(self.on_serie_virtual_criada)
            self.thread_dsa.erro_sinal.connect(self.on_subtracao_erro)
            self.thread_dsa.start()

    def ativar_ferramenta_semente_dsa(self):
        if not hasattr(self, 'coordenador_navegacao') or not self.coordenador_navegacao: return
        self.statusBar().showMessage("Semente Vascular ativada: Clique na Aorta na visão 2D.")
        
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Subtração Rápida", "Clique no vaso de interesse na visão 2D.")
        
        for nome, filtro in self.coordenador_navegacao.filtros_eventos.items():
            if hasattr(filtro, 'ferramenta_ativa'):
                filtro.ferramenta_ativa = "SementeDSA"

    def atualizar_progresso_dsa(self, valor, mensagem):
        if hasattr(self, 'progress_dsa'):
            self.progress_dsa.setValue(valor)
            self.progress_dsa.setLabelText(mensagem)

    def iniciar_subtracao_semente(self, index_itk):
        if not hasattr(self, '_sitk_img_ref') or self._sitk_img_ref is None:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Aviso", "Nenhuma série carregada para subtração.")
            return
            
        self.statusBar().showMessage("Inundando árvore vascular...")
        
        if hasattr(self, 'btn_subtracao_ossea') and self.btn_subtracao_ossea:
            self.btn_subtracao_ossea.setEnabled(False)
            
        from PyQt6.QtWidgets import QProgressDialog
        from PyQt6.QtCore import Qt
        
        self.progress_dsa = QProgressDialog("Iniciando subtração...", "Cancelar", 0, 100, self)
        self.progress_dsa.setWindowTitle("Subtração Óssea Guiada")
        self.progress_dsa.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dsa.setAutoClose(True)
        self.progress_dsa.show()
        
        self.thread_semente = ThreadSubtracaoSemente(self._sitk_img_ref, index_itk)
        self.thread_semente.progresso_sinal.connect(self.atualizar_progresso_dsa)
        self.thread_semente.virtual_sinal.connect(self.on_serie_virtual_criada)
        self.thread_semente.log_sinal.connect(self.statusBar().showMessage)
        self.thread_semente.erro_sinal.connect(self.on_subtracao_erro)
        self.thread_semente.start()

    def on_subtracao_erro(self, msg):
        from PyQt6.QtWidgets import QMessageBox
        self.statusBar().showMessage("Erro no processamento da subtração.")
        QMessageBox.warning(self, "Erro de Processamento", f"Falha na subtração óssea:\n{msg}")
        
        # Reabilitar o botão caso tenha sido desativado
        if hasattr(self, 'btn_subtracao_ossea') and self.btn_subtracao_ossea:
            self.btn_subtracao_ossea.setEnabled(True)

    def iniciar_subtracao_rapida(self):
        if not hasattr(self, '_sitk_img_ref') or self._sitk_img_ref is None:
            QMessageBox.warning(self, "Aviso", "Nenhuma série carregada para subtração.")
            return

        self.progresso_dsa = QProgressDialog("Iniciando Morfologia Matemática...", None, 0, 0, self)
        self.progresso_dsa.setWindowTitle("Subtração Rápida")
        self.progresso_dsa.setWindowModality(Qt.WindowModality.WindowModal)
        self.progresso_dsa.setCancelButton(None)
        self.progresso_dsa.show()

        self.thread_dsa = ThreadSubtracaoRapida(self._sitk_img_ref)
        self.thread_dsa.log_sinal.connect(self.progresso_dsa.setLabelText)
        self.thread_dsa.virtual_sinal.connect(self.on_serie_virtual_criada)
        self.thread_dsa.erro_sinal.connect(self.on_subtracao_erro)
        self.thread_dsa.start()

    def on_serie_virtual_criada(self, vtk_image, sitk_image, nome):
        if hasattr(self, "progresso_dsa"):
            self.progresso_dsa.close()
            
        # Força o reset global da ferramenta e do cursor
        if hasattr(self, 'coordenador_navegacao') and self.coordenador_navegacao:
            for n, filtro in self.coordenador_navegacao.filtros_eventos.items():
                filtro.ferramenta_ativa = "Normal"
                if hasattr(filtro, 'interactor') and filtro.interactor:
                    from PyQt6.QtCore import Qt
                    filtro.interactor.setCursor(Qt.CursorShape.ArrowCursor)
                    filtro.interactor.GetRenderWindow().Render()
                    
        item = QListWidgetItem(nome)
        dados = {
            "virtual": True, 
            "vtk_image": vtk_image, 
            "sitk_image": sitk_image,
            "np_array": getattr(vtk_image, "_np_ref", None)
        }
        item.setData(Qt.ItemDataRole.UserRole, dados)
        item.setToolTip(f"Série gerada virtualmente em RAM.")
        self.list_series.addItem(item)
        
        # Seleciona o novo item na lista para visualização imediata
        self.list_series.setCurrentItem(item)
        self.carregar_serie_selecionada(item)
        
        QMessageBox.information(self, "Sucesso", f"{nome} processada e anexada na lista com sucesso!")

    def on_subtracao_erro(self, erro):
        if hasattr(self, "progresso_dsa"):
            self.progresso_dsa.close()
        QMessageBox.critical(self, "Erro", f"Ocorreu um erro durante a subtração:\n{erro}")

    def carregar_arquivo_nrrd(self, caminho_nrrd: str):
        """
        Carrega um arquivo .nrrd ou .nii.gz isolado usando SimpleITK e injeta na cena VTK (zero-copy).
        """
        if not caminho_nrrd or not os.path.exists(caminho_nrrd):
            return
            
        self.statusBar().showMessage(f"Carregando volume: {caminho_nrrd}...")
        try:
            sitk_img = sitk.ReadImage(caminho_nrrd)
            # Reutiliza o fluxo de injeção que já inicializa todos os mappers
            self.on_subtracao_concluida(sitk_img)
            self.statusBar().showMessage(f"Volume carregado com sucesso: {caminho_nrrd}")
        except Exception as e:
            self.statusBar().showMessage(f"Erro ao carregar volume: {str(e)}")
            import traceback
            traceback.print_exc()

    def aplicar_subtracao_ossea(self):
        if self._sitk_img_ref is None:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Aviso", "Nenhuma série carregada para subtração.")
            return

        from PyQt6.QtWidgets import QProgressDialog
        self.progresso_subtracao = QProgressDialog("Processando Subtração Óssea (IA)...", None, 0, 0, self)
        self.progresso_subtracao.setWindowModality(Qt.WindowModality.WindowModal)
        self.progresso_subtracao.setCancelButton(None)
        self.progresso_subtracao.show()

        # Desativa os botões temporariamente
        if hasattr(self, 'btn_subtracao_ossea') and self.btn_subtracao_ossea:
            self.btn_subtracao_ossea.setEnabled(False)

        self.thread_subtracao = ThreadSubtracaoOssea(self._sitk_img_ref)
        self.thread_subtracao.resultado.connect(self.on_subtracao_concluida)
        self.thread_subtracao.erro.connect(self.on_erro_subtracao)
        self.thread_subtracao.start()

    def on_erro_subtracao(self, mensagem):
        if hasattr(self, 'progresso_subtracao') and self.progresso_subtracao:
            self.progresso_subtracao.close()
        if hasattr(self, 'btn_subtracao_ossea') and self.btn_subtracao_ossea:
            self.btn_subtracao_ossea.setEnabled(True)
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(self, "Erro de Processamento", f"Falha na subtração óssea: {mensagem}")

    def on_subtracao_concluida(self, sitk_img_result):
        import numpy as np
        if hasattr(self, 'progresso_subtracao') and self.progresso_subtracao:
            self.progresso_subtracao.close()
        
        if hasattr(self, 'btn_subtracao_ossea') and self.btn_subtracao_ossea:
            self.btn_subtracao_ossea.setEnabled(True)

        # Atualiza a referência global
        self._sitk_img_ref = sitk_img_result
        np_array = sitk.GetArrayFromImage(sitk_img_result)
        
        if not np_array.flags["C_CONTIGUOUS"]:
            np_array = np.ascontiguousarray(np_array)
        self._np_view_ref = np_array # Protege GC (Garbage Collector)

        spacing = sitk_img_result.GetSpacing()
        origin = sitk_img_result.GetOrigin()
        direction = sitk_img_result.GetDirection()
        
        dims = np_array.shape # Z, Y, X
        nx, ny, nz = dims[2], dims[1], dims[0]

        # Conversão LPS -> RAS (Origem e Matriz de Direção)
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
        
        # Geometria / Flip Direcional LPS -> RAS
        mat = vtk.vtkMatrix3x3()
        for r in range(3):
            for c in range(3):
                val = direction[r*3 + c]
                mat.SetElement(r, c, -val if r in (0,1) else val)
        vtk_image.SetDirectionMatrix(mat)
        
        vtk_image.ComputeBounds()
        vtk_image.GetScalarRange()

        # 1. Entrega a imagem desossada para os motores 2D e 3D do VTK
        self.coordenador_navegacao.navegador_2d.atualizar_volume(vtk_image)
        self.coordenador_navegacao.navegador_3d.atualizar_volume(vtk_image)
        
        # 2. Atualiza a Bounding Box do MIP para a nova imagem
        if hasattr(self.coordenador_navegacao, 'operador_projecao'):
            self.coordenador_navegacao.operador_projecao.bounds = vtk_image.GetBounds()
            
        # 3. Força a Placa de Vídeo a redesenhar as 4 telas instantaneamente
        if hasattr(self.coordenador_exibicao.widget_layout_ativo, "visoes"):
            for quadrante in self.coordenador_exibicao.widget_layout_ativo.visoes.values():
                quadrante.interactor.GetRenderWindow().Render()

    def anonimizar_e_exportar(self):
        """
        Exporta a série de imagens ativa aplicando a rotina de anonimização nas tags DICOM,
        ou permite exportar todas as séries carregadas em lote.
        """
        item = self.list_series.currentItem()
        if not item:
            self.statusBar().showMessage("Nenhuma série carregada para anonimizar.")
            return
            
        if not hasattr(self, "series_carregadas") or not self.series_carregadas:
            self.statusBar().showMessage("Erro: Séries não localizadas.")
            return

        series_id = item.data(Qt.ItemDataRole.UserRole)
        serie_ativa = next((s for s in self.series_carregadas if s["SeriesID"] == series_id), None)

        from PyQt6.QtWidgets import QMessageBox, QProgressDialog, QApplication
        import os

        # Caixa de diálogo para escolha
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Exportar Séries Anonimizadas")
        msg_box.setText("Deseja anonimizar apenas a série ativa ou TODAS as séries deste diretório?")
        msg_box.setIcon(QMessageBox.Icon.Question)
        btn_ativa = msg_box.addButton("Apenas Série Ativa", QMessageBox.ButtonRole.ActionRole)
        btn_todas = msg_box.addButton("Todas as Séries", QMessageBox.ButtonRole.ActionRole)
        btn_cancelar = msg_box.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        msg_box.exec()

        escolha = msg_box.clickedButton()
        if escolha == btn_cancelar:
            return

        exportar_todas = (escolha == btn_todas)

        # Seleciona o diretório de destino
        diretorio_destino = QFileDialog.getExistingDirectory(
            self, 
            "Selecionar Diretório de Destino para Anonimização"
        )
        if not diretorio_destino:
            return

        try:
            from anonimizador import AnonimizadorDicom
            anonimizador = AnonimizadorDicom()

            series_alvo = self.series_carregadas if exportar_todas else [serie_ativa]
            
            # Recalcula o total corretamente buscando dinamicamente
            total_arquivos = 0
            for s in series_alvo:
                if s:
                    dir_busca = s.get("Directory", self.diretorio_ativo)
                    arqs = sitk.ImageSeriesReader.GetGDCMSeriesFileNames(dir_busca, s["SeriesID"])
                    total_arquivos += len(arqs)

            progresso_dialog = QProgressDialog("Lendo e anonimizando do disco...", "Cancelar", 0, total_arquivos, self)
            progresso_dialog.setWindowTitle("Processando")
            progresso_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            progresso_dialog.show()

            arquivos_processados = 0
            todas_sucesso = True

            for s in series_alvo:
                if not s: continue
                
                # Busca os arquivos dinâmicos da série direto do HD
                dir_busca = s.get("Directory", self.diretorio_ativo)
                arquivos_completos = sitk.ImageSeriesReader.GetGDCMSeriesFileNames(dir_busca, s["SeriesID"])
                
                # Cria subpasta se exportar todas
                pasta_alvo = diretorio_destino
                if exportar_todas:
                    nome_pasta = f"Serie_{s['SeriesNumber']}" if s.get("SeriesNumber") else f"Serie_{s['SeriesID'][-6:]}"
                    pasta_alvo = os.path.join(diretorio_destino, nome_pasta)

                def callback_progresso(idx, total_serie, atual=arquivos_processados):
                    progresso_dialog.setValue(atual + idx)
                    QApplication.processEvents()

                sucesso_serie = anonimizador.anonimizar_serie(list(arquivos_completos), pasta_alvo, progress_callback=callback_progresso)
                arquivos_processados += len(arquivos_completos)
                
                if not sucesso_serie:
                    todas_sucesso = False

                if progresso_dialog.wasCanceled():
                    self.statusBar().showMessage("Anonimização cancelada pelo usuário.")
                    return

            if todas_sucesso:
                msg = f"Anonimização concluída com sucesso em: {diretorio_destino}"
                self.statusBar().showMessage(msg)
            else:
                self.statusBar().showMessage("Falha parcial ao anonimizar os arquivos.")

        except Exception as e:
            self.statusBar().showMessage(f"Erro no processo de anonimização: {str(e)}")

    def abrir_pasta(self):
        """
        Abre o seletor de arquivos de sistema para o usuário escolher o diretório DICOM.
        """
        diretorio = QFileDialog.getExistingDirectory(self, "Selecionar Pasta de Série DICOM")
        if diretorio:
            self.carregar_diretorio_dicom(diretorio)

    def carregar_diretorio_dicom(self, diretorio: str):
        """
        Efetua a varredura recursiva de pastas e o carregamento inteligente da primeira série.
        """
        t_inicio_dir = time.perf_counter()
        
        if not diretorio:
            return
            
        self.statusBar().showMessage(f"Escaneando diretório: {diretorio}...")
        try:
            from carregamento import CoordenadorCarregamento
            coordenador = CoordenadorCarregamento()
            
            from PyQt6.QtWidgets import QProgressDialog
            progresso = QProgressDialog("Analisando cabeçalhos DICOM...", "Cancelar", 0, 100, self)
            progresso.setWindowTitle("Escaneando Pasta")
            progresso.setWindowModality(Qt.WindowModality.WindowModal)
            progresso.setStyleSheet("QProgressDialog { background-color: #1a1a1a; color: #e0e0e0; } QLabel { color: #e0e0e0; } QPushButton { background-color: #2a2a2a; color: white; border: 1px solid #3d3d3d; padding: 4px; border-radius: 4px;}")
            progresso.show()

            def update_progress(atual, total):
                progresso.setMaximum(total)
                progresso.setValue(atual)
                QApplication.processEvents() # Força a interface a não congelar
                return not progresso.wasCanceled()

            series = coordenador.escanear_diretorio(diretorio, progress_callback=update_progress)
            print(f"\n[SENSOR DIR 1] Tempo travado na barra de progresso (Escaneamento): {time.perf_counter() - t_inicio_dir:.4f}s")
            
            if progresso.wasCanceled():
                self.statusBar().showMessage("Escaneamento cancelado pelo usuário.")
                return
            
            progresso.close()
            
            if not series:
                self.statusBar().showMessage("Nenhuma série DICOM válida encontrada no diretório.")
                return
            
            # Salva o diretório ativo e as séries carregadas
            self.diretorio_ativo = diretorio
            self.series_carregadas = series
            
            # Popula o list widget com as séries encontradas
            self.list_series.clear()
            for s in series:
                s_id = s["SeriesID"]
                num_slices = len(s["Files"])
                
                desc_serie = s.get("Description", "Desconhecida")
                num_serie = s.get("Number", "N/A")
                if len(desc_serie) > 25:
                    desc_serie = desc_serie[:22] + "..."
                    
                texto_item = f"Série {num_serie}: {desc_serie} ({num_slices} fatias)"
                item = QListWidgetItem(texto_item)
                item.setData(Qt.ItemDataRole.UserRole, {"id": s_id, "dir": s["Directory"], "files": s["Files"]})
                item.setToolTip(f"ID Completo: {s_id}\nDescrição: {s.get('Description', 'N/A')}\nNúmero: {num_serie}\nFatias: {num_slices}\nDiretório: {s['Directory']}")
                self.list_series.addItem(item)
            
            # Seleciona visualmente a primeira série na barra lateral
            if self.list_series.count() > 0:
                self.list_series.setCurrentRow(0)
            
            # Carrega a primeira série do diretório em background
            self.statusBar().showMessage("Carregando série DICOM em alta velocidade...")
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            
            primeira_serie_id = series[0]["SeriesID"]
            primeira_serie_dir = series[0]["Directory"]
            
            print(f"[SENSOR DIR 2] UI Lateral populada. Tempo Total até disparo do carregamento da 1ª Série: {time.perf_counter() - t_inicio_dir:.4f}s")
            
            self.thread_carregamento = ThreadCarregamento(coordenador, series[0]["Files"], primeira_serie_id)
            self.thread_carregamento.resultado.connect(lambda res: self.on_carregamento_concluido(res, primeira_serie_id))
            self.thread_carregamento.erro_carregamento.connect(self.on_carregamento_erro)
            self.thread_carregamento.start()
            
        except Exception as e:
            self.statusBar().showMessage(f"Erro ao analisar diretório DICOM: {str(e)}")
            import traceback
            traceback.print_exc()

    def on_carregamento_concluido(self, resultado_tupla, series_id):
        import time
        t_concluido_inicio = time.perf_counter()
        QApplication.restoreOverrideCursor()
        vtk_image, sitk_image, np_view, prop_dicom = resultado_tupla
        
        # Salva referências para evitar Garbage Collector do buffer C++
        self._sitk_img_ref = sitk_image
        self._np_view_ref = np_view
        
        # ─── LOG DE AUDITORIA DE INTEGRIDADE DE FASE ─────────────────────────
        # Executado obrigatoriamente ANTES de atualizar os Mappers
        try:
            from carregamento.carregamento_dicom import verificar_integridade_fase
            from vtk.util import numpy_support
            import numpy as np
            
            # Extrai a média de HU do centro
            scalars = vtk_image.GetPointData().GetScalars()
            media_hu = 0.0
            if scalars is not None:
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
            
            # Exibe no Console de Debug e no Status Bar
            log_auditoria = f"[AUDITORIA] Série: {series_id} | Fase Estimada: {media_hu:.2f} HU"
            print(log_auditoria)
            self.statusBar().showMessage(log_auditoria)
            
            # Identifica se a fase esperada é Pré-Contraste
            nome_fase_esperada = "Pré-Contraste" if "_PRE" in series_id or "PRE" in series_id.upper() else "Outra"
            
            # Executa a auditoria completa
            alerta = verificar_integridade_fase(vtk_image, nome_fase_esperada, series_id)
            if alerta:
                print(alerta)
                self.statusBar().showMessage(f"⚠️ {alerta}")
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "Alerta de Auditoria Médica", alerta)
        except Exception as e_aud:
            print(f"[AUDITORIA] Erro na execução da auditoria: {e_aud}")
            
        # a) Tempo gasto atualizando os volumes nas visões 2D e 3D.
        t_a_inicio = time.perf_counter()
        # Inicializa a renderização 2D (MPR) e 3D (Volume Rendering)
        if hasattr(self, 'coordenador_navegacao') and self.coordenador_navegacao is not None:
            # Object Pool Hot-Swapping! Não destrói os atores nem reseta câmeras
            self.coordenador_navegacao.navegador_2d.update_volume_data(vtk_image)
            t_mpr = time.perf_counter()
            print(f"[PROFILER] Atualização do MPR (navegador_2d): {t_mpr - t_a_inicio:.4f}s")
            
            self.coordenador_navegacao.navegador_3d.update_volume_data(vtk_image)
            t_3d = time.perf_counter()
            print(f"[PROFILER] Atualização do Volume 3D (navegador_3d): {t_3d - t_mpr:.4f}s")
            
            if hasattr(self.coordenador_navegacao, 'operador_projecao'):
                self.coordenador_navegacao.operador_projecao.bounds = vtk_image.GetBounds()
        else:
            # Primeira vez abrindo um exame, faz o processo completo
            from navegacao import CoordenadorNavegacao
            self.coordenador_navegacao = CoordenadorNavegacao(self)

            self.coordenador_navegacao.inicializar_visualizacao(
                vtk_image,
                self.coordenador_exibicao.widget_layout_ativo.visoes,
                janelamento_callback=self.on_mouse_janelamento_changed,
                espessura_callback=self.on_mouse_espessura_changed
            )
            t_mpr_3d = time.perf_counter()
            print(f"[PROFILER] Inicialização MPR e Volume 3D: {t_mpr_3d - t_a_inicio:.4f}s")
        
        # b) Tempo gasto na extração de Metadados (HUD).
        t_b_inicio = time.perf_counter()
        # Extração dos Metadados para o HUD
        hud_texto = self.extrair_texto_hud(prop_dicom)
        self.coordenador_navegacao.navegador_2d.atualizar_metadados_hud(hud_texto)
        self.coordenador_navegacao.navegador_3d.atualizar_metadados_hud(hud_texto)

        try:
            if hasattr(self, 'label_boas_vindas') and self.label_boas_vindas is not None:
                self.label_boas_vindas.hide()
                self.label_boas_vindas.deleteLater()
                self.label_boas_vindas = None
        except RuntimeError:
            self.label_boas_vindas = None

        if hasattr(self, 'coordenador_exibicao'):
            self.coordenador_exibicao.show()

        # c) Tempo gasto no Hard Reset de Mappers e Câmeras.
        # Hard Reset do Cinturão Vascular para o novo carregamento
        self.modo_projecao_atual = "Normal"
        self.spin_espessura.blockSignals(True)
        self.spin_espessura.setValue(0)
        self.spin_espessura.blockSignals(False)
        if hasattr(self, 'coordenador_navegacao') and hasattr(self.coordenador_navegacao, 'operador_projecao'):
            self.coordenador_navegacao.operador_projecao.aplicar_projecao_global("Normal", 0.0)

        # Configura as visões no layout 4-up
        if hasattr(self, 'coordenador_exibicao') and hasattr(self.coordenador_exibicao, 'widget_layout_ativo'):
            self.coordenador_exibicao.show()
            self.setCentralWidget(self.coordenador_exibicao)

        # Aplica o preset padrão Angio-TC Vascular (WW: 600 / WL: 150)
        self.aplicar_preset_por_nome("angio_tc")
        
        # d) Tempo gasto no "Render" final (o loop final onde chama GetRenderWindow().Render()).
        t_d_inicio = time.perf_counter()
        if hasattr(self.coordenador_exibicao.widget_layout_ativo, "visoes"):
            for visao_nome, widget_vtk in self.coordenador_exibicao.widget_layout_ativo.visoes.items():
                # Removido ResetCamera() repetitivo
                if hasattr(widget_vtk, "GetRenderWindow") and widget_vtk.GetRenderWindow():
                    widget_vtk.GetRenderWindow().Render()
        t_d_fim = time.perf_counter()
        print(f"[PROFILER] Renderização Final (RenderWindow().Render()): {t_d_fim - t_d_inicio:.4f}s")
        
        dim = vtk_image.GetDimensions()
        info_msg = f"Série carregada: {series_id} | Resolução: {dim[0]}x{dim[1]}x{dim[2]}"
        self.statusBar().showMessage(info_msg)

        def _deferred_update_3d():
            if hasattr(self, 'coordenador_navegacao') and hasattr(self.coordenador_navegacao, 'navegador_3d'):
                if self.coordenador_navegacao.navegador_3d.volume_ator:
                    mapper_3d = self.coordenador_navegacao.navegador_3d.volume_ator.GetMapper()
                    if mapper_3d:
                        mapper_3d.Update()
            if hasattr(self, 'coordenador_exibicao') and hasattr(self.coordenador_exibicao, 'widget_layout_ativo'):
                if hasattr(self.coordenador_exibicao.widget_layout_ativo, "visoes"):
                    if "3D" in self.coordenador_exibicao.widget_layout_ativo.visoes:
                        widget_3d = self.coordenador_exibicao.widget_layout_ativo.visoes["3D"]
                        if hasattr(widget_3d, "GetRenderWindow") and widget_3d.GetRenderWindow():
                            widget_3d.GetRenderWindow().Render()

        QTimer.singleShot(100, _deferred_update_3d)

        # Atualiza o cache e dispara cache preditivo da próxima série
        if series_id in self.cache_series:
            del self.cache_series[series_id]
        self.cache_series[series_id] = resultado_tupla
        if len(self.cache_series) > 3:
            del self.cache_series[next(iter(self.cache_series))]
            
        self._iniciar_cache_preditivo(series_id)
        
    def _iniciar_cache_preditivo(self, series_id_atual):
        """Inicia pré-carregamento da próxima série em background com IdlePriority."""
        if not hasattr(self, 'list_series'): return

        prox_item = None
        for i in range(self.list_series.count()):
            item = self.list_series.item(i)
            dados = item.data(Qt.ItemDataRole.UserRole)
            if dados and dados.get("id") == series_id_atual:
                if i + 1 < self.list_series.count():
                    prox_item = self.list_series.item(i + 1)
                break

        if not prox_item:
            return

        dados_prox = prox_item.data(Qt.ItemDataRole.UserRole)
        if not dados_prox:
            return

        prox_id  = dados_prox.get("id")
        arquivos = dados_prox.get("files")

        # Já está no cache de memória ou já existe uma thread de prefetch
        if not prox_id or not arquivos:
            return
        if prox_id in self.cache_series:
            print(f"[PREFETCH] Série '{prox_id}' já em cache de memória, nada a fazer.")
            return
        if prox_id in self._threads_prefetch:
            print(f"[PREFETCH] Série '{prox_id}' já está sendo carregada em background.")
            return

        from carregamento import CoordenadorCarregamento
        coordenador = CoordenadorCarregamento()
        thread = ThreadCarregamento(coordenador, arquivos, prox_id, prefetch=True)
        thread.prefetch_concluido.connect(self._on_prefetch_concluido)
        thread.finished.connect(lambda t=prox_id: self._threads_prefetch.pop(t, None))

        self._threads_prefetch[prox_id] = thread

        # IdlePriority: o SO só cede CPU quando nenhum outro processo precisa
        thread.start(QThread.Priority.IdlePriority)
        print(f"[PREFETCH] Iniciando pré-carregamento de '{prox_id}' em IdlePriority.")

    def _on_prefetch_concluido(self, resultado_tupla, series_id):
        """Recebe o resultado do prefetch e deposita no cache de memória."""
        print(f"[PREFETCH] '{series_id}' carregado em background. Depositando no cache.")
        if series_id in self.cache_series:
            del self.cache_series[series_id]
        self.cache_series[series_id] = resultado_tupla
        if len(self.cache_series) > 3:
            del self.cache_series[next(iter(self.cache_series))]
        # Remove da fila de prefetch
        self._threads_prefetch.pop(series_id, None)

    def _on_cache_silencioso_concluido(self, resultado_tupla, series_id):
        if series_id in self.cache_series:
            del self.cache_series[series_id]
        self.cache_series[series_id] = resultado_tupla
        if len(self.cache_series) > 3:
            del self.cache_series[next(iter(self.cache_series))]

    def on_layout_selecionado(self, modo: str):
        if not hasattr(self, 'coordenador_exibicao'):
            return
            
        self.coordenador_exibicao.definir_layout(modo)
        
        # Força o repinte do fundo nas visões ativas
        if hasattr(self.coordenador_exibicao.widget_layout_ativo, "visoes"):
            for visao_nome, widget_vtk in self.coordenador_exibicao.widget_layout_ativo.visoes.items():
                if hasattr(widget_vtk, "GetRenderWindow") and widget_vtk.GetRenderWindow():
                    widget_vtk.GetRenderWindow().Render()

    def on_carregamento_erro(self, msg):
        QApplication.restoreOverrideCursor()
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.warning(self, "Aviso de Carregamento", f"Falha ao carregar a série:\n{msg}")
        self.statusBar().showMessage(f"Erro durante carregamento multithread.")

    def carregar_serie_virtual(self, vtk_image, sitk_image, np_array):
        # Salva referências para evitar Garbage Collector do buffer C++
        self._sitk_img_ref = sitk_image
        self._np_view_ref = np_array
        
        # Entrega a imagem desossada para os motores 2D e 3D do VTK
        if hasattr(self, 'coordenador_navegacao') and self.coordenador_navegacao is not None:
            self.coordenador_navegacao.navegador_2d.update_volume_data(vtk_image)
            self.coordenador_navegacao.navegador_3d.update_volume_data(vtk_image)
            
            if hasattr(self.coordenador_navegacao, 'operador_projecao'):
                self.coordenador_navegacao.operador_projecao.bounds = vtk_image.GetBounds()
        else:
            from navegacao import CoordenadorNavegacao
            self.coordenador_navegacao = CoordenadorNavegacao(self)
            self.coordenador_navegacao.inicializar_visualizacao(
                vtk_image,
                self.coordenador_exibicao.widget_layout_ativo.visoes,
                janelamento_callback=self.on_mouse_janelamento_changed,
                espessura_callback=self.on_mouse_espessura_changed
            )
            
        # Hard Reset do Cinturão Vascular para o novo carregamento
        self.modo_projecao_atual = "Normal"
        self.spin_espessura.blockSignals(True)
        self.spin_espessura.setValue(0)
        self.spin_espessura.blockSignals(False)
        if hasattr(self, 'coordenador_navegacao') and hasattr(self.coordenador_navegacao, 'operador_projecao'):
            self.coordenador_navegacao.operador_projecao.aplicar_projecao_global("Normal", 0.0)

        # Configura as visões no layout 4-up
        if hasattr(self, 'coordenador_exibicao') and hasattr(self.coordenador_exibicao, 'widget_layout_ativo'):
            self.coordenador_exibicao.show()
            self.setCentralWidget(self.coordenador_exibicao)

        # Aplica o preset padrão Angio-TC Vascular (WW: 600 / WL: 150)
        self.aplicar_preset_por_nome("angio_tc")
        
        # Aplica o preset 3D específico para DSA
        if hasattr(self, 'coordenador_navegacao') and self.coordenador_navegacao is not None:
            if hasattr(self.coordenador_navegacao, 'navegador_3d') and self.coordenador_navegacao.navegador_3d is not None:
                self.coordenador_navegacao.navegador_3d.aplicar_preset_dsa()
        
        # Renderização Final
        if hasattr(self.coordenador_exibicao.widget_layout_ativo, "visoes"):
            for visao_nome, widget_vtk in self.coordenador_exibicao.widget_layout_ativo.visoes.items():
                if hasattr(widget_vtk, "GetRenderWindow") and widget_vtk.GetRenderWindow():
                    widget_vtk.GetRenderWindow().Render()
                    
        def _deferred_update_3d():
            if hasattr(self, 'coordenador_navegacao') and hasattr(self.coordenador_navegacao, 'navegador_3d'):
                if self.coordenador_navegacao.navegador_3d.volume_ator:
                    mapper_3d = self.coordenador_navegacao.navegador_3d.volume_ator.GetMapper()
                    if mapper_3d:
                        mapper_3d.Update()
            if hasattr(self, 'coordenador_exibicao') and hasattr(self.coordenador_exibicao, 'widget_layout_ativo'):
                if hasattr(self.coordenador_exibicao.widget_layout_ativo, "visoes"):
                    if "3D" in self.coordenador_exibicao.widget_layout_ativo.visoes:
                        widget_3d = self.coordenador_exibicao.widget_layout_ativo.visoes["3D"]
                        if hasattr(widget_3d, "GetRenderWindow") and widget_3d.GetRenderWindow():
                            widget_3d.GetRenderWindow().Render()

        QTimer.singleShot(100, _deferred_update_3d)
        
        self.statusBar().showMessage(f"Série Virtual carregada com sucesso.")
 
    def carregar_serie_selecionada(self, item):
        """
        Carrega dinamicamente a série selecionada no list widget de forma assíncrona.
        
        Se a série já estiver no cache de memória (incluindo por prefetch), é instantâneo.
        Se estiver sendo carregada em background (prefetch), promove a prioridade da thread.
        """
        if not item or not hasattr(self, "series_carregadas") or not self.series_carregadas:
            return
 
        dados = item.data(Qt.ItemDataRole.UserRole)
        if not dados or not isinstance(dados, dict):
            return
            
        # Hot-swapping de Série Virtual
        if dados.get("virtual"):
            self.statusBar().showMessage("Carregando Série Virtual instantaneamente...")
            self.on_subtracao_concluida(dados["sitk_image"])
            
            nome_serie = item.text()
            if "[SUB]" in nome_serie:
                if hasattr(self, 'coordenador_navegacao') and hasattr(self.coordenador_navegacao, 'navegador_3d'):
                    self.coordenador_navegacao.navegador_3d.aplicar_preset_angio()
            
            return

        series_id = dados.get("id")
        diretorio_serie = dados.get("dir")

        if not series_id or not diretorio_serie:
            self.statusBar().showMessage("Erro: Dados da série inválidos no item.")
            return

        # 1. Cache de memória: entrega instantânea
        if series_id in getattr(self, 'cache_series', {}):
            self.statusBar().showMessage("⚡ Série em CACHE! Troca instantânea.")
            self.on_carregamento_concluido(self.cache_series[series_id], series_id)
            return

        # 2. Prefetch em andamento: promove para HighPriority e aguarda
        if series_id in self._threads_prefetch:
            thread_bg = self._threads_prefetch[series_id]
            if thread_bg.isRunning():
                print(f"[PREFETCH] Promovendo '{series_id}' para HighPriority!")
                thread_bg.setPriority(QThread.Priority.HighPriority)
                self.statusBar().showMessage("🔄 Acelerando carregamento em background...")
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

                # Redireciona o sinal de prefetch para a tela principal e aguarda
                thread_bg.prefetch_concluido.disconnect()
                thread_bg.prefetch_concluido.connect(
                    lambda res, sid=series_id: self._on_prefetch_promovido(res, sid)
                )
                return

        # 3. Série não está no cache nem em prefetch: carregamento normal
        self.statusBar().showMessage("Carregando série...")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        if hasattr(self, 'coordenador_navegacao'):
            self.coordenador_navegacao.navegador_2d.atualizar_metadados_hud("CARREGANDO SÉRIE ALTA RESOLUÇÃO...")
            self.coordenador_navegacao.navegador_3d.atualizar_metadados_hud("CARREGANDO SÉRIE ALTA RESOLUÇÃO...")

        from carregamento import CoordenadorCarregamento
        coordenador = CoordenadorCarregamento()
        arquivos = dados.get("files")
        print(f"DEBUG: Carregando Série {dados['id']} do diretório {dados['dir']}")
        self.thread_carregamento = ThreadCarregamento(coordenador, arquivos, series_id)
        self.thread_carregamento.resultado.connect(lambda res: self.on_carregamento_concluido(res, series_id))
        self.thread_carregamento.erro_carregamento.connect(self.on_carregamento_erro)
        self.thread_carregamento.start()

    def _on_prefetch_promovido(self, resultado_tupla, series_id):
        """Chamado quando uma thread de prefetch promovida termina."""
        QApplication.restoreOverrideCursor()
        self._on_prefetch_concluido(resultado_tupla, series_id)  # deposita no cache
        self.on_carregamento_concluido(resultado_tupla, series_id)  # exibe na tela

    def carregar_serie_no_quadrante(self, dados_serie, quadrante):
        print(f"\n--- INICIANDO DRAG & DROP NA {quadrante.label.text()} ---")
        t_inicio_dd = time.perf_counter()
        
        series_id = dados_serie.get("id")
        
        if series_id in getattr(self, 'cache_series', {}):
            print(f"[SENSOR CACHE] Hit! Imagem extraída da RAM. Tempo: {time.perf_counter() - t_inicio_dd:.4f}s")
            tupla = self.cache_series[series_id]
            vtk_image = tupla[0]
            prop_dicom = tupla[3]
            nome_visao = quadrante.label.text()
            
            tempo_antes = time.perf_counter()
            self.coordenador_navegacao.inicializar_tela_dinamica(nome_visao, vtk_image, quadrante, self.on_mouse_janelamento_changed, self.on_mouse_espessura_changed)
            tempo_final = time.perf_counter()
            print(f"[SENSOR DRAW] Tempo total para inicializar e desenhar na tela: {tempo_final - tempo_antes:.4f}s")
            
            self.coordenador_navegacao.navegador_2d.meta_actors[nome_visao].SetInput(self.extrair_texto_hud(prop_dicom))
            
            import gc
            QTimer.singleShot(100, gc.collect)
            return
            
        arquivos = dados_serie.get("files")
        if not arquivos:
            return
            
        from carregamento import CoordenadorCarregamento
        coordenador = CoordenadorCarregamento()
        
        thread_isolada = ThreadCarregamento(coordenador, arquivos, series_id)
        if not hasattr(self, 'threads_isoladas'): self.threads_isoladas = []
        self.threads_isoladas.append(thread_isolada)
        
        def on_loaded(res, q=quadrante):
            nome_visao = q.label.text()
            
            tempo_antes = time.perf_counter()
            self.coordenador_navegacao.inicializar_tela_dinamica(nome_visao, res[0], q, self.on_mouse_janelamento_changed, self.on_mouse_espessura_changed)
            tempo_final = time.perf_counter()
            print(f"[SENSOR DRAW] Tempo total para inicializar e desenhar na tela: {tempo_final - tempo_antes:.4f}s")
            
            self.coordenador_navegacao.navegador_2d.meta_actors[nome_visao].SetInput(self.extrair_texto_hud(res[3]))
            
            import gc
            QTimer.singleShot(100, gc.collect)
            
        thread_isolada.resultado.connect(on_loaded)
        thread_isolada.finished.connect(lambda t=thread_isolada: self.threads_isoladas.remove(t) if t in self.threads_isoladas else None)
        thread_isolada.start()
