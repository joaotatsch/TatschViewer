# -*- coding: utf-8 -*-
"""
Script de Compilação Automatizada do TatschViewer 1.5 (Release Candidate).
Empacota a aplicação com todas as dependências ocultas de C++ (VTK, SimpleITK)
e os recursos visuais (icones) em um diretório executável standalone.
"""
import os
import sys
import subprocess

def verificar_pyinstaller():
    """
    Verifica se o PyInstaller está disponível no ambiente atual do Python.
    Caso não esteja, realiza a instalação automática utilizando pip.
    """
    try:
        import PyInstaller
        print("[COMPILAÇÃO] PyInstaller já está instalado no ambiente.")
        return True
    except ImportError:
        print("[COMPILAÇÃO] PyInstaller não encontrado. Tentando instalar via pip...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
            print("[COMPILAÇÃO] PyInstaller instalado com sucesso!")
            return True
        except Exception as e:
            print(f"[COMPILAÇÃO] Falha crítica ao instalar PyInstaller: {e}")
            return False

def compilar_aplicativo():
    """
    Orquestra o comando do PyInstaller com flags personalizadas e hidden-imports
    necessários para evitar falhas em runtime do VTK, SimpleITK e PyQt6.
    """
    if not verificar_pyinstaller():
        print("[COMPILAÇÃO] Erro: Não foi possível configurar o PyInstaller.")
        sys.exit(1)
        
    print("\n" + "="*70)
    print("[COMPILAÇÃO] Iniciando empacotamento do TatschViewer 1.5 para Grau Médico...")
    print("="*70)
    
    # Definição do separador de arquivos correto para --add-data (; no Windows, : no Unix)
    separador = ";" if os.name == "nt" else ":"
    
    # Mapeamento estrito de todos os Hidden Imports e subpacotes nativos de C++
    # Isso impede que o PyInstaller perca módulos dinâmicos não-referenciados por importação direta
    importacoes_ocultas = [
        "vtk",
        "vtkmodules",
        "vtkmodules.all",
        "vtkmodules.qt",
        "vtkmodules.qt.QVTKRenderWindowInteractor",
        "vtkmodules.util",
        "vtkmodules.util.numpy_support",
        "SimpleITK",
        "pydicom",
        "numpy",
        "PyQt6",
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "ui",
        "ui.textos_e_estilos",
        "ui.config_presets",
        "processamento_imagem",
        "processamento_imagem.threads_subtracao",
        "processamento_imagem.subtracao_ossea",
        "carregamento",
        "carregamento.carregamento_dicom",
        "carregamento.carregamento_pastas_dicom",
        "carregamento.carregamento_arquivos_zip",
        "carregamento.controlador_arquivos",
        "carregamento.controlador_exportacao",
        "carregamento.threads_carregamento",
        "exibicao",
        "exibicao.formatador_hud",
        "exibicao.layout_4_up",
        "exibicao.multiplas_telas",
        "navegacao",
        "manipulacao_da_imagem",
        "medidas",
        "ajuda",
        "anonimizador"
    ]
    
    # Montagem do comando base
    comando = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name=TatschViewer",
        "--noconfirm",
        "--onedir",    # Gera pasta com executável leve para inicialização rápida
        "--windowed",  # Desativa o console de terminal em segundo plano (GUI pura)
        "--icon=icones/logo_tatsch.ico",  # Ícone do executável para Windows Explorer
        f"--add-data=icones{separador}icones",  # Copia os arquivos de ícones clínicos
        "--clean"  # Limpa o cache do PyInstaller para evitar conflitos de cache
    ]
    
    # Incorpora as importações ocultas ao comando
    for imp in importacoes_ocultas:
        comando.append(f"--hidden-import={imp}")
        
    # Ponto de entrada do executável
    comando.append("main.py")
    
    print(f"\n[COMPILAÇÃO] Executando comando:\n{' '.join(comando)}\n")
    
    try:
        # Executa o processo de build do PyInstaller
        subprocess.run(comando, check=True)
        
        print("\n" + "="*70)
        print("[SUCESSO] O TatschViewer 1.5 foi compilado com êxito!")
        print("A pasta standalone (otimizada para inicialização rápida) está localizada em:")
        print(f" -> {os.path.abspath('dist/TatschViewer')}")
        print("="*70 + "\n")
        
    except subprocess.CalledProcessError as e:
        print(f"\n[ERRO] Falha no processo de compilação. Código de retorno: {e.returncode}")
        sys.exit(e.returncode)

if __name__ == "__main__":
    compilar_aplicativo()
