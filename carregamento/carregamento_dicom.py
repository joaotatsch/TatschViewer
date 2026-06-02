import vtk, numpy as np, SimpleITK as sitk
import concurrent.futures, os, json, hashlib

class CarregadorDicom:

    @staticmethod
    def _caminho_cache_raw(arquivos_limpos, series_id=""):
        """Deriva um caminho de cache determinístico baseado no hash do diretório e do series_id."""
        pasta = os.path.dirname(arquivos_limpos[0])
        hash_base = f'{series_id}_{pasta}'.encode("utf-8")
        serie_hash = hashlib.md5(hash_base).hexdigest()
        home = os.path.expanduser("~")
        dir_cache = os.path.join(home, ".tatschviewer_cache", "volumes")
        os.makedirs(dir_cache, exist_ok=True)
        return os.path.join(dir_cache, serie_hash)   # prefixo sem extensão

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

    def carregar_serie(self, diretorio_ou_arquivos, series_id="", ignorar_cache=False):
        import time
        if not isinstance(diretorio_ou_arquivos, list):
            raise ValueError("Erro de otimização: Passe a lista de arquivos limpos.")
        arquivos_limpos = diretorio_ou_arquivos

        # ─── FAST PATH: cache binário ────────────────────────────────────────
        prefixo = self._caminho_cache_raw(arquivos_limpos, series_id)
        if not ignorar_cache:
            cache = self.carregar_cache_raw(prefixo)
            if cache is not None:
                vtk_image, np_array, meta = cache
                sitk_image = sitk.GetImageFromArray(np_array)
                sitk_image.SetSpacing(meta["spacing"])
                # Garante que vtk_image tem a propriedade
                vtk_image.SeriesInstanceUID = meta["propriedades"].get("SeriesInstanceUID", "")
                return vtk_image, sitk_image, np_array, meta["propriedades"]

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
        t1 = time.perf_counter()
        pass

        t2 = time.perf_counter()
        if np_array.dtype != np.int16:
            np_array = np_array.astype(np.int16)
        t3 = time.perf_counter()
        pass

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
                        dist_total = abs(np.dot(p_last - p0, vetor_normal))
                        z_spacing = dist_total / (len(arquivos_limpos) - 1)
                        if z_spacing > 0.0:
                            spacing[2] = float(z_spacing)
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
        sitk_image.SetSpacing(spacing)
        sitk_image.SetOrigin(origin)
        sitk_image.SetDirection(direction)

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
        except: pass

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
