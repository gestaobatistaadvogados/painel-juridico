"""
Investigacao secundaria: como distinguir "lado do cliente" vs "lado
adversario" dentro do array customers de cada lawsuit?

Surpresa da v1: o id do cliente piloto (13669008) NAO aparece via
customer_id em nenhum dos 132 lawsuits. Logo, o filtro
`c.customer_id != cliente.id_advbox` falharia (incluiria o cliente
como adversario).

Esta v2 testa duas hipoteses:
  H1) o cliente aparece via `identification` (CNPJ) em vez de customer_id
  H2) o campo `origin` distingue ("CLIENTE" vs "PARTE CONTRARIA")

Imprime APENAS contagens — sem expor nomes nem CNPJs.
"""

import json
import os
import sys
from pathlib import Path
from collections import Counter

from dotenv import load_dotenv

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / '.env')

CACHE_LAWSUITS = RAIZ / 'cache' / 'lawsuits_customer_13669008.json'
CACHE_CUSTOMER = RAIZ / 'cache' / 'customers_13669008.json'
CLIENTE_PILOTO_ID = 13669008


def normalizar(s):
    if s is None:
        return ''
    return ''.join(ch for ch in str(s) if ch.isdigit())


def main():
    if not CACHE_LAWSUITS.exists() or not CACHE_CUSTOMER.exists():
        print('ERRO: caches faltantes.')
        return 1

    # Pegar identification do cliente do cache do customer
    with CACHE_CUSTOMER.open('r', encoding='utf-8') as f:
        env_cust = json.load(f)
    cust = env_cust.get('data') or {}
    ident_cliente = normalizar(cust.get('identification'))
    print(f'Identification do cliente piloto (so digitos, len): {len(ident_cliente)}')
    print(f'(mascarado) ****{ident_cliente[-4:] if len(ident_cliente) >= 4 else "??"}')
    print()

    # Carregar lawsuits
    with CACHE_LAWSUITS.open('r', encoding='utf-8') as f:
        env_law = json.load(f)
    lawsuits = (env_law.get('data') or {}).get('data') or []
    print(f'Total lawsuits: {len(lawsuits)}')
    print()

    # ========================================================
    # HIPOTESE H1: cliente aparece via identification (CNPJ)
    # ========================================================
    aparece_por_identification = 0
    customers_total = 0
    customers_com_ident_cliente = 0
    for law in lawsuits:
        custs = law.get('customers') or []
        achou = False
        for c in custs:
            if not isinstance(c, dict):
                continue
            customers_total += 1
            if normalizar(c.get('identification')) == ident_cliente:
                customers_com_ident_cliente += 1
                achou = True
        if achou:
            aparece_por_identification += 1

    print('H1: cliente aparece via identification?')
    print(f'  Lawsuits com pelo menos 1 customer com ident do cliente: {aparece_por_identification}/{len(lawsuits)}')
    print(f'  Total de customers em todos os lawsuits: {customers_total}')
    print(f'  Customers com identification do cliente: {customers_com_ident_cliente}')
    print()

    # ========================================================
    # HIPOTESE H2: origin distingue cliente vs adversario
    # ========================================================
    contagem_origin = Counter()
    origin_por_posicao = {0: Counter(), 1: Counter(), 2: Counter()}
    for law in lawsuits:
        custs = law.get('customers') or []
        for j, c in enumerate(custs):
            if not isinstance(c, dict):
                continue
            o = c.get('origin') or '(vazio)'
            contagem_origin[o] += 1
            if j in origin_por_posicao:
                origin_por_posicao[j][o] += 1

    print('H2: distribuicao de origin entre TODOS os customers de TODOS os lawsuits:')
    for o, n in contagem_origin.most_common():
        print(f'  {n:>4}  {o}')
    print()
    print('H2 detalhado: origin por posicao no array:')
    for pos in sorted(origin_por_posicao.keys()):
        print(f'  posicao [{pos}]:')
        for o, n in origin_por_posicao[pos].most_common(5):
            print(f'    {n:>4}  {o}')
    print()

    # ========================================================
    # TENTATIVA DE CASAR: para customers com ident do cliente, qual e o origin?
    # ========================================================
    origins_de_quem_eh_o_cliente = Counter()
    origins_de_quem_NAO_eh_o_cliente = Counter()
    for law in lawsuits:
        custs = law.get('customers') or []
        for c in custs:
            if not isinstance(c, dict):
                continue
            o = c.get('origin') or '(vazio)'
            if normalizar(c.get('identification')) == ident_cliente:
                origins_de_quem_eh_o_cliente[o] += 1
            else:
                origins_de_quem_NAO_eh_o_cliente[o] += 1

    print('Customers que TEM identification == cliente piloto, distribuicao de origin:')
    for o, n in origins_de_quem_eh_o_cliente.most_common(): print(f'  {n:>4}  {o}')
    print()
    print('Customers que NAO tem identification == cliente, distribuicao de origin (top 10):')
    for o, n in origins_de_quem_NAO_eh_o_cliente.most_common(10): print(f'  {n:>4}  {o}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
