import sys
import os
import pydicom

# Ensure the parent directory is in sys.path
sys.path.insert(0, r"D:\Desktop\Projetos\TatschViewer")

from carregamento.carregamento_pastas_dicom import CarregadorPastasDicom
from carregamento.carregamento_dicom import CarregadorDicom

path = r"D:\Desktop\Bagunça\AngioTC normal (AVCh)\CLAUDIO_ANTONIO_DE_SOUZA_RAMOS SES_585095"

leitor = CarregadorPastasDicom()
series_list = leitor.escanear_pasta(path)

if not series_list:
    print("No series found in the directory!")
    sys.exit(1)

# Find the largest series by number of files
largest_series = max(series_list, key=lambda s: len(s["Files"]))

series_id = largest_series["SeriesID"]
arquivos_limpos = largest_series["Files"]
print(f"Loading largest series {series_id} with {len(arquivos_limpos)} files...")

# Forensic Extraction
print("--- FORENSIC EXTRACTION ---")
def get_ipp(file_path):
    try:
        ds = pydicom.dcmread(file_path, stop_before_pixels=True, specific_tags=['ImagePositionPatient'])
        return getattr(ds, 'ImagePositionPatient', None)
    except Exception as e:
        return str(e)

print(f"Index 0: {get_ipp(arquivos_limpos[0])}")
print(f"Index 1: {get_ipp(arquivos_limpos[1])}")
if len(arquivos_limpos) > 2:
    print(f"Index 2: {get_ipp(arquivos_limpos[2])}")
print(f"Index -1 (last): {get_ipp(arquivos_limpos[-1])}")
print("---------------------------")

carregador = CarregadorDicom()
# Ignoring cache to ensure we compute the spacing
try:
    vtk_img, sitk_img, np_array, prop = carregador.carregar_serie(arquivos_limpos, series_id, ignorar_cache=True)
    print("VTK Spacing:", vtk_img.GetSpacing())
    print("SimpleITK Spacing:", sitk_img.GetSpacing())
except Exception as e:
    print(f"Error loading series: {e}")
