import os

file_path = r'd:\Desktop\Projetos\TatschViewer\navegacao\ferramentas\ferramenta_normal.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
"""        elif getattr(filtro, 'arrastando_rotacao', False):
            if hasattr(filtro, 'operador_interacao_reslice'):
                filtro.operador_interacao_reslice.rotacionar_plano(filtro.nome_visao, dx)
            else:
                renderer = filtro.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
                if renderer:
                    camera = renderer.GetActiveCamera()
                    if camera:
                        camera.Roll(dx * 0.5)
                        filtro.navegador_2d.atualizar_bussola()
                        filtro.interactor.GetRenderWindow().Render()
            filtro.ultimo_pos_x = event.position().x()
            filtro.ultimo_pos_y = event.position().y()
            return True""",
"""        elif getattr(filtro, 'arrastando_rotacao', False):
            renderer = filtro.interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
            if renderer:
                camera = renderer.GetActiveCamera()
                if camera:
                    camera.Roll(dx * 0.5)
                    filtro.navegador_2d.atualizar_bussola()
                    filtro.interactor.GetRenderWindow().Render()
            filtro.ultimo_pos_x = event.position().x()
            filtro.ultimo_pos_y = event.position().y()
            return True"""
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
