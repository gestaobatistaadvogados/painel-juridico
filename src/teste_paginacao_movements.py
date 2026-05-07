"""
Investiga paginacao oculta em /movements/{id}.

Cobaia: lawsuit_id 13006320 (retornou exatamente 25 itens na execucao do
gerador — candidato a truncamento silencioso).

Para cada parametro testado, registra:
  - URL chamada (sem token; token vai em header)
  - HTTP status
  - Quantidade de itens em data
  - Hash do 1o item (para detectar se a chamada paginou de verdade —
    se o hash mudar em relacao a base, e sinal de paginacao funcional)

NAO imprime conteudo dos movimentos.
"""

import os
import sys
import time
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
INTERVALO = 2.0  # respeitar 30 GET/min

# Parametros a testar (rotulo, dict de params).
TESTES = [
    ('base (sem params)',          None),
    ('?limit=100',                 {'limit': 100}),
    ('?per_page=100',              {'per_page': 100}),
    ('?page=2',                    {'page': 2}),
    ('?offset=25',                 {'offset': 25}),
    ('?limit=100&offset=0',        {'limit': 100, 'offset': 0}),
]

# Fallback caso os 5 primeiros nao paginem.
TESTES_FALLBACK = [
    ('?cursor=25',                 {'cursor': 25}),
    ('?after=25',                  {'after': 25}),
]


def assinatura(item):
    """Identifica unicamente um movement sem expor seu texto."""
    if not isinstance(item, dict):
        return f'tipo:{type(item).__name__}'
    chave = (item.get('date'), item.get('header'), item.get('title'))
    return f'h={abs(hash(chave)) % 10**10:010d}'


def chamar(rotulo, params):
    url = f'{URL_BASE}/movements/{LAWSUIT_ID}'
    headers = {
        'Authorization': f'Bearer {TOKEN}',
        'Accept': 'application/json',
        'User-Agent': USER_AGENT,
    }
    print(f'  > {rotulo}')
    print(f'    URL    : /movements/{LAWSUIT_ID} | params={params}')
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
    except requests.RequestException as e:
        print(f'    EXC    : {type(e).__name__}: {e}')
        return None

    print(f'    Status : {resp.status_code}')
    if resp.status_code != 200:
        snippet = (resp.text or '').strip()[:120]
        print(f'    Body   : {snippet!r}')
        return None

    try:
        d = resp.json()
    except ValueError as e:
        print(f'    JSON   : nao parseou ({e})')
        return None

    if isinstance(d, dict) and isinstance(d.get('data'), list):
        itens = d['data']
        chaves_envelope = sorted(d.keys())
    elif isinstance(d, list):
        itens = d
        chaves_envelope = ['(resposta = list direto)']
    else:
        print(f'    Forma  : inesperada ({type(d).__name__})')
        return None

    print(f'    Itens  : {len(itens)}')
    print(f'    Envelope: {chaves_envelope}')
    if itens:
        print(f'    1o hash: {assinatura(itens[0])}')
    if len(itens) >= 2:
        print(f'    2o hash: {assinatura(itens[1])}')
    return itens


def main():
    if not TOKEN or not URL_BASE:
        print('ERRO: ADVBOX_API_TOKEN ou ADVBOX_API_URL ausente em .env')
        return 1

    print(f'Cobaia: lawsuit_id {LAWSUIT_ID} (retornou 25 na execucao do gerador)')
    print(f'Intervalo entre chamadas: {INTERVALO}s (rate limit 30/min)')
    print()

    resultados = {}
    for i, (rotulo, params) in enumerate(TESTES):
        if i > 0:
            time.sleep(INTERVALO)
        resultados[rotulo] = chamar(rotulo, params)
        print()

    # Avalia se algum teste paginou (1o item != base, ou itens > 25)
    base = resultados.get('base (sem params)') or []
    sig_base = assinatura(base[0]) if base else None
    qtd_base = len(base)

    paginou_algum = False

    print('=' * 64)
    print('RESUMO COMPARATIVO')
    print('=' * 64)
    print(f'  base: {qtd_base} itens, 1o hash={sig_base}')
    for rotulo, itens in resultados.items():
        if rotulo == 'base (sem params)':
            continue
        if itens is None:
            print(f'  {rotulo:<28}: SEM RESPOSTA')
            continue
        sig = assinatura(itens[0]) if itens else None
        diff = sig != sig_base
        mais = len(itens) > 25
        marca = ''
        if diff:
            marca += ' [1o item DIFERENTE]'
            paginou_algum = True
        if mais:
            marca += ' [count>25]'
            paginou_algum = True
        print(f'  {rotulo:<28}: {len(itens):>3} itens, 1o hash={sig}{marca}')

    if not paginou_algum:
        print()
        print('Nenhum dos 5 parametros paginou. Tentando fallback (cursor/after)...')
        for rotulo, params in TESTES_FALLBACK:
            time.sleep(INTERVALO)
            itens = chamar(rotulo, params)
            print()
            if itens is None:
                continue
            sig = assinatura(itens[0]) if itens else None
            if sig != sig_base or len(itens) > 25:
                print(f'  -> {rotulo} mostra sinal de paginacao!')
                paginou_algum = True

    print()
    print('=' * 64)
    print('VEREDITO')
    print('=' * 64)
    if paginou_algum:
        print('  /movements ACEITA paginacao (algum parametro funcionou).')
    else:
        print('  /movements NAO PAGINOU em nenhum parametro testado.')
        print('  O teto silencioso de 25 itens parece ser limite duro da API.')

    return 0


if __name__ == '__main__':
    sys.exit(main())
