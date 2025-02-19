from flask import Flask, request, jsonify
import requests
import re
import pandas as pd
import json
import openai
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
import time

# 🚨 NÃO COMPARTILHE SUA API_KEY 🚨
GOOGLE_API_KEY = "AIzaSyAoGD39ieZeCHqM73ltYNbBms-NQUQo5xU"
CSE_ID = "a6c5683482ef64641"
OPENAI_API_KEY = "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"

# Configurar OpenAI
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Criar a API Flask
app = Flask(__name__)

def iniciar_driver():
    """Inicializa o Selenium para acessar sites bloqueados como Instagram e Facebook."""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # Executar em segundo plano
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

        # Se for PDF, ignorar
        if url.endswith(".pdf"):
            return None, None

        # Para Instagram, extrair o @ do usuário
        if "instagram.com" in url:
            driver.get(url)
            time.sleep(5)
            try:
                username = driver.current_url.split("instagram.com/")[-1].split("/")[0]
                return None, f"@{username}"
            except:
                return None, None

        # Para outros sites, acessar com Selenium
        driver.get(url)
        time.sleep(10)
        return driver.page_source, None

    except requests.exceptions.RequestException:
        return None, None

def extract_data_with_gpt(site_url, html_text):
    """Usa o ChatGPT para extrair informações relevantes do HTML."""
    
    # Se for Instagram e já tivermos o @, não precisamos do ChatGPT
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

    # **Salvar em planilha Excel**
    if dados_coletados:
        df = pd.DataFrame(dados_coletados)
        df.to_excel("dados_scraper.xlsx", index=False)
        print("\n✅ Dados salvos no arquivo 'dados_scraper.xlsx'")

    return jsonify(dados_coletados)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
