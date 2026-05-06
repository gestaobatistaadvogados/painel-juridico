# Manual de Condução das Fases 2 e 3 com Claude Code

Este é o manual mais importante do projeto. Ele orienta o senhor a usar o **Claude Code** (já instalado no seu PC) para conduzir as próximas fases do projeto: a integração com a API real do ADVBox e a automação na nuvem.

> **Pressuposto:** o senhor já concluiu o `MANUAL-INSTALACAO.md` e o sistema está rodando localmente com dados mock.

---

## 🤔 O que é o Claude Code?

O **Claude Code** é uma versão do Claude (esta inteligência artificial) que roda no terminal do seu PC. Ele consegue:

- Ler, criar e editar arquivos do projeto
- Rodar comandos do sistema (como `python`, `git`)
- Diagnosticar erros e propor correções
- Conduzir tarefas complexas automaticamente

Pense nele como um **estagiário sênior técnico**: o senhor descreve o que quer, ele executa e mostra o resultado para sua aprovação antes de continuar.

---

## 🚀 Como abrir o Claude Code

1. Abra o **PowerShell** (não precisa ser administrador)
2. Navegue até a pasta do projeto:
   ```powershell
   cd C:\Users\Felipe\Desktop\Dashboards-Batista
   ```
3. Execute:
   ```powershell
   claude
   ```
4. Aguarde alguns segundos até aparecer o prompt do Claude Code (geralmente algo como `> ` ou um quadrado de input)

> **Importante:** sempre abra o Claude Code **dentro da pasta do projeto**. Ele só consegue mexer nos arquivos da pasta onde foi aberto.

---

## 📋 FASE 2 — Integração com API ADVBox

Esta fase substitui os dados simulados (mock) por dados reais vindos do ADVBox.

### Pré-requisitos

✅ Token da API ADVBox em mãos
✅ Sistema rodando localmente com mock (já validado)
✅ Claude Code aberto na pasta do projeto

### Passo 1 — Guardar o token com segurança

No Claude Code, **copie e cole exatamente este prompt**:

```
Quero guardar o token da API ADVBox de forma segura no projeto.

Crie um arquivo chamado `.env` na raiz do projeto com a seguinte estrutura:

ADVBOX_API_TOKEN=COLE_O_TOKEN_AQUI
ADVBOX_API_URL=https://app.advbox.com.br/api/v1

E confirme que o `.env` está listado no `.gitignore` para nunca subir ao GitHub.

Após criar, peça-me para confirmar antes de prosseguir.
```

O Claude Code vai criar o arquivo. **Em seguida, abra o arquivo `.env` no Notepad++** e substitua `COLE_O_TOKEN_AQUI` pelo seu token real.

> **Por que pelo Notepad e não pelo Claude Code?** Para que o token nunca apareça no histórico do Claude. É uma camada extra de segurança.

### Passo 2 — Construir o cliente da API

No Claude Code, **copie e cole**:

```
Agora preciso que você construa o cliente da API ADVBox.

Crie um arquivo `src/advbox_client.py` que:
1. Lê o token do arquivo .env
2. Implementa funções para chamar os endpoints documentados:
   - GET /customers (lista de clientes)
   - GET /lawsuits (lista de processos)
   - GET /movements/{lawsuit_id} (andamentos de um processo)
3. Trata os rate limits documentados (GET 30/min)
4. Tem timeout de 30s e retry em caso de falha temporária
5. Documenta cada função em português

Após criar, mostre-me o código produzido para eu validar antes de prosseguir.
```

> O Claude Code mostrará o código. **Confira se ele tratou os rate limits** (não pode bombardear a API). Aprove a criação.

### Passo 3 — Testar a conexão

```
Antes de integrar ao gerador principal, vamos testar a conexão.

Crie um script `src/teste_api.py` que:
1. Conecta na API do ADVBox usando o cliente que você acabou de criar
2. Lista os primeiros 5 clientes do ADVBox
3. Imprime o nome de cada um na tela

Rode esse script e me mostre o resultado. Se der erro, diagnostique.
```

**Resultado esperado:**
```
✅ Conexão com ADVBox OK
Cliente 1: NOME DO PRIMEIRO CLIENTE
Cliente 2: NOME DO SEGUNDO CLIENTE
... (e assim por diante)
```

> **Se der erro de autenticação:** o token está errado ou expirou. Verifique no painel do ADVBox.

### Passo 4 — Adaptar o gerador para usar API real

```
Agora vamos criar o gerador de produção.

Crie um arquivo `src/gerador_producao.py` que:
1. Tem a MESMA estrutura do `gerador_teste.py`
2. MAS, em vez de ler dos arquivos JSON em mock_data/, busca os dados via cliente API:
   - customers_data → GET /customers
   - lawsuits_data → percorre os IDs dos clientes e busca cada lawsuit
   - movements_data → para cada lawsuit, busca seus movements

3. Implementa cache local (evita chamar API 100 vezes em sequência se já tiver os dados):
   - Salva resposta em `cache/customers.json`, `cache/lawsuits.json`, etc.
   - Cache expira em 24 horas
   - Permite forçar refresh com argumento --force

4. Tem flag --apenas-um para gerar dashboard de um cliente específico (útil para testes)

Mostre-me o código produzido antes de rodar.
```

### Passo 5 — Validar com 1 cliente real

```
Vamos testar com um cliente real antes de processar todos.

Pegue o ID de um cliente real no ADVBox que tenha poucos processos (3-5).
Adicione esse cliente ao config/clientes.json (com slug_url novo, departamento direito_publico ou direito_privado).

Depois rode:
python src/gerador_producao.py --apenas-um <ID_DO_CLIENTE>

Mostre-me o resultado e abra o HTML gerado.
```

**Validação humana:** abra o dashboard gerado e confirme:
- Os processos listados batem com o que o senhor vê no ADVBox
- Os números de processo (CNJ) estão corretos
- O nome do cliente está correto
- A área classificada faz sentido

### Passo 5.1 — Integrar o Painel de Produtividade (diligências reais)

Atualmente, o painel de produtividade do dashboard usa dados simulados em `mock_data/diligencias_mock.json`. Para puxar dados reais do ADVBox:

```
Quero integrar o painel de produtividade com a API ADVBox.

Atualize o cliente da API (`src/advbox_client.py`) para incluir
um método que busque as DILIGÊNCIAS dos últimos 90 dias por cliente.

Provavelmente isso envolve consultar:
- GET /tasks (audiências, reuniões, despachos) — filtrar por customer_id
- GET /history ou /movements (peças e demais lançamentos manuais)
- Filtrar por data dos últimos 90 dias

Retorne um dicionário no mesmo formato de `diligencias_mock.json`:
{
  "<customer_id>": {
    "total": <int>,
    "pecas": <int>,
    "audiencias": <int>,
    "reunioes": <int>,
    "despachos": <int>,
    "outros": <int>,
    "ultima_atividade": {
      "data": "AAAA-MM-DD",
      "tipo": "<categoria>",
      "descricao": "<texto>"
    }
  }
}

Depois, atualize `src/gerador_producao.py` para usar essa nova função
no lugar de carregar o arquivo mock.

Antes de rodar, mostre-me a documentação da API que você consultou
e o mapeamento de campos que pretende usar (qual campo do ADVBox
classificou como "peças", qual como "audiências", etc.).
```

> **Importante:** o ADVBox pode ter classificações próprias diferentes das categorias do painel. Faça o mapeamento explícito (ex: "tipo X do ADVBox = peças no painel"). Validar esse mapeamento com o senhor é essencial para os números fazerem sentido.

### Passo 6 — Migrar todos os clientes reais

Quando estiver tudo certo:

```
Vou agora cadastrar todos os clientes reais do escritório.

Por favor, me oriente passo a passo. Para cada cliente real,
você me pergunta:
1. Qual o ID dele no ADVBox?
2. Qual o departamento (privado/imobiliario/publico)?
3. Algum nome curto preferido (ou usa o padrão)?

Após cada cadastro, rode o gerador para esse cliente apenas
e me mostre o resultado.
```

> **Conduza com paciência.** Para cada cliente real, valide o dashboard antes de passar ao próximo. Erros descobertos cedo são fáceis de corrigir.

### Passo 7 — Conclusão da Fase 2

Quando todos os clientes reais estiverem migrados:

```
A Fase 2 está concluída. Todos os clientes reais estão cadastrados
e seus dashboards refletem dados reais do ADVBox.

Faça um commit final:
git add .
git commit -m "Fase 2 concluída - integração ADVBox real"
git push

Em seguida, mostre-me um resumo do estado do projeto.
```

---

## ⚙️ FASE 3 — Automação com GitHub Actions

Esta fase faz o sistema rodar **sozinho na nuvem**, todo dia às 5h da manhã.

### Passo 1 — Subir o token aos GitHub Secrets

**Esta etapa é manual** (você faz no navegador, não no Claude Code):

1. Acesse: `https://github.com/dirprivadoleonardobatista-ai/dashboards-batista/settings/secrets/actions`
2. Clique em **New repository secret**
3. Nome: `ADVBOX_API_TOKEN`
4. Value: cole o token real
5. Clique em **Add secret**

> O GitHub agora **criptografa** o token. Nem mesmo o senhor consegue ver o valor depois — só o GitHub Actions consegue lê-lo durante a execução.

### Passo 2 — Criar o GitHub Action

No Claude Code:

```
Crie o GitHub Action para automação diária.

Crie o arquivo `.github/workflows/atualizar-dashboards.yml` que:
1. Roda automaticamente todo dia às 5h da manhã (horário de Brasília = 8h UTC)
2. Permite execução manual (workflow_dispatch)
3. Faz checkout do repositório
4. Configura Python 3.11
5. Instala as dependências (pip install -r requirements.txt)
6. Lê o token do secrets como variável de ambiente
7. Roda src/gerador_producao.py
8. Faz commit dos HTMLs gerados
9. Push automaticamente
10. Em caso de falha, marca o workflow como failed (notifica por e-mail automaticamente)

Mostre o YAML para eu validar.
```

### Passo 3 — Testar a automação

```
Vamos disparar o workflow manualmente para testar.

Faça commit e push do arquivo do workflow:
git add .github/workflows/atualizar-dashboards.yml
git commit -m "Configuração GitHub Actions"
git push

Depois me oriente a disparar manualmente pelo navegador.
```

**No navegador:**
1. Acesse `https://github.com/dirprivadoleonardobatista-ai/dashboards-batista/actions`
2. Clique no workflow "Atualizar Dashboards"
3. Clique em **Run workflow** → **Run workflow** (botão verde)
4. Aguarde 2-5 minutos
5. Confirme que o status fica verde ✅

### Passo 4 — Validação final

Acesse:
```
https://dirprivadoleonardobatista-ai.github.io/dashboards-batista/painel-interno.html
```

Confira:
- ✅ Painel interno atualizado
- ✅ Todos os dashboards funcionando
- ✅ Data de "Última atualização" mostrando há poucos minutos

**O sistema agora está 100% autônomo.** O senhor pode desligar o PC, viajar, ficar uma semana sem acessar — e o sistema continua atualizando todo dia às 5h.

---

## 🔄 Procedimentos pós-implantação

### Como cadastrar novo cliente após Fase 3

Agora há **duas formas** de cadastrar:

#### Forma A — Pelo PC (como antes)
Edite `config/clientes.json` localmente, faça push. O próximo ciclo de atualização vai gerar o novo dashboard.

#### Forma B — Pelo navegador (sem PC)
1. Acesse `https://github.com/dirprivadoleonardobatista-ai/dashboards-batista/blob/main/config/clientes.json`
2. Clique no ícone de **lápis** (editar) no canto superior direito
3. Edite o JSON diretamente no navegador
4. Role para baixo, clique em **Commit changes**
5. O GitHub Action dispara automaticamente

### Como ver os logs de execução

Acesse `https://github.com/dirprivadoleonardobatista-ai/dashboards-batista/actions` e clique em qualquer execução para ver:
- Quanto tempo levou
- Se houve erros
- Quantos dashboards foram regenerados

### Como pausar a automação temporariamente

No arquivo `.github/workflows/atualizar-dashboards.yml`, comente a seção `schedule:` (adicione `#` no início das linhas). Faça push.

Para reativar, descomente.

---

## 🆘 Recuperação de desastre

### Cenário: GitHub fora do ar

Improvável, mas possível. Procedimentos:
1. O sistema continua disponível para clientes (GitHub Pages tem alta disponibilidade)
2. Apenas a atualização diária fica suspensa até o GitHub voltar
3. Não é necessária nenhuma ação sua

### Cenário: API ADVBox fora do ar

O GitHub Action vai falhar e enviar e-mail. Quando o ADVBox voltar:
1. Acesse a aba Actions no GitHub
2. Clique em "Run workflow" para forçar nova execução
3. Confirme sucesso

### Cenário: Quero desfazer uma alteração ruim

Git permite **voltar no tempo**. No Claude Code:

```
Quero desfazer o último commit que fiz (ele quebrou algo).
Use git revert para reverter sem perder o histórico.
```

### Cenário: Quero migrar para outro PC ou outro sócio

```
Como o repositório está no GitHub, basta o sócio:
1. Instalar Python, Git, Claude Code
2. Clonar o repositório: git clone https://github.com/...
3. Pronto - o sistema está disponível no PC dele
```

---

## 🎓 Recomendações finais

1. **Documente decisões:** sempre que mudar algo importante, faça commit com mensagem descritiva
2. **Não exclua a pasta `mock_data/`:** ela serve para testes futuros sem onerar a API ADVBox
3. **Eventualmente faça backup:** o GitHub é redundante, mas um clone local mensal é boa prática
4. **Convide os outros sócios:** dê acesso ao repositório (Settings → Manage access → Invite collaborator)
5. **Monitore o consumo de minutos do GitHub Actions:** o limite gratuito é 2.000 min/mês — uma execução diária consome ~5 min/dia = 150 min/mês (bem dentro do limite)

---

## 📞 Quando pedir ajuda

Se algo travar, abra o Claude Code e descreva o problema com:
- O que estava tentando fazer
- O que apareceu na tela (mensagem exata)
- O que esperava que acontecesse

Exemplo de bom pedido:
> *"Tentei rodar `python src/gerador_producao.py` e apareceu erro `ModuleNotFoundError: No module named 'requests'`. Esperava que rodasse normalmente como antes."*

O Claude Code vai diagnosticar e propor solução.
