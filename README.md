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
