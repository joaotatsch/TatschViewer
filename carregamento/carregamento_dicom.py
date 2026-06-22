import logging
import vtk, numpy as np, SimpleITK as sitk
import concurrent.futures, os, json, hashlib
import sys
from core.utils_profiling import profiler_time

class MriSequenceClassifier:
    """Classifica a sequência de RM com base na descrição da série DICOM."""
    @staticmethod
    @profiler_time
    def classificar(descricao: str) -> str:
        if not descricao:
            return "GENERIC"
        desc = descricao.lower()
        if "adc" in desc:
            return "ADC"
        elif "dwi" in desc or "b1000" in desc or "b0" in desc or "difus" in desc:
            return "DWI"
        elif "flair" in desc or "stir" in desc:
            return "FLAIR"
        elif "t2" in desc or "ffe" in desc or "tse" in desc:
            return "T2"
        elif "t1" in desc or "mprage" in desc:
            return "T1"
        elif "pha" in desc or "phase" in desc or "fase" in desc:
            return "PHASE"
        return "GENERIC"


class CarregadorDicom:

    @staticmethod
    @profiler_time
    def _caminho_cache_raw(arquivos_limpos, series_id=""):
        """Deriva um caminho de cache determinístico baseado no hash do diretório, series_id e características dos arquivos."""
        pasta = os.path.dirname(arquivos_limpos[0])
        identificador = f"{series_id}_{pasta}_{len(arquivos_limpos)}_{os.path.basename(arquivos_limpos[0])}_{os.path.basename(arquivos_limpos[-1])}"
        hash_base = identificador.encode("utf-8")
        serie_hash = hashlib.md5(hash_base).hexdigest()
        home = os.path.expanduser("~")
        dir_cache = os.path.join(home, ".tatschviewer_cache", "volumes")
        os.makedirs(dir_cache, exist_ok=True)
        return os.path.join(dir_cache, serie_hash)   # prefixo sem extensão

    @profiler_time
    def salvar_cache_raw(self, np_array, spacing, origin_vtk, direction, propriedades, prefixo):
        """Persiste o volume em (prefixo.raw, prefixo.json) de forma assíncrona e atômica.
        
        Escrita atômica: grava em .tmp e usa os.replace() garantido pelo NTFS.
        Isso impede que indexadores (Defender, indexador Windows) leiam um .raw incompleto.
        """
        import threading, time
        def _gravar():
            t0 = time.perf_counter()
            caminho_raw  = prefixo + ".raw"
            caminho_json = prefixo + ".json"
            caminho_tmp  = prefixo + ".tmp"  # escrita temporária NUNCA vai direto ao .raw
            try:
                dims = (np_array.shape[2], np_array.shape[1], np_array.shape[0])

                # Grava SEMPRE no .tmp primeiro (buffer 1 MB = menos syscalls WriteFile)
                with open(caminho_tmp, 'wb', buffering=1024*1024) as f:
                    f.write(np_array.tobytes())
                    f.flush()
                    os.fsync(f.fileno())  # garante flush para o disco antes do rename

                # Renomeio atômico: o SO garante que nunca há um estado intermediário
                os.replace(caminho_tmp, caminho_raw)

                meta = {
                    "dims":        list(dims),
                    "shape":       list(np_array.shape),
                    "dtype":       "int16",
                    "spacing":     list(spacing),
                    "origin":      list(origin_vtk),
                    "direction":   list(direction),
                    "propriedades": propriedades
                }
                with open(caminho_json, "w", encoding="utf-8") as f:
                    json.dump(meta, f, indent=2)

            except Exception as e:
                print(f"[CACHE RAW] Erro ao salvar: {e}")
                # Remove .tmp orphan se existir
                if os.path.exists(caminho_tmp):
                    try: os.remove(caminho_tmp)
                    except: pass
        threading.Thread(target=_gravar, daemon=True).start()

    def carregar_cache_raw(self, prefixo):
        """Carrega (prefixo.raw + prefixo.json) via numpy.fromfile com verificações de segurança.
        
        Retorna (vtk_image, np_array, meta) ou None se o cache não existir/estiver inválido.
        """
        import time, gc
        caminho_raw  = prefixo + ".raw"
        caminho_json = prefixo + ".json"

        if not (os.path.exists(caminho_raw) and os.path.exists(caminho_json)):
            return None

        # Força fechamento de qualquer handle anterior antes de tentar abrir
        gc.collect()
        time.sleep(0.1)  # janela de segurança para o SO liberar handles

        # Verifica se o arquivo está de fato acessível (não bloqueado por escrita)
        try:
            with open(caminho_raw, 'r+b') as _probe:
                pass  # apenas testa se o handle pode ser obtido
        except (PermissionError, OSError):
            return None

        try:
            t0 = time.perf_counter()
            with open(caminho_json, "r", encoding="utf-8") as f:
                meta = json.load(f)
            shape      = tuple(meta["shape"])
            dims       = tuple(meta["dims"])
            spacing    = meta["spacing"]
            origin_vtk = meta["origin"]
            direction  = meta["direction"]

            # Validação de tamanho antes de qualquer I/O pesado
            tamanho_esperado = int(np.prod(shape)) * 2  # int16 = 2 bytes
            tamanho_real = os.path.getsize(caminho_raw)
            if tamanho_real != tamanho_esperado:
                raise ValueError(
                    f"Tamanho inválido: esperado {tamanho_esperado}B, encontrado {tamanho_real}B"
                )

            # Leitura via fromfile em variável local forte (sem memmap)
            np_array = np.fromfile(caminho_raw, dtype=np.int16)

            # Guarda de vazio: não passa array vazio para o VTK
            if np_array.size == 0:
                raise ValueError("numpy.fromfile retornou array vazio — arquivo truncado ou corrompido.")

            np_array = np_array.reshape(shape)

            if not np_array.flags["C_CONTIGUOUS"]:
                np_array = np.ascontiguousarray(np_array)

            # Retenção forte: impede GC prematuro enquanto o VTK usa o ponteiro
            self._buffer_keep_alive = np_array

            import_vtk = vtk.vtkImageImport()
            import_vtk.SetImportVoidPointer(np_array)
            import_vtk.SetDataScalarTypeToShort()
            import_vtk.SetNumberOfScalarComponents(1)
            import_vtk.SetDataExtent(0, dims[0]-1, 0, dims[1]-1, 0, dims[2]-1)
            import_vtk.SetWholeExtent(0, dims[0]-1, 0, dims[1]-1, 0, dims[2]-1)
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
            vtk_image.GetScalarRange()

            pass
            return vtk_image, np_array, meta

        except Exception as e:
            for sufixo in (".raw", ".json"):
                alvo = prefixo + sufixo
                try:
                    if os.path.exists(alvo):
                        os.remove(alvo)
                except Exception as e_del:
                    pass
            return None

    @profiler_time
    def carregar_serie(self, diretorio_ou_arquivos, series_id="", ignorar_cache=False):
        import time
        if not isinstance(diretorio_ou_arquivos, list):
            raise ValueError("Erro de otimização: Passe a lista de arquivos limpos.")

        # ─── FAST PATH: Check do Cache Antecipado ────────────────────────────
        # Usamos a lista original para gerar o hash. Se existir, evitamos o DEDUP 4D inteiro!
        prefixo = self._caminho_cache_raw(diretorio_ou_arquivos, series_id)
        if not ignorar_cache:
            cache = self.carregar_cache_raw(prefixo)
            if cache is not None:
                vtk_image, np_array, meta = cache
                sitk_image = sitk.GetImageFromArray(np_array)
                sitk_image.SetSpacing(meta["spacing"])
                vtk_image.SeriesInstanceUID = meta["propriedades"].get("SeriesInstanceUID", "")
                return vtk_image, sitk_image, np_array, meta["propriedades"]

        # ─── DEDUPLICAÇÃO 4D ROBUSTA (Slow Path Otimizado) ───────────────────
        arquivos_limpos = diretorio_ou_arquivos
        if len(arquivos_limpos) > 1:
            try:
                import pydicom
                import io
                import concurrent.futures

                def _ler_tags_dedup(arquivo):
                    try:
                        try:
                            with open(arquivo, 'rb') as f:
                                chunk = f.read(4096)
                            ds = pydicom.dcmread(io.BytesIO(chunk), stop_before_pixels=True, force=True, specific_tags=['EchoNumbers', 'ImagePositionPatient', 'ImageOrientationPatient', 'InstanceNumber', 'ImageType'])
                            # Verifica se extraiu com sucesso as tags cruciais de geometria e ordenação
                            if getattr(ds, 'ImagePositionPatient', None) is None or getattr(ds, 'InstanceNumber', None) is None or getattr(ds, 'ImageOrientationPatient', None) is None:
                                raise ValueError("Tags essenciais não encontradas no limite de 4KB. Forçando fallback.")
                        except Exception:
                            # Fallback para o arquivo inteiro se 4KB não foi suficiente
                            ds = pydicom.dcmread(arquivo, stop_before_pixels=True, force=True, specific_tags=['EchoNumbers', 'ImagePositionPatient', 'ImageOrientationPatient', 'InstanceNumber', 'ImageType'])
                        echo_val = getattr(ds, 'EchoNumbers', 1)
                        echo_num = int(echo_val) if echo_val not in (None, "") else 1
                        
                        z_pos = 0.0
                        ipp = getattr(ds, 'ImagePositionPatient', None)
                        iop = getattr(ds, 'ImageOrientationPatient', None)
                        
                        if ipp is not None and len(ipp) >= 3 and iop is not None and len(iop) >= 6:
                            # Calcula o vetor normal (produto vetorial dos eixos X e Y da imagem)
                            nx = float(iop[1])*float(iop[5]) - float(iop[2])*float(iop[4])
                            ny = float(iop[2])*float(iop[3]) - float(iop[0])*float(iop[5])
                            nz = float(iop[0])*float(iop[4]) - float(iop[1])*float(iop[3])
                            # Projeta a posição da imagem no eixo normal (funciona para qualquer plano ortogonal)
                            z_pos = float(ipp[0])*nx + float(ipp[1])*ny + float(ipp[2])*nz
                        elif ipp is not None and len(ipp) >= 3:
                            # Fallback básico para imagens estritamente axiais
                            z_pos = float(ipp[2])
                        inst_val = getattr(ds, 'InstanceNumber', 0)
                        inst_num = int(inst_val) if inst_val not in (None, "") else 0
                        
                        img_type = getattr(ds, 'ImageType', "")
                        img_type_str = "\\".join(map(str, img_type)) if isinstance(img_type, (list, tuple, pydicom.multival.MultiValue)) else str(img_type)
                        parts = [p.strip().upper() for p in img_type_str.split('\\')] if img_type_str else []
                        is_magnitude = True
                        if parts:
                            is_mag_part = any(p in ["M", "MAGNITUDE", "ADC", "DWI"] for p in parts) or any(p.startswith("M_") for p in parts)
                            is_phase_or_real = any(p in ["R", "REAL", "P", "PHASE", "I", "IMAGINARY"] for p in parts) or any(p.startswith("R_") or p.startswith("P_") for p in parts)
                            if is_mag_part and not is_phase_or_real:
                                is_magnitude = True
                            elif is_phase_or_real:
                                is_magnitude = False
                                
                        return (echo_num, z_pos, inst_num, is_magnitude, arquivo)
                    except Exception:
                        return (1, 0.0, 0, True, arquivo)

                entradas = []
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    for res in executor.map(_ler_tags_dedup, arquivos_limpos):
                        entradas.append(res)

                n_total = len(entradas)

                # Passo 1.5: Filtrar por tipo de reconstrução (Magnitude vs Outros)
                tem_magnitude = any(e[3] for e in entradas)
                tem_outros = any(not e[3] for e in entradas)
                if tem_magnitude and tem_outros:
                    entradas = [e for e in entradas if e[3]]
                    print(f"[DEDUP IMAGETYPE] Mistura detectada. Mantendo Magnitude: {len(entradas)} de {n_total}.")

                # Passo 2: Filtrar pelo eco primário
                ecos_detectados = set(e[0] for e in entradas)
                if len(ecos_detectados) > 1:
                    eco_primario = min(ecos_detectados)
                    entradas = [e for e in entradas if e[0] == eco_primario]
                    print(f"[DEDUP ECHO] {len(ecos_detectados)} ecos → mantendo eco={eco_primario}, {len(entradas)} de {n_total}.")

                # Passo 3: Desduplicar por Z (arredonda para 4 casas decimais)
                # OBRIGATÓRIO: ordenar entradas primeiro por InstanceNumber, depois por Nome do Arquivo. 
                # Isso garante determinismo se houver fatias com o MESMO Z e mesmo InstanceNumber.
                entradas.sort(key=lambda x: (x[2], x[4]))
                mapa_z = {}
                for echo_num, z_pos, inst_num, is_magnitude, arquivo in entradas:
                    z_key = round(z_pos, 4)
                    if z_key not in mapa_z:
                        mapa_z[z_key] = (inst_num, arquivo)

                # Passo 3.5: Truncar volumes artificialmente empilhados (GE/Philips usam pulos de 1000mm+ para esconder b-values)
                z_keys = sorted(mapa_z.keys())
                if len(z_keys) > 1:
                    diffs = [z_keys[i] - z_keys[i-1] for i in range(1, len(z_keys))]
                    mediana = sorted(diffs)[len(diffs)//2]
                    limite_pulo = max(mediana * 5, 50.0) # Se pular mais de 50mm ou 5x a espessura, é falso
                    z_validos = [z_keys[0]]
                    for i in range(1, len(z_keys)):
                        if z_keys[i] - z_keys[i-1] > limite_pulo:
                            print(f"[DEDUP GAP] Pulo artificial massivo em Z ({z_keys[i-1]} -> {z_keys[i]}). Truncando volume para evitar 'Stacked Brains'.")
                            break
                        z_validos.append(z_keys[i])
                    mapa_z = {k: mapa_z[k] for k in z_validos}

                n_unicos = len(mapa_z)
                print(f"[DEDUP 4D] Série: Z únicos={n_unicos} / total={len(diretorio_ou_arquivos)}")

                # Passo 4: Ordenar e reconstruir lista
                if n_unicos > 1:
                    arquivos_limpos = [v[1][1] for v in sorted(mapa_z.items(), key=lambda x: x[0])]
                else:
                    entradas_ord = sorted(entradas, key=lambda x: x[2])
                    arquivos_limpos = [e[4] for e in entradas_ord]

            except Exception as e:
                logging.getLogger(__name__).warning(f"Falha na dedup 4D: {e}")

        # ─── SLOW PATH: decodificação DICOM completa ─────────────────────────
        t0 = time.perf_counter()
        img0 = sitk.ReadImage(arquivos_limpos[0])
        spacing  = list(img0.GetSpacing())
        origin   = img0.GetOrigin()
        direction = img0.GetDirection()

        if len(direction) == 4:
            direction = (direction[0], direction[1], 0.0,
                         direction[2], direction[3], 0.0,
                         0.0,          0.0,          1.0)

        def _ler_fatia(caminho):
            r = sitk.ImageFileReader()
            r.SetFileName(caminho)
            array = sitk.GetArrayFromImage(r.Execute())
            return array[0] if array.ndim == 3 else array

        with concurrent.futures.ThreadPoolExecutor() as executor:
            fatias = list(executor.map(_ler_fatia, arquivos_limpos))

        np_array = np.stack(fatias, axis=0)
        print(f"[STACK] Shape={np_array.shape} dtype={np_array.dtype} min={np_array.min()} max={np_array.max()} arquivos={len(arquivos_limpos)}")
        t1 = time.perf_counter()


        # Detecção de modalidade MR
        is_mr = False
        try:
            r_mod = sitk.ImageFileReader()
            r_mod.SetFileName(arquivos_limpos[0])
            r_mod.ReadImageInformation()
            if r_mod.HasMetaDataKey("0008|0060"):
                is_mr = ("MR" in r_mod.GetMetaData("0008|0060").strip(" \0").upper())
        except:
            pass

        # Cast: CT -> int16 sempre. MR: preserva escala nativa quando possível.
        is_scaled_float = False
        if not is_mr:
            if np_array.dtype != np.int16:
                np_array = np_array.astype(np.int16)
        else:
            # Tratar floats pequenos (ex: eADC na faixa [0, 1])
            if np.issubdtype(np_array.dtype, np.floating):
                max_f = float(np_array.max())
                if max_f <= 10.0:
                    np_array = np_array * 1000.0
                    is_scaled_float = True

            if np_array.dtype == np.uint16:
                max_u16 = int(np_array.max())
                if max_u16 <= 32767:
                    np_array = np_array.astype(np.int16)
                else:
                    np_array = (np_array.astype(np.int32) >> 1).astype(np.int16)
            elif np_array.dtype != np.int16:
                np_array = np_array.astype(np.int16)


        if len(spacing) < 3:
            spacing.append(1.0)

        if len(arquivos_limpos) > 1:
            try:
                r0, r1 = sitk.ImageFileReader(), sitk.ImageFileReader()
                r0.SetFileName(arquivos_limpos[0]); r0.ReadImageInformation()
                r1.SetFileName(arquivos_limpos[-1]); r1.ReadImageInformation()
                if r0.HasMetaDataKey("0020|0032") and r1.HasMetaDataKey("0020|0032") and r0.HasMetaDataKey("0020|0037"):
                    p0 = np.array(r0.GetMetaData("0020|0032").split('\\'), dtype=float)
                    p_last = np.array(r1.GetMetaData("0020|0032").split('\\'), dtype=float)
                    iop = np.array(r0.GetMetaData("0020|0037").split('\\'), dtype=float)
                    if len(iop) == 6:
                        vetor_normal = np.cross(iop[:3], iop[3:])
                        vetor_normal = vetor_normal / np.linalg.norm(vetor_normal)
                        
                        projecoes = []
                        for arq in arquivos_limpos:
                            try:
                                r_meta = sitk.ImageFileReader()
                                r_meta.SetFileName(arq)
                                r_meta.ReadImageInformation()
                                if r_meta.HasMetaDataKey("0020|0032"):
                                    ipp_fatia = np.array(r_meta.GetMetaData("0020|0032").split('\\'), dtype=float)
                                    projecoes.append(np.dot(ipp_fatia, vetor_normal))
                            except Exception:
                                pass
                                
                        if len(projecoes) > 1:
                            projecoes.sort()
                            deltas = np.diff(projecoes)
                            deltas_validos = [d for d in deltas if abs(d) > 1e-4]
                            if len(deltas_validos) > 0:
                                z_spacing = float(np.median(deltas_validos))
                                if z_spacing > 0.0:
                                    spacing[2] = z_spacing
            except Exception:
                pass

        t4 = time.perf_counter()
        dims = (np_array.shape[2], np_array.shape[1], np_array.shape[0])

        if not np_array.flags["C_CONTIGUOUS"]:
            np_array = np.ascontiguousarray(np_array)
        self._buffer_keep_alive = np_array

        # Origem já transformada para coordenadas VTK (flip X e Y)
        if len(origin) >= 3:
            origin_vtk = [-origin[0], -origin[1], origin[2]]
        else:
            origin_vtk = [0.0, 0.0, 0.0]

        import_vtk = vtk.vtkImageImport()
        import_vtk.SetImportVoidPointer(np_array)
        import_vtk.SetDataScalarTypeToShort()
        import_vtk.SetNumberOfScalarComponents(1)
        import_vtk.SetDataExtent(0, dims[0]-1, 0, dims[1]-1, 0, dims[2]-1)
        import_vtk.SetWholeExtent(0, dims[0]-1, 0, dims[1]-1, 0, dims[2]-1)
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
        vtk_image.GetScalarRange()

        t5 = time.perf_counter()
        pass

        sitk_image = sitk.GetImageFromArray(np_array)
        try:
            dim = sitk_image.GetDimension()
            if dim == len(spacing):
                sitk_image.SetSpacing(spacing)
                sitk_image.SetOrigin(origin)
                sitk_image.SetDirection(direction)
            else:
                new_spacing = list(spacing)[:dim] + [1.0] * (dim - len(spacing))
                new_origin = list(origin)[:dim] + [0.0] * (dim - len(origin))
                sitk_image.SetSpacing(new_spacing)
                sitk_image.SetOrigin(new_origin)
        except Exception as e:
            logging.getLogger(__name__).warning(f"Erro ao definir metadados geometricos SimpleITK: {e}")

        propriedades = {"Nome": "Desconhecido", "Inst": "", "Data": "", "Hora": "", "SeriesInstanceUID": ""}
        try:
            r_meta = sitk.ImageFileReader()
            r_meta.SetFileName(arquivos_limpos[0])
            r_meta.ReadImageInformation()
            if r_meta.HasMetaDataKey("0010|0010"): propriedades["Nome"] = r_meta.GetMetaData("0010|0010").replace("^", " ")
            if r_meta.HasMetaDataKey("0008|0080"): propriedades["Inst"] = r_meta.GetMetaData("0008|0080")
            if r_meta.HasMetaDataKey("0008|0020"): propriedades["Data"] = r_meta.GetMetaData("0008|0020")
            if r_meta.HasMetaDataKey("0008|0030"): propriedades["Hora"] = r_meta.GetMetaData("0008|0030")
            if r_meta.HasMetaDataKey("0020|000e"): propriedades["SeriesInstanceUID"] = r_meta.GetMetaData("0020|000e").strip()
            if r_meta.HasMetaDataKey("0008|0060"): propriedades["Modality"] = r_meta.GetMetaData("0008|0060").strip()

            # Auto-Windowing para RM
            if propriedades.get("Modality") == "MR":
                # Classifica a sequência e calcula janela por percentil (sempre prioritário para RM)
                descricao = r_meta.GetMetaData("0008|103e").strip() if r_meta.HasMetaDataKey("0008|103e") else ""
                seq_type = MriSequenceClassifier.classificar(descricao)
                logging.getLogger(__name__).info(f"MR Auto-Windowing: seq={seq_type}, desc='{descricao}'")

                # Filtra fundo (ar) antes de calcular percentis (pula para imagens de Fase)
                if seq_type == "PHASE":
                    arr_tecido = np_array
                else:
                    try:
                        limiar = max(50, int(np.percentile(np_array, 10)))
                        arr_tecido = np_array[np_array > limiar]
                        if arr_tecido.size < 100:
                            arr_tecido = np_array
                    except:
                        arr_tecido = np_array

                pcts = {
                    "T1":      (1,  99),
                    "T2":      (2,  95),
                    "FLAIR":   (2,  96),
                    "DWI":     (1,  99),
                    "ADC":     (2,  98),
                    "PHASE":   (2,  98),
                    "GENERIC": (2,  98),
                }
                p_lo, p_hi = pcts.get(seq_type, (2, 98))
                p_min = float(np.percentile(arr_tecido, p_lo))
                p_max = float(np.percentile(arr_tecido, p_hi))
                ww_calc = max(1.0, p_max - p_min)
                propriedades["WindowCenter"] = float((p_min + p_max) / 2.0)
                propriedades["WindowWidth"] = ww_calc
                print(f"[MR WINDOWING PERCENTILE] Calculado: WL={propriedades['WindowCenter']:.1f} WW={propriedades['WindowWidth']:.1f} (seq={seq_type})", flush=True)
        except Exception as e:
            import traceback
            traceback.print_exc()

        # Garante que vtk_image tem SeriesInstanceUID
        vtk_image.SeriesInstanceUID = propriedades.get("SeriesInstanceUID", "")

        # Persiste cache em background (não bloqueia a UI)
        self.salvar_cache_raw(np_array, spacing, origin_vtk, direction, propriedades, prefixo)

        return vtk_image, sitk_image, np_array, propriedades


def is_scout_ou_localizer_ou_secundario(caminho_arquivo):
    import SimpleITK as sitk
    try:
        reader = sitk.ImageFileReader()
        reader.SetFileName(caminho_arquivo)
        reader.ReadImageInformation()
        img_type = reader.GetMetaData("0008|0008").upper() if reader.HasMetaDataKey("0008|0008") else ""
        if "SCOUT" in img_type or "LOCALIZER" in img_type or "SECONDARY" in img_type or "SCREEN SAVE" in img_type:
            return True
        if not reader.HasMetaDataKey("0020|0037") or not reader.HasMetaDataKey("0020|0032"):
            return True
        return False
    except:
        return True


def verificar_integridade_fase(vtk_image, nome_fase_esperada, uid_solicitado=None):
    """
    Extrai uma amostra tridimensional (11x11x11 voxels) do centro do volume usando numpy_support,
    calcula a densidade média (HU) e valida se as regras clínicas estão satisfeitas.
    """
    from vtk.util import numpy_support
    import numpy as np

    # 1. Extração da amostra de voxels do centro
    scalars = vtk_image.GetPointData().GetScalars()
    if scalars is None:
        return "[ALERTA CRÍTICO] Nenhum escalar de voxel encontrado no volume VTK!"

    np_array = numpy_support.vtk_to_numpy(scalars)
    dims = vtk_image.GetDimensions()  # (Nx, Ny, Nz)
    np_volume = np_array.reshape((dims[2], dims[1], dims[0]))

    cz, cy, cx = dims[2] // 2, dims[1] // 2, dims[0] // 2
    rz, ry, rx = 5, 5, 5
    sample = np_volume[
        max(0, cz-rz):min(dims[2], cz+rz+1),
        max(0, cy-ry):min(dims[1], cy+ry+1),
        max(0, cx-rx):min(dims[0], cx+rx+1)
    ]

    media_hu = float(np.mean(sample)) if sample.size > 0 else 0.0

    # 2. Verificar UIDs
    # Obtém o UID processado anexado ao vtk_image
    uid_processado = getattr(vtk_image, "SeriesInstanceUID", "")

    # Se não foi fornecido via parâmetro, tenta ler do vtk_image
    if uid_solicitado is None:
        uid_solicitado = getattr(vtk_image, "requested_uid", "")

    # Limpa UIDs para comparação (despreza sufixos gerados na UI)
    uid_sol_clean = uid_solicitado.split('_')[0] if uid_solicitado else ""
    uid_proc_clean = uid_processado.split('_')[0] if uid_processado else ""

    # 3. Regras de Auditoria
    alertas = []

    # Regra da Fase
    if nome_fase_esperada == "Pré-Contraste" and media_hu > 150.0:
        alertas.append(
            f"Fase esperada é 'Pré-Contraste', mas densidade média estimada do centro é {media_hu:.2f} HU (> 150 HU). Risco de contraste injetado!"
        )

    # Regra do UID
    if uid_sol_clean and uid_proc_clean and uid_sol_clean != uid_proc_clean:
        alertas.append(
            f"UID solicitado na UI ({uid_sol_clean}) diverge do UID processado no DICOM ({uid_proc_clean})!"
        )

    if alertas:
        return "[ALERTA CRÍTICO] " + " | ".join(alertas)

    return None
