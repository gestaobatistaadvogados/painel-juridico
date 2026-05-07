"""
Diagnostico do bloco "Trabalho 90 dias" para o cliente piloto.

Distingue 3 hipoteses:
  (a) falha de autenticacao (token invalido/expirado)
  (b) endpoint /posts ou /tasks vazio mesmo (escritorio nao usa)
  (c) bug no gerador (filtro/categorizacao/janela)

So leitura. Nao modifica gerador, template, nem cache.

NOTA sobre adaptacoes:
  - O AdvboxClient._request(endpoint, params) NAO recebe metodo HTTP
    (so faz GET). Chamamos passando endpoint sem barra inicial.
  - calcular_atividade_90d tem signature (client, customer_id) —
    nao (customer_id, client) como no spec.
  - Imports usam estilo do projeto (sem prefixo `src.`).
"""

import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Adiciona src/ ao path (mesmo padrao dos demais scripts)
sys.path.insert(0, str(Path(__file__).resolve().parent))

from advbox_client import AdvboxClient, AdvboxError, AdvboxAuthError

CUSTOMER_PILOTO = 13669008


def _safe_str(v, max_len=80):
    s = str(v) if v is not None else 'None'
    if len(s) > max_len:
        s = s[:max_len] + '...'
    return s


def _extrair_lista_e_total(resp):
    """Normaliza varias formas de resposta da API ADVBox em (data, total)."""
    if isinstance(resp, dict):
        data = resp.get('data') if isinstance(resp.get('data'), list) else None
        total = resp.get('totalCount')
        return data, total
    if isinstance(resp, list):
        return resp, None
    return None, None


def main():
    print(f'Diagnostico /posts em {datetime.now().isoformat(timespec="seconds")}')
    print(f'Cliente piloto: {CUSTOMER_PILOTO} (HOSPITAL AMPARO LTDA)')
    print()

    # ---------------------------------------------------------------
    # [1] Validar autenticacao basica
    # ---------------------------------------------------------------
    try:
        client = AdvboxClient()
    except AdvboxError as e:
        print(f'[0] ERRO ao inicializar AdvboxClient: {e}')
        return 1

    print('[1] Validando token via GET /settings...')
    try:
        settings = client.get_settings()
        n_users = len(settings.get('users') or []) if isinstance(settings, dict) else 0
        chaves_topo = sorted(settings.keys()) if isinstance(settings, dict) else []
        print(f'    OK — {n_users} usuarios no escritorio')
        print(f'    Chaves no topo de /settings: {chaves_topo[:8]}{"..." if len(chaves_topo) > 8 else ""}')
        print('    Token VALIDO.')
    except AdvboxAuthError as e:
        print(f'    FALHA AUTH — token invalido: {e}')
        print()
        print('Diagnostico interrompido — sem token valido nao da pra prosseguir.')
        return 1
    except AdvboxError as e:
        print(f'    FALHA — {type(e).__name__}: {e}')
        return 1
    print()

    # ---------------------------------------------------------------
    # [2] /posts sem filtro
    # ---------------------------------------------------------------
    print('[2] GET /posts (sem filtro, primeiros 100)...')
    posts_geral = None
    try:
        resp = client._request('posts', params={'limit': 100, 'offset': 0})
        data, total = _extrair_lista_e_total(resp)
        posts_geral = data
        print(f'    Resposta tipo:        {type(resp).__name__}')
        if isinstance(resp, dict):
            print(f'    Chaves do envelope:   {sorted(resp.keys())}')
        print(f'    totalCount global:    {total}')
        print(f'    Items retornados:     {len(data) if isinstance(data, list) else "N/A"}')
        if isinstance(data, list) and data and isinstance(data[0], dict):
            print(f'    Schema do 1o item:')
            for k, v in data[0].items():
                print(f'      {k:<24} : {_safe_str(v)}')
    except AdvboxError as e:
        print(f'    FALHA — {type(e).__name__}: {e}')
    print()

    # ---------------------------------------------------------------
    # [3] /tasks sem filtro
    # ---------------------------------------------------------------
    print('[3] GET /tasks (sem filtro, ultimos 90 dias)...')
    tasks_geral = None
    try:
        resp = client.get_tasks()
        data, total = _extrair_lista_e_total(resp)
        tasks_geral = data
        print(f'    Resposta tipo:        {type(resp).__name__}')
        if isinstance(resp, dict):
            print(f'    Chaves do envelope:   {sorted(resp.keys())}')
        print(f'    totalCount global:    {total}')
        print(f'    Items retornados:     {len(data) if isinstance(data, list) else "N/A"}')
        if isinstance(data, list) and data and isinstance(data[0], dict):
            print(f'    Schema do 1o item:')
            for k, v in data[0].items():
                print(f'      {k:<24} : {_safe_str(v)}')
    except AdvboxError as e:
        print(f'    FALHA — {type(e).__name__}: {e}')
    print()

    # ---------------------------------------------------------------
    # [4] /posts filtrado por customer_id
    # ---------------------------------------------------------------
    print(f'[4] GET /posts?customer_id={CUSTOMER_PILOTO}...')
    posts_cliente = None
    try:
        resp = client._request('posts', params={
            'customer_id': CUSTOMER_PILOTO,
            'limit': 100,
            'offset': 0,
        })
        data, total = _extrair_lista_e_total(resp)
        posts_cliente = data
        print(f'    totalCount:        {total}')
        print(f'    Items retornados:  {len(data) if isinstance(data, list) else "N/A"}')
        if isinstance(data, list) and data:
            print(f'    Schema do 1o item:')
            for k, v in data[0].items():
                print(f'      {k:<24} : {_safe_str(v)}')
    except AdvboxError as e:
        print(f'    FALHA — {type(e).__name__}: {e}')
    print()

    # ---------------------------------------------------------------
    # [4b] /tasks filtrado por customer_id (e o que o gerador usa)
    # ---------------------------------------------------------------
    print(f'[4b] GET /tasks?customer_id={CUSTOMER_PILOTO} (90 dias) — esse e o usado pelo gerador...')
    tasks_cliente = None
    try:
        resp = client.get_tasks(customer_id=CUSTOMER_PILOTO, days=90)
        data, total = _extrair_lista_e_total(resp)
        tasks_cliente = data
        print(f'    Resposta tipo:     {type(resp).__name__}')
        if isinstance(resp, dict):
            print(f'    Chaves do envelope: {sorted(resp.keys())}')
        print(f'    totalCount:        {total}')
        print(f'    Items retornados:  {len(data) if isinstance(data, list) else "N/A"}')
        if isinstance(data, list) and data:
            print(f'    Schema do 1o item (campos sem dados sensiveis):')
            for k, v in data[0].items():
                print(f'      {k:<24} : {_safe_str(v)}')
    except AdvboxError as e:
        print(f'    FALHA — {type(e).__name__}: {e}')
    print()

    # ---------------------------------------------------------------
    # [5] Distribuicao temporal — usa o que tiver dados.
    # ---------------------------------------------------------------
    print('[5] Distribuicao temporal (ultimos 365 dias)...')
    fonte = None
    if isinstance(posts_cliente, list) and posts_cliente:
        fonte_dados, fonte_label = posts_cliente, '/posts?customer_id'
    elif isinstance(tasks_cliente, list) and tasks_cliente:
        fonte_dados, fonte_label = tasks_cliente, '/tasks?customer_id'
    elif isinstance(posts_geral, list) and posts_geral:
        fonte_dados, fonte_label = posts_geral, '/posts (geral)'
    elif isinstance(tasks_geral, list) and tasks_geral:
        fonte_dados, fonte_label = tasks_geral, '/tasks (geral)'
    else:
        fonte_dados, fonte_label = None, None

    if fonte_dados:
        print(f'    Usando fonte: {fonte_label}')
        hoje = datetime.now().date()
        c30 = c60 = c90 = c365 = 0
        datas = []
        sem_data = 0
        for item in fonte_dados:
            if not isinstance(item, dict):
                continue
            # Tenta varios campos de data
            valor = (item.get('created_at') or item.get('start')
                     or item.get('date_deadline') or item.get('date'))
            if not valor:
                sem_data += 1
                continue
            try:
                s = str(valor).replace('Z', '+00:00')
                dt = datetime.fromisoformat(s).date()
            except (ValueError, TypeError):
                try:
                    dt = datetime.strptime(str(valor)[:10], '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    sem_data += 1
                    continue
            datas.append(dt)
            dias = (hoje - dt).days
            if dias <= 30: c30 += 1
            if dias <= 60: c60 += 1
            if dias <= 90: c90 += 1
            if dias <= 365: c365 += 1
        if datas:
            print(f'    Total de items com data valida: {len(datas)}')
            print(f'    Items sem data:                 {sem_data}')
            print(f'    Items nos ultimos 30 dias:      {c30}')
            print(f'    Items nos ultimos 60 dias:      {c60}')
            print(f'    Items nos ultimos 90 dias:      {c90}')
            print(f'    Items nos ultimos 365 dias:     {c365}')
            print(f'    Data mais antiga:  {min(datas)}')
            print(f'    Data mais recente: {max(datas)}')
        else:
            print(f'    Nenhuma data valida encontrada nos {len(fonte_dados)} items.')
    else:
        print('    Nenhuma fonte com dados disponiveis para analise temporal.')
    print()

    # ---------------------------------------------------------------
    # [6] Testar calcular_atividade_90d do gerador
    # ---------------------------------------------------------------
    print('[6] Testando calcular_atividade_90d() do gerador...')
    print('    NOTA: o cache em cache/tasks_customer_13669008.json pode estar')
    print('          stale (envelope vazio cacheado quando o token expirou).')
    print('          Esse teste mostra o que o gerador devolveria HOJE.')
    try:
        from gerador_producao import calcular_atividade_90d
        resultado = calcular_atividade_90d(client, CUSTOMER_PILOTO)
        print(f'    Retorno:')
        print(f'      total       : {resultado.get("total")}')
        print(f'      ultima_data : {resultado.get("ultima_data")}')
        print(f'      categorias  :')
        cats = resultado.get('categorias') or {}
        for k, v in cats.items():
            print(f'        {k:<14} : {v}')
    except ImportError as e:
        print(f'    FALHA import: {e}')
    except Exception as e:
        print(f'    FALHA — {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()
    print()

    # ---------------------------------------------------------------
    # RESUMO
    # ---------------------------------------------------------------
    print('=' * 64)
    print('RESUMO — guia de leitura')
    print('=' * 64)
    print(' [1] FALHOU  -> token expirado, regerar no painel ADVBox')
    print(' [2] = 0     -> /posts vazio (escritorio nao usa esse endpoint)')
    print(' [3] = 0     -> /tasks vazio (idem para /tasks)')
    print(' [4] = 0 mas [2] > 0 -> filtro customer_id ignorado pela API;')
    print('                       precisamos filtrar localmente.')
    print(' [4b] = 0    -> a fonte usada pelo gerador (/tasks com filtro)')
    print('                nao retorna nada para esse cliente.')
    print(' [5] mostra que ha posts antigos -> janela de 90 dias e curta')
    print(' [6] retorna zeros -> ou cache stale, ou bug no mapping.')
    print()
    print('Acoes possiveis (depois de ver os resultados):')
    print('  - Para forcar refetch limpo: deletar cache/tasks_customer_*.json')
    print('  - Se /posts > 0 e /tasks = 0: trocar a chamada do gerador')
    print('    para /posts (com filtro local se necessario)')
    print('  - Se ambos vazios: bloco mostra 0 e a inferencia precisa vir')
    print('    de outro caminho (ex: contar movements proprios do cliente)')

    return 0


if __name__ == '__main__':
    sys.exit(main())
