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
    ganache --server.port 8545
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

### Headers Padrão

```json
{
  "Content-Type": "application/json",
  "Accept": "application/json"
}
```

---

## 💼 Jobs

### Criar Job

Cria um novo job/serviço no sistema.

**Endpoint:** `POST /jobs/createJob`

**Payload Request:**

```json
{
  "provider_address": "0xd52FB1F884f6909baB0fb9Ddc4A484E80Bc6e525",
  "from_address": "0x79CC510987C4B63796E91dB129f4fF92aBc0Df9f",
  "deadline": "20-9-2025",
  "service_type": "Pintar parede",
  "value": 10,
  "ipfs_hash": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
}
```

**Response Success (200):**

```json
{
  "job_id": "c1467980ba577d239ff6b57fe05e6a7032d0a42744ca22fcdefb9b30e762b864"
}
```

### Buscar Job por ID

Retorna os detalhes de um job específico.

**Endpoint:** `GET /jobs/{job_id}`

**Response Success (200):**

```json
{
  "id": "c1467980ba577d239ff6b57fe05e6a7032d0a42744ca22fcdefb9b30e762b864",
  "client": "0x79CC510987C4B63796E91dB129f4fF92aBc0Df9f",
  "provider": "0xd52FB1F884f6909baB0fb9Ddc4A484E80Bc6e525",
  "amount": 9.5,
  "platform_fee": 0.5,
  "created_at": 1757522729,
  "accepted_at": 0,
  "completed_at": 0,
  "deadline": 1758337200,
  "status": 1,
  "service_type": "Pintar parede",
  "ipfs_hash": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
  "client_rating": 0,
  "provider_rating": 0,
  "created_at_formatted": "2025-09-10T13:45:29",
  "accepted_at_formatted": null,
  "completed_at_formatted": null,
  "deadline_formatted": "2025-09-20T00:00:00"
}
```
