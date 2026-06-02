"""
Módulo para anonimização de arquivos DICOM.
"""
import os
from PyQt6.QtCore import QObject
import pydicom

class AnonimizadorDicom(QObject):
    """
    Tornará os arquivos DICOM anônimos utilizando o pydicom, removendo
    metadados confidenciais com preservação absoluta de UIDs e estrutura.
    """
    def __init__(self):
        super().__init__()

    def anonimizar_arquivo(self, caminho_origem: str, caminho_destino: str) -> bool:
        try:
            import pydicom
            from pydicom.uid import ImplicitVRLittleEndian, ExplicitVRLittleEndian
            ds = pydicom.dcmread(caminho_origem, force=True)
            
            # 1. Anonimização Clínica
            ds.PatientName = "ANONIMO"
            ds.PatientID = "ANON_ID"
            if "InstitutionName" in ds: ds.InstitutionName = "ANONIMA"
            if "PatientBirthDate" in ds: ds.PatientBirthDate = ""
            if "StudyDate" in ds: ds.StudyDate = "20000101"
                
            # 2. Extermínio de Group Lengths
            tags_del = [tag for tag in ds.keys() if tag.element == 0]
            for tag in tags_del:
                del ds[tag]
                
            # 3. Higiene do File Meta Header (Grupo 2)
            if not hasattr(ds, 'file_meta') or ds.file_meta is None:
                ds.file_meta = pydicom.dataset.FileMetaDataset()
                
            # Sincronização obrigatória
            if "SOPClassUID" in ds: ds.file_meta.MediaStorageSOPClassUID = ds.SOPClassUID
            if "SOPInstanceUID" in ds: ds.file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
                
            # Alinhamento estrito de Sintaxe de Transferência
            if getattr(ds, 'is_implicit_VR', True):
                ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
            else:
                ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
            
            # 4. Força pydicom a reconstruir o cabeçalho matematicamente e alinhar bytes
            pydicom.dataset.validate_file_meta(ds.file_meta, enforce_standard=True)
            
            if not caminho_destino.lower().endswith(".dcm"):
                caminho_destino += ".dcm"
                
            # 5. Salvamento cravado no padrão Part 10
            ds.save_as(caminho_destino, write_like_original=False)
            return True
            
        except Exception as e:
            print(f"[ANONIMIZADOR] Erro ao anonimizar arquivo {caminho_origem}: {e}")
            return False

    def anonimizar_serie(self, caminhos_origem: list, diretorio_destino: str, progress_callback=None, check_cancel=None) -> bool:
        """
        Lê e anonimiza uma série completa de arquivos DICOM, salvando-os no diretório de destino.
        Permite enviar o progresso atual através do progress_callback opcional e checar cancelamento.
        """
        if not caminhos_origem:
            print("[ANONIMIZADOR] Lista de arquivos de origem vazia.")
            return False
            
        if not os.path.exists(diretorio_destino):
            try:
                os.makedirs(diretorio_destino)
            except Exception as e:
                print(f"[ANONIMIZADOR] Falha ao criar diretório de destino: {e}")
                return False
                
        sucessos = 0
        total = len(caminhos_origem)
        arquivos_salvos = []
        
        print(f"[ANONIMIZADOR] Iniciando anonimização de {total} fatias para {diretorio_destino}...")
        for idx, caminho in enumerate(caminhos_origem):
            if check_cancel and check_cancel():
                print("[ANONIMIZADOR] Processo cancelado. Limpando arquivos parciais...")
                for arq in arquivos_salvos:
                    try:
                        if os.path.exists(arq):
                            os.remove(arq)
                    except Exception as e:
                        print(f"[ANONIMIZADOR] Falha ao remover arquivo parcial {arq}: {e}")
                return False

            try:
                nome_sequencial = f"slice_{idx:04d}.dcm"
                caminho_salvar = os.path.join(diretorio_destino, nome_sequencial)
                
                if self.anonimizar_arquivo(caminho, caminho_salvar):
                    sucessos += 1
                    arquivos_salvos.append(caminho_salvar)
            except Exception as e:
                print(f"[ANONIMIZADOR] Falha inesperada ao processar {caminho}: {e}")
                continue
                
            if progress_callback:
                progress_callback(idx + 1, total)
                
        print(f"[ANONIMIZADOR] Concluído. Sucesso em {sucessos} de {total} fatias.")
        return sucessos == total
