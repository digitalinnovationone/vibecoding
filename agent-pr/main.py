
import os, sys, re, json, base64, subprocess, shlex, textwrap, hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import requests
from dotenv import load_dotenv

load_dotenv()

# ====== CONFIG ======
ORG = os.getenv("ADO_ORG", "")
PROJECT = os.getenv("ADO_PROJECT", "")
REPO_NAME = os.getenv("ADO_REPO", "")
PR_ID = os.getenv("ADO_PR_ID", "")
ADO_PAT = os.getenv("ADO_PAT", "")

AOAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AOAI_KEY = os.getenv("AZURE_OPENAI_KEY", "")
AOAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
AOAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
print(f"[info] Usando AOAI endpoint: {AOAI_ENDPOINT}, deployment: {AOAI_DEPLOYMENT}")
# Limites de revisão
MAX_FILE_BYTES = 300_000       
MAX_CHARS_PER_CHUNK = 10_000   
MAX_FILES = 200                

WORKDIR = Path("./work_pr_repo")
REPORT_JSON = Path("report.json")
REPORT_MD = Path("report.md")


def die(msg: str):
    print(f"[ERRO] {msg}", file=sys.stderr)
    sys.exit(1)

def auth_header_pat(pat: str) -> Dict[str, str]:
    token = base64.b64encode(f":{pat}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}

def ado_get(url: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
    h = auth_header_pat(ADO_PAT)
    r = requests.get(url, headers=h, params=params, timeout=60)
    if r.status_code in (401,403,404):
        die(f"{r.status_code} em {url}\n{r.text[:400]}")
    r.raise_for_status()
    return r.json()

def run(cmd: str, cwd: Optional[Path] = None) -> Tuple[int,str,str]:
    p = subprocess.Popen(shlex.split(cmd), cwd=str(cwd) if cwd else None,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = p.communicate()
    return p.returncode, out, err

def is_text_file(path: Path) -> bool:
    # heurística simples: ignora binários por extensão + tentativa de decodificação
    bin_ext = {".png",".jpg",".jpeg",".gif",".pdf",".zip",".exe",".dll",".so",".dylib",
               ".mp4",".mov",".avi",".jar",".7z",".gz",".tar",".tgz",".ico",".ttf",".otf",
               ".xlsx",".xls",".doc",".docx",".ppt",".pptx"}
    if path.suffix.lower() in bin_ext:
        return False
    try:
        with path.open("r", encoding="utf-8") as f:
            f.read(2048)
        return True
    except Exception:
        return False

def chunk_text(s: str, max_chars: int) -> List[str]:
    chunks = []
    start = 0
    n = len(s)
    while start < n:
        end = min(start + max_chars, n)
        chunks.append(s[start:end])
        start = end
    return chunks

# ====== 1) Descobrir source/target do PR ======
def get_pr_info() -> Dict[str, Any]:
    url = f"https://dev.azure.com/{ORG}/{requests.utils.quote(PROJECT, safe='')}/_apis/git/repositories/{REPO_NAME}/pullRequests/{PR_ID}"
    data = ado_get(url, params={"api-version":"7.1-preview.1"})
    return data

# ====== 2) Clonar e checar branch ======
def ensure_repo(url_https: str, branch: str, target_branch: str) -> None:
    WORKDIR.mkdir(parents=True, exist_ok=True)
    repo_dir = WORKDIR
    if not (repo_dir / ".git").exists():
        print("[git] clonando repositório...")
        code, out, err = run(f"git clone {shlex.quote(url_https)} .", cwd=repo_dir)
        if code != 0:
            die(f"git clone falhou: {err}")
    # fetch tudo que precisa
    run("git fetch --all --prune", cwd=repo_dir)
    # garantir branches remotos
    run(f"git checkout {shlex.quote(target_branch)}", cwd=repo_dir)
    run(f"git pull origin {shlex.quote(target_branch)}", cwd=repo_dir)
    # criar/atualizar branch source
    run(f"git fetch origin {shlex.quote(branch)}:{shlex.quote(branch)}", cwd=repo_dir)
    code, out, err = run(f"git checkout {shlex.quote(branch)}", cwd=repo_dir)
    if code != 0:
        die(f"checkout branch source falhou: {err}")
    run(f"git pull origin {shlex.quote(branch)}", cwd=repo_dir)

# ====== 3) Arquivos alterados no PR ======
def list_changed_files(source_branch: str, target_branch: str) -> List[str]:
    # compara target..source (commits presentes em source e não em target)
    code, out, err = run(f"git diff --name-only {shlex.quote(target_branch)}...{shlex.quote(source_branch)}", cwd=WORKDIR)
    if code != 0:
        die(f"git diff falhou: {err}")
    files = [line.strip() for line in out.splitlines() if line.strip()]
    return files

# ====== 4) Azure OpenAI ======
def aoai_chat(messages: List[Dict[str,str]], temperature: float=0.2) -> str:
    url = f"{AOAI_ENDPOINT}/openai/deployments/{AOAI_DEPLOYMENT}/chat/completions?api-version={AOAI_API_VERSION}"
    headers = {
        "api-key": AOAI_KEY,
        "Content-Type": "application/json"
    }
    body = {
        "messages": messages,
        "temperature": temperature
    }
    r = requests.post(url, headers=headers, json=body, timeout=120)
    if r.status_code in (401,403,404,429,500):
        raise RuntimeError(f"Azure OpenAI erro {r.status_code}: {r.text[:400]}")
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"]

def build_review_prompt(repo_name: str, file_path: str, code_chunk: str) -> List[Dict[str,str]]:
    sys_prompt = textwrap.dedent(f"""
    Você é um revisor de código sênior chamado Henrique Eduardo Souza. Revise diffs ou arquivos de código com foco em:
      - Corrija e casos extremos
      - Segurança (segredos, injeções, traversal de caminho, desserialização insegura, SSRF, SCARF, XSS, CSRF)
      - Desempenho e escalabilidade
      - Confiabilidade (exceções, vazamento de recursos)
      - Manutenibilidade (nomes, estrutura, testes)
      - Boas práticas de Cloud/Azure DevOps, quando relevante
      Return a STRICT JSON with:
    {{
      "file": "<string>",
      "issues": [
        {{
          "title": "<short>",
          "severity": "critical|high|medium|low",
          "line": <int|null>,
          "description": "<O que está errado>",
          "recommendation": "<Como corrigir>",
          "tags": ["security"|"performance"|"readability"|...]
        }}
      ]
    }}

    Se não houver problemas: return {{"file":"...", "issues":[]}}.
    Nunca inclua code fences em Markdown. Não escreva texto fora do JSON.
    """).strip()

    user_prompt = f"Repository: {repo_name}\nFile: {file_path}\n\nCODE:\n{code_chunk}"
    return [{"role":"system","content":sys_prompt},{"role":"user","content":user_prompt}]

# ====== 5) Postar comentário no PR (opcional) ======
def post_pr_comment(summary_md: str) -> None:
    url = f"https://dev.azure.com/{ORG}/{requests.utils.quote(PROJECT, safe='')}/_apis/git/repositories/{REPO_NAME}/pullRequests/{PR_ID}/threads?api-version=7.1-preview.1"
    payload = {
        "comments": [{
            "parentCommentId": 0,
            "content": summary_md,
            "commentType": 1
        }],
        "status": 1
    }
    r = requests.post(url, headers=auth_header_pat(ADO_PAT) | {"Content-Type":"application/json"},
                      json=payload, timeout=60)
    if r.status_code not in (200,201):
        print(f"[aviso] não consegui comentar no PR ({r.status_code}): {r.text[:300]}")

# ====== MAIN ======
def main():
    if not all([ORG, PROJECT, REPO_NAME, PR_ID, ADO_PAT, AOAI_ENDPOINT, AOAI_KEY, AOAI_DEPLOYMENT]):
        die("Configure .env com ADO_* e AZURE_OPENAI_* (veja instruções no topo).")

    # 1) Info do PR
    pr = get_pr_info()
    source_ref = pr["sourceRefName"]            # ex: refs/heads/feature/x
    target_ref = pr["targetRefName"]            # ex: refs/heads/main
    source_branch = source_ref.replace("refs/heads/","")
    target_branch = target_ref.replace("refs/heads/","")

    # 2) Montar URL https autenticada (PAT no user/password)
    #    Formato: https://{ORG}@dev.azure.com/{ORG}/{PROJECT}/_git/{REPO}
    proj_enc = requests.utils.quote(PROJECT, safe="")
    repo_url = f"https://{ORG}@dev.azure.com/{ORG}/{proj_enc}/_git/{REPO_NAME}"
    # git vai pedir senha; passaremos via GIT_ASKPASS? Simples: vai interativo. Alternativa: store.
    # Para evitar prompt, use credential helper do git previamente. Aqui assumimos cred cache configurado.

    ensure_repo(repo_url, source_branch, target_branch)

    # 3) Arquivos alterados
    changed = list_changed_files(source_branch, target_branch)
    if not changed:
        print("Nenhum arquivo alterado no PR.")
        REPORT_JSON.write_text(json.dumps({"summary":"no changes","files":[]}, ensure_ascii=False, indent=2), encoding="utf-8")
        REPORT_MD.write_text("# Code Quality Report\n\nNenhuma alteração detectada.\n", encoding="utf-8")
        return

    if len(changed) > MAX_FILES:
        print(f"[aviso] PR com {len(changed)} arquivos; analisarei apenas os primeiros {MAX_FILES}.")
        changed = changed[:MAX_FILES]

    # 4) Rodar revisão via AOAI por arquivo/chunk
    results: List[Dict[str, Any]] = []
    repo_root = WORKDIR
    for rel in changed:
        path = repo_root / rel
        if not path.exists():
            # arquivo removido; podemos ignorar ou buscar diff. Aqui, ignoramos conteúdos deletados.
            continue
        if not is_text_file(path):
            continue
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            print(f"[skip] {rel} ({size} bytes) > MAX_FILE_BYTES")
            continue
        try:
            code_text = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(f"[skip] {rel}: {e}")
            continue

        chunks = chunk_text(code_text, MAX_CHARS_PER_CHUNK)
        all_issues = []
        for idx, ch in enumerate(chunks, 1):
            messages = build_review_prompt(REPO_NAME, rel, ch)
            try:
                content = aoai_chat(messages)
                # Deve ser JSON estrito
                obj = json.loads(content)
                file_resp = obj.get("file") or rel
                issues = obj.get("issues", [])
                # anexa
                all_issues.extend(issues)
            except Exception as e:
                # fallback: se vier texto, cria uma issue agregada
                all_issues.append({
                    "title": f"AI Review (chunk {idx}) parse error",
                    "severity": "low",
                    "line": None,
                    "description": f"Falha ao interpretar resposta como JSON: {e}",
                    "recommendation": "Reexecutar revisão para este chunk.",
                    "tags": ["tooling"]
                })

        results.append({"file": rel, "issues": all_issues})

    # 5) Sumário e severidades
    sev_order = {"critical":4,"high":3,"medium":2,"low":1}
    total_issues = sum(len(f["issues"]) for f in results)
    by_sev = {"critical":0,"high":0,"medium":0,"low":0}
    for f in results:
        for i in f["issues"]:
            s = (i.get("severity") or "low").lower()
            if s not in by_sev: s="low"
            by_sev[s]+=1

    # 6) Gravar relatórios
    REPORT_JSON.write_text(json.dumps({
        "org": ORG, "project": PROJECT, "repo": REPO_NAME, "prId": PR_ID,
        "sourceBranch": source_branch, "targetBranch": target_branch,
        "totals": {"files": len(results), "issues": total_issues, **by_sev},
        "results": results
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # Markdown
    md = [ "# Code Quality Report",
           f"- **Org/Proj/Repo**: `{ORG}/{PROJECT}/{REPO_NAME}`",
           f"- **PR**: `{PR_ID}`",
           f"- **Branches**: `{source_branch}` → `{target_branch}`",
           f"- **Arquivos analisados**: {len(results)}",
           f"- **Issues**: {total_issues} (crit: {by_sev['critical']}, high: {by_sev['high']}, med: {by_sev['medium']}, low: {by_sev['low']})",
           "\n---\n" ]

    for f in results:
        if not f["issues"]:
            continue
        md.append(f"## `{f['file']}`")
        for i in sorted(f["issues"], key=lambda x: sev_order.get((x.get('severity') or 'low').lower(),1), reverse=True):
            md.append(f"- **[{i.get('severity','low').upper()}]** {i.get('title','Issue')}"
                      + (f" (linha {i['line']})" if i.get("line") else ""))
            md.append(f"  - *Descrição*: {i.get('description','')}")
            md.append(f"  - *Recomendação*: {i.get('recommendation','')}")
            tags = i.get("tags") or []
            if tags:
                md.append(f"  - *Tags*: {', '.join(tags)}")
        md.append("")

    if total_issues == 0:
        md.append("Nenhuma issue encontrada nos arquivos analisados.")

    REPORT_MD.write_text("\n".join(md), encoding="utf-8")
    print(f"[ok] Gerado {REPORT_JSON} e {REPORT_MD}")
    # 7) Comentar no PR
    # summary = textwrap.dedent(f"""
    # **Code Quality Report — PR #{PR_ID}**
    # - Arquivos: {len(results)}
    # - Issues: {total_issues} (critical: {by_sev['critical']}, high: {by_sev['high']}, medium: {by_sev['medium']}, low: {by_sev['low']})
    # > [Relatório Completo]({md})
    # """).strip()
    with REPORT_MD.open("r", encoding="utf-8") as f:
      summary = f.read()
  
    try:
        post_pr_comment(summary)
        print("[ok] Comentário postado no PR.")
    except Exception as e:
        print(f"[aviso] não foi possível comentar no PR: {e}")

if __name__ == "__main__":
    main()
