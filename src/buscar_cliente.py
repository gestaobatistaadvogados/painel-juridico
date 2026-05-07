"""
Busca um cliente no ADVBox pelo CNPJ/CPF (campo `identification`).

Estrategia em duas etapas:
  1) Tenta filtro via query string `?identification=<digitos>`. A API ja foi
     observada ignorando silenciosamente parametros nao documentados
     (page/per_page), entao validamos o resultado antes de confiar.
  2) Se o filtro for ignorado ou nao encontrar match, varre a base com
     limit=1000 + offset crescente, parando no primeiro match.

Imprime APENAS metadados nao sensiveis do cliente encontrado:
  - ID ADVBox
  - Tipo (PF/PJ pelo tamanho de identification)
  - Quantidade de lawsuits no array
  - Origin
  - Lista de chaves do JSON (schema)

Nao imprime nome, email, telefone, endereco nem o CNPJ completo.
"""

import sys
from pathlib import Path

# Permite rodar com `python src/buscar_cliente.py` a partir da raiz.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from advbox_client import AdvboxClient, AdvboxError

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


CNPJ_ALVO = '05919720000179'

# Acima deste totalCount entendemos que o filtro foi ignorado pela API
# (a base do escritorio tem ~5229 registros — qualquer valor >> 100
# significa que voltou a base toda).
LIMITE_FILTRO_VALIDO = 100


def normalizar(valor):
    """Mantem apenas digitos de uma string. None -> ''."""
    if valor is None:
        return ''
    return ''.join(c for c in str(valor) if c.isdigit())


def classificar_tipo(identification):
    """PF (11 digitos), PJ (14 digitos) ou desconhecido."""
    digitos = normalizar(identification)
    if len(digitos) == 11:
        return 'PF'
    if len(digitos) == 14:
        return 'PJ'
    if len(digitos) == 0:
        return 'desconhecido (identification vazio)'
    return f'desconhecido ({len(digitos)} digitos)'


def mascarar(digitos):
    """Mascara CPF/CNPJ para log (mostra so primeiros 4 e ultimos 2)."""
    if len(digitos) < 6:
        return '*' * len(digitos)
    return f'{digitos[:4]}{"*" * (len(digitos) - 6)}{digitos[-2:]}'


def achou_no_lote(lote, alvo):
    """Procura `alvo` (so digitos) no campo identification de cada item."""
    for c in lote:
        if normalizar(c.get('identification')) == alvo:
            return c
    return None


def buscar_via_filtro(client, alvo):
    """Etapa 1: tenta usar o parametro identification na query string."""
    print('[1/2] Tentando filtro via query string ?identification=...')
    resp = client._request(
        'customers',
        params={'identification': alvo, 'limit': LIMITE_FILTRO_VALIDO, 'offset': 0},
    )
    data = resp.get('data') or []
    total = resp.get('totalCount')
    print(f'      totalCount = {total} | itens no lote = {len(data)}')

    if total is not None and total > LIMITE_FILTRO_VALIDO:
        print('      => totalCount alto: a API ignorou o filtro. Vou varrer.')
        return None, False

    achado = achou_no_lote(data, alvo)
    if achado:
        print('      => filtro funcionou e encontrou o cliente.')
        return achado, True

    print('      => filtro retornou poucos registros mas sem match.')
    return None, True


def buscar_via_scan(client, alvo):
    """Etapa 2: varredura paginada limit=1000 + offset crescente."""
    print('[2/2] Varredura paginada (limit=1000, offset crescente)...')
    examinados = 0
    pagina = 0
    offset = 0

    while True:
        resp = client.get_customers(limit=1000, offset=offset)
        data = resp.get('data') or []
        if not data:
            break

        pagina += 1
        examinados += len(data)
        print(f'      pagina {pagina}: offset={offset}, itens={len(data)}, total={examinados}')

        achado = achou_no_lote(data, alvo)
        if achado:
            print(f'      => MATCH na pagina {pagina} (apos {examinados} registros).')
            return achado

        total = resp.get('totalCount')
        offset += len(data)
        if total is not None and offset >= total:
            break
        if len(data) < 1000:
            break

    print(f'      => varredura completa: {examinados} registros, sem match.')
    return None


def imprimir_resumo(cliente, alvo):
    ident_norm = normalizar(cliente.get('identification'))
    lawsuits = cliente.get('lawsuits')
    qtd_lawsuits = len(lawsuits) if isinstance(lawsuits, list) else 'N/A'

    print()
    print('=' * 60)
    print('CLIENTE ENCONTRADO')
    print('=' * 60)
    print(f'  ID ADVBox        : {cliente.get("id")}')
    print(f'  Tipo             : {classificar_tipo(ident_norm)}')
    print(f'  Qtd. de lawsuits : {qtd_lawsuits}')
    print(f'  Origin           : {cliente.get("origin")!r}')
    print(f'  Identification   : confere ({mascarar(alvo)}, {len(ident_norm)} digitos)')
    print('=' * 60)
    print()
    print('Schema do customer (chaves disponiveis, sem valores):')
    for k in sorted(cliente.keys()):
        print(f'  - {k}')


def imprimir_nao_encontrado(alvo):
    print()
    print('=' * 60)
    print('NAO ENCONTRADO')
    print('=' * 60)
    print(f'  Alvo (mascarado) : {mascarar(alvo)} ({len(alvo)} digitos => {classificar_tipo(alvo)})')
    print()
    print('Possiveis proximos passos:')
    print('  1. Confirmar com o cliente que o CNPJ esta correto.')
    print('  2. Conferir no painel ADVBox se o cadastro existe e se o campo')
    print('     "identification" esta preenchido (38% da base esta com esse')
    print('     campo vazio, conforme o levantamento da Fase 2).')
    print('  3. Verificar se o cadastro esta como PF (CPF do socio) em vez')
    print('     de PJ.')
    print('  4. Buscar pelo nome em /customers (precisaria saber o nome')
    print('     fantasia/razao social exata como cadastrada no ADVBox).')


def main():
    alvo = normalizar(CNPJ_ALVO)
    print(f'Alvo: {mascarar(alvo)} ({len(alvo)} digitos => {classificar_tipo(alvo)})')
    print()

    try:
        client = AdvboxClient()
    except AdvboxError as e:
        print(f'ERRO ao inicializar AdvboxClient: {e}')
        return 1

    try:
        achado, filtro_ok = buscar_via_filtro(client, alvo)
        if achado:
            imprimir_resumo(achado, alvo)
            return 0

        if filtro_ok:
            print('      (filtro foi processado mas sem match — ainda assim varremos por seguranca)')
        print()

        achado = buscar_via_scan(client, alvo)
        if achado:
            imprimir_resumo(achado, alvo)
            return 0

        imprimir_nao_encontrado(alvo)
        return 1

    except AdvboxError as e:
        print(f'ERRO de API: {e}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
