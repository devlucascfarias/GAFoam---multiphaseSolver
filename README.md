# GAFoam adaptado para o solver multiphaseEuler

Interface gráfica para OpenFOAM utilizando Python e PyQt5.

---

## Instalação e Execução

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
source /CAMINHO/ABSOLUTO/DA/PASTA/.venv/bin/activate
python3 /CAMINHO/ABSOLUTO/DA/PASTA/main.py' | sudo tee /usr/local/bin/gafoam-multiphaseEuler > /dev/null

sudo chmod +x /usr/local/bin/gafoam-multiphaseEuler

```
**Substitua `/CAMINHO/ABSOLUTO/DA/PASTA` pelo caminho completo da pasta do projeto.**

Agora basta digitar:
```bash
gafoam-multiphaseEuler
```

---


