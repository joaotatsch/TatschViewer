"""
Módulo para descompactar e extrair arquivos DICOM de pacotes compactados .zip.
"""
import os
import zipfile
import tempfile
from PyQt6.QtCore import QObject
from carregamento.carregamento_pastas_dicom import CarregadorPastasDicom

class CarregadorArquivosZip(QObject):
    """
    Responsável por gerenciar o fluxo de descompactação e leitura temporária de arquivos DICOM contidos em arquivos .zip.
    """
    def __init__(self):
        super().__init__()

    def extrair_e_carregar(self, caminho_zip: str) -> tuple[list, tempfile.TemporaryDirectory]:
        """
        Descompacta o arquivo zip em um diretório temporário e realiza o carregamento
        dos arquivos DICOM encontrados. Retorna a lista de séries e a referência do
        diretório temporário (temp_dir) para preservação de escopo.
        """
        # Cria diretório temporário seguro
        temp_dir = tempfile.TemporaryDirectory()
        caminho_extraido = temp_dir.name
        
        try:
            print(f"[ZIP] Descompactando {caminho_zip} para {caminho_extraido}...")
            with zipfile.ZipFile(caminho_zip, 'r') as zip_ref:
                zip_ref.extractall(caminho_extraido)
                
            # Escaneia a pasta extraída recursivamente
            varredor = CarregadorPastasDicom()
            series_encontradas = varredor.escanear_pasta(caminho_extraido)
            
            print(f"[ZIP] Descompactação concluída. Encontradas {len(series_encontradas)} séries DICOM.")
            return series_encontradas, temp_dir
            
        except Exception as e:
            print(f"[ZIP] Erro ao extrair e escanear arquivo ZIP: {e}")
            # Em caso de erro, limpa o diretório temporário
            try:
                temp_dir.cleanup()
            except Exception:
                pass
            return [], None
