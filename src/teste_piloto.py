"""
Validacao de schema para o cliente piloto (ID ADVBox 13669008).

Faz duas chamadas:
  1) GET /customers/{id}    -> schema do customer detalhado
  2) GET /lawsuits?customer_id={id} -> contagem de processos + amostra de IDs

Imprime APENAS metadados nao sensiveis:
  - Chaves do JSON (schema)
  - Contagens
  - Tipos das chaves de alto nivel (str, int, list, dict, None, bool)
  - Apenas os 5 primeiros lawsuit_ids para podermos escolher 1 de teste

Nao imprime: nome, email, telefone, endereco, descricao do processo,
nomes de partes, valores ou anotacoes textuais.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from advbox_client import AdvboxClient, AdvboxError

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


CLIENTE_PILOTO_ID = 13669008


def tipo_de(valor):
    """Nome curto do tipo Python para uso no resumo de schema."""
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
    """Lista as chaves de um dict mostrando o tipo (sem valores sensiveis)."""
    print(f'  Schema de {rotulo}:')
    if not isinstance(obj, dict):
        print(f'    (objeto nao e dict, e {type(obj).__name__})')
        return
    for k in sorted(obj.keys()):
        print(f'    - {k:<22} : {tipo_de(obj[k])}')


def passo_2_get_customer(client):
    print('=' * 60)
    print(f'[2] GET /customers/{CLIENTE_PILOTO_ID}')
    print('=' * 60)

    cust = client.get_customer(CLIENTE_PILOTO_ID)

    if isinstance(cust, dict) and 'data' in cust and isinstance(cust['data'], (dict, list)):
        # Algumas APIs envelopam mesmo o detalhe em {"data": ...}
        print('  (resposta veio envelopada em "data" — desempacotando)')
        envelope = cust
        cust = cust['data']
        print(f'  Chaves do envelope: {sorted(envelope.keys())}')

    if isinstance(cust, list):
        print(f'  AVISO: resposta veio como list de {len(cust)} itens (esperavamos dict).')
        if cust:
            cust = cust[0]
            print('  Usando primeiro item da lista para inspecao do schema.')

    if not isinstance(cust, dict):
        print(f'  ERRO: tipo inesperado {type(cust).__name__}')
        return None

    print(f'  ID confirmado    : {cust.get("id")}')
    print(f'  Origin           : {cust.get("origin")!r}')
    lawsuits_inline = cust.get('lawsuits')
    if isinstance(lawsuits_inline, list):
        print(f'  lawsuits inline  : list com {len(lawsuits_inline)} itens')
        if lawsuits_inline and isinstance(lawsuits_inline[0], dict):
            print('  Schema do PRIMEIRO item de cust["lawsuits"] (so chaves+tipos):')
            for k in sorted(lawsuits_inline[0].keys()):
                print(f'    - {k:<22} : {tipo_de(lawsuits_inline[0][k])}')
    else:
        print(f'  lawsuits inline  : {tipo_de(lawsuits_inline)}')

    print()
    imprimir_schema('cust (top-level)', cust)
    return cust


def passo_3_get_lawsuits(client):
    print()
    print('=' * 60)
    print(f'[3] GET /lawsuits?customer_id={CLIENTE_PILOTO_ID}')
    print('=' * 60)

    resp = client.get_lawsuits(customer_id=CLIENTE_PILOTO_ID, limit=1000, offset=0)

    if not isinstance(resp, dict):
        print(f'  ERRO: resposta nao e dict, e {type(resp).__name__}')
        return None

    print(f'  Chaves do envelope: {sorted(resp.keys())}')
    total = resp.get('totalCount')
    data = resp.get('data')
    if not isinstance(data, list):
        print(f'  ERRO: "data" nao e list, e {type(data).__name__}')
        return None

    print(f'  totalCount        : {total}')
    print(f'  itens em data     : {len(data)}')
    print(f'  limit retornado   : {resp.get("limit")}')
    print(f'  offset retornado  : {resp.get("offset")}')

    if not data:
        print('  (nenhum processo retornado para este cliente)')
        return None

    primeiro = data[0]
    if isinstance(primeiro, dict):
        print()
        imprimir_schema('lawsuit (1o item de data)', primeiro)

    print()
    print('  Amostra de lawsuit_ids (primeiros 5, para escolha do teste):')
    ids_amostra = []
    for i, item in enumerate(data[:5]):
        if isinstance(item, dict):
            lid = item.get('id')
            ids_amostra.append(lid)
            print(f'    [{i}] id = {lid}')
        else:
            print(f'    [{i}] (item nao e dict)')

    return ids_amostra


def main():
    print(f'Cliente piloto: ID {CLIENTE_PILOTO_ID}')
    print()

    try:
        client = AdvboxClient()
    except AdvboxError as e:
        print(f'ERRO ao inicializar AdvboxClient: {e}')
        return 1

    try:
        cust = passo_2_get_customer(client)
        if cust is None:
            return 1

        ids_amostra = passo_3_get_lawsuits(client)
        if ids_amostra is None:
            return 1

        print()
        print('=' * 60)
        print('RESUMO')
        print('=' * 60)
        print('  /customers/{id} respondeu com schema esperado.')
        print(f'  /lawsuits?customer_id= retornou processos do piloto.')
        print(f'  Amostra de lawsuit_ids para o proximo passo: {ids_amostra}')
        print()
        print('  PROXIMO PASSO (aguardando confirmacao do usuario):')
        print('    - Escolher 1 lawsuit_id desta amostra para testar')
        print('      /movements/{id} e /history/{id}.')
        return 0

    except AdvboxError as e:
        print(f'ERRO de API: {e}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
