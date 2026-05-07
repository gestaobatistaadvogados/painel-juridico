"""
Diagnostico cru da API ADVBox.

Faz uma requisicao GET direta a /settings (sem usar AdvboxClient)
e imprime status, headers e corpo da resposta — para entender
exatamente o que o servidor esta retornando.

NUNCA imprime o token.
"""

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')

token = os.getenv('ADVBOX_API_TOKEN')
url_base = os.getenv('ADVBOX_API_URL')

if not token or token == 'COLE_O_TOKEN_AQUI':
    print('ERRO: ADVBOX_API_TOKEN ausente ou ainda no placeholder no .env.')
    sys.exit(1)
if not url_base:
    print('ERRO: ADVBOX_API_URL ausente no .env.')
    sys.exit(1)

url = f"{url_base.rstrip('/')}/settings"
USER_AGENT = 'L-Batista-Dashboards/1.0 (+contato: gestaobatistaadvogados@gmail.com)'

headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'User-Agent': USER_AGENT,
}

print(f'GET {url}')
print(f'User-Agent: {USER_AGENT}')
print('Headers enviados: Authorization=Bearer <oculto>, Content-Type=application/json, Accept=application/json, User-Agent=<acima>')
print('-' * 70)

try:
    resp = requests.get(url, headers=headers, timeout=30)
except requests.RequestException as e:
    print(f'FALHA DE REDE: {type(e).__name__}: {e}')
    sys.exit(1)

print(f'HTTP Status: {resp.status_code} {resp.reason}')
print()
print('Headers da resposta:')
for chave, valor in resp.headers.items():
    print(f'  {chave}: {valor}')

print()
print('Corpo da resposta (response.text):')
print('-' * 70)
print(resp.text)
print('-' * 70)
