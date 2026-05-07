"""
Auditoria do dados.json gerado pelo gerador_producao (Etapa A).

Verifica:
  1. Chaves no JSON nao estao em TERMOS_PROIBIDOS
  2. Estrutura tem meta/cliente/processos
  3. cliente.identification esta mascarado (so 2 ultimos digitos visiveis)
  4. Cada processo tem so chaves do CAMPOS_LAWSUIT_PUBLICOS + 'movements'
  5. Cada movement tem so chaves do CAMPOS_MOVEMENT_PUBLICOS

Imprime estatisticas e qualquer violacao encontrada.
NAO imprime conteudo sensivel (nomes, descricoes de andamento).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gerador_producao import (
    CAMPOS_CLIENTE_PUBLICOS, CAMPOS_LAWSUIT_PUBLICOS, CAMPOS_MOVEMENT_PUBLICOS,
    CAMPOS_LAWSUIT_DERIVADOS, CAMPOS_PARTE_ADVERSARIA,
    CAMPOS_ATIVIDADE_90D, CATEGORIAS_ATIVIDADE_90D,
    MAX_MOVIMENTOS_POR_LAWSUIT,
    TERMOS_PROIBIDOS, assert_sem_termos_proibidos,
    assert_atividade_90d_estruturada, WhitelistError,
)

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


RAIZ = Path(__file__).resolve().parent.parent
ALVO = RAIZ / 'clientes' / 'painel-piloto-pj-2026-n4q8' / 'dados.json'

CAMPOS_CLIENTE_ESPERADOS = set(CAMPOS_CLIENTE_PUBLICOS) | {'identification_tipo'}
CAMPOS_LAWSUIT_ESPERADOS = set(CAMPOS_LAWSUIT_PUBLICOS) | set(CAMPOS_LAWSUIT_DERIVADOS)
CAMPOS_MOVEMENT_ESPERADOS = set(CAMPOS_MOVEMENT_PUBLICOS)


def coletar_todas_chaves(obj, conjunto):
    if isinstance(obj, dict):
        for k, v in obj.items():
            conjunto.add(k)
            coletar_todas_chaves(v, conjunto)
    elif isinstance(obj, list):
        for item in obj:
            coletar_todas_chaves(item, conjunto)


def main():
    print(f'Auditando: {ALVO.relative_to(RAIZ)}')
    print()

    if not ALVO.exists():
        print('ERRO: arquivo nao existe.')
        return 1

    with ALVO.open('r', encoding='utf-8') as f:
        dados = json.load(f)

    # === ESTRUTURA TOPO ===
    chaves_topo = set(dados.keys())
    print(f'Chaves de topo: {sorted(chaves_topo)}')
    esperadas_topo = {'meta', 'cliente', 'processos', 'atividade_90d'}
    if chaves_topo != esperadas_topo:
        print(f'  FALHA: esperado {sorted(esperadas_topo)}')
    else:
        print('  OK')
    print()

    # === META ===
    meta = dados.get('meta', {})
    print('META:')
    print(f'  gerado_em        : {meta.get("gerado_em")}')
    print(f'  gerado_em_humano : {meta.get("gerado_em_humano")}')
    print(f'  slug_url         : {meta.get("slug_url")}')
    print(f'  departamento     : {meta.get("departamento")}')
    print(f'  qtd avisos       : {len(meta.get("avisos", []))}')
    print()

    # === CLIENTE ===
    cliente = dados.get('cliente', {})
    print('CLIENTE:')
    chaves_cliente = set(cliente.keys())
    print(f'  Chaves         : {sorted(chaves_cliente)}')
    extras = chaves_cliente - CAMPOS_CLIENTE_ESPERADOS
    faltando = CAMPOS_CLIENTE_ESPERADOS - chaves_cliente
    if extras:
        print(f'  FALHA - chaves NAO esperadas: {sorted(extras)}')
    if faltando:
        print(f'  AVISO - chaves esperadas faltando: {sorted(faltando)}')
    if not extras and not faltando:
        print('  OK - bate exatamente com whitelist + identification_tipo')

    ident = cliente.get('identification', '')
    digitos = ''.join(c for c in str(ident) if c.isdigit())
    print(f'  identification   : "{ident}" (so {len(digitos)} digitos visiveis)')
    if len(digitos) > 2:
        print(f'  FALHA: mascaramento permitiu {len(digitos)} digitos')
    elif len(digitos) == 2:
        print('  OK: so 2 digitos visiveis (mascaramento aplicado)')
    print(f'  identification_tipo: {cliente.get("identification_tipo")!r}')
    print()

    # === PROCESSOS ===
    processos = dados.get('processos', [])
    print(f'PROCESSOS: {len(processos)} itens')

    chaves_lawsuit_unicas = set()
    chaves_movement_unicas = set()
    chaves_parte_unicas = set()
    total_movs = 0
    movs_acima_do_cap = 0
    movs_no_cap = 0
    total_partes = 0
    partes_com_extras = 0
    fases_grupo = set()
    for p in processos:
        chaves_lawsuit_unicas.update(p.keys())
        movs = p.get('movements', [])
        total_movs += len(movs)
        if len(movs) > MAX_MOVIMENTOS_POR_LAWSUIT:
            movs_acima_do_cap += 1
        elif len(movs) == MAX_MOVIMENTOS_POR_LAWSUIT:
            movs_no_cap += 1
        for m in movs:
            chaves_movement_unicas.update(m.keys())
        for adv in (p.get('partes_adversarias') or []):
            total_partes += 1
            chaves = set(adv.keys()) if isinstance(adv, dict) else set()
            chaves_parte_unicas.update(chaves)
            if chaves != set(CAMPOS_PARTE_ADVERSARIA):
                partes_com_extras += 1
        if p.get('fase_grupo'):
            fases_grupo.add(p['fase_grupo'])

    print(f'  Chaves unicas em processos: {sorted(chaves_lawsuit_unicas)}')
    extras = chaves_lawsuit_unicas - CAMPOS_LAWSUIT_ESPERADOS
    if extras:
        print(f'  FALHA - extras: {sorted(extras)}')
    else:
        print(f'  OK - todas dentro da whitelist + derivados ({sorted(CAMPOS_LAWSUIT_ESPERADOS)})')

    print(f'  Total de movimentos: {total_movs}')
    print(f'  Cap de produto: {MAX_MOVIMENTOS_POR_LAWSUIT} movs/processo')
    print(f'  Processos saturados no cap (== {MAX_MOVIMENTOS_POR_LAWSUIT}): {movs_no_cap}')
    if movs_acima_do_cap:
        print(f'  FALHA - {movs_acima_do_cap} processos com movs > cap (gerador deveria cortar)')
    else:
        print(f'  OK - nenhum processo acima do cap')

    # Partes adversarias
    print()
    print('PARTES ADVERSARIAS:')
    print(f'  Total entries em partes_adversarias: {total_partes}')
    print(f'  Chaves unicas: {sorted(chaves_parte_unicas)}')
    if partes_com_extras:
        print(f'  FALHA - {partes_com_extras} entries com chaves alem da whitelist {CAMPOS_PARTE_ADVERSARIA}')
    else:
        print(f'  OK - todas as entries tem somente {CAMPOS_PARTE_ADVERSARIA}')

    # Fase grupo
    print()
    print('FASE_GRUPO (filtros chips):')
    print(f'  Valores observados: {sorted(fases_grupo)}')
    print(f'  Chaves unicas em movements: {sorted(chaves_movement_unicas)}')
    extras_m = chaves_movement_unicas - CAMPOS_MOVEMENT_ESPERADOS
    if extras_m:
        print(f'  FALHA - extras em movements: {sorted(extras_m)}')
    else:
        print(f'  OK - todas dentro de CAMPOS_MOVEMENT_PUBLICOS')
    print()

    # === ATIVIDADE 90 DIAS ===
    print('ATIVIDADE 90 DIAS:')
    atividade = dados.get('atividade_90d')
    if atividade is None:
        print('  AVISO - atividade_90d ausente do JSON')
    else:
        print(f'  Chaves: {sorted(atividade.keys()) if isinstance(atividade, dict) else type(atividade).__name__}')
        print(f'  total       : {atividade.get("total") if isinstance(atividade, dict) else "—"}')
        print(f'  ultima_data : {atividade.get("ultima_data") if isinstance(atividade, dict) else "—"}')
        if isinstance(atividade, dict) and isinstance(atividade.get('categorias'), dict):
            print(f'  categorias  :')
            for cat in CATEGORIAS_ATIVIDADE_90D:
                v = atividade['categorias'].get(cat, 0)
                print(f'    {cat:<14} : {v}')
        try:
            assert_atividade_90d_estruturada(atividade)
            print('  OK - assert_atividade_90d_estruturada passou')
        except WhitelistError as e:
            print(f'  FALHA - schema: {e}')
    print()

    # === DEFESA EM PROFUNDIDADE (recursiva) ===
    print('DEFESA EM PROFUNDIDADE (varredura recursiva):')
    todas = set()
    coletar_todas_chaves(dados, todas)
    print(f'  Chaves unicas em todo o JSON: {sorted(todas)}')
    suspeitas = []
    for k in todas:
        kl = str(k).lower()
        # 1. Match exato (pega `lawsuits_id`, `tasks_id`, `internal_note` como compostos)
        if kl in TERMOS_PROIBIDOS:
            suspeitas.append((k, kl, 'exato'))
            continue
        # 2. Match por token (pega `internal` em `internal_xxx`, etc.)
        for t in kl.split('_'):
            if t in TERMOS_PROIBIDOS:
                suspeitas.append((k, t, 'token'))
                break
    if suspeitas:
        print('  FALHA - chaves suspeitas:')
        for k, m, tipo in suspeitas:
            print(f'    "{k}" (match {tipo}: "{m}")')
    else:
        print('  OK - nenhum token/chave proibido encontrado')

    # E rodar o assert oficial
    try:
        assert_sem_termos_proibidos(dados)
        print('  OK - assert_sem_termos_proibidos passou')
    except WhitelistError as e:
        print(f'  FALHA - assert: {e}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
