# GAFoam adaptado para o solver multiphaseEuler

Interface gráfica para OpenFOAM utilizando Python e PyQt5.

---

## Instalação simples

```bash

git clone https://github.com/devlucascfarias/GAFoam---multiphaseSolver.git && cd GAFoam---multiphaseSolver && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && echo '#!/bin/bash\nexport LD_LIBRARY_PATH=""\nsource /CAMINHO/REAL/DO/PROJETO/.venv/bin/activate\npython3 /CAMINHO/REAL/DO/PROJETO/main.py "$@"' | sudo tee /usr/local/bin/gafoam-multiphaseEuler > /dev/null && sudo chmod +x /usr/local/bin/gafoam-multiphaseEuler

```


## Se ocorreu algum erro, faça manualmente

### 1. Clone o repositório

```bash
git clone https://github.com/devlucascfarias/GAFoam---multiphaseSolver.git
cd GAFoam---multiphaseSolver
```

### 2. Crie e ative um ambiente virtual

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

---

## Criando um comando global `gafoam-multiphaseEuler`

Se quiser rodar o programa de qualquer lugar do terminal, faça:

```bash

echo '#!/bin/bash
export LD_LIBRARY_PATH=""
source /home/reynolds-01/Documentos/GAFoam---multiphaseSolver/.venv/bin/activate
python3 /home/reynolds-01/Documentos/GAFoam---multiphaseSolver/main.py "$@"' | sudo tee /usr/local/bin/gafoam-multiphaseEuler > /dev/null

sudo chmod +x /usr/local/bin/gafoam-multiphaseEuler


```
**Substitua `/CAMINHO/ABSOLUTO/DA/PASTA` pelo caminho completo da pasta do projeto.**

Agora basta digitar:
```bash
gafoam-multiphaseEuler
```

---

## Como usar

2. **Carregue um caso**
   - Clique em **Arquivo > Carregar Caso** para selecionar o diretório do caso OpenFOAM (deve conter as pastas `0`, `constant`, `system`).
   - Ou clique em **Arquivo > Carregar Arquivo .unv** para importar apenas a malha UNV.

3. **Configuração do diretório base**
   - Se necessário, defina o diretório base em **Arquivo > Definir Diretório Base**.

4. **Conversão e checagem de malha**
   - Use os botões laterais `convertMesh` para converter arquivos `.unv` para OpenFOAM.
   - Use `checkMesh` para validar a malha carregada.

5. **Decomposição e reconstrução**
   - `decomposePar`: Decompõe o caso para execução paralela.
   - `Reconstruct`: Reconstrói os resultados após simulação paralela.
   - `clearProcessors`: Remove diretórios `processor*` antigos.

6. **Configuração de núcleos**
   - Use `configureDecomposeParCores` para definir o número de núcleos no `decomposeParDict`.

7. **Execução da simulação**
   - Clique em **Iniciar** para rodar a simulação. Será solicitado o tempo final (`endTime`).
   - Use **Pausar**, **Retomar**, **Reiniciar** ou **Parar** conforme necessário.

8. **Visualização**
   - **ParaView**: Abre o caso no ParaView.
   - **Gráfico de Resíduos**: Visualize resíduos em tempo real.
   - **Exportar Dados**: Exporte resíduos para CSV.

9. **Histórico de Simulações**
   - Acesse em **Histórico > Ver Histórico de Simulação**.
   - Veja, exclua ou limpe entradas do histórico.
   - Visualize os últimos logs de cada simulação.

10. **Utilitários**
    - **Calcular Δy**: Calcula taxa de crescimento de malha.
    - **Propriedades**: Calcula propriedades do fluido (densidade, viscosidade).

11. **Terminal Integrado**
    - Execute comandos OpenFOAM diretamente pelo terminal na interface.


