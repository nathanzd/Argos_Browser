# Argos MCP Browser — Para CLIs de IA

## O que é?

Um servidor REST que expõe um navegador Edge controlável por comando Python, pensado para **agentes de IA** que precisam de um browser real (não headless-por-padrão, mas configurável).

## Porquê para CLIs de IA?

CLIs como `opencode`, `claude code` ou `copilot` têm acesso ao terminal, mas **não têm um navegador**. Com este servidor a correr localmente:

- O agente faz `POST /execute` com comandos Python reais (`driver.get`, `find_element`, `click`)
- O browser responde: screenshot, HTML, cookies, rede — tudo disponível
- Sessões interativas permitem múltiplos passos sem perder estado

## Exemplo (para qualquer agente CLI)

```
POST /execute
{"command": "driver.get('https://exemplo.com')"}
```

O LLM inspeciona o resultado e decide o próximo passo — tal como faria com comandos shell.

## Segurança

3 camadas independentes:
- **AST pre-checker** bloqueia código perigoso antes de executar
- **Namespace controlado** só expõe objetos do Selenium
- **Timeout** mata comandos lentos (default 60s)

## Setup

```bash
pip install -r requirements.txt
python server.py
# Servidor em http://127.0.0.1:8000
```

## Ligação do agente ao servidor

Cada CLI de IA tem a sua forma de integrar ferramentas HTTP. O conceito é o mesmo: expor `/execute` como tool, e o LLM passa comandos Selenium como argumento.

---

**TL;DR:** Dá a um LLM o poder de navegar na web como um humano, sem abrir olhos humanos.
