import os
import glob

def remove_logs(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    new_lines = []
    for line in lines:
        if 'print(\'LOG-TOOL:' in line or 'print("LOG-TOOL:' in line:
            continue
        if 'print(\'LOG-EVENT:' in line or 'print("LOG-EVENT:' in line:
            continue
        new_lines.append(line)
        
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

files = glob.glob('navegacao/**/*.py', recursive=True)
for f in files:
    remove_logs(f)
