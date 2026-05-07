"""
Validacao de schema dos endpoints /movements/{id} e /history/{id}.

Usa o lawsuit_id 12944529 (primeiro processo do cliente piloto 13669008,
pego em src/teste_piloto.py).

Imprime APENAS:
  - Estrutura do envelope
  - Tipos das chaves de alto nivel
  - Schema (chaves) de items quando for list
  - Quantidade de items
  - Quando for str, so o tamanho — nao o conteudo

Nao imprime: descricao das movimentacoes, partes, observacoes, despachos,
nem qualquer texto livre que possa conter PII ou conteudo processual
sensivel.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from advbox_client import AdvboxClient, AdvboxError

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


LAWSUIT_ID_TESTE = 12944529


def tipo_de(valor):
    if valor is None:
        return 'None'
    if isinstance(valor, bool):
        return 'bool'
    if isinstance(valor, int):
        return 'int'
    if isinstance(valor, float):
        return 'float'
    if isinstance(valor, str):
        return f'str(len={len(valor)})'
    if isinstance(valor, list):
        return f'list(len={len(valor)})'
    if isinstance(valor, dict):
        return f'dict(keys={len(valor)})'
    return type(valor).__name__


def imprimir_schema(rotulo, obj):
    print(f'  Schema de {rotulo}:')
    if not isinstance(obj, dict):
        print(f'    (objeto nao e dict, e {type(obj).__name__})')
        return
    for k in sorted(obj.keys()):
        print(f'    - {k:<22} : {tipo_de(obj[k])}')


def inspecionar(rotulo, resp):
    """Inspeciona generica e seguramente uma resposta de endpoint."""
    print(f'  Tipo da resposta : {type(resp).__name__}')

    if isinstance(resp, dict):
        chaves_topo = sorted(resp.keys())
        print(f'  Chaves do topo   : {chaves_topo}')

        # Padrao envelope { data: [...], totalCount, ... }
        if 'data' in resp and isinstance(resp['data'], list):
            data = resp['data']
            print(f'  totalCount       : {resp.get("totalCount")}')
            print(f'  limit            : {resp.get("limit")}')
            print(f'  offset           : {resp.get("offset")}')
            print(f'  itens em data    : {len(data)}')
            if data and isinstance(data[0], dict):
                print()
                imprimir_schema(f'{rotulo}.data[0]', data[0])
            elif data:
                print(f'  data[0] tipo     : {type(data[0]).__name__}')
            return

        # Dict simples (sem envelope)
        print()
        imprimir_schema(rotulo, resp)
        return

    if isinstance(resp, list):
        print(f'  Itens na lista   : {len(resp)}')
        if resp and isinstance(resp[0], dict):
            print()
            imprimir_schema(f'{rotulo}[0]', resp[0])
        elif resp:
            print(f'  [0] tipo         : {type(resp[0]).__name__}')
        return

    print(f'  (tipo inesperado: {type(resp).__name__})')


def passo_4a_movements(client):
    print('=' * 60)
    print(f'[4a] GET /movements/{LAWSUIT_ID_TESTE}')
    print('=' * 60)
    try:
        resp = client.get_movements(LAWSUIT_ID_TESTE)
    except AdvboxError as e:
        print(f'  ERRO: {e}')
        return False
    inspecionar('movements', resp)
    return True


def passo_4b_history(client):
    print()
    print('=' * 60)
    print(f'[4b] GET /history/{LAWSUIT_ID_TESTE}')
    print('=' * 60)
    try:
        resp = client.get_history(LAWSUIT_ID_TESTE)
    except AdvboxError as e:
        print(f'  ERRO: {e}')
        return False
    inspecionar('history', resp)
    return True


def main():
    print(f'Lawsuit de teste: {LAWSUIT_ID_TESTE} (1o processo do piloto 13669008)')
    print()

    try:
        client = AdvboxClient()
    except AdvboxError as e:
        print(f'ERRO ao inicializar AdvboxClient: {e}')
        return 1

    ok_a = passo_4a_movements(client)
    ok_b = passo_4b_history(client)

    print()
    print('=' * 60)
    print('RESUMO')
    print('=' * 60)
    print(f'  /movements/{LAWSUIT_ID_TESTE}: {"OK" if ok_a else "FALHOU"}')
    print(f'  /history/{LAWSUIT_ID_TESTE}  : {"OK" if ok_b else "FALHOU"}')
    return 0 if (ok_a and ok_b) else 1


if __name__ == '__main__':
    sys.exit(main())
