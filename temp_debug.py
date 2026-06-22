import sys
import pydicom
import numpy as np
sys.path.insert(0, r"D:\Desktop\Projetos\TatschViewer")
from carregamento.carregamento_pastas_dicom import CarregadorPastasDicom
from carregamento.carregamento_dicom import CarregadorDicom

path = r"D:\Desktop\Projetos\TatschViewer\_arquivados\dados_de_teste\normal\Serie_507361"
leitor = CarregadorPastasDicom()
series = leitor.escanear_pasta(path)
if not series:
    print("No series found!")
    sys.exit(1)
s = series[0]
print("Files:", len(s["Files"]))

c = CarregadorDicom()
vtk_img, sitk_img, np_array, prop = c.carregar_serie(s["Files"], s["SeriesID"], ignorar_cache=True)
print("VTK Spacing:", vtk_img.GetSpacing())
print("SimpleITK Spacing:", sitk_img.GetSpacing())

print("Pydicom spacing calculation:")
d0 = pydicom.dcmread(s["Files"][0], stop_before_pixels=True)
d1 = pydicom.dcmread(s["Files"][-1], stop_before_pixels=True)
p0 = np.array(d0.ImagePositionPatient, dtype=float)
p_last = np.array(d1.ImagePositionPatient, dtype=float)
iop = np.array(d0.ImageOrientationPatient, dtype=float)
print("p0:", p0)
print("p_last:", p_last)
print("dist_euclidiana:", np.linalg.norm(p_last - p0) / (len(s["Files"]) - 1))
vetor_normal = np.cross(iop[:3], iop[3:])
dist_ortogonal = abs(np.dot(p_last - p0, vetor_normal))
print("dist_ortogonal (dot):", dist_ortogonal / (len(s["Files"]) - 1))
