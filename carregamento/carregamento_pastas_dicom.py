from PyQt6.QtCore import QObject
import os
import concurrent.futures
import io
import numpy as np
import pydicom
import time
import json
import hashlib
from core.utils_profiling import profiler_time

@profiler_time
def _ler_meta_rapido(caminho):
    try:
        # Tenta a otimização extrema: lê apenas os primeiros 4096 bytes do arquivo
        try:
            with open(caminho, 'rb') as f:
                chunk = f.read(4096)
        except Exception:
            return None
            
        specific_tags = [
            'SeriesInstanceUID', 'SeriesDescription', 'SeriesNumber', 
            'ImageType', 'ImageOrientationPatient', 'ImagePositionPatient', 'ProtocolName'
        ]
        
        try:
            # Parsing em RAM: passa o buffer para io.BytesIO e força a leitura dos cabeçalhos
            ds = pydicom.dcmread(io.BytesIO(chunk), stop_before_pixels=True, force=True, specific_tags=specific_tags)
            uid = getattr(ds, 'SeriesInstanceUID', "")
            if not uid or not hasattr(ds, 'ImageOrientationPatient') or not hasattr(ds, 'ImagePositionPatient') or not hasattr(ds, 'SeriesNumber'):
                raise ValueError("Tags cruciais (UID/IOP/IPP/Num) ausentes no chunk de 4KB")
        except Exception:
            # Fallback nativo: caso o dicionário exceda 4KB ou falte tags críticas, lê do arquivo diretamente
            try:
                ds = pydicom.dcmread(caminho, stop_before_pixels=True, force=True, specific_tags=specific_tags)
                uid = getattr(ds, 'SeriesInstanceUID', "")
            except Exception:
                return None
        
        if not uid:
            return None
        
        desc = getattr(ds, 'SeriesDescription', "Sem Descrição")
        num = str(getattr(ds, 'SeriesNumber', "N/A"))
        img_type = getattr(ds, 'ImageType', "")
        
        if isinstance(img_type, (list, tuple, pydicom.multival.MultiValue)):
            img_type_str = "\\".join(map(str, img_type))
        else:
            img_type_str = str(img_type) if img_type is not None else ""
            
        proto = getattr(ds, 'ProtocolName', "")
        
        iop = getattr(ds, 'ImageOrientationPatient', None)
        ipp = getattr(ds, 'ImagePositionPatient', None)
        
        if iop is not None and len(iop) == 6:
            iop = tuple(np.round(np.array(iop, dtype=float), 3))
        else:
            iop = ()
            
        if ipp is not None and len(ipp) == 3:
            ipp = np.array(ipp, dtype=float)
        else:
            ipp = np.array([0.0, 0.0, 0.0])
            
        is_scout = "SCOUT" in img_type_str.upper() or "LOCALIZER" in img_type_str.upper()
        
        return {
            "file": caminho,
            "uid": str(uid),
            "desc": str(desc).strip(),
            "num": str(num).strip(),
            "iop": iop,
            "ipp": ipp,
            "scout": is_scout,
            "proto": str(proto).strip()
        }
    except Exception:
        return None

@profiler_time
def _listar_arquivos_recursivo(caminho_pasta):
    arquivos = []
    pilha = [caminho_pasta]
    while pilha:
        pasta_atual = pilha.pop()
        try:
            for entry in os.scandir(pasta_atual):
                if entry.is_file():
                    if not entry.name.lower().endswith('.zip'):
                        arquivos.append(entry.path)
                elif entry.is_dir(follow_symlinks=False):
                    pilha.append(entry.path)
        except (PermissionError, FileNotFoundError):
            continue
    return arquivos

class CarregadorPastasDicom(QObject):
    def __init__(self):
        super().__init__()
    
    @staticmethod
    def _obter_caminho_cache(caminho_pasta):
        home = os.path.expanduser("~")
        dir_cache = os.path.join(home, ".tatschviewer_cache")
        os.makedirs(dir_cache, exist_ok=True)
        hash_nome = hashlib.md5(caminho_pasta.encode('utf-8')).hexdigest()
        return os.path.join(dir_cache, f"{hash_nome}.json")
    
    @profiler_time
    def escanear_pasta(self, caminho_pasta: str, progress_callback=None) -> list:
        t_scan_total = time.perf_counter()
        t_walk = time.perf_counter()
        arquivos = _listar_arquivos_recursivo(caminho_pasta)
        
        caminho_cache = self._obter_caminho_cache(caminho_pasta)
        if os.path.exists(caminho_cache):
            try:
                with open(caminho_cache, 'r', encoding='utf-8') as f:
                    dados = json.load(f)
                if dados.get("qtd_arquivos") == len(arquivos):
                    return dados.get("series", [])
            except Exception as e:
                print(f"Erro ao ler cache: {e}")
                
        grupos = {}
        t_threads = time.perf_counter()
        
        # ThreadPoolExecutor: evita o overhead de processos do Windows
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(_ler_meta_rapido, f) for f in arquivos]
            total = len(futures)
            processados = 0
            cancelled = False
            for future in concurrent.futures.as_completed(futures):
                try:
                    res = future.result()
                except concurrent.futures.CancelledError:
                    continue
                
                processados += 1
                if res:
                    grupos.setdefault((res["uid"], res["iop"], res["scout"]), []).append(res)
                if progress_callback and processados % 25 == 0:
                    if not progress_callback(processados, total):
                        cancelled = True
                        for f_item in futures:
                            f_item.cancel()
            if progress_callback:
                progress_callback(total, total)
                
        series_encontradas = []
        for chave, itens in grupos.items():
            if len(itens) < 2:
                continue
            uid, iop, is_scout = chave
            if iop and len(iop) == 6:
                normal = np.cross(iop[:3], iop[3:])
                normal = normal / np.linalg.norm(normal)
                itens.sort(key=lambda x: np.dot(x["ipp"], normal))
            arquivos_limpos = [x["file"] for x in itens]
            
            # Suffix detection from ProtocolName and SeriesDescription
            desc = itens[0]["desc"]
            proto = itens[0].get("proto", "")
            
            desc_upper = desc.upper()
            proto_upper = proto.upper()
            
            sufixo_fase = ""
            for keyword in ["ARTERIAL", "VENOSA", "PRE"]:
                if keyword in desc_upper or keyword in proto_upper:
                    sufixo_fase = f"_{keyword}"
                    break
            
            s_id = f"{uid}_SCOUT" if is_scout else f"{uid}_{hash(iop)}{sufixo_fase}"
            desc_exibicao = desc + (" - SCOUT" if is_scout else "")
            series_encontradas.append({
                "SeriesID": s_id, "Files": arquivos_limpos,
                "Directory": os.path.dirname(arquivos_limpos[0]),
                "Description": desc_exibicao, "Number": itens[0]["num"]
            })
        series_encontradas.sort(key=lambda x: x["Description"])
        
        try:
            with open(caminho_cache, 'w', encoding='utf-8') as f:
                json.dump({"qtd_arquivos": len(arquivos), "series": series_encontradas}, f, indent=2)
        except Exception as e:
            print(f"Erro ao salvar cache de índice: {e}")
            
        return series_encontradas
