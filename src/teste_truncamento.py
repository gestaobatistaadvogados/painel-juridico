"""
Teste de truncamento silencioso em GET /movements/{lawsuit_id}.

A API nao retorna `totalCount`/`limit`/`offset` neste endpoint, entao se
houver um teto interno (ex: 100 itens) nao temos como saber via metadados.
Heuristica: rodar em um lawsuit_id provavelmente "rico" em movimentacoes
e checar se o count vem como numero suspeitosamente redondo (50, 100, 200,
500, 1000).

So /movements e testado — /history nao sera usado no painel publico do
cliente conforme regra critica do projeto.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from advbox_client import AdvboxClient, AdvboxError

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


# Segundo mais antigo da amostra (12944529 ja foi testado e retornou 15 itens
# nao redondos — primeiro data point). Heuristica: IDs mais baixos no ADVBox
# tendem a corresponder a processos cadastrados ha mais tempo, logo com mais
# movimentos acumulados.
LAWSUIT_ID_TESTE = 12944576

# Lista de numeros suspeitos de serem "tetos" silenciosos.
NUMEROS_REDONDOS_SUSPEITOS = {25, 50, 100, 200, 250, 500, 1000}


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


def main():
    print(f'Teste de truncamento em /movements/{LAWSUIT_ID_TESTE}')
    print(f'Comparacao: /movements/12944529 retornou 15 itens (data point anterior).')
    print()

    try:
        client = AdvboxClient()
    except AdvboxError as e:
        print(f'ERRO ao inicializar AdvboxClient: {e}')
        return 1

    try:
        resp = client.get_movements(LAWSUIT_ID_TESTE)
    except AdvboxError as e:
        print(f'ERRO de API: {e}')
        return 1

    if not isinstance(resp, dict):
        print(f'ERRO: resposta nao e dict, e {type(resp).__name__}')
        return 1

    data = resp.get('data')
    if not isinstance(data, list):
        print(f'ERRO: "data" nao e list, e {type(data).__name__}')
        return 1

    qtd = len(data)
    suspeito = qtd in NUMEROS_REDONDOS_SUSPEITOS

    print('=' * 60)
    print(f'  Itens em data    : {qtd}')
    print(f'  Numero suspeito? : {"SIM — possivel truncamento!" if suspeito else "NAO (numero nao listado como teto comum)"}')
    print('=' * 60)

    if data and isinstance(data[0], dict):
        print()
        print('  Schema do 1o item (chaves + tipos, sem conteudo):')
        for k in sorted(data[0].keys()):
            print(f'    - {k:<22} : {tipo_de(data[0][k])}')

    print()
    print('Comparacao consolidada de /movements:')
    print(f'  - lawsuit 12944529 (mais antigo): 15 itens')
    print(f'  - lawsuit {LAWSUIT_ID_TESTE} (2o mais antigo): {qtd} itens')

    if suspeito:
        print()
        print('AVISO: o numero retornado e um candidato classico a teto silencioso.')
        print('Sugiro testar mais 1-2 lawsuit_ids antes de partir para producao.')
    else:
        if qtd > 30:
            print()
            print(f'Bom sinal: {qtd} > 30 e nao e numero "redondo classico".')
            print('Aumenta a confianca de que a API nao trunca em valor pequeno.')
        else:
            print()
            print('Resultado em range modesto. Nao prova ausencia de truncamento,')
            print('mas combinado com o outro data point reduz a chance.')

    return 0


if __name__ == '__main__':
    sys.exit(main())
