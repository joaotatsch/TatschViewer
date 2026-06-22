# -*- coding: utf-8 -*-
import sys
import gc
import traceback
import numpy as np
import vtk
from vtkmodules.util import numpy_support
from PyQt6.QtCore import QThread, pyqtSignal
import SimpleITK as sitk

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

            # --- Novo Algoritmo de Mascaramento Ã“sseo e Subtração ---
            self.log_sinal.emit("Criando Máscara Ã“ssea (Threshold)...")
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

class ThreadExtracaoVascularRMRapida(QThread):
    progresso_sinal = pyqtSignal(int, str)
    log_sinal = pyqtSignal(str)
    virtual_sinal = pyqtSignal(object, object, str)  # vtk_image, sitk_image, nome_serie
    erro_sinal = pyqtSignal(str)

    def __init__(self, sitk_image, seed_index):
        super().__init__()
        self.sitk_image = sitk_image
        self.seed_index = seed_index

    def run(self):
        try:
            import time
            import gc
            import numpy as np
            import vtk
            from vtkmodules.util import numpy_support
            import SimpleITK as sitk

            self.log_sinal.emit("Iniciando Subtração Guiada MRA (Anti-Leaking)...")
            
            t0_global = time.time()

            # PASSO 1: SKULL STRIPPING ULTRA-RÁPIDO (Corte das Pontes de Gordura em < 1s)
            self.progresso_sinal.emit(10, "Isolando cavidade central (Erosão)...")
            t_start = time.time()
            
            # ESTRATÉGIA ULTRA-RÁPIDA (Trabalhar em baixa resolução para milissegundos de tempo)
            shrink = sitk.ShrinkImageFilter()
            shrink.SetShrinkFactor(2)
            img_small = shrink.Execute(self.sitk_image)
            
            max_val = float(sitk.GetArrayViewFromImage(img_small).max())
            mask_small = sitk.BinaryThreshold(img_small, lowerThreshold=15.0, upperThreshold=max_val)
            
            # Preenche buracos em baixa resolução (muito mais rápido, de 7s cai para 0.1s)
            mask_small = sitk.BinaryFillhole(mask_small)
            
            # Erode a cabeça sólida em [6, 6, 6] (equivalente a arrancar 12 pixels da imagem original)
            mask_small_erodida = sitk.BinaryErode(mask_small, [6, 6, 6])
            
            # Retorna para o tamanho original
            resampler = sitk.ResampleImageFilter()
            resampler.SetReferenceImage(self.sitk_image)
            resampler.SetInterpolator(sitk.sitkNearestNeighbor)
            mask_erodida = resampler.Execute(mask_small_erodida)
            
            # Multiplica a imagem original pela mascara erodida profunda (Isola o Cerebro)
            cerebro_isolado = sitk.Mask(self.sitk_image, mask_erodida)
            print(f"[SENSOR] Erosao da Pele: {time.time() - t_start:.2f}s", flush=True)

            # PASSO 2: CÁLCULO DE LIMIAR SUPERIOR (Vetorizado)
            self.progresso_sinal.emit(30, "Calculando Limiar Superior Vascular...")
            t_start = time.time()
            array_cerebro = sitk.GetArrayViewFromImage(cerebro_isolado)
            
            # Filtra apenas os pixels do cérebro
            array_validos = array_cerebro[array_cerebro > 0]
            if len(array_validos) > 0:
                # O percentil 91 é a "Barreira de Contenção Oftálmica".
                # Se baixarmos para P87 ou P85, a enchente atravessa a artéria oftálmica e inunda
                # a gordura retrobulbar (órbitas) que fica no fundo do crânio.
                thresh_value = float(np.percentile(array_validos, 91.0))
            else:
                thresh_value = 0.0
                
            max_value = float(array_cerebro.max())
            print(f"[SENSOR] Calculo Percentil (Threshold): {time.time() - t_start:.2f}s", flush=True)

            # PASSO 3: CRESCIMENTO DE REGIÃO ENGAIOLADO (Anti-Leaking)
            self.progresso_sinal.emit(50, "Crescimento Engaiolado de Região (Anti-Leaking)...")
            t_start = time.time()
            
            seed_x = max(0, int(self.seed_index[0]))
            seed_y = max(0, int(self.seed_index[1]))
            seed_z = max(0, int(self.seed_index[2]))
            semente = (seed_x, seed_y, seed_z)
            
            seed_intensity_caged = float(cerebro_isolado.GetPixel(seed_x, seed_y, seed_z))
            
            # MATEMÁTICA ANTI-LEAKING GLOBAL:
            if seed_intensity_caged >= thresh_value:
                lower_bound = thresh_value
            else:
                # Se o vaso for marginal, permite descer até o percentil 90 absoluto
                lower_bound = max(seed_intensity_caged * 0.95, float(np.percentile(array_validos, 90.0)) if len(array_validos) > 0 else 0)
            
            print(f"[SENSOR DEBUG] Semente na Gaiola: {seed_intensity_caged:.2f} | Chão Vascular (P91): {thresh_value:.2f} | Lower Bound Seguro: {lower_bound:.2f}", flush=True)
            
            if seed_intensity_caged < lower_bound:
                self.log_sinal.emit("⚠️ Semente caiu fora do cérebro ou em área apagada. Clique mais ao centro!")
                
            # Inicia na semente e inunda tudo que seja mais brilhante que o lower_bound
            vasos_mask = sitk.ConnectedThreshold(cerebro_isolado, seedList=[semente], lower=lower_bound, upper=max_value, replaceValue=1)
            print(f"[SENSOR] ConnectedThreshold (Vaso Isolado): {time.time() - t_start:.2f}s", flush=True)

            # PASSO 4: CORTE FINAL
            self.progresso_sinal.emit(85, "Aplicando Corte Final...")
            t_start = time.time()
            # Multiplica a imagem original apenas pela mascara do vaso extraido
            resultado_final_sitk = sitk.Mask(self.sitk_image, vasos_mask)
            print(f"[SENSOR] Injeção Final: {time.time() - t_start:.2f}s", flush=True)
            print(f"[SENSOR] TEMPO TOTAL MRA: {time.time() - t0_global:.2f}s", flush=True)

            # VTK Export
            self.progresso_sinal.emit(95, "Convertendo para formato VTK...")
            np_array = sitk.GetArrayFromImage(resultado_final_sitk)
            if not np_array.flags["C_CONTIGUOUS"]:
                np_array = np.ascontiguousarray(np_array)
            
            spacing = resultado_final_sitk.GetSpacing()
            origin = resultado_final_sitk.GetOrigin()
            direction = resultado_final_sitk.GetDirection()
            
            dims = np_array.shape
            nx, ny, nz = dims[2], dims[1], dims[0]
            
            if len(origin) >= 3:
                origin_vtk = [-origin[0], -origin[1], origin[2]]
            else:
                origin_vtk = [0.0, 0.0, 0.0]
                
            vtk_type = numpy_support.get_vtk_array_type(np_array.dtype)
            vtk_array = numpy_support.numpy_to_vtk(num_array=np_array.ravel(), deep=False, array_type=vtk_type)
            
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
            
            min_val = float(np.min(np_array))
            p99_9 = float(np.percentile(np_array, 99.9))
            if p99_9 > min_val:
                ww = p99_9 - min_val
                wl = min_val + (ww / 2.0)
                vtk_image.GetScalarRange()
                vtk_image._mr_windowing = (ww, wl)

            self.progresso_sinal.emit(100, "Concluído!")
            self.log_sinal.emit("Subtração Guiada MR Concluída!")
            self.virtual_sinal.emit(vtk_image, resultado_final_sitk, "Série Virtual: [SUB MR] MRA Rápida (Semente)")
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.erro_sinal.emit(str(e))
