"""
Cache local em arquivos JSON para chamadas a API ADVBox.

Cada chamada e gravada em cache/<chave>.json com timestamp embutido.
Entradas expiram apos 24h. Util durante desenvolvimento para evitar
chamadas repetidas a API e respeitar o rate limit (30 GET/min).

Uso tipico:
    from cache import cache_get, cache_set

    dados = cache_get('customers_14083291')
    if dados is None:
        dados = client.get_customer(14083291)
        cache_set('customers_14083291', dados)
"""

import json
import time
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / 'cache'
TTL_SEGUNDOS = 24 * 60 * 60


def _path(chave):
    return CACHE_DIR / f'{chave}.json'


def cache_get(chave):
    """Retorna os dados gravados para a chave, ou None se ausente/expirado/corrompido."""
    p = _path(chave)
    if not p.exists():
        return None
    try:
        with p.open('r', encoding='utf-8') as f:
            envelope = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    cached_at = envelope.get('_cached_at')
    if not isinstance(cached_at, (int, float)):
        return None
    if time.time() - cached_at > TTL_SEGUNDOS:
        return None
    return envelope.get('data')


def cache_set(chave, dados):
    """Grava os dados no cache com timestamp atual (cria a pasta se necessario)."""
    CACHE_DIR.mkdir(exist_ok=True)
    agora = time.time()
    envelope = {
        '_cached_at': agora,
        '_cached_at_iso': datetime.fromtimestamp(agora).isoformat(timespec='seconds'),
        'data': dados,
    }
    p = _path(chave)
    with p.open('w', encoding='utf-8') as f:
        json.dump(envelope, f, ensure_ascii=False, indent=2)


def cache_invalidate(chave):
    """Remove uma entrada especifica do cache (forca refresh na proxima chamada)."""
    p = _path(chave)
    if p.exists():
        p.unlink()


def cache_clear():
    """Remove todos os arquivos *.json da pasta cache/."""
    if CACHE_DIR.exists():
        for arquivo in CACHE_DIR.glob('*.json'):
            arquivo.unlink()
