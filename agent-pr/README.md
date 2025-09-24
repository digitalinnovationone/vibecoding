# PR Code Quality Reviewer (Azure DevOps + Azure OpenAI)

## Visão geral
Este utilitário Python analisa **arquivos alterados de um Pull Request (PR) do Azure DevOps** e gera um relatório de qualidade de código com foco em segurança, desempenho, confiabilidade e manutenibilidade. Ele também **comenta automaticamente no PR** com um resumo do relatório.

**Saídas geradas:**
- `report.json` — resultado estruturado por arquivo e severidade
- `report.md` — relatório em Markdown, pronto para leitura/compartilhamento
- Diretório de trabalho: `./work_pr_repo` (cópia do repositório/branches para diff)

## Como funciona (pipeline)
1. Lê metadados do PR via API do Azure DevOps.
2. Clona o repositório, faz checkout do **branch alvo** e do **branch do PR**.
3. Descobre os arquivos alterados (`git diff --name-only target...source`).
4. Ignora binários e arquivos grandes, divide textos em *chunks*.
5. Envia cada *chunk* para **Azure OpenAI (chat completions)** com um *prompt* de revisão que exige **JSON estrito**.
6. Consolida *issues* por severidade e gera `report.json`/`report.md`.
7. Publica um **comentário no PR** com o sumário (se o PAT tiver permissão).

## Requisitos
- **Python** 3.10+
- **Git** instalado e autenticado para clonar/fetch do repositório
- **Azure DevOps PAT** (Personal Access Token) com escopos mínimos:
  - **Code (Read)** — para listar PR e metadados
  - **Pull Requests (Read & Write)** — para comentar no PR
- **Azure OpenAI** (recurso ativo, *deployment* de modelo de chat, e chave de acesso)

> Dica: Para evitar prompts interativos de senha na etapa de `git clone/fetch`, configure um **credential helper** do Git, por exemplo:
> - Windows: `git config --global credential.helper manager-core`
> - macOS: `git config --global credential.helper osxkeychain`
> - Linux: `git config --global credential.helper store` (ou libsecret/manager equivalente)

## Configuração (.env)
Crie um arquivo `.env` na raiz do projeto (ou copie de `.env.example`) e preencha:

```
ADO_ORG=org-da-sua-empresa
ADO_PROJECT=Nome do Projeto (pode ter espaço)
ADO_REPO=nome-do-repositorio
ADO_PR_ID=12345
ADO_PAT=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

AZURE_OPENAI_ENDPOINT=https://<seu-recurso>.openai.azure.com
AZURE_OPENAI_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini
AZURE_OPENAI_API_VERSION=2024-02-15-preview
```

**Descrição das variáveis**  
- `ADO_ORG`: slug da organização no DevOps (ex.: `contoso`).  
- `ADO_PROJECT`: nome do projeto (o script faz URL-encode automaticamente).  
- `ADO_REPO`: nome do repositório Git dentro do projeto.  
- `ADO_PR_ID`: ID numérico do Pull Request que será analisado.  
- `ADO_PAT`: PAT com escopos descritos acima.  
- `AZURE_OPENAI_ENDPOINT`: endpoint base do Azure OpenAI (formato `https://<recurso>.openai.azure.com`).  
- `AZURE_OPENAI_KEY`: chave do Azure OpenAI.  
- `AZURE_OPENAI_DEPLOYMENT`: nome do *deployment* do modelo de chat (ex.: `gpt-4o-mini`).  
- `AZURE_OPENAI_API_VERSION`: versão da API (ex.: `2024-02-15-preview`).

> **Segurança**: Nunca *commite* `.env`. Use variáveis de ambiente ou *secret stores* em CI/CD.

## Instalação
Recomendado usar *virtualenv*:
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

python -m pip install --upgrade pip
pip install requests python-dotenv
```

## Execução
1. Configure o `.env` conforme acima.
2. Certifique-se de que o Git tem acesso ao repositório (credential helper/SSO).
3. Rode:
```bash
python main.py
```
Durante a execução você verá logs informativos (endpoint/modelo AOAI, clonagem, contagem de arquivos, etc.). Ao final, os arquivos `report.json` e `report.md` serão criados na raiz do projeto e um comentário será tentado no PR.

## Parâmetros e limites padrão
No código (`main.py`), os seguintes limites podem ser ajustados conforme necessidade:
- `MAX_FILE_BYTES = 300_000` — ignora arquivos de texto maiores que 300 KB
- `MAX_CHARS_PER_CHUNK = 10_000` — tamanho de *chunk* por chamada ao AOAI
- `MAX_FILES = 200` — máximo de arquivos analisados por execução
- Diretórios/arquivos binários são ignorados por heurística de extensão e tentativa de leitura

> Observação: arquivos **removidos** não são analisados (sem conteúdo para revisar).

## Saídas
- **`report.json`**  
  Estatísticas gerais (arquivos, issues por severidade) e lista de issues por arquivo.
- **`report.md`**  
  Sumário legível por humanos, agrupado por arquivo e severidade. Útil para colar em comentários ou enviar por e-mail.

## Erros comuns & Solução
- `401/403/404 em https://dev.azure.com/...`  
  Verifique escopos do PAT, org/projeto/repo/PR corretos e se o usuário do PAT tem acesso.
- `git clone falhou: ...`  
  Valide se a URL montada está correta e se o Git tem credenciais válidas. Configure credential helper.
- `Azure OpenAI erro 401/403/404/429/500`  
  Confira endpoint, chave, *deployment* e `AZURE_OPENAI_API_VERSION`. Em 429, reduza volume ou aumente *rate limits* no recurso.
- `Nenhum arquivo alterado no PR.`  
  Não há diffs entre o branch do PR e o branch de destino.

## Uso em CI (exemplo Azure Pipelines)
```yaml
steps:
  - task: UsePythonVersion@0
    inputs:
      versionSpec: '3.11'
  - script: |
      python -m pip install --upgrade pip
      pip install requests python-dotenv
      python main.py
    env:
      ADO_ORG: $(ADO_ORG)
      ADO_PROJECT: $(ADO_PROJECT)
      ADO_REPO: $(ADO_REPO)
      ADO_PR_ID: $(System.PullRequest.PullRequestId)
      ADO_PAT: $(ADO_PAT)             # armazenar como secret
      AZURE_OPENAI_ENDPOINT: $(AOAI_ENDPOINT)
      AZURE_OPENAI_KEY: $(AOAI_KEY)   # secret
      AZURE_OPENAI_DEPLOYMENT: $(AOAI_DEPLOYMENT)
      AZURE_OPENAI_API_VERSION: '2024-02-15-preview'
```

> Em CI, o agente de build já tem Git instalado. Garanta que o PAT/Service Connection tem permissão de leitura no repositório e de comentar no PR.

## Notas adicionais
- O *prompt* exige **JSON estrito** na resposta do modelo. Se o parsing falhar, é criada uma *issue* de *tooling* orientando reexecutar aquele *chunk*.
- O script usa a API **Chat Completions** do Azure OpenAI.
- O repositório é clonado em `./work_pr_repo`. A limpeza é opcional (não automática).

---

**Autor/Script**: consulte `main.py` na raiz do projeto.
