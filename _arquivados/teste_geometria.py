import os
import sys

def main():
    try:
        from carregamento import CoordenadorCarregamento
        coordenador = CoordenadorCarregamento()
        
        test_dir = os.path.abspath("dados_de_teste")
        if not os.path.exists(test_dir):
            print(f"ERRO: Pasta {test_dir} não encontrada.")
            sys.exit(1)
            
        print(f"Buscando séries em: {test_dir}")
        series = coordenador.escanear_diretorio(test_dir)
        
        if not series:
            print("ERRO: Nenhuma série encontrada.")
            sys.exit(1)
            
        for s in series:
            sid = s['SeriesID']
            print(f"\nTestando Série: {sid} - {s['Description']} ({len(s['Files'])} arquivos)")
            
            # Se for SCOUT, pula o teste rigoroso, pois Scout é 2D
            if "SCOUT" in sid or "LOCALIZER" in s['Description']:
                print("Série identificada como SCOUT. Ignorando geometria 3D.")
                continue
                
            vtk_image, sitk_image, np_view, prop = coordenador.carregar_serie(s['Files'], sid)
            
            if not vtk_image:
                print("ERRO: vtk_image é None.")
                sys.exit(1)
                
            dim = vtk_image.GetDimensions()
            spacing = vtk_image.GetSpacing()
            bounds = vtk_image.GetBounds()
            
            z_bounds = bounds[5] - bounds[4]
            nz = dim[2]
            z_spacing = spacing[2]
            
            print(f"Dimensões: {dim}")
            print(f"Spacing: {spacing}")
            print(f"Bounds Z: {bounds[4]:.2f} a {bounds[5]:.2f} (Delta Z = {z_bounds:.2f})")
            
            if nz < 10:
                print(f"FALHA: Nz = {nz} (Esperado > 10)")
                sys.exit(1)
                
            if z_spacing < 0.1:
                print(f"FALHA: Z-Spacing = {z_spacing} (Esperado > 0.1)")
                sys.exit(1)
                
            if z_bounds < 50.0:
                print(f"FALHA: Z-Bounds = {z_bounds} (Esperado > 50.0)")
                sys.exit(1)
                
            print("SUCESSO: Geometria 3D Perfeita")
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Exceção capturada: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
