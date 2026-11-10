# Operações diretamente nos servidores do NetBox

## Objetivo

Em **Infraestrutura → Servidores**, cada cartão representa somente o objeto do NetBox. Clicar no cartão abre imediatamente dados, configurações operacionais, ocorrências, grupos, Nagios, redes, sistema operacional e ações de FreeIPA, conta local, status e VM aplicáveis. Nenhuma interação com esse fluxo cria uma linha em `infra.Servidor` ou `infra.Equipamento` para representar o dispositivo. O usuário não seleciona nem associa novamente o mesmo servidor.

## Identidade e armazenamento

O par `(netbox_object_type, netbox_object_id)` identifica o servidor. Um novo modelo `NetBoxServerOperations` guarda exclusivamente estado que pertence ao portal: tipo de uso, serviços, status operacional, tipo de conta, vínculos operacionais, configuração de VM e data de alterações. A linha é criada automaticamente no primeiro comando que precisa persistir estado; abrir a página não escreve no banco. Não há campos de inventário duplicados nesse modelo. Uma restrição única impede dois registros operacionais para o mesmo objeto do NetBox.

Grupos de acesso, tenants, sistemas operacionais e serviços Nagios têm relações próprias com `NetBoxServerOperations`. Ocorrências do servidor têm referência ao par tipo/ID ou ao registro operacional, sem depender de `Equipamento`. A UI mostra essas relações desde a primeira abertura, vazias quando ainda não houve gravação. O salvamento de cada seção cria o registro operacional quando necessário sem etapa de associação.

`infra.Servidor` permanece somente para registros legados e consumidores ainda não migrados. Registros existentes já vinculados ao NetBox são migrados para `NetBoxServerOperations` com suas relações, status, conta e histórico preservados; a migração é idempotente e não apaga linhas antigas até que o fluxo novo seja validado. Depois da migração, a listagem e ações de NetBox consultam apenas o modelo novo. Registros legados sem referência ao NetBox continuam acessíveis na área de registros antigos. Não há correspondência automática por nome.

## Inventário do NetBox

Nome, modelo, fabricante, serial, patrimônio, descrição, localização e IPs vêm da API do NetBox, usando o ID do cartão. Nome, serial, patrimônio e descrição são editáveis no portal e enviados por `PATCH` ao objeto correspondente no NetBox; os demais dados são somente leitura nesta etapa. O backend valida o papel `Server`/`Servidor` para dispositivos físicos e trata VMs pela API de virtualização. Uma falha na escrita remota é exibida sem confirmar a edição como salva.

Quando o NetBox estiver indisponível, o portal não inventa identificação a partir de um registro local. A página mostra o erro; estado operacional já salvo pode ser recuperado pelo ID quando a identidade estiver disponível novamente. Nenhuma ação externa roda sem os dados necessários, como IP ou DNS.

## Ações operacionais

FreeIPA e conta local recebem uma representação de servidor montada a partir dos dados atuais do NetBox e das configurações do portal. Ela expõe apenas os atributos necessários às rotinas existentes, sem salvar `infra.Servidor`. A validação de grupos e regras de automount continua antes do provisionamento. O resultado atualiza `conta` em `NetBoxServerOperations` e registra histórico com a referência do NetBox.

Alterar status atualiza o status operacional do portal, mantém o status de inventário do NetBox independente e aplica os serviços Nagios padrão como no fluxo atual. Criar VM e seu worker usam `(tipo, ID)` para recarregar os dados do NetBox no momento da execução; o worker não busca `infra.Servidor` por chave local. Exclusão de VM, quando habilitada, segue a mesma referência. Falhas de FreeIPA, Xen, NetBox e broker continuam visíveis e não são tratadas como sucesso.

As rotas antigas por `pk` continuam disponíveis somente para registros legados. Rotas novas incluem tipo e ID do NetBox e exigem as permissões equivalentes às ações atuais. Ações que mudam FreeIPA, status ou VM passam a usar POST com CSRF, evitando efeitos de um GET ou de pré-carregamento de links.

## Interface

O cartão inteiro navega para uma página operacional identificada pelo ID do NetBox. A página exibe inventário e seções operacionais sem botão de associação, sem formulário de cadastro de servidor e sem popup de detalhes. Botões de ação aparecem conforme permissões e estado. O usuário pode editar e salvar uma seção sem criar manualmente outro servidor. A lista de registros antigos fica em navegação separada, para histórico e manutenção legada.

## Migração e verificação

A migração cria tabelas operacionais e copia vínculos de registros já associados por tipo/ID, sem perda dos registros legados. Verificações de contagem e referência confirmam que grupos, tenants, SO, Nagios e ocorrências foram preservados. Testes de integração devem afirmar que abrir e salvar um servidor do NetBox não altera a contagem de `Servidor`/`Equipamento`; que as seções e ações aparecem antes do primeiro salvamento; que um único conjunto operacional é usado após vários salvamentos; e que permissões, erros de API e ações FreeIPA/VM não criam entidade duplicada. FreeIPA e Xen são simulados nos testes; nenhuma ação real é executada na verificação automatizada.
