# Alertas Nagios do NOC com NetBox

Escopo aprovado pelo usuário: selecionar equipamento físico do NetBox e serviço Nagios existente no relatório do turno. Preservar relatórios antigos, tabelas locais e todo o módulo de monitoramento. Sem recebimento automático de alertas.

## Implementação

- [x] Testar criação, edição offline, transição explícita de vínculo legado, falha de API, permissões, e-mail misto e admin somente leitura.
- [x] Manter a tabela intermediária `ChecklistServidorNagiosServico`, tornar o vínculo legado opcional e adicionar referência NetBox, serviço e nomes históricos. Validar uma única origem completa.
- [x] Reutilizar widget e API existentes no formulário do bloco Nagios. Manter os campos novos vazios para preservar um alerta legado; preencher ambos para reassociá-lo.
- [x] Ampliar busca para editores autorizados de alertas, mantendo exigência de acesso ao checklist e administração.
- [x] Renderizar alertas antigos e novos pelo vínculo intermediário no e-mail, sem consultar a rede. Preservar o M2M legado para compatibilidade.
- [x] Rodar regressões NOC e NetBox, check Django, migrações e revisão de código.
- [x] Preservar backup da tabela alterada, aplicar somente a migração nova no banco local e validar formulário/busca/salvamento no navegador, removendo dados temporários.

## Dados e apresentação

Referência externa: `dcim.device`, ID e nome do equipamento; FK para `monitoramento.NagiosServicos` com proteção de exclusão e nome histórico do serviço. A FK antiga para `infra.ServidorNagiosServico` permanece opcional, sem migração automática dos dados. Acesso somente leitura exibe a identificação completa do vínculo por método próprio do inline.

O acesso por `checklist.alerta_monitoramento` continua representando vínculos legados; `checklist.alertas_nagios` apresenta todos os vínculos para relatórios. Não alterar relações/modelos de monitoramento nem criar servidor local quando um alerta é salvo.

## Resultado

- 66 testes passaram: 18 novos cenários Nagios, 28 de ocorrências NOC e 20 regressões NetBox/Datacenter.
- Verificação Django, detecção de migrações pendentes no código e `git diff --check` passaram.
- Revisão independente não encontrou problemas acionáveis.
- Backup privado prévio da tabela em `/tmp/portal-noc-nagios-before-netbox-20261109.json`; o banco local tinha zero vínculos Nagios. Migração `noc.0005` aplicada apenas no ambiente local.
- Navegador: busca real de equipamento ID 186, seleção de serviço temporário e salvamento do relatório na porta 8001. Conferidos no banco os nomes históricos, FK legada vazia e ausência de novos equipamentos/vínculos de servidor local. E-mail e tela de edição validados.
- Serviço Nagios, relatório, alerta e sessão temporários removidos após a validação. O catálogo local de serviços continua vazio: cadastrar um serviço antes de testar manualmente.
- Arquivos de monitoramento e core não foram modificados.

## Implantação e reversão

Aplicar `python manage.py migrate` no ambiente de destino após backup e ensaio em cópia do banco. Preservar a migração antiga e os vínculos existentes. Não reverter o esquema de `noc.0005` enquanto houver vínculos externos: a versão antiga exige FK legada preenchida e não apresenta os novos alertas nos e-mails. Planejar uma reversão com exportação/preservação desses registros, sem descartar dados.
