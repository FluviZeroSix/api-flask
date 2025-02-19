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

# Configurações da API Flask
app = Flask(__name__)

# Configuração da OpenAI
OPENAI_API_KEY = "SUA_OPENAI_API_KEY"
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Configuração do Google Custom Search
GOOGLE_API_KEY = "SUA_GOOGLE_API_KEY"
CSE_ID = "SEU_CSE_ID"

def iniciar_driver():
    """Inicializa o Selenium para acessar sites bloqueados como Instagram e Facebook."""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # Para rodar sem abrir janela
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

def google_search(query, num_results=5):
    """Faz uma busca no Google e retorna os links encontrados."""
    url = f"https://www.googleapis.com/customsearch/v1?q={query}&key={GOOGLE_API_KEY}&cx={CSE_ID}&num={num_results}"
    response = requests.get(url)

    if response.status_code == 200:
        results = response.json()
        links = [item['link'] for item in results.get("items", [])]
        return links
    else:
        return []

def scrape_website(url, driver):
    """Acessa o site e retorna seu conteúdo para análise."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        if url.endswith(".pdf"):
            return None, None

        if "instagram.com" in url:
            driver.get(url)
            time.sleep(5)
            try:
                username = driver.current_url.split("instagram.com/")[-1].split("/")[0]
                return None, f"@{username}"
            except:
                return None, None

        driver.get(url)
        time.sleep(10)
        return driver.page_source, None

    except requests.exceptions.RequestException:
        return None, None

def extract_data_with_gpt(site_url, html_text):
    """Usa o ChatGPT para extrair informações úteis do HTML."""
    if html_text is None:
        return {"nome_estabelecimento": "Não encontrado", "emails": [], "telefones": [], "nomes_pessoas": []}

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
        return json.loads(refined_data)

    except json.JSONDecodeError:
        return None
    except Exception:
        return None

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
    app.run(host='0.0.0.0', port=10000)
