import SimpleITK as sitk
import numpy as np

class OperadorSubtracaoOssea:
    def __init__(self):
        self.BACKGROUND_HU = -1000

    def executar_subtracao_rapida(self, sitk_image: sitk.Image) -> sitk.Image:
        # 1. A Matriz de Preservação (Todos os vasos + ossos)
        # Limiar abaixado para 120 HU para blindar vasos distais finos (A2, M2).
        mask_all = sitk.BinaryThreshold(sitk_image, lowerThreshold=120.0, upperThreshold=5000.0)

        # 2. A Casca Cortical (O Osso Duro)
        # 600 HU atua como limite de segurança intransponível. A ICA (440 HU) está imune.
        mask_cortical = sitk.BinaryThreshold(sitk_image, lowerThreshold=600.0, upperThreshold=5000.0)

        # 3. Escavação Cortical (A Mágica da Separação)
        # Dilatamos a casca dura em 1 pixel. Isso cria um "fosso" que engole o volume parcial,
        # descolando a parede da carótida do osso do canal carotídeo sem apagar a artéria.
        dilate_osso = sitk.BinaryDilateImageFilter()
        dilate_osso.SetKernelRadius(1)
        mask_cortical_expandida = dilate_osso.Execute(mask_cortical)

        # 4. A Extração Bruta
        # Tiramos a casca óssea do volume total.
        # Sobra a Árvore Vascular Inteira + poeira esfarelada de osso esponjoso facial/mandibular.
        mask_candidatos = sitk.And(mask_all, sitk.Not(mask_cortical_expandida))

        # 5. O Peneirão de Massa (Filtro Topológico)
        cc = sitk.ConnectedComponent(mask_candidatos)
        stats = sitk.LabelShapeStatisticsImageFilter()
        stats.Execute(cc)

        # A árvore vascular é conectada do pescoço ao cérebro (Volume altíssimo).
        # A poeira esponjosa foi retalhada pela remoção da casca e está em ilhas pequenas.
        # 2500 mm3 é uma restrição severa que oblitera mandíbula isolada e dentes.
        labels_vasos = [l for l in stats.GetLabels() if stats.GetPhysicalSize(l) > 2500.0]

        labels_arr = sitk.GetArrayViewFromImage(cc)
        mask_arvore_arr = np.isin(labels_arr, labels_vasos).astype(np.uint8)
        mask_arvore = sitk.GetImageFromArray(mask_arvore_arr)
        mask_arvore.CopyInformation(cc)

        # 6. Restauração Anatômica do Lúmen
        # Devolvemos o 1 pixel raspado da parede das artérias no Passo 3.
        # Limitamos o crescimento aos limites exatos da mask_all para manter precisão cirúrgica.
        dilate_vaso = sitk.BinaryDilateImageFilter()
        dilate_vaso.SetKernelRadius(1)
        mask_arvore_restaurada = dilate_vaso.Execute(mask_arvore)
        mask_final = sitk.And(mask_arvore_restaurada, mask_all)

        # 7. Corte Final no Volume DICOM
        mask_apply = sitk.MaskImageFilter()
        mask_apply.SetOutsideValue(self.BACKGROUND_HU)
        return mask_apply.Execute(sitk_image, mask_final)

    def executar_subtracao_por_semente(self, sitk_image: sitk.Image, lista_indices_voxel: list) -> sitk.Image:
        import numpy as np
        
        # 1. Mapeamento Vascular Total (Suficientemente baixo para preservar vasos distais finos)
        mask_vasos_candidatos = sitk.BinaryThreshold(sitk_image, lowerThreshold=120.0, upperThreshold=3000.0)

        # 2. Mapeamento do Osso Cortical Denso (O "Inimigo")
        # > 850 HU isola a base do crânio/petroso, mas permite que a semente passe por placas calcificadas (600-800 HU).
        mask_osso_duro = sitk.BinaryThreshold(sitk_image, lowerThreshold=850.0, upperThreshold=5000.0)

        # 3. A Trincheira Cirúrgica
        # Engordamos o osso duro em 1 voxel. Isso empurra a parede do canal carotídeo para longe da artéria,
        # quebrando a ponte física de volume parcial sem tocar no lúmen do vaso.
        dilate_osso = sitk.BinaryDilateImageFilter()
        dilate_osso.SetKernelRadius(1)
        mask_osso_dilatado = dilate_osso.Execute(mask_osso_duro)

        # 4. O Labirinto Seguro (Vasos intactos e não-erodidos, isolados do crânio)
        mask_nav = sitk.And(mask_vasos_candidatos, sitk.Not(mask_osso_dilatado))

        # 5. Configuração da Inundação Topológica
        connected = sitk.ConnectedThresholdImageFilter()
        connected.SetLower(1)
        connected.SetUpper(1)

        mask_nav_img = sitk.GetArrayViewFromImage(mask_nav)
        size = mask_nav.GetSize()
        sementes_validas = 0

        # Rastreio das Sementes com Snapper Inteligente
        for voxel_coords in lista_indices_voxel:
            ix, iy, iz = voxel_coords
            try:
                if mask_nav_img[iz, iy, ix] == 0:
                    achou = False
                    melhor_hu = -2000
                    melhor_coord = (ix, iy, iz)
                    # Busca 3D expandida caso tenha clicado fora do lúmen ou numa calcificação > 850 HU
                    for dz in range(-3, 4):
                        for dy in range(-3, 4):
                            for dx in range(-3, 4):
                                nz, ny, nx = iz+dz, iy+dy, ix+dx
                                if (0 <= nx < size[0] and 0 <= ny < size[1] and 0 <= nz < size[2]):
                                    if mask_nav_img[nz, ny, nx] == 1:
                                        vizinho_hu = sitk_image.GetPixel(nx, ny, nz)
                                        if vizinho_hu > melhor_hu:
                                            melhor_hu = vizinho_hu
                                            melhor_coord = (nx, ny, nz)
                                            achou = True
                    if achou:
                        connected.AddSeed([melhor_coord[0], melhor_coord[1], melhor_coord[2]])
                        sementes_validas += 1
                else:
                    connected.AddSeed([ix, iy, iz])
                    sementes_validas += 1
            except Exception as e:
                print(f"Semente falhou: {e}")

        if sementes_validas == 0:
            print("[FALHA] Nenhuma semente encontrou a rede vascular.")
            return sitk_image

        # 6. A Inundação
        mask_vasos_isolados = connected.Execute(mask_nav)

        # 7. Restauração Anatômica
        # Como não erodimos a imagem globalmente, as artérias cerebrais médias/anteriores já estão perfeitas.
        # Dilatamos apenas 1 pixel para recuperar a "pele" da carótida interna que foi sobreposta pelo osso dilatado no Passo 3.
        dilate_vaso = sitk.BinaryDilateImageFilter()
        dilate_vaso.SetKernelRadius(1)
        mask_vaso_restaurado = dilate_vaso.Execute(mask_vasos_isolados)

        # 8. Mascaramento Final Limitador
        # Impede que a restauração crie vasos onde não existia sinal radiológico (>120 HU).
        mask_total = sitk.BinaryThreshold(sitk_image, lowerThreshold=120.0, upperThreshold=5000.0)
        mask_final = sitk.And(mask_vaso_restaurado, mask_total)

        mask_apply = sitk.MaskImageFilter()
        mask_apply.SetOutsideValue(self.BACKGROUND_HU)
        return mask_apply.Execute(sitk_image, mask_final)
