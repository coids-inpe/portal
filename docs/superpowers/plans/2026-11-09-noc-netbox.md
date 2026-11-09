# NOC NetBox Implementation Plan

**Goal:** selecionar dispositivos físicos do NetBox nas ocorrências do turno e preservar os históricos locais.
**Architecture:** referência externa opcional em Ocorrencia, busca autenticada no backend e identificação histórica sem consulta HTTP na leitura. Preservar FK antiga e consumidores existentes.
**Tech Stack:** Django, requests, JavaScript nativo, pytest-django.
**Spec:** `docs/superpowers/specs/2026-11-09-noc-netbox-design.md`.

## Restrições

Monitoramento, alertas Nagios e core ficam intactos. Não excluir dados nem tabelas. Manter alterações preexistentes do usuário. Aplicar somente migração aditiva no banco local e não executar scripts de coleta.

## Execução nesta sessão

- [x] Escrever e executar testes falhando para criação externa, edição legada, identificação histórica, falhas de API e autorização.
- [x] Adicionar referência externa e identificação histórica a `apps/infra/models.py`; gerar migração em `apps/infra/migrations/`.
- [x] Criar `apps/noc/netbox.py` com `search_devices(query, offset)` e `get_device(id)`, reutilizando configuração e autenticação do cliente existente; erros distinguem indisponibilidade, permissão e objeto ausente.
- [x] Criar formulário e widget do NOC em `apps/noc/forms.py` e `apps/noc/widgets.py`; busca paginada, seleção validada e histórico preservado em edições sem troca de equipamento.
- [x] Criar endpoint autenticado em `apps/noc/views.py` e rota em `apps/noc/urls.py`; conectar inline próprio em `apps/noc/admin.py`.
- [x] Atualizar templates NOC para usar identificação histórica e link seguro. Adicionar JavaScript/CSS do seletor, incluindo suporte a linhas dinâmicas do admin.
- [x] Executar testes novos e regressões pertinentes, `check`, `makemigrations --check --dry-run` e `git diff --check`.
- [x] Revisar a implementação; corrigir problemas antes de subir.
- [x] Conferir API real, preservar backup local, aplicar migração e validar servidor na porta 8001 e fluxo visual do formulário.
- [x] Documentar o caminho de teste e informar resultados e limitações.

## Verificação

`python -m pytest -q apps/noc/tests/test_netbox_occurrences.py` cobre o contrato novo. Acrescentar regressões de modelos/formulários infra e integrações NetBox existentes conforme arquivos alterados. Servidor real deve responder ao login e formulário NOC com assets e endpoint de busca. Dados temporários de verificação devem ser revertidos ou removidos.

## Resultado da execução

- 48 testes passaram na seleção de NOC e integrações NetBox/Datacenter.
- `check`, verificação de migrações, sintaxe JavaScript e `git diff --check` passaram.
- Quatro falhas antigas de modelos/formulários infra foram reproduzidas também em cópia do HEAD anterior, sem esta atualização; não foram alteradas.
- Revisão corrigiu apresentação do equipamento em modo somente leitura e edição de históricos sem equipamento.
- Navegador real: formulário respondeu 200, buscou 20 dispositivos, paginou para 40 e salvou ocorrência com `dcim.device`, ID 186, nome histórico e FK local vazia. Registro e sessão temporários removidos.
- Ajustado refresh do bootstrap-select já usado pelo tema para apresentar os resultados da busca.
- A listagem administrativa apresenta um erro JavaScript legado em `admin/js/actions.js:159`, fora do seletor e sem impedir o salvamento; nenhum arquivo dessa funcionalidade foi alterado.
- Migração aditiva `infra.0022` aplicada no MySQL local. Backup prévio da tabela de ocorrências em `/tmp/portal-ocorrencias-before-netbox-20261109.json` (permissão 600; zero ocorrências no banco local antes do teste).
- Atualização disponível em `http://localhost:8001/admin/noc/checklist/add/`. Monitoramento e alertas Nagios preservados.
