## Configuração do Ambiente

1.  **Instalar dependências Python:**
    ```bash
    poetry install
    ```

2.  **Instalar Ganache (globalmente):**
    ```bash
    npm install -g ganache
    ```
3. **Compilação dos Contratos Solidity (apenas 1 vez para gerar a pasta build):**
    ```bash
    poetry run python script/compile_contracts.py
    ```

4. **Iniciar Ganache:**
    Abra um novo terminal e execute:
    ```bash
    ganache --gasPrice=0 --gasLimit 999999999 --defaultBalanceEther 100000 --port 8545 --hardfork berlin
    ```
    Mantenha este terminal aberto enquanto executa a api.

5. **Deploy dos contratos:**

    ```bash
    poetry run python script/deploy_contracts.py
    ```
6. **Iniciar o uvicorn:**

    ```bash
    poetry run uvicorn app.main:app --reload
    ```


### Base URL

```
Desenvolvimento: http://localhost:8000/
```
