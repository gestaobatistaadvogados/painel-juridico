"""
Cliente Python para a API REST do ADVBox.

Encapsula autenticacao, throttle (30 GET/min), retry em erros temporarios
e tratamento de erros 401/403 com mensagens em portugues.

Le ADVBOX_API_TOKEN e ADVBOX_API_URL do arquivo .env na raiz do projeto.
"""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv


RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / '.env')


class AdvboxError(Exception):
    """Erro generico em chamadas a API do ADVBox."""


class AdvboxAuthError(AdvboxError):
    """Token invalido (HTTP 401) ou sem permissao (HTTP 403)."""


class AdvboxClient:
    """Cliente para a API do ADVBox.

    Carrega ADVBOX_API_TOKEN e ADVBOX_API_URL do .env e expoe metodos
    de alto nivel para clientes, processos, andamentos e tarefas.
    """

    TIMEOUT = 30
    MAX_TENTATIVAS = 3
    INTERVALO_MIN_SEGUNDOS = 2.0  # 30 GET/min => 1 a cada 2 segundos
    USER_AGENT = 'L-Batista-Dashboards/1.0 (+contato: gestaobatistaadvogados@gmail.com)'

    def __init__(self):
        token = os.getenv('ADVBOX_API_TOKEN')
        url_base = os.getenv('ADVBOX_API_URL')

        if not token or token == 'COLE_O_TOKEN_AQUI':
            raise AdvboxError(
                'ADVBOX_API_TOKEN nao foi carregado do .env. '
                'Verifique se o arquivo .env existe na raiz do projeto '
                'e contem o token real (nao o placeholder).'
            )
        if not url_base:
            raise AdvboxError(
                'ADVBOX_API_URL nao foi carregado do .env. '
                'Verifique a variavel no arquivo .env.'
            )

        self._token = token
        self._url_base = url_base.rstrip('/')
        self._ultimo_request = 0.0

    def _headers(self):
        """Monta os headers padrao das requisicoes (Bearer + JSON)."""
        return {
            'Authorization': f'Bearer {self._token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': self.USER_AGENT,
        }

    def _aguardar_throttle(self):
        """Garante intervalo minimo entre requisicoes para respeitar rate limit."""
        decorrido = time.monotonic() - self._ultimo_request
        if decorrido < self.INTERVALO_MIN_SEGUNDOS:
            time.sleep(self.INTERVALO_MIN_SEGUNDOS - decorrido)

    def _request(self, endpoint, params=None):
        """Executa GET com throttle, retry e tratamento de erros."""
        url = f"{self._url_base}/{endpoint.lstrip('/')}"
        ultimo_erro = None

        for tentativa in range(1, self.MAX_TENTATIVAS + 1):
            self._aguardar_throttle()
            try:
                resp = requests.get(
                    url,
                    headers=self._headers(),
                    params=params,
                    timeout=self.TIMEOUT,
                )
                self._ultimo_request = time.monotonic()
            except (requests.Timeout, requests.ConnectionError) as e:
                ultimo_erro = e
                self._ultimo_request = time.monotonic()
                if tentativa < self.MAX_TENTATIVAS:
                    time.sleep(2 ** tentativa)
                    continue
                raise AdvboxError(
                    f'Falha de conexao apos {self.MAX_TENTATIVAS} tentativas: {e}'
                ) from e

            if resp.status_code == 401:
                raise AdvboxAuthError(
                    'Token ADVBox invalido (HTTP 401). '
                    'Verifique ADVBOX_API_TOKEN no arquivo .env.'
                )
            if resp.status_code == 403:
                raise AdvboxAuthError(
                    'Acesso negado pela API ADVBox (HTTP 403). '
                    'O token nao tem permissao para este recurso.'
                )

            if 500 <= resp.status_code < 600:
                ultimo_erro = AdvboxError(
                    f'Erro do servidor ADVBox (HTTP {resp.status_code}).'
                )
                if tentativa < self.MAX_TENTATIVAS:
                    time.sleep(2 ** tentativa)
                    continue
                raise ultimo_erro

            if not resp.ok:
                raise AdvboxError(
                    f'Requisicao falhou (HTTP {resp.status_code}): '
                    f'{resp.text[:300]}'
                )

            # HTTP 204 No Content: semantica "OK mas sem corpo". A API ADVBox
            # retorna 204 em /movements/{id} quando o processo nao tem nenhum
            # andamento — devolvemos envelope vazio para o caller tratar como
            # lista vazia.
            if resp.status_code == 204 or not resp.text.strip():
                return {'data': []}

            try:
                return resp.json()
            except (json.JSONDecodeError, ValueError) as e:
                ctype = resp.headers.get('Content-Type', '?')
                snippet = (resp.text or '').strip()[:200]
                raise AdvboxError(
                    f'Resposta nao e JSON valido em {endpoint!r} '
                    f'(HTTP {resp.status_code}, Content-Type={ctype}, '
                    f'body_len={len(resp.text or "")}). '
                    f'Snippet: {snippet!r}'
                ) from e

        raise AdvboxError(f'Falha inesperada apos retries: {ultimo_erro}')

    def get_settings(self):
        """Retorna metadados da conta ADVBox (usuarios, fases, tipos, categorias).

        Endpoint recomendado pela documentacao oficial como primeiro teste
        de conectividade — nao recebe parametros.
        """
        return self._request('settings')

    def get_customers(self, limit=1000, offset=0):
        """Retorna uma pagina de clientes (limit/offset).

        A API da ADVBox ignora silenciosamente page/per_page — o servidor usa
        limit (max 1000) e offset. A resposta tras totalCount para varredura.
        """
        return self._request(
            'customers',
            params={'limit': limit, 'offset': offset},
        )

    def iter_customers(self, lote=1000):
        """Itera por todos os customers da base usando paginacao limit/offset."""
        offset = 0
        while True:
            resp = self.get_customers(limit=lote, offset=offset)
            data = resp.get('data') if isinstance(resp, dict) else None
            if not data:
                return
            for c in data:
                yield c
            total = resp.get('totalCount') if isinstance(resp, dict) else None
            offset += len(data)
            if total is not None and offset >= total:
                return
            if len(data) < lote:
                return

    def get_customer(self, customer_id):
        """Retorna os dados completos de um cliente especifico (cadastro + processos vinculados)."""
        return self._request(f'customers/{customer_id}')

    def get_lawsuits(self, customer_id=None, limit=1000, offset=0):
        """Retorna uma pagina de processos. Se customer_id for informado, filtra por aquele cliente."""
        params = {'limit': limit, 'offset': offset}
        if customer_id is not None:
            params['customer_id'] = customer_id
        return self._request('lawsuits', params=params)

    def get_movements(self, lawsuit_id):
        """Retorna a lista de andamentos (movimentacoes processuais) do processo informado."""
        return self._request(f'movements/{lawsuit_id}')

    def get_history(self, lawsuit_id):
        """Retorna o historico de tarefas/atividades internas vinculadas ao processo."""
        return self._request(f'history/{lawsuit_id}')

    def get_tasks(self, customer_id=None, days=90):
        """Retorna tarefas dos ultimos N dias (default 90) para o painel de produtividade.

        Se customer_id for informado, filtra por aquele cliente.
        """
        data_inicio = (datetime.now() - timedelta(days=days)).date().isoformat()
        params = {'start_date': data_inicio}
        if customer_id is not None:
            params['customer_id'] = customer_id
        return self._request('tasks', params=params)
