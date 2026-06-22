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

    def anonimizar_arquivo(self, caminho_origem: str, diretorio_destino: str) -> str:
        try:
            import pydicom
            import traceback
            import uuid
            from pydicom.uid import ImplicitVRLittleEndian, ExplicitVRLittleEndian
            ds = pydicom.dcmread(caminho_origem, force=True)
            
            # 1. Preservação Estrita de Geometria e Topologia
            # Salva as chaves de orientação antes de qualquer modificação,
            # para reatribuí-las rigorosamente no momento de escrita
            # e evitar inversão de lateralidade.
            ipp = ds.get("ImagePositionPatient", None)
            iop = ds.get("ImageOrientationPatient", None)
            ps = ds.get("PixelSpacing", None)
            
            # Cofre Topológico (Preservação Explícita DEDUP 4D) via DataElement
            series_num_elem = ds.data_element("SeriesNumber") if "SeriesNumber" in ds else None
            study_uid_elem = ds.data_element("StudyInstanceUID") if "StudyInstanceUID" in ds else None
            series_uid_elem = ds.data_element("SeriesInstanceUID") if "SeriesInstanceUID" in ds else None
            sop_uid_elem = ds.data_element("SOPInstanceUID") if "SOPInstanceUID" in ds else None
            desc_elem = ds.data_element("SeriesDescription") if "SeriesDescription" in ds else None
            proto_elem = ds.data_element("ProtocolName") if "ProtocolName" in ds else None
            echo_elem = ds.data_element("EchoNumber") if "EchoNumber" in ds else None
            acq_elem = ds.data_element("AcquisitionNumber") if "AcquisitionNumber" in ds else None
            inst_elem = ds.data_element("InstanceNumber") if "InstanceNumber" in ds else None
            
            # 2. Anonimização Clínica (Blacklist Alvo)
            ds.PatientName = "ANONIMO"
            ds.PatientID = "ANON_ID"
            if "PatientBirthDate" in ds: ds.PatientBirthDate = ""
            
            # Limpeza de médicos e operadores (IDs/Nomes vulneráveis)
            if "OtherPatientIDs" in ds: ds.OtherPatientIDs = "ANON_ID"
            if "PatientTelephoneNumbers" in ds: ds.PatientTelephoneNumbers = ""
            if "ReferringPhysicianName" in ds: ds.ReferringPhysicianName = "ANONIMO"
            if "PerformingPhysicianName" in ds: ds.PerformingPhysicianName = "ANONIMO"
            if "NameOfPhysiciansReadingStudy" in ds: ds.NameOfPhysiciansReadingStudy = "ANONIMO"
            if "OperatorsName" in ds: ds.OperatorsName = "ANONIMO"
                
            # 3. Extermínio de Group Lengths
            tags_del = [tag for tag in ds.keys() if tag.element == 0]
            for tag in tags_del:
                del ds[tag]
                
            # 4. Reaplicação Rigorosa da Geometria (Anti-Inversão) e Topologia
            if ipp is not None: ds.ImagePositionPatient = ipp
            if iop is not None: ds.ImageOrientationPatient = iop
            if ps is not None: ds.PixelSpacing = ps
            
            # Restauração do Cofre Topológico via DataElement
            if series_num_elem is not None: ds[series_num_elem.tag] = series_num_elem
            if study_uid_elem is not None: ds[study_uid_elem.tag] = study_uid_elem
            if series_uid_elem is not None: ds[series_uid_elem.tag] = series_uid_elem
            if sop_uid_elem is not None: ds[sop_uid_elem.tag] = sop_uid_elem
            if desc_elem is not None: ds[desc_elem.tag] = desc_elem
            if proto_elem is not None: ds[proto_elem.tag] = proto_elem
            if echo_elem is not None: ds[echo_elem.tag] = echo_elem
            if acq_elem is not None: ds[acq_elem.tag] = acq_elem
            if inst_elem is not None: ds[inst_elem.tag] = inst_elem
                
            # 5. Higiene do File Meta Header (Grupo 2)
            original_ts = None
            if hasattr(ds, 'file_meta') and ds.file_meta is not None:
                original_ts = ds.file_meta.get('TransferSyntaxUID', None)
            else:
                ds.file_meta = pydicom.dataset.FileMetaDataset()
                
            # Sincronização obrigatória
            if "SOPClassUID" in ds: ds.file_meta.MediaStorageSOPClassUID = ds.SOPClassUID
            if "SOPInstanceUID" in ds: ds.file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
                
            # Preservação Rigorosa de Sintaxe de Transferência e Endianness (Resolve o bug do Scramble na RM)
            if original_ts is not None:
                ds.file_meta.TransferSyntaxUID = original_ts
            else:
                # Apenas faz deduções baseadas em is_implicit_VR caso o arquivo original tenha vindo sem meta
                if getattr(ds, 'is_implicit_VR', True):
                    ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
                else:
                    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
            
            # 4. Força pydicom a reconstruir o cabeçalho matematicamente e alinhar bytes
            pydicom.dataset.validate_file_meta(ds.file_meta, enforce_standard=True)
            
            # Garante unicidade usando o SOPInstanceUID
            sop_uid = ds.get("SOPInstanceUID", None)
            if not sop_uid:
                sop_uid = str(uuid.uuid4())
            caminho_destino = os.path.join(diretorio_destino, f"{sop_uid}.dcm")
                
            # 5. Salvamento cravado no padrão Part 10
            ds.save_as(caminho_destino, write_like_original=False)
            return caminho_destino
            
        except Exception as e:
            import traceback
            print(f"[DROP] Erro fatal ao anonimizar arquivo {caminho_origem}: {e}\nTraceback:\n{traceback.format_exc()}")
            return None

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
                caminho_salvo = self.anonimizar_arquivo(caminho, diretorio_destino)
                if caminho_salvo:
                    sucessos += 1
                    arquivos_salvos.append(caminho_salvo)
                else:
                    print(f"[DROP] Arquivo ignorado na escrita (retornou None): {caminho}")
            except Exception as e:
                import traceback
                print(f"[DROP] Falha inesperada ao processar {caminho}: {e}\nTraceback:\n{traceback.format_exc()}")
                continue
                
            if progress_callback:
                progress_callback(idx + 1, total)
                
        print(f"[ANONIMIZADOR] Concluído. Sucesso em {sucessos} de {total} fatias.")
        return sucessos == total
