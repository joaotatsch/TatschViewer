# -*- coding: utf-8 -*-

def formatar_texto_hud(prop_dicom: dict) -> str:
    linhas = []
    
    nome = prop_dicom.get("Nome", "").strip()
    nomes_ignorados = ["", "ANONIMO", "PACIENTE ANONIMIZADO", "DESCONHECIDO", "N/A"]
    if nome.upper() not in nomes_ignorados:
        linhas.append(f"Paciente: {nome}")
        
    inst = prop_dicom.get("Inst", "").strip()
    inst_ignoradas = ["", "ANONIMA", "INSTITUICAO ANONIMA", "HOSPITAL DE NEUROIMAGEM", "N/A"]
    if inst.upper() not in inst_ignoradas:
        linhas.append(f"Inst: {inst}")
        
    data = prop_dicom.get("Data", "").strip()
    if len(data) == 8 and data.isdigit():
        data = f"{data[6:8]}/{data[4:6]}/{data[0:4]}"

    hora = prop_dicom.get("Hora", "").strip()
    hora_limpa = hora.split(".")[0] if "." in hora else hora
    if len(hora_limpa) >= 4:
        hora = f"{hora_limpa[0:2]}:{hora_limpa[2:4]}"
    
    linha_data_hora = ""
    datas_ignoradas = ["", "N/A", "01/01/2000", "01/01/1900", "20000101", "19000101"]
    
    if data and data not in datas_ignoradas:
        linha_data_hora += f"Data: {data}"
        
    if hora and hora not in ["", "N/A"]:
        separador = "   " if linha_data_hora else ""
        linha_data_hora += f"{separador}Hora: {hora}"
        
    if linha_data_hora.strip():
        linhas.append(linha_data_hora.strip())
        
    return "\n".join(linhas)
