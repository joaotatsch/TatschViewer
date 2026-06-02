# Neuroviewer 🧠

Neuroviewer é um software avançado de visualização e processamento de imagens médicas (DICOM), construído em Python. Ele combina a flexibilidade de interfaces gráficas ricas do **PyQt6** com o poder de renderização 3D e processamento do **VTK** e **SimpleITK**.

Recentemente reestruturado sob os princípios de **Clean Architecture** (Arquitetura Limpa), o projeto prioriza o Desacoplamento, a Separação de Responsabilidades (Separation of Concerns) e a manutenibilidade, abolindo anti-patterns como o *God Object*.

---

## 🏗️ Arquitetura do Sistema

A arquitetura foi dividida de forma lógica em módulos independentes que conversam entre si utilizando *callbacks*, sinais assíncronos (`pyqtSignal`) e controladores.

### 1. `interface.py` (A Camada de Orquestração)
Atua puramente como o maestro da interface. A `MainWindow` não possui regras de negócios, strings hardcoded pesadas ou amarras de I/O de disco.
* **Responsabilidade:** Criar layouts, capturar ações do usuário (cliques em botões, redimensionamentos) e delegar tarefas aos Coordenadores apropriados.
* Construída com métodos segmentados (`_construir_toolbar`, `_construir_area_central`, `_construir_painel_lateral`) para facilitar a navegação do código.

### 2. Módulo `ui/` (Dados Estáticos e Visuais)
Centraliza toda a Poluição de Strings (CSS, HTML, Dicionários) fora dos arquivos lógicos, mantendo o código limpo.
* **`textos_e_estilos.py`:** Armazena marcações de estilo nativo PyQt (`STYLE_MAIN_WINDOW`, `STYLE_TOOLBAR_BUTTONS`) e textos em HTML longos (Boas-Vindas e Dicas).
* **`config_presets.py`:** Guarda configurações estáticas e dicionários, como os presets clínicos de Janelamento (Window Width / Window Level).

### 3. Módulo `carregamento/` (Entrada, Saída e File System)
Isola as interações pesadas com o disco rígido e o SimpleITK.
* **`threads_carregamento.py`:** Contém a `ThreadCarregamento`, responsável por ler dados assincronamente em segundo plano, evitando que a interface congele durante o *parse* dos metadados GDCM.
* **`controlador_exportacao.py`:** O `ControladorExportacao` gerencia os laços de iteração pelas pastas de exames e aciona as rotinas de exportação do Anonimizador, injetando retornos de progresso à interface.
* **`CoordenadorCarregamento`:** Escaneamento inicial de arquivos DICOM.

### 4. Módulo `processamento_imagem/` (Matemática e Processamento)
Dedica-se inteiramente ao processamento intensivo de matrizes numéricas (Numpy) e VTK.
* **`threads_subtracao.py`:** Organiza QThreads isoladas para cálculos lentos ou rápidos como Subtração Digital (DSA), Subtração Óssea e Segmentação por Semente, enviando os volumes processados de volta ao visualizador via sinais assíncronos.

### 5. Módulo `exibicao/` (Regras de Apresentação)
* **`formatador_hud.py`:** Contém lógicas limpas e independentes (`def formatar_texto_hud`) para limpeza e anonimização de *strings* dos atributos DICOM visíveis na tela.
* **`CoordenadorExibicao`:** Coordena de forma dinâmica as trocas entre layouts (MPR Clássico 4-Up, Grade 2x2, Comparação 1x3).

### 6. Módulo `navegacao/` (Interação VTK e Interactors)
Contém os filtros e os eventos de interação nativa da janela.
* **Filtros de Eventos Dicom (`__init__.py`)**: Captura e trata os comportamentos do mouse no ambiente 3D. Emprega táticas extremas de *Blindagem Anti-Segfault* (ex: verificação nula de renders, *try/except* em chamadas nativas de C++, cálculos seguros para Push de planos). Também incorpora mecânicas híbridas como o *Sync Scroll*.

### 7. Serviços de Apoio
* **`anonimizador.py`:** Módulo backend puro do SimpleITK configurado para sobrescrever ou limpar tags DICOM sensíveis e salvar os exames em lote de maneira protegida e ética.

---

## 🛠️ Tecnologias Principais

* **Python 3.x**
* **PyQt6:** Interface gráfica (GUI), Event Loops, QThreads, QProgressDialog.
* **VTK (Visualization Toolkit):** Renderização avançada (Volume Rendering, Interatores 3D, Reslice, MPR).
* **SimpleITK / GDCM:** Leitura dos arquivos DICOM e manipulação dos arrays da imagem tridimensional.
* **NumPy:** Matrizes de alta performance para os algoritmos de Subtração (DSA).

## ✨ Características Técnicas (Pós-Refatoração)
- **Zero God Object:** O código não mistura regras de processamento e layout.
- **Assincronismo Focado:** Utilização intensiva de `pyqtSignal` e `QThread` para evitar *Freezing* da UI.
- **Fail-Safes:** Uso de *try/except* silenciosos nos blocos *C++ Bindings* (VTK) para impedir crashes irrecuperáveis por ponteiros nulos ou chaves inexistentes durante o dinamismo de troca de telas.
- **Single Source of Truth:** Estilos e textos ficam em um só lugar (`ui/`), evitando poluição cognitiva.

## 🚀 Funcionalidades Clínicas (Features)

Apesar de sua arquitetura complexa, o Neuroviewer entrega uma experiência de usuário simples, fluida e focada na dor do médico radiologista/neurologista:

* **Navegação MPR Nativa:** Visões Axial, Coronal e Sagital sincronizadas, com suporte a reconstruções de espessura (MIP, MinIP e Average).
* **Cinematic Volume Rendering (3D):** Renderização tridimensional acelerada por GPU, com Presets customizados para Angio-TC, Osso, e Tecidos Moles.
* **Ferramentas de Medição 3D:** Réguas milimétricas e Elipses de ROI (Region of Interest) que calculam densidade (HU) e área em tempo real, respeitando o espaço mundial (World Space) do VTK.
* **Subtração Óssea Automática:** Algoritmos híbridos de morfologia matemática para isolar a árvore vascular intracraniana sem a necessidade da fase pré-contraste.
* **Bisturi Digital (Dissecção 3D):** Ferramenta de corte à mão livre e caixas de recorte (Cropping Box) para remover calota craniana e expor polígonos vasculares.
* **Sincronização Espacial (Sync Scroll):** Permite rolar múltiplas telas e fases diferentes de um exame mantendo o alinhamento anatômico absoluto (em milímetros).

---

## 💻 Instalação e Execução (Quick Start)

Para configurar o ambiente de desenvolvimento e executar o Neuroviewer, recomenda-se o uso de um ambiente virtual Python (ex: `venv` ou `conda`).

**1. Clone o repositório e acesse a pasta:**
```bash
git clone https://seu-repositorio/neuroviewer.git
cd neuroviewer

**2. Instale as dependências rigorosas:**
'''bash
pip install -r requirements.txt
(Certifique-se de que o arquivo requirements.txt contenha PyQt6, vtk, SimpleITK, numpy e pydicom).

**3. Execute o Software:**
code
Bash
python main.py