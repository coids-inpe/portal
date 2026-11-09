# NOC com inventário do NetBox — proposta para revisão

Status: primeira entrega autorizada pelo usuário e implementada em 2026-11-09; entregas posteriores permanecem propostas.

## Objetivo e limites

Permitir selecionar equipamentos do NetBox nas ocorrências dos relatórios de turno, mantendo no portal os textos, responsáveis, status e históricos.

O usuário excluiu o monitoramento desta etapa. Não alterar suas telas, modelos, consultas, coletores, integrações Xen/NetApp/Kafka, tarefas ou históricos. Não remover tabelas de inventário nem desativar cadastros dos quais esses fluxos dependem.

A primeira entrega considera dispositivos físicos (`dcim.device`). É uma premissa para revisão, baseada no seletor atual, que exclui servidores virtuais. VMs, redes e racks poderão entrar em entregas próprias.

## Dependências encontradas

- `apps/noc/admin.py`: o checklist inclui responsáveis, alertas Nagios e ocorrências.
- `apps/infra/models.py`: `Ocorrencia` referencia `Equipamento` por FK opcional com exclusão em cascata; também referencia `Checklist`.
- `apps/infra/forms.py`: `OcorrenciaChecklistInLineForm` oferece equipamentos do banco local.
- `apps/infra/admin.py`: `OcorrenciaChecklistInLine` incorpora esse formulário ao NOC; outros formulários de ocorrência são usados pelo inventário legado.
- Templates do NOC exibem `ocorrencia.equipamento` no formulário e no e-mail, inclusive nas ocorrências abertas de outros turnos.
- `ChecklistServidorNagiosServico` referencia `infra.ServidorNagiosServico`, que referencia um servidor local e um serviço Nagios.
- `apps/infra/utils/netbox.py` já fornece acesso à API. Seus contratos existentes devem permanecer compatíveis.

## Primeira entrega: ocorrências do turno

1. O operador pesquisa dispositivos pelo portal, com consulta paginada ao NetBox pelo backend.
2. O resultado apresenta nome e contexto suficiente para distinguir homônimos, como site e rack quando disponíveis.
3. O backend valida o ID selecionado consultando o dispositivo e grava a ocorrência no banco do portal.
4. A ocorrência guarda tipo do objeto, ID e nome no momento da associação. Somente o relato e demais dados operacionais continuam editáveis no portal.
5. Relatórios e e-mails usam a identificação histórica e podem oferecer um link ao objeto no NetBox.

Não criar um espelho completo do inventário. Reutilizar a infraestrutura HTTP existente com funções adicionais de busca e validação; não adicionar uma biblioteca nova apenas para esse fluxo.

## Persistência e compatibilidade

Adicionar campos opcionais de referência externa e nome histórico a `Ocorrencia`, mantendo sua FK legada. Novas ocorrências criadas pelo NOC usam a referência NetBox e deixam a FK legada vazia. Fluxos antigos fora do NOC continuam aceitando equipamentos locais.

Uma ocorrência deve ter uma origem inequívoca. A validação dos novos formulários não deve aceitar simultaneamente equipamento local e referência externa nem pares incompletos de tipo/ID. O tipo aceito inicialmente é somente `dcim.device`.

Os registros antigos continuam legíveis sem conexão com o NetBox. Sua edição não deve obrigar a escolher um novo equipamento. Um nome histórico já registrado não deve ser atualizado automaticamente ao visualizar ou editar o texto de uma ocorrência.

A apresentação compartilhada do equipamento deve resolver tanto a referência nova quanto a FK antiga, sem realizar consultas HTTP por ocorrência. Revisar os consumidores de `Ocorrencia` fora do NOC para evitar regressões causadas por novas ocorrências sem equipamento local.

Não remover nem mudar a política de exclusão das relações antigas nesta entrega. Elas ainda têm risco de cascata; a migração futura deverá proteger ou desvincular registros históricos antes de qualquer remoção de equipamentos.

## Indisponibilidade e acesso

- Token do NetBox permanece no servidor; endpoint de busca exige autenticação e permissões compatíveis com o cadastro de ocorrências.
- Construir URLs a partir da configuração e de IDs/tipos validados, nunca de URLs arbitrárias enviadas pelo navegador.
- Distinguir busca sem resultados, objeto inexistente, acesso negado e falha de conexão.
- Falha no NetBox impede nova associação não validada, mantendo o texto digitado e exibindo erro no formulário.
- Ler, exibir e enviar relatórios já salvos não depende de consultar o NetBox.
- Renomear ou excluir um dispositivo no NetBox não apaga nem reescreve o relato histórico.
- Revalidar o objeto no envio reduz associações inválidas; não existe transação distribuída entre os dois sistemas. Uma exclusão posterior deve ser tolerada.

## Alertas Nagios e core

O bloco de alertas Nagios do checklist fica como está na primeira entrega. Embora apareça no NOC, ele depende de vínculos locais de monitoramento; migrá-lo agora ampliaria o escopo excluído pelo usuário.

O core entra primeiro como levantamento de vínculos. Mudanças em grupos, tenants, sistemas operacionais e equipamentos só serão propostas em uma entrega posterior, com evidência de que não alteram o monitoramento. Não há alteração de core necessária para entregar o novo seletor de ocorrências.

## Migração dos históricos: entrega posterior

Produzir um relatório de correspondência entre equipamentos locais e dispositivos do NetBox, sem alterar dados inicialmente. IDs locais não são IDs do NetBox. Correspondências por nome são candidatas, não confirmação quando houver ambiguidade.

Revisar correspondências, duplicidades e itens ausentes; preservar registros sem correspondência como históricos locais. Uma migração aprovada deve poder ser repetida sem duplicação e registrar o mapeamento utilizado. Não fazer chamadas de rede em migrações de esquema Django.

## Entregas e critérios de aceitação

### 1. Ocorrências NOC com NetBox

- Busca de dispositivos e gravação sem criar `Equipamento` local.
- Validação de IDs, permissões, falhas de API e tentativa de enviar tipo não permitido.
- Exibição de relatórios antigos, novos e mistos; e-mails com identificação correta.
- Edição de registro antigo e manutenção de texto após falha na seleção.
- Histórico legível após renomear/remover dispositivo ou desligar o NetBox.
- Testes de regressão dos consumidores legados de ocorrências e contratos do cliente NetBox.
- Migração de esquema aditiva, ensaiada em cópia de teste. Rollback de código deve considerar que versões antigas não exibem a identificação externa; não apagar os novos dados para reverter.

### 2. Correspondência e migração dos vínculos antigos

- Executar primeiro em cópia do banco, com backup e contagem dos históricos antes/depois.
- Revisão explícita das correspondências antes de alteração dos dados.
- Nenhuma exclusão de histórico ou de equipamento nesta fase.

### 3. Core, após levantamento

- Propor separadamente os vínculos operacionais que podem apontar ao NetBox.
- Manter intactas todas as dependências do monitoramento.

## Fora deste plano

Remoção de tabelas, migração de monitoramento, escrita de inventário no NetBox pelo portal, sincronização bidirecional, mudança de login/FreeIPA, inclusão de novos tipos de objetos e alterações não relacionadas ao NOC.

## Revisão antes da implementação

Confirmar a premissa de equipamentos físicos e a manutenção do bloco Nagios. Na preparação técnica, conferir a versão instalada do NetBox, permissões do token e filtros disponíveis. Só então detalhar os passos de implementação e executar a primeira entrega.
