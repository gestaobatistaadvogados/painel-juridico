"""
Diagnostico da estrutura de resposta de /customers.

Mostra apenas o tipo da resposta, chaves de top-level e — se houver
algum campo numerico/string nao-lista — o valor (uteis para detectar
metadata de paginacao como total, page, per_page, last_page).

NAO imprime nenhum customer.
"""

import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from src.advbox_client import AdvboxClient, AdvboxError
except ImportError:
    from advbox_client import AdvboxClient, AdvboxError


def main():
    print('GET /customers (page=1, per_page=100) — inspecao da estrutura')
    try:
        cliente = AdvboxClient()
        resp = cliente.get_customers(page=1, per_page=100)
    except AdvboxError as e:
        print(f'Falha: {e}')
        return 1

    print(f'Tipo da resposta: {type(resp).__name__}')

    if isinstance(resp, list):
        print(f'Resposta e uma lista pura. Tamanho: {len(resp)}')
        return 0

    if isinstance(resp, dict):
        print(f'Chaves de top-level: {sorted(resp.keys())}')
        print()
        print('Detalhe por chave (apenas tipos e tamanhos, sem valores de customers):')
        for k in sorted(resp.keys()):
            v = resp[k]
            tipo = type(v).__name__
            if isinstance(v, list):
                print(f'  {k}: list (tamanho={len(v)})')
            elif isinstance(v, dict):
                print(f'  {k}: dict (chaves={sorted(v.keys())}, valores={v})')
            elif isinstance(v, (int, float, bool)) or v is None:
                print(f'  {k}: {tipo} = {v}')
            elif isinstance(v, str):
                print(f'  {k}: str = "{v}"')
            else:
                print(f'  {k}: {tipo}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
