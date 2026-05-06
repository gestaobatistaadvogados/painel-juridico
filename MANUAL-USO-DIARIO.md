# Manual de Uso Diário

Este manual descreve as tarefas rotineiras de operação do sistema. Após a Fase 3 (automação), a maior parte das tarefas será automática — mas é fundamental conhecer o procedimento manual para casos de exceção.

---

## 🎯 Casos de uso comuns

### Caso 1 — Cadastrar um novo cliente

Quando um novo cliente é admitido pelo escritório, o senhor precisa:

#### 1.1 — Cadastrar no ADVBox (já existe, fluxo padrão)
Cadastre o cliente normalmente no ADVBox como sempre fez. Anote o **ID interno** que o sistema atribui (geralmente um número de 6-7 dígitos).

#### 1.2 — Adicionar ao cadastro centralizado do sistema

Abra o arquivo `config/clientes.json` no Bloco de Notas (ou Notepad++).

Localize o array `"clientes": [` e adicione um novo registro **antes do `]` final**, no seguinte formato:

```json
{
  "id_advbox": 9000999,
  "nome_curto": "novo-cliente",
  "departamento": "direito_publico",
  "slug_url": "painel-novo-cliente-2026-a1b2",
  "ativo": true,
  "data_cadastro": "2026-05-15"
}
```

**Atenção a 3 detalhes:**
- `id_advbox`: o ID que o ADVBox atribuiu
- `slug_url`: deve terminar com 4 caracteres aleatórios (ex: `a1b2`, `x9k7`). Use letras minúsculas e números. **Esse sufixo é o que torna a URL secreta** — não use nome óbvio.
- `departamento`: um de `direito_privado`, `direito_imobiliario`, `direito_publico`

> **NÃO se esqueça da vírgula:** se o novo registro não for o último, deve haver vírgula após o `}` antes dele. Se for o último, não tem vírgula no final.

#### 1.3 — Regenerar dashboards

```powershell
cd C:\Users\Felipe\Desktop\Dashboards-Batista
python src\gerador_teste.py
```

#### 1.4 — Subir ao GitHub

```powershell
git add .
git commit -m "Adicionado cliente Novo Cliente Ltda"
git push
```

Em ~1 minuto, o novo cliente já estará no painel interno e seu dashboard estará online.

#### 1.5 — Enviar o link ao cliente

1. Abra o painel interno
2. Localize o novo cliente
3. Clique em **COPIAR LINK**
4. Envie ao cliente pelo canal preferido (e-mail, WhatsApp)

---

### Caso 2 — Atualizar dados de processos

> **Após a Fase 3 (automação), isto acontecerá sozinho todo dia às 5h.** O procedimento abaixo só é necessário para atualizações manuais (urgentes).

```powershell
cd C:\Users\Felipe\Desktop\Dashboards-Batista
python src\gerador_producao.py    # Use o gerador de produção (Fase 2 em diante)
git add .
git commit -m "Atualização manual"
git push
```

Em ~1 minuto, todos os dashboards estarão atualizados online.

---

### Caso 3 — Desativar um cliente (sem apagar)

Quando o cliente sai do escritório, ou um processo termina e o senhor quer remover o painel:

#### Opção A — Apenas desativar (recomendado)

No `config/clientes.json`, altere `"ativo": true` para `"ativo": false` no registro do cliente.

Rode novamente o gerador. O dashboard daquele cliente será removido da pasta `clientes/`, e o cliente desaparecerá do painel interno. **Mas o cadastro fica preservado** — basta reativar quando precisar.

#### Opção B — Apagar definitivamente

Remova o registro do cliente do `config/clientes.json` e a pasta `clientes/painel-xxx/` correspondente. Faça commit e push.

---

### Caso 4 — Trocar a URL secreta de um cliente

Útil se o senhor suspeitar que o link vazou ou queira renovar a segurança.

1. No `config/clientes.json`, localize o cliente
2. Altere o `slug_url`, mudando o sufixo aleatório (ex: `painel-rgp-2026-x9k7` → `painel-rgp-2026-y8m4`)
3. Rode o gerador
4. **Apague manualmente** a pasta antiga em `clientes/painel-rgp-2026-x9k7/` (a nova já foi criada com o novo nome)
5. Faça commit e push
6. Envie o **novo link** ao cliente

> **Atenção:** o link antigo continuará funcionando enquanto o GitHub Pages não atualizar (até 1 minuto). Não envie o novo link nesse intervalo.

---

### Caso 5 — Adicionar ou remover áreas do direito

O sistema vem com 14 áreas pré-cadastradas. Para adicionar/remover/renomear:

Abra `config/areas_direito.json` e edite. Cada área tem:
- `id`: identificador único interno
- `nome`: nome de exibição
- `cor`: cor em formato hex (ex: `#0A1628`)
- `icone`: identificador de ícone SVG (use os existentes; criar novos requer alterar código)
- `palavras_chave_advbox`: lista de termos que o sistema procura nos dados do ADVBox para classificar processos nessa área

> **Atenção:** se o senhor remover uma área que ainda tem processos vinculados, o sistema usará a "detecção automática" (modelo híbrido) para criar uma área alternativa.

---

### Caso 6 — Editar dados do escritório

Para mudar logo, cores, contatos, endereço:

Abra `config/escritorio.json` e edite os campos. Para trocar o logo, substitua o arquivo `config/logo.png` (mantenha o mesmo nome).

Rode o gerador para aplicar.

---

### Caso 7 — Sobre o Painel de Produtividade do Escritório

Cada dashboard de cliente possui, logo abaixo do banner, um **Painel de Produtividade** que mostra ao cliente o trabalho realizado pelo escritório nos últimos 90 dias (peças, audiências, reuniões, despachos e outras diligências).

#### Na Fase 1 (atual — dados mock)

Os números desse painel vêm do arquivo `mock_data/diligencias_mock.json`. Para ajustar manualmente os números exibidos a um cliente específico:

1. Abra `mock_data/diligencias_mock.json`
2. Localize a seção do `customer_id` desejado (ex: `"9000001"`)
3. Edite os valores de cada categoria (`pecas`, `audiencias`, `reunioes`, `despachos`, `outros`) e o `total` (deve bater com a soma)
4. Atualize a `ultima_atividade` se desejar (data, tipo e descrição)
5. Rode o gerador

#### Na Fase 2 em diante (API real)

Os dados serão puxados automaticamente do ADVBox via API. O senhor não precisará mais editar este arquivo manualmente — a integração foi documentada em `MANUAL-CLAUDE-CODE.md` (Passo 5.1 da Fase 2).

> **Importante:** o cálculo automático considera **todas as diligências dos últimos 90 dias** registradas no ADVBox para aquele cliente, em todos os processos. Se o senhor quer que um lançamento apareça no painel do cliente, registre-o vinculado ao cliente correto no ADVBox.

---

## 📝 Editores recomendados

Para editar arquivos `.json`, recomenda-se:

| Editor | Vantagens | Onde baixar |
|---|---|---|
| **Notepad++** (mais simples) | Realça erros de sintaxe, gratuito | https://notepad-plus-plus.org/ |
| **Visual Studio Code** (profissional) | Avisa de erros, integração com Git | https://code.visualstudio.com/ |

> **NÃO** use Bloco de Notas comum — ele pode salvar em formato errado e quebrar os arquivos.

---

## 🛡️ Boas práticas operacionais

### Sempre que mexer em arquivos de configuração:

1. **Faça backup antes**: copie o arquivo `.json` que vai editar para `.json.bak`
2. **Edite com cuidado**: JSON é sensível a vírgulas e aspas
3. **Valide rodando o gerador**: se houver erro de sintaxe, o gerador acusa
4. **Só faça commit/push depois de validar visualmente**

### Sobre o token da API ADVBox:

- **NUNCA** suba o token ao GitHub
- O arquivo `config/token_advbox.txt` está no `.gitignore` (não será incluído nos commits)
- Após a Fase 3, o token vai para **GitHub Secrets** (criptografado)

### Sobre a pasta `clientes/`:

- O conteúdo dela é **gerado** pelo gerador
- Se o senhor apagar a pasta inteira, basta rodar o gerador para recriar
- Não edite arquivos HTML lá manualmente — eles serão sobrescritos no próximo ciclo

---

## 🆘 Quando algo der errado

### Gerador acusa erro de JSON

Mensagem como: `json.decoder.JSONDecodeError: Expecting ',' delimiter: line 12 column 5`

**O que fazer:**
1. Abra o arquivo apontado (ex: `clientes.json`) no Notepad++
2. Vá à linha indicada (ex: linha 12)
3. Verifique se há vírgula faltando ou aspas erradas
4. Corrija e salve

### Gerador roda mas falta algum cliente

**O que fazer:**
1. Verifique se o cliente está com `"ativo": true` em `clientes.json`
2. Verifique se o `id_advbox` corresponde a algum cliente em `mock_data/customers_mock.json` (ou na resposta da API real, na Fase 2)

### Site online não atualiza

**O que fazer:**
1. Aguarde 1-2 minutos (GitHub Pages tem cache)
2. Force atualização no navegador: `Ctrl + Shift + R`
3. Confirme que o `git push` foi bem-sucedido (sem erro)

---

## 📞 Em caso de dúvida

Use o Claude Code para perguntar:

```powershell
claude
```

E pergunte algo como: *"Estou com erro X ao rodar o gerador. O que faço?"*

Ele tem acesso ao código completo do projeto e consegue diagnosticar.
