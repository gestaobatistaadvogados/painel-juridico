# Pasta de Workflows do GitHub Actions

Esta pasta abrigará o workflow de automação (Fase 3 do projeto).

## Status atual: PENDENTE

O arquivo `atualizar-dashboards.yml` será criado durante a Fase 3, conduzida pelo Claude Code conforme `MANUAL-CLAUDE-CODE.md`.

## O que ele fará quando estiver implementado

- Executar o gerador de produção todo dia às 5h da manhã (horário de Brasília)
- Permitir execução manual via botão no GitHub
- Buscar token da API ADVBox dos GitHub Secrets (criptografado)
- Gerar todos os dashboards com dados reais
- Fazer commit e push automático
- Notificar por e-mail em caso de falha

## NÃO crie este arquivo manualmente

A criação correta do workflow envolve detalhes técnicos (sintaxe YAML, permissões, autenticação) que devem ser conduzidos pelo Claude Code.

Siga o passo a passo em `MANUAL-CLAUDE-CODE.md` → seção FASE 3.
