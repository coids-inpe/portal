# Migração para Python 3.12 e Django 5.2

## Estado verificado

- O workflow `.github/workflows/test.yml` executa em push e pull request com Python 3.12. Ele instala dependências, faz `pip check`, `manage.py check`, verifica migrations, migra o SQLite de teste, abre a página de novo colaborador e roda os testes de core e Kafka já estabilizados. O job encerra após 20 minutos e as etapas mais demoradas têm limites próprios de 2 a 12 minutos. A suíte completa ainda não é bloqueante no CI devido às falhas registradas abaixo.

- A imagem de desenvolvimento com Python 3.12 instalou as dependências de produção, teste e desenvolvimento.
- `python manage.py check`: sem problemas (7 verificações silenciadas na configuração existente).
- `python manage.py makemigrations --check --dry-run`: nenhuma alteração detectada.
- `pip check`: nenhuma dependência declarada como incompatível.
- `pytest -q apps/core/tests/test_models.py apps/core/tests/test_forms.py`: 9 testes passaram.
- A `.venv` local existente (Python 3.14.4) também instalou os três arquivos de requisitos com `pip`; `pip check`, `manage.py check` e os mesmos 9 testes passaram nela.
- A suíte completa ainda não passa. Os testes não exercitaram FreeIPA, XenAPI, Kafka, MQTT, MySQL e Celery em serviços reais.
- Após remover o teste obsoleto de `NetappView`, `pytest --collect-only -q` coletou 162 testes na `.venv` local com Python 3.14.4 e `portal.settings.test`. Isso verifica a coleta, não a aprovação da suíte.
- Na rodada seguinte, com `doc/environment/_test.env` copiado para `test.env`, a suíte coletou 163 testes: 127 passaram e 36 falharam. `manage.py check` não apontou problemas (7 verificações silenciadas), `makemigrations --check --dry-run` não detectou alterações e `pip check` não encontrou conflitos declarados.
- A imagem de desenvolvimento foi reconstruída com `docker build` usando Python 3.12. Em um container isolado, `python manage.py check` passou e o servidor Django respondeu HTTP 200 em `/` com `portal.settings.test`. Nenhum módulo precisou ser retirado de `INSTALLED_APPS`. O container temporário foi removido após o teste.
- Após corrigir os testes do admin e substituir `pykafka`, a suíte local ficou em 135 testes aprovados, 26 falhas e 4 pulados. Na nova imagem Python 3.12, os testes específicos de admin e Kafka ficaram em 25 aprovados e 4 pulados; `pykafka` não está instalado na imagem.

As verificações acima usaram `portal.settings.test` e variáveis fictícias para os serviços externos. A imagem de desenvolvimento foi reconstruída após a troca do cliente Kafka.

## Quebras encontradas e próximos ajustes

1. **`wiki==0.8` bloqueava a instalação do Django 5.2.** O pacote exigia Django anterior a 4.1. A faixa foi atualizada para `wiki>=0.13,<0.14`. Revisar páginas, anexos, imagens e migrations da wiki em uma cópia do banco antes de usar em produção.
2. **Cliente Kafka substituído.** `pykafka` e o pin de `setuptools` foram retirados dos requisitos; `kafka-python>=3.0.12,<3.1` lê as mensagens recentes nas páginas de nós e histórico. A leitura conserva a primeira partição usada anteriormente. Há testes isolados para mensagens recentes e tópico vazio; ainda falta validar a integração com um broker de homologação.
3. **`force_text` foi removido do Django.** Quatro imports que não eram usados foram retirados. O comando `check` passou após essa mudança.
4. **Fixtures de teste marcadas com `django_db` não coletavam no pytest atual.** Os fixtures passaram a solicitar `db` diretamente. O helper de middleware foi ajustado para receber `get_response`.
5. **Coleta dos testes de monitoramento corrigida.** `NetappView` não existe mais em `apps/monitoramento/views/storage.py` e a rota `storage_netapp` também não existe em `apps/monitoramento/urls.py`. Foram removidos apenas o import e o teste obsoletos de `apps/monitoramento/tests/test_views.py`. Os testes das views Netapp ainda presentes foram mantidos; a coleta agora encontra 162 testes.
6. **Testes do admin ajustados.** A biblioteca verifica o filtro de documentos por grupo sem exigir uma permissão de edição não concedida à fixture. As expectativas de campos e inlines do colaborador foram alinhadas ao comportamento atual. O admin de grupos evita conectar ao FreeIPA ao excluir um grupo que nunca foi criado lá. Os quatro testes de admin que realmente dependem de FreeIPA são pulados quando `IPA_AUTH_SERVER` não está configurado.
7. **Integrações externas e mudanças de API.** Validar especialmente `XenAPI` (nova série de versão), `paho-mqtt` 2, Celery 5.6, FreeIPA e o cliente Kafka. Fazer testes com serviços de homologação antes de alterar produção.

## Ajustes da primeira rodada de estabilização dos testes

- **FreeIPA:** `apps/core/utils/freeipa.py` agora chama `Client.__init__` com host, verificação SSL e versão, em vez de preencher atributos privados manualmente. A descoberta DNS foi desativada porque o portal usa um host configurado. Um teste isolado confirma a inicialização sem rede. Os testes de operações reais ainda exigem um servidor FreeIPA configurado; com `IPA_AUTH_SERVER` vazio, continuam falhando.
- **Referências obsoletas nos testes:** `infra:criar_servidor` foi trocada pela rota existente `infra:criar_servidor_ldap`; `HostnameIPInLine` foi trocada pela classe existente `HostnameIPServidorInLine`. O teste de `get_documento_principal()` foi ajustado para verificar somente `full_name`, pois o método e os campos de documento estão comentados no modelo atual.
- **Xen:** os testes de `Vm` e `Host` agora contêm os campos exigidos pelos construtores atuais. Dois testes de erro de login usam a assinatura atual de `XenInfo` e simulam as respostas do XenAPI sem conexão externa. A tela `XenPoolListView` ainda precisa de um ambiente com servidor Xen configurado para seu teste de integração.
- **Ambiente de teste:** os três modelos de `.env` agora incluem `WAZUH_SERVER`, `WAZUH_PASS` e `XEN_AUTH_PASSWORD_DMZ`, pois essas variáveis são usadas por tarefas e pela integração Xen. O modelo de teste removeu uma linha inválida, ganhou chave local e broker em memória. `portal.settings.test` usa resultado Celery em memória e tarefas síncronas. Os pontos de entrada de Django/Celery aceitam `DJANGO_SETTINGS_MODULE`, além da variável minúscula legada.
- **Teste HTTP no Docker:** `portal.settings.test` aceita `localhost`, `127.0.0.1` e `testserver` em `ALLOWED_HOSTS`, permitindo verificar a página inicial dentro do container. O teste foi feito sem rede externa nem banco persistente; o servidor informou 82 migrations ainda não aplicadas. Isso confirma a inicialização e a resposta da página inicial, não os fluxos com banco ou serviços externos.
- **Frontend sem CSS/JS no ambiente de teste:** `portal.settings.test` usa `DEBUG=False`; o `runserver` comum não serve `/staticfiles/`. O CSS do `django-garb` está instalado e foi localizado com `findstatic css/style.min.css`. O Compose de teste agora define o serviço `web` com `runserver --insecure`, exclusivo para testes, e publica a porta 8000. Após criar `test.env` a partir de `doc/environment/_test.env`, execute `docker compose -f docker/docker-compose_test.yml --project-directory . up --build web` e abra `http://localhost:8000/`. Em uma implantação com Gunicorn, os arquivos estáticos dependem de `collectstatic` e de um servidor como Nginx.
- **Mensagem de erro 500:** a tradução em português da frase usada por `django-garb/templates/500.html` exibia `Obirgado`. Um `templates/500.html` local mantém a página e apresenta `Obrigado por sua paciência` corretamente.
- **Cadastro de colaborador no Compose de teste:** `GET /colaborador/inicio/novo/?motivo=novo` retornava 500 porque faltava a tabela `colaborador_vinculo`; o container indicava 82 migrations pendentes. O SQLite em memória de `portal.settings.test` não persistia entre `migrate` e `runserver`. O teste agora usa `test.sqlite3` ignorado pelo Git e o serviço `web` aplica migrations antes de iniciar.
- **Ainda pendente:** 26 testes falham na `.venv` local. Há testes que precisam de FreeIPA/Xen/MQTT e expectativas antigas de modelos, consultas e rotas. O aviso sobre `LogEntry.objects.log_action()` (remover no Django 6) continua. O novo cliente Kafka ainda requer validação com broker real.

## Ordem sugerida

1. Corrigir as falhas restantes dos testes e obter uma linha de base completa com SQLite.

2. Testar migrations e fluxos principais em cópia do MySQL, incluindo a wiki.

3. Testar os serviços externos em homologação, com foco em autenticação, filas, métricas e criação de VMs.

4. Fixar as versões exatas validadas e gerar um lock de dependências antes da implantação.

Para repetir as verificações, configure as variáveis exigidas por `portal/settings/common.py` em um arquivo de ambiente local e execute os comandos dentro da imagem de desenvolvimento. Não use credenciais de produção no ambiente de testes.
