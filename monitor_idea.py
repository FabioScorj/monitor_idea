import os
import json
import hashlib
import requests
import time
from datetime import datetime, timezone, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ──────────────────────────────────────────────
# IDEAs monitorados
# ──────────────────────────────────────────────
IDEAS = [
    {
        "nome": "Leandro Sansom",
        "url": "https://sicop.sistemas.mpba.mp.br/Modulos/Consulta/Processo.aspx?L0QifJI5OZahgUIIKOI87Z/rcsjolQ3gnC0GZFPwmKuFX9DoeHylJQ==#tabela-resultado"
    },
    {
        "nome": "Emporio II",
        "url": "https://sicop.sistemas.mpba.mp.br/Modulos/Consulta/Processo.aspx?L0QifJI5OZay/N8MYuNlm7GOhf3NBvJxPHjDdi6yVUmSr7RNnASmfg=="
    },
    {
        "nome": "Emporio I",
        "url": "https://sicop.sistemas.mpba.mp.br/Modulos/Consulta/Processo.aspx?L0QifJI5OZay/N8MYuNlm8V69edbtqAzNFmRrplM0oJzQgYajEecEQ=="
    },
    {
        "nome": "Jô Paz",
        "url": "https://sicop.sistemas.mpba.mp.br/Modulos/Consulta/Processo.aspx?L0QifJI5OZay/N8MYuNlm1IuhGVCUinkoH9MjYinD1ii+n1KLCo4Pw=="
    },
    {
        "nome": "Diarias II",
        "url": "https://sicop.sistemas.mpba.mp.br/Modulos/Consulta/Processo.aspx?L0QifJI5OZahgUIIKOI87ZX4yW5AKi6TXzrHANkpI/0hssBw3ax1CA=="
    },
    {
        "nome": "Maurilio",
        "url": "https://sicop.sistemas.mpba.mp.br/Modulos/Consulta/Processo.aspx?L0QifJI5OZay/N8MYuNlmy+RkXYEJLFE1fVii7QiX1pP6ennsdbx4Q=="
    },
    {
        "nome": "Acompanhamento TAC",
        "url": "https://sicop.sistemas.mpba.mp.br/Modulos/Consulta/Processo.aspx?L0QifJI5OZahgUIIKOI87apHwKjrDMZZOeguNj5nYgCkBhW1SSUDPA==#tabela-resultado"
    },
]

# ──────────────────────────────────────────────
# Configs
# ──────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID        = os.environ.get("CHAT_ID", "")
GH_TOKEN       = os.environ.get("GH_TOKEN", "")
REPO           = os.environ.get("GITHUB_REPOSITORY", "")  # ex: FabioScorj/monitor_idea

STATE_FILE  = "estado.json"
STATUS_FILE = "docs/status.json"   # lido pelo GitHub Pages

BRT = timezone(timedelta(hours=-3))

# ──────────────────────────────────────────────
# Selenium headless
# ──────────────────────────────────────────────
def get_driver():
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=opts)

def fetch_content(driver, url):
    """Carrega a página e retorna o texto relevante (tabela de movimentações)."""
    driver.get(url)
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(3)  # aguarda JS renderizar
    except Exception:
        pass
    # Tenta pegar só a tabela de resultados; se não achar, pega o body todo
    try:
        tabela = driver.find_element(By.ID, "tabela-resultado")
        return tabela.get_attribute("outerHTML")
    except Exception:
        pass
    try:
        content = driver.find_element(By.TAG_NAME, "main")
        return content.get_attribute("outerHTML")
    except Exception:
        pass
    return driver.find_element(By.TAG_NAME, "body").get_attribute("outerHTML")

def make_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]

# ──────────────────────────────────────────────
# Estado persistido no repo (estado.json)
# ──────────────────────────────────────────────
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

# ──────────────────────────────────────────────
# Status para o dashboard (docs/status.json)
# ──────────────────────────────────────────────
def save_status(results):
    os.makedirs("docs", exist_ok=True)
    agora = datetime.now(BRT).strftime("%d/%m/%Y %H:%M")
    payload = {
        "ultima_verificacao": agora,
        "ideas": results
    }
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

# ──────────────────────────────────────────────
# Telegram
# ──────────────────────────────────────────────
def send_telegram(msg):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("[TELEGRAM] Token/Chat não configurados, pulando.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": msg,
            "parse_mode": "HTML"
        }, timeout=10)
        print(f"[TELEGRAM] Status: {r.status_code}")
    except Exception as e:
        print(f"[TELEGRAM] Erro: {e}")

# ──────────────────────────────────────────────
# Git commit via API do GitHub
# ──────────────────────────────────────────────
def git_commit_files():
    """Faz commit de estado.json e docs/status.json via GitHub API."""
    if not GH_TOKEN or not REPO:
        print("[GIT] GH_TOKEN ou REPO não configurados.")
        return

    import base64
    headers = {
        "Authorization": f"token {GH_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    base_url = f"https://api.github.com/repos/{REPO}/contents"
    agora = datetime.now(BRT).strftime("%d/%m/%Y %H:%M BRT")

    for filepath in [STATE_FILE, STATUS_FILE]:
        if not os.path.exists(filepath):
            continue
        with open(filepath, "rb") as f:
            content_b64 = base64.b64encode(f.read()).decode()

        # Pega SHA atual do arquivo (necessário para update)
        r = requests.get(f"{base_url}/{filepath}", headers=headers)
        sha = r.json().get("sha") if r.status_code == 200 else None

        body = {
            "message": f"monitor: atualiza {filepath} [{agora}]",
            "content": content_b64,
        }
        if sha:
            body["sha"] = sha

        r2 = requests.put(f"{base_url}/{filepath}", headers=headers, json=body)
        print(f"[GIT] {filepath} → {r2.status_code}")

# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  Monitor IDEA · SICOP MP-BA")
    print(f"  {datetime.now(BRT).strftime('%d/%m/%Y %H:%M BRT')}")
    print("=" * 55)

    state   = load_state()
    driver  = get_driver()
    results = []
    alertas = []

    for idea in IDEAS:
        nome = idea["nome"]
        url  = idea["url"]
        print(f"\n→ Verificando: {nome}")

        try:
            html  = fetch_content(driver, url)
            novo_hash = make_hash(html)
            prev  = state.get(nome, {})
            prev_hash = prev.get("hash")

            agora_str = datetime.now(BRT).strftime("%d/%m/%Y %H:%M")

            if prev_hash is None:
                status = "baseline"
                print(f"   📌 Baseline registrado: {novo_hash}")
            elif prev_hash != novo_hash:
                status = "atualizado"
                alertas.append(nome)
                print(f"   🔔 ATUALIZAÇÃO DETECTADA! {prev_hash} → {novo_hash}")
            else:
                status = "sem_mudanca"
                print(f"   ✓  Sem mudança ({novo_hash})")

            state[nome] = {
                "hash": novo_hash,
                "ultima_verificacao": agora_str,
                "status": status,
                "url": url
            }
            results.append({
                "nome": nome,
                "status": status,
                "hash": novo_hash,
                "ultima_verificacao": agora_str,
                "url": url,
                "erro": None
            })

        except Exception as e:
            err_msg = str(e)[:120]
            agora_str = datetime.now(BRT).strftime("%d/%m/%Y %H:%M")
            print(f"   ✗  Erro: {err_msg}")
            state[nome] = {**state.get(nome, {}), "status": "erro", "ultima_verificacao": agora_str}
            results.append({
                "nome": nome,
                "status": "erro",
                "hash": state.get(nome, {}).get("hash"),
                "ultima_verificacao": agora_str,
                "url": url,
                "erro": err_msg
            })

    driver.quit()

    # Salva arquivos
    save_state(state)
    save_status(results)

    # Telegram: só notifica se houver atualizações
    if alertas:
        linhas = "\n".join(f"  • {a}" for a in alertas)
        msg = (
            f"🔔 <b>Monitor IDEA · SICOP MP-BA</b>\n\n"
            f"Atualização detectada em {len(alertas)} IDEA(s):\n\n"
            f"{linhas}\n\n"
            f"🕐 {datetime.now(BRT).strftime('%d/%m/%Y %H:%M')} BRT"
        )
        send_telegram(msg)
    else:
        print("\n[OK] Nenhuma atualização detectada.")

    # Commit dos arquivos de estado
    git_commit_files()

    print("\n" + "=" * 55)
    print("  Concluído.")
    print("=" * 55)

if __name__ == "__main__":
    main()
