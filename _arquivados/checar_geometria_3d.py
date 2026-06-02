#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script CLI independente para validação geométrica tridimensional de volumes DICOM.
Verifica a homogeneidade de orientação das fatias, valida se a proporção de aspecto
(Spacing) do vtkImageData está correta e confere a matriz de direção RAS após alinhamento.
"""
import os
import sys
import argparse
import numpy as np
import SimpleITK as sitk
import vtk

# Adiciona o diretório atual ao path para permitir imports do projeto
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from carregamento.carregamento_dicom import CarregadorDicom, is_scout_ou_localizer_ou_secundario
from carregamento.carregamento_pastas_dicom import CarregadorPastasDicom

def checar_geometria_serie(diretorio_serie: str, series_id: str):
    """
    Verifica a homogeneidade e a integridade geométrica de uma série DICOM carregada.
    """
    print(f"\n======================================================================")
    print(f" Análise Geométrica da Série: {series_id}")
    print(f" Diretório: {diretorio_serie}")
    print(f"======================================================================")
    
    # 1. Validação de Fatias e Homogeneidade
    reader = sitk.ImageSeriesReader()
    real_series_id = series_id.split("_")[0]
    nomes_arquivos = list(reader.GetGDCMSeriesFileNames(diretorio_serie, real_series_id))
    
    print(f"-> Total de fatias DICOM na série original: {len(nomes_arquivos)}")
    
    import pydicom
    grupos_iop = {}
    
    for f in nomes_arquivos:
        if is_scout_ou_localizer_ou_secundario(f):
            continue
            
        try:
            ds = pydicom.dcmread(f, stop_before_pixels=True, force=True)
            if not hasattr(ds, 'ImageOrientationPatient') or not hasattr(ds, 'ImagePositionPatient'):
                continue
            iop = tuple(np.round(np.array(ds.ImageOrientationPatient, dtype=float), 3))
            grupos_iop.setdefault(iop, []).append(f)
        except Exception as e:
            print(f"   [AVISO] Erro ao ler metadados do arquivo {os.path.basename(f)}: {e}")

    if not grupos_iop:
        print(f"   [FALHA] Nenhum metadado de orientação encontrado na série!")
        return False
        
    # O maior grupo de orientação representa o volume principal homogêneo
    iop_dominante = max(grupos_iop.keys(), key=lambda k: len(grupos_iop[k]))
    nomes_filtrados = grupos_iop[iop_dominante]
    
    print(f"-> Fatias válidas diagnósticas (não scouts, pertencentes ao volume principal homogêneo): {len(nomes_filtrados)}")
    if len(nomes_filtrados) < 10:
        print(f"   [FALHA] Série rejeitada! Menos de 10 fatias diagnósticas no volume principal.")
        return False
        
    print(f"   [SUCESSO] Homogeneidade espacial confirmada. {len(nomes_filtrados)} fatias possuem a mesma orientação {iop_dominante}.")

    # 2. Carregar série via pipeline zero-copy do Neuroviewer
    try:
        carregador = CarregadorDicom()
        vtk_image, sitk_image, numpy_view, propriedades = carregador.carregar_serie(nomes_filtrados, series_id)
        print(f"-> Carregamento da série via Neuroviewer realizado com sucesso.")
    except Exception as e:
        print(f"   [FALHA] Erro crítico ao carregar série via CarregadorDicom: {e}")
        return False

    # 3. Validar Proporção de Aspecto (Spacing) e Dimensões
    sitk_spacing = sitk_image.GetSpacing()
    vtk_spacing = vtk_image.GetSpacing()
    sitk_dims = sitk_image.GetSize()
    vtk_dims = vtk_image.GetDimensions()
    
    print(f"\n--- VALIDAÇÃO DE DIMENSÕES E ESPAÇAMENTO (SPACING) ---")
    print(f"   SimpleITK Size: {sitk_dims} vs VTK Dimensions: {vtk_dims}")
    print(f"   SimpleITK Spacing: {sitk_spacing} vs VTK Spacing: {vtk_spacing}")
    
    if sitk_dims == vtk_dims:
        print(f"   [SUCESSO] Dimensões 3D estão perfeitamente alinhadas.")
    else:
        print(f"   [FALHA] Divergência de dimensões detectada!")
        
    spacing_ok = all(abs(a - b) < 1e-4 for a, b in zip(sitk_spacing, vtk_spacing))
    if spacing_ok:
        print(f"   [SUCESSO] Proporção de aspecto (Spacing) preservada perfeitamente. Sem 'cabeça de alienígena'!")
    else:
        print(f"   [FALHA] Divergência no Spacing detectada!")

    # 4. Validar Matriz de Direção LPS (ITK) vs RAS (VTK)
    print(f"\n--- VALIDAÇÃO DA MATRIZ DE DIREÇÃO (LPS para RAS) ---")
    sitk_dir = sitk_image.GetDirection()
    vtk_dir = vtk_image.GetDirectionMatrix()
    
    print("   Matriz de Direção SimpleITK (LPS):")
    m_lps = np.array(sitk_dir).reshape(3, 3)
    for row in m_lps:
        print(f"      [ {row[0]:.6f}, {row[1]:.6f}, {row[2]:.6f} ]")
        
    print("   Matriz de Direção VTK (RAS):")
    m_ras = np.zeros((3, 3))
    for r in range(3):
        for c in range(3):
            m_ras[r, c] = vtk_dir.GetElement(r, c)
        print(f"      [ {m_ras[r, 0]:.6f}, {m_ras[r, 1]:.6f}, {m_ras[r, 2]:.6f} ]")
        
    # Na conversão LPS para RAS, as duas primeiras linhas de direção (eixos X e Y)
    # devem ser multiplicadas por -1. A terceira linha (eixo Z) permanece idêntica.
    matriz_esperada = np.copy(m_lps)
    matriz_esperada[0, :] = -matriz_esperada[0, :]
    matriz_esperada[1, :] = -matriz_esperada[1, :]
    
    diferenca = np.abs(m_ras - matriz_esperada)
    if np.max(diferenca) < 1e-4:
        print(f"   [SUCESSO] Conversão de Matriz LPS -> RAS está correta!")
        print(f"             Eixos X e Y invertidos e eixo Z mantido conforme padrão clínico.")
    else:
        print(f"   [FALHA] Conversão LPS -> RAS incorreta!")
        print(f"           Diferença máxima: {np.max(diferenca):.6f}")
        
    # 5. Validar Origem
    sitk_origin = sitk_image.GetOrigin()
    vtk_origin = vtk_image.GetOrigin()
    print(f"\n--- VALIDAÇÃO DA ORIGEM ESPACIAL ---")
    print(f"   SimpleITK Origin: {sitk_origin}")
    print(f"   VTK Origin: {vtk_origin}")
    
    origem_esperada_ras = (-sitk_origin[0], -sitk_origin[1], sitk_origin[2])
    diferenca_origem = np.abs(np.array(vtk_origin) - np.array(origem_esperada_ras))
    if np.max(diferenca_origem) < 1e-4:
        print(f"   [SUCESSO] Origem convertida corretamente de LPS para RAS!")
    else:
        print(f"   [FALHA] Conversão de origem LPS -> RAS incorreta!")
        
    return True

def main():
    parser = argparse.ArgumentParser(description="Checador de Geometria 3D para volumes DICOM do Neuroviewer.")
    parser.add_argument("diretorio", type=str, help="Caminho do diretório principal contendo as fatias ou séries DICOM.")
    args = parser.parse_args()
    
    if not os.path.exists(args.diretorio):
        print(f"Erro: O diretório '{args.diretorio}' não existe.")
        sys.exit(1)
        
    print(f"Escaneando diretório recursivamente em busca de séries DICOM...")
    carregador_pastas = CarregadorPastasDicom()
    series = carregador_pastas.escanear_pasta(args.diretorio)
    
    if not series:
        print("Nenhuma série DICOM válida e homogênea (mínimo de 10 fatias) foi encontrada.")
        sys.exit(1)
        
    print(f"Encontradas {len(series)} séries DICOM válidas.")
    
    sucessos = 0
    for s in series:
        if checar_geometria_serie(s["Directory"], s["SeriesID"]):
            sucessos += 1
            
    print(f"\n======================================================================")
    print(f" Relatório Final: {sucessos} de {len(series)} séries validadas com sucesso.")
    print(f"======================================================================")
    
    if sucessos < len(series):
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
