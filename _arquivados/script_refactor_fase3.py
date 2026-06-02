import re

with open('interface.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Imports
imports = """from ui.textos_e_estilos import (
    HTML_BOAS_VINDAS, HTML_DICAS_NAVEGACAO, STYLE_MAIN_WINDOW,
    STYLE_TOOLBAR_BUTTONS, STYLE_MENU, STYLE_BTN_PRESETS,
    STYLE_SPINBOX, STYLE_BTN_CROSSHAIR, STYLE_BTN_TOGGLE,
    STYLE_BTN_SUBTRACAO, STYLE_BTN_SYNC_SCROLL, STYLE_LABEL_BOAS_VINDAS,
    STYLE_DOCK_WIDGET, STYLE_LIST_WIDGET, STYLE_BTN_DICAS,
    STYLE_MSGBOX_DICAS, STYLE_PROGRESS_DIALOG
)
from ui.config_presets import PRESETS_CLINICOS
"""
content = content.replace("from exibicao.formatador_hud import formatar_texto_hud\n", "from exibicao.formatador_hud import formatar_texto_hud\n" + imports)

# 2. HTML Boas Vindas
content = re.sub(
    r'self\.label_boas_vindas\.setText\(\s*"<h2.*?</table>"\s*\)',
    r'self.label_boas_vindas.setText(HTML_BOAS_VINDAS)',
    content,
    flags=re.DOTALL
)

# 3. HTML Dicas
content = re.sub(
    r'msg\.setText\(\s*"<table.*?</table>"\s*\)',
    r'msg.setText(HTML_DICAS_NAVEGACAO)',
    content,
    flags=re.DOTALL
)

# 4. Presets
# Match exactly until the end of the dictionary
content = re.sub(
    r'self\.presets_clinicos = \{.*?"Customizado"\}[\s\n]*\}',
    r'self.presets_clinicos = PRESETS_CLINICOS',
    content,
    flags=re.DOTALL
)

# 5. Styles
content = re.sub(r'self\.setStyleSheet\("""\s*QMainWindow.*?"""\)', 'self.setStyleSheet(STYLE_MAIN_WINDOW)', content, flags=re.DOTALL)
content = re.sub(r'widget\.setStyleSheet\("""\s*QToolButton.*?"""\)', 'widget.setStyleSheet(STYLE_TOOLBAR_BUTTONS)', content, flags=re.DOTALL)
content = re.sub(r'self\.menu_presets\.setStyleSheet\("""\s*QMenu.*?"""\)', 'self.menu_presets.setStyleSheet(STYLE_MENU)', content, flags=re.DOTALL)
content = re.sub(r'self\.btn_presets\.setStyleSheet\("""\s*QToolButton.*?"""\)', 'self.btn_presets.setStyleSheet(STYLE_BTN_PRESETS)', content, flags=re.DOTALL)
content = re.sub(r'self\.spin_espessura\.setStyleSheet\("""\s*QSpinBox.*?"""\)', 'self.spin_espessura.setStyleSheet(STYLE_SPINBOX)', content, flags=re.DOTALL)
content = re.sub(r'self\.btn_crosshair\.setStyleSheet\("""\s*QPushButton.*?"""\)', 'self.btn_crosshair.setStyleSheet(STYLE_BTN_CROSSHAIR)', content, flags=re.DOTALL)
content = re.sub(r'self\.btn_regua\.setStyleSheet\("""\s*QToolButton.*?"""\)', 'self.btn_regua.setStyleSheet(STYLE_BTN_TOGGLE)', content, flags=re.DOTALL)
content = re.sub(r'self\.btn_elipse\.setStyleSheet\("""\s*QToolButton.*?"""\)', 'self.btn_elipse.setStyleSheet(STYLE_BTN_TOGGLE)', content, flags=re.DOTALL)
content = re.sub(r'self\.btn_reslice\.setStyleSheet\("""\s*QToolButton.*?"""\)', 'self.btn_reslice.setStyleSheet(STYLE_BTN_TOGGLE)', content, flags=re.DOTALL)
content = re.sub(r'self\.btn_subtracao_ossea\.setStyleSheet\("""\s*QToolButton.*?:pressed.*?"""\)', 'self.btn_subtracao_ossea.setStyleSheet(STYLE_BTN_SUBTRACAO)', content, flags=re.DOTALL)
content = re.sub(r'self\.btn_sync_scroll\.setStyleSheet\("""\s*QPushButton.*?"""\)', 'self.btn_sync_scroll.setStyleSheet(STYLE_BTN_SYNC_SCROLL)', content, flags=re.DOTALL)
content = re.sub(r'self\.label_boas_vindas\.setStyleSheet\(".*?"\)', 'self.label_boas_vindas.setStyleSheet(STYLE_LABEL_BOAS_VINDAS)', content, flags=re.DOTALL)
content = re.sub(r'self\.dock_series\.setStyleSheet\("""\s*QDockWidget.*?"""\)', 'self.dock_series.setStyleSheet(STYLE_DOCK_WIDGET)', content, flags=re.DOTALL)
content = re.sub(r'self\.list_series\.setStyleSheet\("""\s*QListWidget.*?"""\)', 'self.list_series.setStyleSheet(STYLE_LIST_WIDGET)', content, flags=re.DOTALL)
content = re.sub(r'self\.btn_dicas\.setStyleSheet\("""\s*QPushButton.*?"""\)', 'self.btn_dicas.setStyleSheet(STYLE_BTN_DICAS)', content, flags=re.DOTALL)
content = re.sub(r'msg\.setStyleSheet\("QMessageBox.*?"\)', 'msg.setStyleSheet(STYLE_MSGBOX_DICAS)', content, flags=re.DOTALL)
content = re.sub(r'progresso\.setStyleSheet\("QProgressDialog.*?"\)', 'progresso.setStyleSheet(STYLE_PROGRESS_DIALOG)', content, flags=re.DOTALL)

with open('interface.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Refactoring Fase 3 completed successfully!")
