import vtk
import numpy as np
import time

class OperadorBisturi:
    def __init__(self, volume_original):
        self.volume_original = volume_original

    def cortar(self, pontos_tela, renderer, manter_interior):
        print("\n" + "="*60)
        print("[PROFILING BISTURI] INICIANDO CORTE RÁPIDO (EXTRUSÃO LINEAR)")
        t0 = time.time()
        
        if len(pontos_tela) < 3: return self.volume_original

        bounds = self.volume_original.GetBounds()
        diag = np.sqrt((bounds[1]-bounds[0])**2 + (bounds[3]-bounds[2])**2 + (bounds[5]-bounds[4])**2)
        
        origin = np.array(self.volume_original.GetOrigin())
        spacing = self.volume_original.GetSpacing()
        extent = self.volume_original.GetExtent()
        
        mat = self.volume_original.GetDirectionMatrix()
        M = np.array([
            [mat.GetElement(0,0), mat.GetElement(0,1), mat.GetElement(0,2)],
            [mat.GetElement(1,0), mat.GetElement(1,1), mat.GetElement(1,2)],
            [mat.GetElement(2,0), mat.GetElement(2,1), mat.GetElement(2,2)]
        ])
        M_inv = np.linalg.inv(M)

        # Resolução do desenho do mouse
        step = max(1, len(pontos_tela) // 60)
        pts_reduzidos = pontos_tela[::step]
        if pts_reduzidos[-1] != pontos_tela[-1]:
            pts_reduzidos.append(pontos_tela[-1])

        camera = renderer.GetActiveCamera()
        focal_point = np.array(camera.GetFocalPoint())
        pos = np.array(camera.GetPosition())
        
        # O vetor da extrusão é a direção DA CÂMERA PARA O FOCO (o raio visual do médico)
        cam_dir = focal_point - pos
        norm = np.linalg.norm(cam_dir)
        dir_norm_real = cam_dir / norm if norm > 0 else np.array([0.0, 0.0, -1.0])
        
        # Corrige o vetor do raio para o Mundo VTK
        dir_norm_fake = M_inv.dot(dir_norm_real)
        dir_norm_fake = dir_norm_fake / np.linalg.norm(dir_norm_fake)

        renderer.SetWorldPoint(focal_point[0], focal_point[1], focal_point[2], 1.0)
        renderer.WorldToDisplay()
        z_display = renderer.GetDisplayPoint()[2]

        points = vtk.vtkPoints()
        polygon = vtk.vtkPolygon()
        polygon.GetPointIds().SetNumberOfIds(len(pts_reduzidos))

        # Recuo massivo na direção contrária da câmera para garantir que a extrusão comece ANTES do crânio
        recuo = dir_norm_fake * diag

        for i, (x, y) in enumerate(pts_reduzidos):
            renderer.SetDisplayPoint(x, y, z_display)
            renderer.DisplayToWorld()
            wp = renderer.GetWorldPoint()
            p_real = np.array([wp[0]/wp[3], wp[1]/wp[3], wp[2]/wp[3]])
            
            p_fake = M_inv.dot(p_real - origin) + origin
            p_recuado = p_fake - recuo # Joga o ponto para trás
            
            points.InsertNextPoint(p_recuado)
            polygon.GetPointIds().SetId(i, i)

        polygons = vtk.vtkCellArray()
        polygons.InsertNextCell(polygon)

        polyData = vtk.vtkPolyData()
        polyData.SetPoints(points)
        polyData.SetPolys(polygons)

        t1 = time.time()
        print(f"[PROFILING BISTURI] 1. Preparação Geométrica: {t1-t0:.4f}s")

        # EXTRUSÃO LINEAR: "O Cortador de Biscoitos 3D"
        extruder = vtk.vtkLinearExtrusionFilter()
        extruder.SetInputData(polyData)
        extruder.SetExtrusionTypeToVectorExtrusion()
        extruder.SetVector(dir_norm_fake)
        extruder.SetScaleFactor(diag * 2.5) # Varar até o outro lado do crânio
        extruder.CappingOn() # Transforma o tubo numa malha sólida (Watertight)
        extruder.Update()

        t2 = time.time()
        print(f"[PROFILING BISTURI] 2. Extrusão do Tubo: {t2-t1:.4f}s")

        # GERAÇÃO DO STENCIL (A Rasterização)
        stencil_gen = vtk.vtkPolyDataToImageStencil()
        stencil_gen.SetInputConnection(extruder.GetOutputPort())
        stencil_gen.SetOutputOrigin(origin)
        stencil_gen.SetOutputSpacing(spacing)
        stencil_gen.SetOutputWholeExtent(extent)
        stencil_gen.Update()

        t3 = time.time()
        print(f"[PROFILING BISTURI] 3. Rasterização do Stencil (NOVO GARGALO?): {t3-t2:.4f}s")

        stencil = vtk.vtkImageStencil()
        stencil.SetInputData(self.volume_original)
        stencil.SetStencilConnection(stencil_gen.GetOutputPort())
        stencil.SetBackgroundValue(-1024)

        if manter_interior: stencil.ReverseStencilOff()
        else: stencil.ReverseStencilOn()
        stencil.Update()

        t4 = time.time()
        print(f"[PROFILING BISTURI] 4. Aplicação Física dos Pixels: {t4-t3:.4f}s")

        novo_volume = vtk.vtkImageData()
        novo_volume.DeepCopy(stencil.GetOutput())

        t5 = time.time()
        print(f"[PROFILING BISTURI] 5. DeepCopy na RAM: {t5-t4:.4f}s")
        print(f"[PROFILING BISTURI] TEMPO TOTAL DO BISTURI: {t5-t0:.4f}s")
        print("="*60 + "\n")

        return novo_volume
