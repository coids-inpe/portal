# Seleção de servidores do NetBox no portal

Escopo aprovado: substituir cadastro manual de servidor por seleção de servidor físico ou VM no NetBox. Preservar registros antigos, grupos de acesso, tenants, SO, ambientes e templates de VM. Monitoramento e colaborador ficam fora da migração.

## Decisões

- Manter `Servidor` como registro operacional compatível com as FKs existentes. Adicionar referência `(tipo, ID)` única e opcional; endereços e localização de origem em snapshots e data da última atualização.
- A primeira seleção e a atualização explícita leem o NetBox. Edição operacional e leitura de histórico funcionam sem rede. Identificação/inventário não são editáveis pelo novo formulário.
- Servidor físico precisa ter papel Server/Servidor. VM vem de `virtualization.virtual-machines`. Buscar e validar no backend, usando permissões de servidor do admin, sem exigir permissões NOC.
- Não reassociar silenciosamente um registro já ligado. Cadastros antigos podem receber referência explicitamente; caso não recebam, preservam seus dados e relações.
- IPs vêm do NetBox. Não criar HostnameIP/Rede automaticamente nem reservar endereços locais para os novos vínculos. Manter todos os IPs retornados e o primário primeiro, para os consumidores de VM.
- Adaptar apenas consumidores operacionais de infraestrutura que precisam dos IPs: host principal, comandos de VM, XenCrud e seleção de rede de automount. Sem executar provisionamento, exclusão de VM ou FreeIPA real nos testes.
- Expor acesso a associar servidor e editar configurações operacionais a partir da listagem; preservar listagem física do NetBox e disponibilizar registros operacionais/legados.

## Execução

- [x] Criar testes falhando para seleção física/VM, papel inválido, duplicidade, campos adulterados, falhas de API, preservação de histórico/vínculos e permissões.
- [x] Implementar serviço de busca, validação e snapshots, reaproveitando transporte HTTP existente sem mudar contratos NOC.
- [x] Adicionar campos e migração aditiva; implementar formulário e widget com tipo de objeto e busca.
- [x] Atualizar admin por requisição sem mutar campos/inlines globais; manter edição operacional dos registros antigos.
- [x] Adaptar consumidores de IP em infraestrutura e testar com mocks, preservando comportamento legado.
- [x] Atualizar testes afetados pelo comportamento intencional do cadastro; rodar regressões NOC, infra, core e monitoramento pertinentes, separando falhas de baseline.
- [x] Revisão independente de código e correção de achados.
- [x] Backup das tabelas alteradas, aplicar migração somente no ambiente local e validar seleção/salvamento/edição em navegador; remover registros temporários.
- [x] Documentar uso, validação e limitações.

## Verificação final

- 30 testes novos de registro operacional; seleção física e VM, campos adulterados, referência única, atualização e falha de API, edição offline, grupos/tenants/SO, visualização somente leitura, IPs/DNS, comandos de VM e validação de montagem.
- Seleção de regressões: **105 passaram** (novos registros, NOC, servidores/racks/Datacenter e serviços de monitoramento).
- Suíte ampla `pytest apps --ignore=apps/infra/tests/test_utils.py`: **236 passaram, 22 falharam, 4 ignorados**. As mesmas 22 falhas foram reproduzidas em cópia do HEAD anterior: não há novos nomes de testes falhando. Baseline: 206 passaram, 22 falharam, 4 ignorados.
- `apps/infra/tests/test_utils.py` tem importação legada quebrada de `apps.infra.utils.datacenter` já no HEAD anterior, por isso foi excluído de ambas as comparações. Não se afirma que a suíte completa está verde.
- `check`, `makemigrations --check --dry-run`, sintaxe JavaScript e `git diff --check` passaram.
- Revisão independente encontrou e verificou correções de visualização somente leitura, DNS do primário, identidade Xen vs hostname guest e validação de rede operacional antes de ações FreeIPA.
- Backup privado em `/tmp/portal-before-server-netbox-20261109.json`; tabelas locais de servidores e vínculos estavam vazias. Migração aditiva `infra.0023` aplicada somente no ambiente local.
- Navegador: busca física real; busca VM respondeu corretamente vazia (NetBox local sem VMs); associado dispositivo físico ID 12, editados dados operacionais e conferido acesso pela lista. Nenhum hostname/IP manual foi criado. Registro e sessão temporários removidos.
- VM, FreeIPA e comandos remotos foram testados com mocks; não houve provisionamento real, exclusão de VM nem escrita no NetBox. O primeiro servidor real selecionado não possui IPs no NetBox: cadastro funciona, operações que exigem IP pedem configuração antes de executar.
- Arquivos de core, colaborador e monitoramento não foram alterados. Painéis de monitoramento continuam usando os consumidores legados; suporte deles aos novos snapshots fica fora desta entrega.

## Implantação

Ensaiar em cópia do banco e preservar backup antes de aplicar `infra.0023` no ambiente de destino. Não remover tabelas de inventário nesta etapa. Não reverter o esquema descartando referências novas; a versão antiga não compreende os snapshots nem o novo cadastro. As alterações estão no checkout para revisão/commit do usuário, sem publicação em produção.
