"""
Ultima cartada: testa endpoint alternativo /lawsuits/{id}/movements.

Caminho original no codigo (que eu havia corrigido para /movements/{id}).
Algumas APIs expoem rotas paralelas com comportamentos diferentes —
vale 1 chamada para confirmar.

Compara com base ja conhecida:
  - /movements/13006320 retornou 25 itens (truncado).
"""

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / '.env')

TOKEN = os.getenv('ADVBOX_API_TOKEN')
URL_BASE = (os.getenv('ADVBOX_API_URL') or '').rstrip('/')
USER_AGENT = 'L-Batista-Dashboards/1.0 (+contato: gestaobatistaadvogados@gmail.com)'

LAWSUIT_ID = 13006320

# Hash do 1o item retornado por /movements/{id} sem params (do teste anterior).
HASH_BASE_1O = 'h=4025365896'
QTD_BASE = 25


def assinatura(item):
    if not isinstance(item, dict):
        return f'tipo:{type(item).__name__}'
    chave = (item.get('date'), item.get('header'), item.get('title'))
    return f'h={abs(hash(chave)) % 10**10:010d}'


def main():
    if not TOKEN or not URL_BASE:
        print('ERRO: .env incompleto.')
        return 1

    endpoint = f'lawsuits/{LAWSUIT_ID}/movements'
    url = f'{URL_BASE}/{endpoint}'
    headers = {
        'Authorization': f'Bearer {TOKEN}',
        'Accept': 'application/json',
        'User-Agent': USER_AGENT,
    }

    print(f'Cobaia: lawsuit_id {LAWSUIT_ID}')
    print(f'Base conhecida: /movements/{LAWSUIT_ID} -> 25 itens, 1o hash={HASH_BASE_1O}')
    print()
    print(f'> GET /{endpoint}')

    try:
        resp = requests.get(url, headers=headers, timeout=30)
    except requests.RequestException as e:
        print(f'  EXC: {type(e).__name__}: {e}')
        return 1

    print(f'  Status : {resp.status_code}')
    if resp.status_code == 404:
        print('  Endpoint NAO existe (404). Conclusao: nao e rota valida.')
        return 0
    if resp.status_code != 200:
        snippet = (resp.text or '').strip()[:200]
        print(f'  Body   : {snippet!r}')
        return 1

    if not resp.text.strip():
        print('  Body vazio (similar ao 204 que ja vimos noutro lawsuit).')
        return 0

    try:
        d = resp.json()
    except ValueError as e:
        print(f'  JSON nao parseou: {e}')
        return 1

    if isinstance(d, dict) and isinstance(d.get('data'), list):
        itens = d['data']
        envelope = sorted(d.keys())
    elif isinstance(d, list):
        itens = d
        envelope = ['(resposta = list direto)']
    else:
        print(f'  Forma inesperada: {type(d).__name__}')
        return 1

    print(f'  Itens   : {len(itens)}')
    print(f'  Envelope: {envelope}')
    if itens:
        sig0 = assinatura(itens[0])
        print(f'  1o hash : {sig0}')
        if sig0 != HASH_BASE_1O:
            print('  -> 1o item DIFERENTE do retornado por /movements/{id}!')
        else:
            print('  -> 1o item IGUAL ao de /movements/{id}.')

    print()
    print('=' * 64)
    print('VEREDITO')
    print('=' * 64)
    if len(itens) > QTD_BASE:
        print(f'  /lawsuits/{{id}}/movements retornou MAIS itens ({len(itens)} > {QTD_BASE}).')
        print('  Possivel endpoint sem (ou com maior) limite!')
    elif len(itens) == QTD_BASE:
        print('  Mesmo numero de itens (25). Provavel mesmo limite duro.')
    else:
        print(f'  Retornou MENOS itens ({len(itens)} < 25). Endpoint diferente, mas pior.')

    return 0


if __name__ == '__main__':
    sys.exit(main())
