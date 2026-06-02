import re

with open('interface.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("=== SET STYLE SHEET ===")
for i, line in enumerate(lines):
    if "setStyleSheet" in line:
        print(f"Line {i+1}: {line.strip()}")

print("\n=== SET TEXT (HTML/Long) ===")
for i, line in enumerate(lines):
    if "setText(" in line and ("<" in line or "Deseja" in line):
        print(f"Line {i+1}: {line.strip()}")
        
print("\n=== PRESETS_CLINICOS ===")
for i, line in enumerate(lines):
    if "presets_clinicos =" in line:
        print(f"Line {i+1}: {line.strip()}")
