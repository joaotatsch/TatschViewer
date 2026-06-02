# -*- coding: utf-8 -*-
"""
Módulo de ajuda do TatschViewer.
Contém o GerenciadorAjuda, que exibe caixas de diálogo explicativas para os recursos do software.
"""

from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import Qt

class GerenciadorAjuda:
    """
    Classe responsável por gerenciar a exibição dos tópicos de ajuda do TatschViewer
    adotando o princípio de separação de responsabilidades (Clean Architecture).
    """

    # Estilização no padrão Dark Mode Clínico estabelecido no aplicativo
    STYLE_AJUDA = """
        QMessageBox {
            background-color: #1a1a1a;
            color: #e0e0e0;
            min-width: 480px;
        }
        QLabel {
            color: #e0e0e0;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 13px;
        }
        QPushButton {
            background-color: #2a2a2a;
            color: #e0e0e0;
            border: 1px solid #3d3d3d;
            border-radius: 4px;
            padding: 6px 18px;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 12px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #353535;
            border-color: #555555;
            color: #ffffff;
        }
        QPushButton:pressed {
            background-color: #121212;
            border-color: #007acc;
            color: #007acc;
        }
    """

    _TOPICOS = {
        "Abrindo arquivos DICOM": (
            "Para abrir exames, você pode usar o botão 'Abrir Pasta' na barra de ferramentas "
            "ou simplesmente arrastar e soltar uma pasta DICOM (ou arquivo .zip) diretamente "
            "em qualquer tela do aplicativo. O sistema possui um cache inteligente que fará exames "
            "já vistos abrirem instantaneamente."
        ),
        "Anonimizador": (
            "Remove todas as tags confidenciais do paciente (Nome, ID, Data) e reescreve o arquivo "
            "no rigoroso padrão DICOM Part 10. Selecione a série na lista à esquerda e clique no botão "
            "Anonimizar. Você pode exportar apenas a série ativa ou todas as séries do diretório."
        ),
        "Usando múltiplas telas": (
            "O TatschViewer permite a comparação de múltiplos exames (ex: Fase Sem Contraste vs Angio). "
            "Clique em uma série na lista lateral esquerda, mantenha o botão do mouse pressionado "
            "e arraste-a para dentro de qualquer um dos quadrantes de visualização."
        ),
        "Botão de Sincronizar (Toggle)": (
            "Representado pelo ícone de Corrente (🔗). Quando ativado, rolar a roda do mouse (scroll) "
            "em uma tela fará com que todas as outras telas acompanhem o movimento fisicamente "
            "(em milímetros), garantindo o alinhamento anatômico perfeito entre exames de diferentes resoluções."
        ),
        "Janelamento": (
            "Ajusta o Contraste (WW) e Brilho (WL). Você pode usar o botão de Presets na barra superior "
            "para seleções rápidas (ex: Cérebro, Osso) ou clicar com o Botão Esquerdo do mouse "
            "sobre o fundo da imagem e arrastar para ajustar manualmente."
        ),
        "MIP, MinIP e Average": (
            "Ferramentas de Projeção de Intensidade. Use o menu 'MIP' para ativar. MIP destaca "
            "vasos e ossos (estruturas densas); MinIP destaca vias aéreas (baixa densidade); "
            "Average cria uma média. Ajuste a espessura da projeção (Slab) na caixa de milímetros ao lado."
        ),
        "Reslice": (
            "Ative o botão de Reslice para reconstrução oblíqua livre. Nas telas 2D, clique e segure "
            "nos eixos coloridos próximos às bordas para rotacionar o plano. Clique no centro exato "
            "da cruz para arrastar o ponto de pivô."
        ),
        "Crosshair (Mira)": (
            "Ative o botão ⌖. Ao clicar em qualquer estrutura no 2D, as outras duas visões "
            "ortogonais e o modelo 3D saltarão instantaneamente para a exata coordenada 3D apontada. "
            "Atalho rápido: Segure a tecla 'C'."
        ),
        "Régua": (
            "Ferramenta de distância linear. Ative o botão da régua, clique e segure o botão esquerdo "
            "no ponto inicial, arraste até o ponto final e solte. Para apagar, passe o mouse "
            "sobre ela e aperte a tecla 'Delete'."
        ),
        "Elipse (ROI)": (
            "Ferramenta de Região de Interesse. Funciona de forma similar à Régua, mas desenha "
            "um círculo. Ela calcula automaticamente a Área em mm², além da Densidade Máxima, "
            "Mínima e Média em Unidades Hounsfield (HU) dos pixels englobados."
        ),
        "Subtração Óssea > Rápida": (
            "Utiliza apenas a fase contrastada (Single-Scan). É um processo de segundos que isola "
            "a árvore vascular intracraniana e cervical através de algoritmos de morfologia matemática "
            "e sementes de inundação (Region Growing). Ideal para rotinas de emergência."
        ),
        "Subtração Óssea > Lenta": (
            "Utiliza a técnica clássica de Subtração Digital (DSA). Demanda mais poder computacional e tempo. "
            "Requer a fase Sem Contraste e a Angio. Executa o registro espacial rígido (alinhamento). "
            "Possui limitações caso o paciente tenha movimentado o pescoço entre as aquisições."
        ),
        "Dissecção > Cubo de Interesse": (
            "Gera uma caixa envolvente (Bounding Box). Arraste as paredes da caixa nas visões 2D "
            "para 'recortar' o modelo 3D em tempo real. Essencial para decaptar a calvária e "
            "observar o polígono de Willis de cima."
        ),
        "Dissecção > Bisturi de Mão livre": (
            "Ferramenta de extirpação. Ative e desenhe um polígono livre com o mouse sobre a "
            "tela 3D ou 2D fechando o círculo. Tudo o que estiver dentro do desenho será apagado "
            "da memória volumétrica."
        )
    }

    @staticmethod
    def mostrar_ajuda(topico: str, parent=None) -> None:
        """
        Exibe uma caixa de diálogo explicativa sobre o tópico especificado,
        estilizada no Dark Mode clínico.
        """
        mapeamento = {
            "Abrindo arquivos DICOM": ("ajuda_abrir_lbl", "ajuda_abrir_val"),
            "Anonimizador": ("ajuda_anonimizador_lbl", "ajuda_anonimizador_val"),
            "Usando múltiplas telas": ("ajuda_multitelas_lbl", "ajuda_multitelas_val"),
            "Botão de Sincronizar (Toggle)": ("ajuda_sync_lbl", "ajuda_sync_val"),
            "Janelamento": ("ajuda_janela_lbl", "ajuda_janela_val"),
            "MIP, MinIP e Average": ("ajuda_mip_lbl", "ajuda_mip_val"),
            "Reslice": ("ajuda_reslice_lbl", "ajuda_reslice_val"),
            "Crosshair (Mira)": ("ajuda_crosshair_lbl", "ajuda_crosshair_val"),
            "Régua": ("ajuda_regua_lbl", "ajuda_regua_val"),
            "Elipse (ROI)": ("ajuda_elipse_lbl", "ajuda_elipse_val"),
            "Subtração Óssea > Rápida": ("ajuda_subtracao_rapida_lbl", "ajuda_subtracao_rapida_val"),
            "Subtração Óssea > Lenta": ("ajuda_subtracao_lenta_lbl", "ajuda_subtracao_lenta_val"),
            "Dissecção > Cubo de Interesse": ("ajuda_disseccao_cubo_lbl", "ajuda_disseccao_cubo_val"),
            "Dissecção > Bisturi de Mão livre": ("ajuda_disseccao_bisturi_lbl", "ajuda_disseccao_bisturi_val")
        }
        
        chaves = mapeamento.get(topico)
        if chaves:
            from traducoes import tr
            titulo_trad = tr(chaves[0])
            texto_trad = tr(chaves[1])
        else:
            titulo_trad = f"Ajuda: {topico}"
            texto_trad = GerenciadorAjuda._TOPICOS.get(topico, "")
            
        if not texto_trad:
            return

        msg = QMessageBox(parent)
        msg.setWindowTitle(titulo_trad)
        msg.setText(texto_trad)
        msg.setStyleSheet(GerenciadorAjuda.STYLE_AJUDA)
        msg.exec()

    _SOBRE = {
        "Intuito do Programa": (
            "O TatschViewer nasceu de uma missão social e médica: auxiliar hospitais, clínicas e "
            "profissionais que não possuem um visualizador DICOM nativo ou não dispõem de recursos "
            "financeiros para licenciar softwares comerciais de alto custo. Este programa é de código "
            "aberto (Open Source) e está disponível gratuitamente para uso, democratizando o acesso à "
            "neuroimagem de alta performance computacional."
        ),
        "Sobre o Autor": (
            "Dr. João Fellipe Santos Tatsch é médico neurologista formado pela Escola Superior de "
            "Ciências da Saúde (ESCS-DF), com período sanduíche na University of Toronto (Canadá), "
            "onde realizou estágio em neurocirurgia no Toronto Western Hospital. Concluiu sua "
            "Residência Médica em Neurologia e Fellowship em Neurologia Geral no Hospital Santa Marcelina (SP). "
            "Atualmente, atua como Neurologista na rede pública do Distrito Federal (Hospital Regional do "
            "Gama e Santa Maria). Aliando sua expertise clínica à engenharia de software, desenvolve "
            "ferramentas tecnológicas para aprimorar a prática médica."
        ),
        "Site Oficial": (
            "Acesse nosso site para novidades, atualizações e documentação:\n\n🌐 www.joaotatsch.com.br\n\n."
        ),
        "Site": (
            "Acesse nosso site para novidades, atualizações e documentação:\n\n🌐 www.joaotatsch.com.br\n\n."
        ),
        "Entre em Contato": (
            "Dúvidas, sugestões ou parcerias? Entre em contato diretamente com o desenvolvedor:\n\n📧 E-mail: neurologistajoao@gmail.com"
        ),
        "Entre em contato": (
            "Dúvidas, sugestões ou parcerias? Entre em contato diretamente com o desenvolvedor:\n\n📧 E-mail: neurologistajoao@gmail.com"
        )
    }

    @staticmethod
    def mostrar_sobre(topico: str, parent=None) -> None:
        """
        Exibe uma caixa de diálogo informativa sobre a missão do projeto, o autor ou contatos,
        estilizada no padrão Dark Mode clínico do TatschViewer.
        """
        mapeamento = {
            "Intuito do Programa": ("sobre_intuito_lbl", "sobre_intuito_val"),
            "Sobre o Autor": ("sobre_autor_lbl", "sobre_autor_val"),
            "Site Oficial": ("sobre_site_lbl", "sobre_site_val"),
            "Site": ("sobre_site_lbl", "sobre_site_val"),
            "Entre em Contato": ("sobre_contato_lbl", "sobre_contato_val"),
            "Entre em contato": ("sobre_contato_lbl", "sobre_contato_val")
        }
        
        chaves = mapeamento.get(topico)
        if chaves:
            from traducoes import tr
            titulo_trad = tr(chaves[0])
            texto_trad = tr(chaves[1])
        else:
            titulo_trad = f"Sobre: {topico}"
            texto_trad = GerenciadorAjuda._SOBRE.get(topico, "")
            
        if not texto_trad:
            return

        msg = QMessageBox(parent)
        msg.setWindowTitle(titulo_trad)
        msg.setText(texto_trad)
        msg.setStyleSheet(GerenciadorAjuda.STYLE_AJUDA)
        msg.exec()
