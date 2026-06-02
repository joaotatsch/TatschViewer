# 🧠 TatschViewer

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Framework: PyQt6](https://img.shields.io/badge/UI-PyQt6-41CD52?style=flat&logo=qt&logoColor=white)](https://www.qt.io/)
[![Engine: VTK](https://img.shields.io/badge/3D_Engine-VTK_9+-red.svg)](https://vtk.org/)

O **TatschViewer** é um visualizador de neuroimagem 3D e 2D de alta performance, desenvolvido sob a missão social e médica de democratizar o acesso a ferramentas diagnósticas avançadas de código aberto. Projetado para neurologistas, neurocirurgiões, radiologistas e instituições de saúde, o software permite a manipulação, reconstrução e análise de exames no padrão **DICOM** sem custos de licenciamento.

O projeto foi concebido e desenvolvido pelo **Dr. João Fellipe Santos Tatsch**, médico neurologista, unindo a prática clínica diária à engenharia de software de ponta.

---

## 🌟 Principais Recursos

### 🔬 Visualização e Reconstrução Avançada
* **Multi-Planar Reconstruction (MPR):** Visualização ortogonal simultânea (Axial, Sagital, Coronal) integrada ao modelo 3D.
* **Reslice Oblíquo Livre:** Rotacione planos de corte 2D de forma interativa e ajuste o ponto de pivô para analisar estruturas complexas sob qualquer ângulo.
* **Crosshair (Mira ⌖):** Sincronização espacial instantânea entre todas as visões 2D e o modelo 3D ao clicar em qualquer ponto (Atalho rápido: `C`).
* **Visualização Multitelas:** Compare até 4 séries ou exames simultaneamente em quadrantes de visualização independentes com suporte a arrastar-e-soltar (*Drag & Drop*).
* **Sincronização Anatômica (🔗):** Navegação coordenada fisicamente (em milímetros) entre múltiplos quadrantes, garantindo alinhamento perfeito mesmo para exames com resoluções diferentes.

### 🖼️ Processamento de Imagem e Projeções
* **Janelamento (WW/WL):** Ajuste fino de brilho e contraste por presets rápidos (Cérebro, Osso, Tecidos Moles) ou controle manual direto arrastando o mouse.
* **MIP, MinIP & Average:** Projeção de Intensidade Máxima (para vasos e ossos), Projeção de Intensidade Mínima (para vias aéreas) e Média, com ajuste dinâmico de espessura da fatia (*Slab*).
* **Subtração Óssea 3D:**
  * **Rápida (Single-Scan):** Algoritmo de morfologia matemática e *Region Growing* em segundos para isolamento vascular cervical e intracraniano de emergência.
  * **Lenta (DSA Digital):** Técnica clássica de subtração digital com registro espacial rígido entre as fases com e sem contraste.

### 📐 Ferramentas de Medição e Diagnóstico
* **Régua Linear:** Medição precisa de distâncias em milímetros.
* **Elipse de Região de Interesse (ROI):** Cálculo automático de área em $\text{mm}^2$, além de densidade mínima, máxima e média em **Unidades Hounsfield (HU)**.

### ✂️ Dissecção Volumétrica 3D
* **Cubo de Interesse (Bounding Box):** Recorte e isole regiões da reconstrução 3D em tempo real através dos planos de controle.
* **Bisturi de Mão Livre (Lasso Tool):** Ferramenta cirúrgica virtual para desenhar contornos livres e remover estruturas indesejadas da memória volumétrica.

### 🔒 Segurança e Privacidade
* **Anonimizador DICOM:** Remoção completa de tags de identificação do paciente (Nome, ID, Data de Nascimento) em conformidade rigorosa com a norma **DICOM Part 10** antes de exportações ou apresentações científicas.

---

## 🛠️ Tecnologias Utilizadas

* **Linguagem:** [Python](https://www.python.org/)
* **Interface Gráfica (GUI):** [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) com folha de estilos customizada em *Dark Mode Clínico*.
* **Processamento 3D/Visualização:** [VTK (Visualization Toolkit)](https://vtk.org/) para renderização volumétrica acelerada por hardware (GPU).
* **Processamento de Dados Médicos:** [PyDicom](https://pydicom.github.io/), [NumPy](https://numpy.org/) e [SimpleITK](https://simpleitk.org/).

---

## 💻 Como Executar o Projeto

### Pré-requisitos
Certifique-se de ter o **Python 3.10 ou superior** instalado em sua máquina.

### Passo 1: Clonar o Repositório
```bash
git clone https://github.com/joaotatsch/TatschViewer.git
cd TatschViewer
```

### Passo 2: Instalar as Dependências
É altamente recomendado o uso de um ambiente virtual (`venv`):
```bash
# Criar ambiente virtual
python -m venv venv

# Ativar ambiente virtual
# No Windows:
venv\Scripts\activate
# No Linux/macOS:
source venv/bin/activate

# Instalar dependências necessárias
pip install -r requirements.txt
```
*(Nota: Certifique-se de gerar o arquivo `requirements.txt` com as dependências do PyQt6, vtk, pydicom, numpy, simpleitk, etc., ou instale-as diretamente)*.

### Passo 3: Executar o Aplicativo
```bash
python main.py
```

---

## ⚖️ Termos de Uso e Licença

Este software é distribuído sob a **Licença MIT** — consulte o arquivo [LICENSE](LICENSE) para obter mais detalhes.

> [!IMPORTANT]
> O TatschViewer foi desenvolvido primariamente como ferramenta auxiliar para visualização, estudos, discussões científicas e fins acadêmicos. O uso do software para diagnósticos clínicos oficiais deve seguir o discernimento e responsabilidade técnica exclusiva do profissional médico assistente responsável.

---

## 📧 Contato e Suporte

* **Desenvolvedor:** Dr. João Fellipe Santos Tatsch
* **Site Oficial:** [www.joaotatsch.com.br](http://www.joaotatsch.com.br)
* **E-mail:** [neurologistajoao@gmail.com](mailto:neurologistajoao@gmail.com)
* **Website Institucional:** Informações médicas e novidades sobre o projeto.
