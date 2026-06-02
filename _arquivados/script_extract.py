import os

with open('interface.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

header = """# -*- coding: utf-8 -*-
import sys
import gc
import traceback
import numpy as np
import vtk
import SimpleITK as sitk
from vtkmodules.util import numpy_support
from PyQt6.QtCore import QThread, pyqtSignal

"""

# Line 50 is index 49 (from processamento_imagem.subtracao_ossea import OperadorSubtracaoOssea)
# Line 424 is index 423 (            self.erro.emit(str(e)))
# We extract lines 49 to 424 (which is lines[49:424])
extracted_lines = lines[49:424]

os.makedirs('processamento_imagem', exist_ok=True)
with open('processamento_imagem/threads_subtracao.py', 'w', encoding='utf-8') as f:
    f.write(header)
    f.writelines(extracted_lines)

# Now modify interface.py
new_interface_lines = lines[:49]
new_interface_lines.append("from processamento_imagem.threads_subtracao import ThreadSubtracaoLenta, ThreadSubtracaoRapida, ThreadSubtracaoSemente, ThreadSubtracaoOssea\n\n")
new_interface_lines.extend(lines[424:])

with open('interface.py', 'w', encoding='utf-8') as f:
    f.writelines(new_interface_lines)

print("Extraction and modification successful.")
