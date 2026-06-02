import os
import argparse
import sys
import SimpleITK as sitk

def load_dicom_series(directory: str) -> sitk.Image:
    """Carrega uma série DICOM de um diretório e retorna um volume SimpleITK."""
    print(f"[!] Lendo série DICOM do diretório: {directory}")
    reader = sitk.ImageSeriesReader()
    dicom_names = reader.GetGDCMSeriesFileNames(directory)
    if not dicom_names:
        raise ValueError(f"Nenhum arquivo DICOM encontrado no diretório: {directory}")
    
    reader.SetFileNames(dicom_names)
    image = reader.Execute()
    print(f"[-] Volume carregado: Tamanho={image.GetSize()}, Spacing={image.GetSpacing()}")
    return image

def command_iteration(method: sitk.ImageRegistrationMethod) -> None:
    """Callback para printar a telemetria do registro (iteração e métrica)."""
    print(f"[-] Iteração: {method.GetOptimizerIteration():3} | Métrica: {method.GetMetricValue():10.5f}")

def perform_dsa(dir_sem_contraste: str, dir_angio: str, output_path: str) -> None:
    """
    Realiza a Subtração Digital Angiográfica (DSA) entre duas fases de tomografia.
    
    Args:
        dir_sem_contraste: Caminho para o diretório DICOM da fase Sem Contraste (Moving).
        dir_angio: Caminho para o diretório DICOM da fase Angio (Fixed).
        output_path: Caminho do arquivo de saída (ex: .nrrd ou .nii.gz).
    """
    try:
        # 1. Carregar as imagens
        print("\n=== Etapa 1: Carregamento das Imagens ===")
        fixed_image = load_dicom_series(dir_angio) # Angio é a imagem Fixed
        moving_image = load_dicom_series(dir_sem_contraste) # Sem contraste é a Moving

        # Assegurar que ambas as imagens sejam float32 para as etapas matemáticas
        fixed_image = sitk.Cast(fixed_image, sitk.sitkFloat32)
        moving_image = sitk.Cast(moving_image, sitk.sitkFloat32)

        # 2. Configurar o Registro de Imagem
        print("\n=== Etapa 2: Registro de Imagem (Alinhamento) ===")
        registration_method = sitk.ImageRegistrationMethod()

        # Métrica: Mattes Mutual Information (ideal para diferentes contrastes)
        registration_method.SetMetricAsMattesMutualInformation(numberOfHistogramBins=50)
        registration_method.SetMetricSamplingStrategy(registration_method.RANDOM)
        registration_method.SetMetricSamplingPercentage(0.01)

        # Interpolador: Linear
        registration_method.SetInterpolator(sitk.sitkLinear)

        # Otimizador: Gradient Descent
        registration_method.SetOptimizerAsRegularStepGradientDescent(
            learningRate=1.0, 
            minStep=1e-4, 
            numberOfIterations=100
        )
        
        # Transformada: Rígida (Euler 3D) pois o crânio não sofre deformações
        initial_transform = sitk.CenteredTransformInitializer(
            fixed_image, 
            moving_image, 
            sitk.Euler3DTransform(), 
            sitk.CenteredTransformInitializerFilter.GEOMETRY
        )
        registration_method.SetInitialTransform(initial_transform, inPlace=False)

        # Adicionar o Callback para acompanhamento da otimização na saída do console
        registration_method.AddCommand(sitk.sitkIterationEvent, lambda: command_iteration(registration_method))

        # Executar registro
        print("[!] Iniciando Otimização...")
        final_transform = registration_method.Execute(fixed_image, moving_image)
        
        print("\n[-] Registro Concluído.")
        print(f"[-] Motivo da parada: {registration_method.GetOptimizerStopConditionDescription()}")
        print(f"[-] Valor final da métrica: {registration_method.GetMetricValue()}")

        # 3. Resampling da imagem Moving para a grade Fixed
        print("\n=== Etapa 3: Resampling da Fase Sem Contraste ===")
        resampled_moving = sitk.Resample(
            moving_image, 
            fixed_image, 
            final_transform, 
            sitk.sitkLinear, 
            0.0, # Valor padrão para partes fora da imagem
            moving_image.GetPixelID()
        )

        # 4. Subtração Matemática
        print("\n=== Etapa 4: Subtração (Angio - Sem Contraste Registrada) ===")
        subtracted_image = sitk.Subtract(fixed_image, resampled_moving)

        # 5. Limpeza (Threshold) - Zerar valores negativos
        print("\n=== Etapa 5: Limpeza (Thresholding) ===")
        # Zera qualquer valor abaixo de 0
        max_val = sys.float_info.max
        dsa_result = sitk.Threshold(
            subtracted_image,
            lower=0.0,
            upper=max_val,
            outsideValue=0.0
        )
        
        # Converte para int16 (tipo de dado mais convencional em volumes médicos para economizar memória na exportação)
        dsa_result = sitk.Cast(dsa_result, sitk.sitkInt16)

        # 6. Exportação
        print(f"\n=== Etapa 6: Exportação ===")
        if not output_path.endswith(('.nrrd', '.nii.gz')):
            print("[!] Aviso: Extensão não reconhecida ou ausente. O formato padrão .nrrd será utilizado.")
            output_path += '.nrrd'
            
        print(f"[!] Salvando Gabarito DSA em: {output_path}")
        sitk.WriteImage(dsa_result, output_path)
        print("[-] Operação finalizada com sucesso!")

    except Exception as e:
        print(f"\n[ERRO FATAL] Ocorreu uma exceção durante o processamento:\n{str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Gerador de Digital Subtraction Angiography (DSA) - Gabarito para o Neuroviewer."
    )
    
    parser.add_argument(
        "--sem-contraste", 
        type=str, 
        required=True, 
        help="Caminho para o diretório contendo a série DICOM Sem Contraste (Moving)."
    )
    
    parser.add_argument(
        "--angio", 
        type=str, 
        required=True, 
        help="Caminho para o diretório contendo a série DICOM Angio-TC (Fixed)."
    )
    
    parser.add_argument(
        "--output", 
        type=str, 
        required=True, 
        help="Caminho e nome do arquivo de saída (ex: gabarito_dsa.nrrd ou .nii.gz)."
    )

    args = parser.parse_args()

    # Validar a existência dos diretórios de entrada
    if not os.path.isdir(args.sem_contraste):
        print(f"[ERRO] O diretório Sem Contraste não existe: {args.sem_contraste}")
        sys.exit(1)
        
    if not os.path.isdir(args.angio):
        print(f"[ERRO] O diretório Angio-TC não existe: {args.angio}")
        sys.exit(1)

    perform_dsa(
        dir_sem_contraste=args.sem_contraste,
        dir_angio=args.angio,
        output_path=args.output
    )
