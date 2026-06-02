import os
import sys
from PyQt6.QtWidgets import QApplication
import vtk
from carregamento.carregamento_pastas_dicom import CarregadorPastasDicom
from carregamento.carregamento_dicom import CarregadorDicom
from navegacao.navegacao_2d import Navegador2D

# Mock básico para rodar headless (sem UI visual)
app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)

def rodar_teste():
    diretorio = "dados_de_teste"
    if not os.path.exists(diretorio):
        print(f"Diretório {diretorio} não encontrado.")
        return

    # 1. Escaneia
    scanner = CarregadorPastasDicom()
    series = scanner.escanear_pasta(diretorio)
    if not series:
        print("Nenhuma série encontrada.")
        return

    serie_id = series[0]["SeriesID"]
    pasta_serie = series[0]["Directory"]

    # 2. Carrega
    carregador = CarregadorDicom()
    vtk_img, _, _, _ = carregador.carregar_serie(series[0]["Files"], serie_id)
    print(f"Volume carregado com dimensões: {vtk_img.GetDimensions()}")

    # 3. Configura MPR via Navegador2D
    # Precisamos de 3 renderizadores "falsos"
    renderers = {
        "Axial": vtk.vtkRenderer(),
        "Sagital": vtk.vtkRenderer(),
        "Coronal": vtk.vtkRenderer()
    }

    nav2d = Navegador2D()
    nav2d.configurar_mpr(vtk_img, renderers)

    # Pegamos as fatias (slice number) iniciais dos 3 planos
    fatia_axial_antes = nav2d.mappers["Axial"].GetSliceNumber()
    fatia_sagital_antes = nav2d.mappers["Sagital"].GetSliceNumber()
    fatia_coronal_antes = nav2d.mappers["Coronal"].GetSliceNumber()

    print("\n--- Estado Inicial ---")
    print(f"Índice Axial:   {fatia_axial_antes}")
    print(f"Índice Sagital: {fatia_sagital_antes}")
    print(f"Índice Coronal: {fatia_coronal_antes}")

    # 4. Dá um scroll massivo no AXIAL (+50 fatias)
    print("\nSimulando Scroll no AXIAL (+50 fatias)...")
    novo_indice = nav2d.navegar_fatia("Axial", 50)
    print(f"Novo índice Axial atingido: {novo_indice}")

    # 5. Verifica as novas fatias
    fatia_axial_depois = nav2d.mappers["Axial"].GetSliceNumber()
    fatia_sagital_depois = nav2d.mappers["Sagital"].GetSliceNumber()
    fatia_coronal_depois = nav2d.mappers["Coronal"].GetSliceNumber()

    print("\n--- Estado Pós-Scroll ---")
    print(f"Índice Axial:   {fatia_axial_depois}")
    print(f"Índice Sagital: {fatia_sagital_depois}")
    print(f"Índice Coronal: {fatia_coronal_depois}")

    # 6. Validação
    assert fatia_axial_antes != fatia_axial_depois, "Erro: A fatia axial não se moveu!"
    assert fatia_sagital_antes == fatia_sagital_depois, "ERRO CRÍTICO: Scroll axial vazou e moveu a tela Sagital!"
    assert fatia_coronal_antes == fatia_coronal_depois, "ERRO CRÍTICO: Scroll axial vazou e moveu a tela Coronal!"
    
    print("\nSucesso! O isolamento de mappers no reslice nativo funcionou perfeitamente.")
    print("Zero vazamento de estado. Telas não somem mais.")

if __name__ == "__main__":
    rodar_teste()
