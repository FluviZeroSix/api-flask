from flask import Flask, request, jsonify
import requests
import json
import openai
from bs4 import BeautifulSoup
import pandas as pd
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from flask_cors import CORS

# Configuração da API Flask
app = Flask(__name__)
CORS(app)  # Habilita CORS para permitir chamadas do navegador

# Configuração da OpenAI
OPENAI_API_KEY = "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"
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Configuração do Google Custom Search
GOOGLE_API_KEY = "AIzaSyAoGD39ieZeCHqM73ltYNbBms-NQUQo5xU"
CSE_ID = "a6c5683482ef64641"

def iniciar_driver():
    """Inicializa o Selenium com opções otimizadas para evitar bloqueios."""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # Para rodar sem abrir janela
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")  # Reduz detecção como bot

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.set_page_load_timeout(10)  # Define um timeout de 10 segundos
    return driver

def google_search(query, num_results=5):
    """Faz uma busca no Google e retorna os links encontrados."""
    url = f"https://www.googleapis.com/customsearch/v1?q={query}&key={GOOGLE_API_KEY}&cx={CSE_ID}&num={num_results}"
    response = requests.get(url)

    if response.status_code == 200:
        results = response.json()
        links = [item['link'] for item in results.get("items", [])]
        print("🔎 Links encontrados:", links)  # Log para verificar os links
        return links
    else:
        print("❌ Erro ao buscar no Google:", response.status_code, response.text)
        return []

def scrape_website(url, driver):
    """Acessa o site e retorna seu conteúdo para análise."""
    try:
        print(f"🔎 Tentando acessar: {url}")  # Log para ver quais sites estão sendo acessados
        driver.get(url)
        time.sleep(5)
        html_text = driver.page_source
        print(f"✅ Página carregada com sucesso: {url}")
        return html_text, None
    except Exception as e:
        print(f"❌ Erro ao acessar {url}, ignorando... Erro: {e}")
        return None, None  # Ignora sites com erro

def extract_data_with_gpt(site_url, html_text):
    """Usa o ChatGPT para extrair informações úteis do HTML."""
    if html_text is None:
        print(f"Aviso: Nenhum HTML extraído de {site_url}")
        return {"nome_estabelecimento": "Não encontrado", "emails": [], "telefones": [], "nomes_pessoas": []}

    print(f"📄 HTML recebido de {site_url}: {html_text[:500]}")  # Mostra os primeiros 500 caracteres do HTML

    prompt = f"""
    Extraia e organize as seguintes informações:

    - 📍 Nome do Estabelecimento
    - 📧 E-mails de Contato
    - 📞 Telefones de Contato
    - 👤 Nomes de Pessoas Relacionadas ao Comércio

    Responda **somente com JSON válido**, no seguinte formato:

    {{
        "nome_estabelecimento": "Nome do Local",
        "emails": ["email1@email.com", "email2@email.com"],
        "telefones": ["+55 11 99999-9999", "+55 11 88888-8888"],
        "nomes_pessoas": ["Nome Pessoa 1", "Nome Pessoa 2"]
    }}

    Conteúdo extraído do site {site_url}:
    {html_text[:3000]}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "system", "content": "Você é um assistente que extrai informações úteis de páginas da web e sempre responde em JSON válido."},
                      {"role": "user", "content": prompt}]
        )

        refined_data = response.choices[0].message.content
        print(f"🤖 Resposta do ChatGPT para {site_url}: {refined_data}")  # Exibe a resposta do ChatGPT
        return json.loads(refined_data)

    except json.JSONDecodeError:
        print(f"❌ Erro ao converter resposta do ChatGPT em JSON para {site_url}")
        return None
    except Exception as e:
        print(f"❌ Erro no ChatGPT: {e}")
        return None


@app.route('/', methods=['GET'])
def home():
    """Página inicial da API"""
    return jsonify({"mensagem": "API está rodando! Use o endpoint /scrape para testar."})

@app.route('/scrape', methods=['GET'])
def scrape_api():
    """Endpoint da API para receber consultas e retornar os dados extraídos."""
    consulta = request.args.get('query', '')

    if not consulta:
        return jsonify({"erro": "Nenhuma consulta foi fornecida"}), 400

    driver = iniciar_driver()
    links = google_search(consulta, num_results=5)
    
    dados_coletados = []
    for link in links:
        html_text, instagram_handle = scrape_website(link, driver)
        
        # Se não conseguir extrair dados, pula o site
        if html_text is None:
            continue

        refined_data = extract_data_with_gpt(link, html_text)
        
        if refined_data:
            dados_coletados.append({
                "Site": link,
                "Nome do Estabelecimento": refined_data.get("nome_estabelecimento", "Não encontrado"),
                "Instagram": instagram_handle if instagram_handle else "",
                "E-mails": ", ".join(refined_data.get("emails", [])),
                "Telefones": ", ".join(refined_data.get("telefones", [])),
                "Pessoas Relacionadas": ", ".join(refined_data.get("nomes_pessoas", []))
            })

    driver.quit()
    return jsonify(dados_coletados)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
