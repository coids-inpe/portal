 <p align="center">
  <strong align="center">3SPORTAL</strong>
</p>
<p align="center">
  <strong align="center">Django  |  Gerenciamento  |  Automatização | FreeIPA | XEN | Kafka | Mosquitto </strong>
</p>
<br>

## Sobre 
3SPORTAL é um Portal de Gerenciamento e Automatização do Serviços de Supercomputação e Suporte.

## Instalação local com pip

Use a `.venv` existente. Para compilar `mysqlclient` em Debian/Ubuntu são necessários `build-essential`, `pkg-config`, `default-libmysqlclient-dev`, `git` e os headers da versão de Python usada pela venv (neste host, `python3.14-dev`). Na raiz do projeto:

```bash
source .venv/bin/activate
python -m pip install -r doc/requirements/requirements.txt -r doc/requirements/requirements-dev.txt -r doc/requirements/requirements-test.txt
python -m pip check
```

Também é possível executar `make install-dev`; esse alvo usa `.venv/bin/python`. A instalação das bibliotecas não exige Docker. Para executar Django e testes, ainda é necessário configurar as variáveis de ambiente descritas em `portal/settings/common.py`.

## Teste local com usuário do Django

No ambiente local atual, `portal.settings.development` usa somente `ModelBackend`,
com cookies `portal_csrftoken` e `portal_sessionid`. Mantenha essa configuração ao
testar sem FreeIPA. O perfil de produção ainda possui autenticação FreeIPA.

Com as dependências instaladas e o MySQL configurado em `dev.env` disponível:

```bash
source .venv/bin/activate
export DJANGO_SETTINGS_MODULE=portal.settings.development
mkdir -p logs
python manage.py check
python manage.py migrate --check
# Se houver migrações pendentes no banco local de teste:
python manage.py migrate
python manage.py runserver 127.0.0.1:8001
```

Se a porta 8001 já estiver ocupada pelo portal, use a instância existente.
Abra `http://localhost:8001/conta/login/?next=/infra/datacenter/` em uma aba nova
ou janela privativa. Após erro CSRF, carregue novamente o endereço do login;
não reenvie o formulário antigo pela página de erro. O CSRF deve permanecer ativo.

O usuário local precisa estar ativo e ter senha definida pelo Django. Para
redefinir a senha de um usuário existente, execute `python manage.py changepassword USUARIO`.
O modelo de usuário também exige vínculo, divisão e data de início para novos cadastros.

Para login e navegação básica são necessários Django e MySQL. Os dados do
Datacenter dependem do NetBox (`NETBOX_URL` e `NETBOX_TOKEN` em `dev.env`).
Operações que enfileiram tarefas exigem o broker configurado e um worker:
`celery -A portal worker -l info`. No desenvolvimento, confira que
`EMAIL_BACKEND=1` em `dev.env` para gravar e-mails em `logs`.
Criar contas no LDAP, sincronizar grupos e redefinir senhas pelo fluxo FreeIPA
continuam exigindo esse serviço; selecionar autenticação local não desativa essas integrações.

Se a inicialização falhar ao abrir `logs/dev.log`, confira o dono e a permissão
do arquivo: executar o portal com usuários diferentes pode deixar o log sem
permissão de escrita. Preserve o log antigo antes de recriá-lo com seu usuário.

## Ocorrências do NOC com NetBox

Na administração, abra **NOC → Checklists → Adicionar checklist**. Em
**Ocorrências de Equipamento**, adicione uma linha, pesquise pelo botão
**Buscar no NetBox**, selecione o dispositivo, escreva a descrição e salve.
O botão **Carregar mais** busca a próxima página de equipamentos.

O portal utiliza `NETBOX_URL` e `NETBOX_TOKEN` do ambiente. O token deve permitir
leitura de dispositivos; não é necessária permissão de escrita no NetBox.
O usuário precisa de acesso à administração e permissões para o checklist e
para adicionar/alterar ocorrências (`infra.Ocorrencia`).

Aplique `python manage.py migrate` ao atualizar: a migração
`infra.0022_ocorrencia_netbox_reference` acrescenta três campos opcionais.
Novas ocorrências do NOC guardam o ID e o nome histórico do equipamento, sem
criar inventário local. Os relatórios e e-mails continuam legíveis quando o
NetBox estiver indisponível. Ocorrências antigas mantêm seus vínculos; ao
editá-las, deixe a nova seleção vazia para preservar o equipamento antigo.

Esta entrega seleciona dispositivos físicos. Os alertas Nagios do checklist e
o módulo de monitoramento continuam usando seus fluxos existentes.

## Funcionalidades 
<p align="center">
  <strong align="center">Cadastro de Colaboradores Integrado com LDAP - django, celery, django-garb, python_freeipa</strong>
</p>
<h1 align="center">
  <img src="https://github.com/marcelogumercinocosta/portal/blob/develop/doc/source/_static/tela1.png" float="center"/>
</h1>
<p align="center">
  <strong align="center">Monitoramento do Datacenter - django, scipy.interpolate, matplotlib, paho.mqtt + mosquitto</strong>
</p>
<h1 align="center">
  <img src="https://github.com/marcelogumercinocosta/portal/blob/develop/doc/source/_static/tela2.png" float="center"/>
</h1>
<p align="center">
  <strong align="center">Monitoramento dos Supercomputadores - django, pykafka + kafka, echarts </strong>
</p>
<h1 align="center">
  <img src="https://github.com/marcelogumercinocosta/portal/blob/develop/doc/source/_static/tela3.png" float="center"/>
</h1>
<p align="center">
  <strong align="center">Monitoramento dos Ambientes Virtuais XEN - django, XenAPI</strong>
</p>
<h1 align="center">
  <img src="https://github.com/marcelogumercinocosta/portal/blob/develop/doc/source/_static/tela4.png" float="center"/>
</h1>
<p align="center">
  <strong align="center">Monitoramento dos Armazenamento - django, sklearn.linear_model</strong>
</p>
<h1 align="center">
  <img src="https://github.com/marcelogumercinocosta/portal/blob/develop/doc/source/_static/tela5.png" float="center"/>
</h1>
<p align="center">
  <strong align="center">Controle de Servidores - django, python_freeipa</strong>
</p>
<h1 align="center">
  <img src="https://github.com/marcelogumercinocosta/portal/blob/develop/doc/source/_static/tela6.png" float="center"/>
</h1>
<p align="center">
  <strong align="center">Controle de Grupos de trabalho - django, python_freeipa</strong>
</p>
<h1 align="center">
  <img src="https://github.com/marcelogumercinocosta/portal/blob/develop/doc/source/_static/tela7.png" float="center"/>
</h1>
<p align="center">
  <strong align="center">Criaçao de VMs - django, XenAPI, celery_progress</strong>
</p>
<h1 align="center">
  <img src="https://github.com/marcelogumercinocosta/portal/blob/develop/doc/source/_static/tela8.png" float="center"/>
</h1>
