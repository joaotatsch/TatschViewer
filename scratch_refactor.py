import os

base_dir = r"d:\Desktop\Projetos\TatschViewer\navegacao"
init_file = os.path.join(base_dir, "__init__.py")

with open(init_file, "r", encoding="utf-8") as f:
    lines = f.readlines()

idx_filtro_2d = -1
idx_filtro_3d = -1
idx_coordenador = -1

for i, line in enumerate(lines):
    if line.startswith("class FiltroEventosDicom(QObject):"):
        idx_filtro_2d = i
    elif line.startswith("class FiltroEventosDicom3D(QObject):"):
        idx_filtro_3d = i
    elif line.startswith("class CoordenadorNavegacao(QObject):"):
        idx_coordenador = i

filtro_2d_code = lines[idx_filtro_2d:idx_filtro_3d]
filtro_3d_code = lines[idx_filtro_3d:idx_coordenador]
coordenador_code = lines[idx_coordenador:]

filtros_eventos_content = [
    "# -*- coding: utf-8 -*-\n",
    "from __future__ import annotations\n",
    "from PyQt6.QtCore import QObject, QEvent, Qt\n",
    "import vtk\n",
    "\n",
    "from typing import TYPE_CHECKING\n",
    "if TYPE_CHECKING:\n",
    "    from .navegacao_2d import Navegador2D\n",
    "    from .navegacao_3d import Navegador3D\n",
    "\n"
]
filtros_eventos_content.extend(filtro_2d_code)
filtros_eventos_content.extend(filtro_3d_code)

coordenador_content = [
    "# -*- coding: utf-8 -*-\n",
    "from PyQt6.QtCore import QObject\n",
    "import vtk\n",
    "\n",
    "from .navegacao_2d import Navegador2D\n",
    "from .navegacao_3d import Navegador3D\n",
    "from .filtros_eventos import FiltroEventosDicom, FiltroEventosDicom3D\n",
    "\n"
]
coordenador_content.extend(coordenador_code)

new_init_content = [
    "# -*- coding: utf-8 -*-\n",
    '"""\n',
    'Módulo de coordenação geral de navegação do usuário.\n',
    '"""\n',
    "from .navegacao_2d import Navegador2D\n",
    "from .navegacao_3d import Navegador3D\n",
    "from .filtros_eventos import FiltroEventosDicom, FiltroEventosDicom3D\n",
    "from .coordenador import CoordenadorNavegacao\n"
]

with open(os.path.join(base_dir, "filtros_eventos.py"), "w", encoding="utf-8") as f:
    f.writelines(filtros_eventos_content)

with open(os.path.join(base_dir, "coordenador.py"), "w", encoding="utf-8") as f:
    f.writelines(coordenador_content)
    
with open(init_file, "w", encoding="utf-8") as f:
    f.writelines(new_init_content)

print("Refatoracao concluida.")
