# Web Agent Server

Servidor de automação web MCP-like para Agentes de IA. Permite que um LLM controle um navegador Microsoft Edge via Selenium através de comandos Python enviados dinamicamente via API REST.

## Arquitetura

```
                    ┌─────────────────────────┐
                    │      AI Agent / LLM      │
                    │  (Cliente HTTP - Futuro) │
                    └───────────┬─────────────┘
                                │ POST /execute
                                │ {"command": "driver.get(...)"}
                    ┌───────────▼─────────────┐
                    │    FastAPI (server.py)   │
                    │  Interface REST / MCP    │
                    └───────────┬─────────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          │                     │                     │
   ┌──────▼──────┐    ┌────────▼────────┐    ┌───────▼────────┐
   │  Executor   │    │ SessionManager  │    │  BrowserManager│
   │ (executor.py)│   │ (interactive.py) │    │  (browser.py)  │
   │  exec/eval   │    │  Sessões multi  │    │  Singleton     │
   │  AST Check   │    │  Variáveis live │    │  Edge Lifecycle│
   └──────┬──────┘    └────────┬────────┘    └───────┬────────┘
          │                     │                     │
   ┌──────▼──────┐             │                     │
   │   Sandbox   │◄────────────┘                     │
   │ (sandbox.py)│                                   │
   │ Namespace   │                                   │
   │ Controlado  │                                   │
   └─────────────┘                                   │
                                          ┌──────────▼──────────┐
                                          │  Selenium WebDriver  │
                                          │  Microsoft Edge      │
                                          └─────────────────────┘
```

### Clean Architecture

| Camada | Módulo | Responsabilidade |
|--------|--------|-----------------|
| **Interface** | `server.py` | FastAPI endpoints, serialização JSON |
| **Application** | `executor.py`, `interactive.py` | Orquestração de comandos, sessão interativa |
| **Domain** | `browser.py`, `sandbox.py` | Ciclo de vida do browser, segurança |
| **Infrastructure** | `utils.py`, `protocol.py`, `config.py` | Logging, helpers, configuração |

## Estrutura do Projeto

```
Argos_MCP_Browser/
├── server.py              # FastAPI endpoints
├── browser.py             # BrowserManager (singleton Edge)
├── executor.py            # CommandExecutor com sandbox
├── interactive.py         # InteractiveSession + SessionManager
├── sandbox.py             # SafeNamespace + ASTPreChecker
├── models.py              # Pydantic request/response
├── protocol.py            # Helpers de resposta JSON
├── utils.py               # Logging, timing, captura I/O
├── exceptions.py          # Exceções customizadas
├── config.py              # Config centralizada
├── requirements.txt
├── README.md
├── downloads/             # Pasta de downloads automática
└── tests/
    ├── __init__.py
    ├── conftest.py        # Fixtures compartilhadas
    ├── test_browser.py    # 11 testes do BrowserManager
    ├── test_executor.py   # 28 testes do CommandExecutor
    ├── test_sandbox.py    # 27 testes de segurança
    └── test_api.py        # 20 testes de integração
```

**Total: 97 testes unitários + 4 suites**

## Instalação

```bash
pip install -r requirements.txt
```

## Uso

### Iniciar servidor

```bash
python server.py
```

Servidor sobe em `http://127.0.0.1:8000` e inicia automaticamente o Edge com janela visível.

### Endpoints

#### `POST /execute`

Executa um comando Python no navegador.

**Request:**
```json
{
    "command": "driver.get('https://google.com')"
}
```

**Response:**
```json
{
    "success": true,
    "result": null,
    "stdout": "",
    "stderr": "",
    "exception": null,
    "traceback": null,
    "execution_time": 1.2345,
    "screenshot_path": "downloads/screenshot_20240101_120000.png"
}
```

**Exemplos de comandos:**

```python
driver.get("https://google.com")

driver.find_element(By.NAME, "q").send_keys("ChatGPT")

driver.find_element(By.NAME, "q").submit()

driver.page_source

driver.current_url

driver.title

driver.save_screenshot("downloads/test.png")

driver.execute_script("return window.scrollY")
```

#### Sessão Interativa

Variáveis persistem entre chamadas:

**Request 1:**
```json
{
    "command": "search = driver.find_element(By.NAME, 'q')",
    "session_id": "<session_id>"
}
```

**Request 2:**
```json
{
    "command": "search.send_keys('ChatGPT')",
    "session_id": "<session_id>"
}
```

#### `POST /session`

Cria nova sessão interativa.

```json
{
    "session_id": "uuid-here",
    "message": "Session created"
}
```

#### `DELETE /session/{session_id}`

Remove sessão interativa.

#### `GET /health`

```json
{
    "status": "ok",
    "version": "0.1.0"
}
```

#### `GET /status`

```json
{
    "browser_running": true,
    "active_sessions": [],
    "commands_executed": 5,
    "uptime_seconds": 120.5,
    "pid": 12345
}
```

#### `POST /restart`

Reinicia o navegador.

#### `POST /close`

Fecha o navegador.

## Funcionalidades

### Browser Manager (browser.py)
- Singleton: apenas uma instância do Edge
- Início automático na inicialização do servidor
- Opções configuradas: download dir, popups, automação
- Timeouts: implícito (2s), página (30s), script (10s)
- Fechamento e reinicialização controlados

### Command Executor (executor.py)
- `exec()`/`eval()` automático: detecta expression vs statement
- Timeout configurável por comando (default 60s)
- Captura de stdout e stderr
- Screenshot automático pós-execução
- Execução em thread separada para timeout seguro

### Segurança em 3 Camadas (sandbox.py)
1. **AST Pre-checker**: analisa a árvore sintática e bloqueia comandos perigosos ANTES da execução
2. **SafeNamespace**: namespace controlado com apenas objetos autorizados
3. **Timeout**: mata execução após tempo limite

**Bloqueados:**
- `__import__`, `open`, `exec`, `eval`, `compile`, `breakpoint`, `input`
- `os.system`, `os.popen`, `subprocess`, `socket`, `ctypes`, `pickle`
- `getattr`, `setattr`, `delattr`
- `__class__`, `__subclasses__`, `__globals__`, `__builtins__`
- Qualquer `import` de módulo perigoso

**Disponíveis:**
- `driver`, `By`, `Keys`, `EC`, `WebDriverWait`, `ActionChains`, `Select`
- `NoSuchElementException`, `TimeoutException`, `JavascriptException`
- `time`, `sleep`, `re`, `json`, `os` (apenas path/join), `pathlib`, `datetime`
- Builtins seguros: `print`, `len`, `str`, `int`, `Exception`, etc.

### Sessões Interativas (interactive.py)
- Sessões UUID independentes
- Namespace persiste entre chamadas na mesma sessão
- Suporte a múltiplas sessões concorrentes
- Limpeza automática de variáveis ao deletar sessão

### Logging
Formato estruturado com timestamp:
```
2024-01-01 12:00:00 | INFO     | executor | Executing: driver.get(...)
2024-01-01 12:00:01 | INFO     | executor | Result: success=True | time=1.234s | stdout=
```

## Testes

```bash
pytest tests/ -v
```

97 testes que cobrem:
- **Browser**: singleton, start/stop/restart, edge options, is_running
- **Executor**: eval, exec, stdout/stderr, syntax/runtime/name errors, timeout, session, security violations
- **Sandbox**: AST checker (allow/blocks), safe namespace, builtins restriction, dunder blocking
- **API**: health, status, execute (success/error/session/security), session CRUD, restart/close

## Configuração

Variáveis de ambiente (ou defaults em `config.py`):

| Variável | Default | Descrição |
|----------|---------|-----------|
| `HOST` | `127.0.0.1` | Endereço do servidor |
| `PORT` | `8000` | Porta do servidor |
| `HEADLESS` | `false` | Modo headless do Edge |
| `LOG_LEVEL` | `INFO` | Nível de logging |
| `EDGE_DRIVER_PATH` | `""` | Caminho customizado do edgedriver |
| `COMMAND_TIMEOUT` | `60` | Timeout máximo por comando (s) |
| `WINDOW_WIDTH` | `1280` | Largura da janela |
| `WINDOW_HEIGHT` | `800` | Altura da janela |
| `IMPLICIT_WAIT` | `2` | Espera implícita Selenium (s) |
| `PAGE_LOAD_TIMEOUT` | `30` | Timeout de carregamento (s) |

## Exemplo de Integração com LLM

```python
import httpx

BASE = "http://127.0.0.1:8000"

def web_command(command: str, session_id: str | None = None) -> dict:
    payload = {"command": command}
    if session_id:
        payload["session_id"] = session_id
    resp = httpx.post(f"{BASE}/execute", json=payload)
    return resp.json()

# Fluxo típico:
web_command("driver.get('https://gmail.com')")
web_command("driver.find_element(By.ID, 'identifierId').send_keys('user@gmail.com')")
web_command("driver.find_element(By.ID, 'identifierNext').click()")
```

## Diferenciais

- **Clean Architecture**: baixo acoplamento, alta coesão, preparado para escala
- **97 testes**: cobertura rigorosa de segurança, execução e API
- **Segurança profunda**: 3 camadas independentes (AST + namespace + timeout)
- **Sessões interativas**: persiste variáveis entre centenas de chamadas consecutivas
- **Pronto para LLM**: design explícito para agente autônomo com dezenas de chamadas
