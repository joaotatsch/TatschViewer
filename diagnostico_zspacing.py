import os
import pydicom
import numpy as np
import SimpleITK as sitk

def calcular_zspacing(pasta):
    # Pega todos os arquivos na pasta (não subpastas)
    arquivos = [os.path.join(pasta, f) for f in os.listdir(pasta) if os.path.isfile(os.path.join(pasta, f)) and f.upper() != "DICOMDIR"]
    if not arquivos:
        return None

    ipps = []
    iop = None
    dicom_names = []

    for arq in arquivos:
        try:
            ds = pydicom.dcmread(arq, stop_before_pixels=True, force=True)
            # Verifica se tem ImagePositionPatient e ImageOrientationPatient
            if not hasattr(ds, 'ImagePositionPatient') or not hasattr(ds, 'ImageOrientationPatient'):
                continue
                
            ipp = np.array(ds.ImagePositionPatient, dtype=float)
            if iop is None:
                iop = np.array(ds.ImageOrientationPatient, dtype=float)
            ipps.append(ipp)
            dicom_names.append(arq)
        except Exception:
            pass

    if len(ipps) < 2 or iop is None or len(iop) != 6:
        return None

    # Ler SimpleITK
    try:
        leitor = sitk.ImageSeriesReader()
        leitor.SetFileNames(dicom_names)
        img = leitor.Execute()
        z_sitk = img.GetSpacing()[2]
    except Exception as e:
        z_sitk = "Erro SITK"

    # Vetor Normal
    normal = np.cross(iop[:3], iop[3:])
    normal = normal / np.linalg.norm(normal)

    # Old method (p1 - p0)
    # p1 no contexto anterior do código (p_last - p0)
    # O código original em carregamento_dicom.py usava arquivos_limpos[0] e arquivos_limpos[-1]
    # Assumindo que a ordem original dos arquivos lidos determinava p0 e p_last
    try:
        p0 = ipps[0]
        p_last = ipps[-1]
        dist_old = abs(np.dot(p_last - p0, normal))
        z_old = dist_old / (len(dicom_names) - 1)
    except:
        z_old = "Erro Old"

    # New method: Project all IPPs
    projecoes = [np.dot(ipp, normal) for ipp in ipps]
    projecoes.sort()

    deltas = np.diff(projecoes)
    
    # Remove imprecisões e fatias sobrepostas
    deltas = [d for d in deltas if abs(d) > 1e-4]
    
    if len(deltas) == 0:
        z_mediana = 0.0
    else:
        z_mediana = np.median(deltas)

    return (os.path.basename(pasta), z_sitk, z_mediana, z_old, len(dicom_names))


if __name__ == "__main__":
    diretorio_testes = r"D:\Desktop\Projetos\TatschViewer\testes_geometria"
    print(f"{'Pasta':<30} | {'N':<5} | {'SITK':<20} | {'Mediana':<20} | {'Old (p_last-p0)':<20}")
    print("-" * 105)
    
    for root, dirs, files in os.walk(diretorio_testes):
        # Checar se a pasta atual tem arquivos normais
        tem_arquivos = any(os.path.isfile(os.path.join(root, f)) for f in files)
        if tem_arquivos:
            resultado = calcular_zspacing(root)
            if resultado:
                nome, sitk_val, med_val, old_val, n = resultado
                # Para evitar nomes de pasta como IDs difíceis, colocar o nome do pai se for um ID pequeno
                nome_mostrar = nome
                if len(nome) < 10 or nome.islower():
                    # pega a pasta pai pra ter um nome mais descritivo
                    parent = os.path.basename(os.path.dirname(root))
                    if parent != "testes_geometria":
                         nome_mostrar = parent + "/" + nome
                
                sitk_str = f"{sitk_val:.6f}" if isinstance(sitk_val, float) else str(sitk_val)
                med_str = f"{med_val:.6f}" if isinstance(med_val, float) else str(med_val)
                old_str = f"{old_val:.6f}" if isinstance(old_val, float) else str(old_val)
                print(f"{nome_mostrar[:30]:<30} | {n:<5} | {sitk_str:<20} | {med_str:<20} | {old_str:<20}")
