#!../../env/bin/python3
import time
import sys
import ssl
import math
import MySQLdb
import smtplib
import email
import configparser
from datetime import *
from .sdk.NetApp.NaServer import NaServer
from environ import Env
import os
from django.conf import settings
sys.path.append('./sdk/NetApp/')


env = Env()
env.read_env(os.path.join(settings.BASE_DIR,"prod.env"))

# Inicio as Configuracoes
list_svm = ["svm_dmz", "svm_share", "svm_int"]
erros = []
conexao_banco_dados = MySQLdb.connect(env("DB_HOST"), env("DB_USER"), env("DB_PASSWORD"), env("DB_NAME"))
cursor = conexao_banco_dados.cursor()
dict_divisao = {}
# Lista as divisoes
try:
    cursor.execute("select * from core_divisao")
    for divisao in cursor.fetchall():
        dict_divisao.update({divisao[1].lower():divisao[1]})
except Exception as e:
    print(e)
    conexao_banco_dados.rollback()

# Atualizo o Update do Storage
now = datetime.now()
try:
    cursor.execute(
        """update infra_storage SET infra_storage.atualizacao = '%s' where infra_storage.equipamento_ptr_id=4;""" % now.strftime('%Y-%m-%d %H:%M:%S'))
    conexao_banco_dados.commit()
except Exception as e:
    print(e)
    conexao_banco_dados.rollback()
# Deleto os dados atuais
try:
    cursor.execute("""DELETE monitoramento_area FROM monitoramento_area \
                        INNER JOIN infra_storageareagrupotrabalho on monitoramento_area.storage_grupo_trabalho_id = infra_storageareagrupotrabalho.id \
                        INNER JOIN infra_storagearea on infra_storageareagrupotrabalho.storage_area_id = infra_storagearea.id \
                        INNER JOIN infra_storage on infra_storagearea.storage_id = infra_storage.equipamento_ptr_id \
                        WHERE infra_storage.equipamento_ptr_id =4;""")
    conexao_banco_dados.commit()
except Exception as e:
    print(e)
    conexao_banco_dados.rollback()

# Gero a Tabela de Ids
lista_id_grupo_divisao = []
try:
    cursor.execute("""SELECT infra_storageareagrupotrabalho.id, core_grupotrabalho.grupo_sistema, core_divisao.divisao \
                        FROM infra_storageareagrupotrabalho \
                        INNER JOIN infra_storagearea on infra_storagearea.id = infra_storageareagrupotrabalho.storage_area_id \
                        INNER JOIN infra_storage on infra_storage.equipamento_ptr_id = infra_storagearea.storage_id \
                        INNER JOIN core_grupotrabalho ON infra_storageareagrupotrabalho.grupo_id=core_grupotrabalho.id \
                        INNER JOIN core_divisao ON core_grupotrabalho.divisao_id=core_divisao.id \
                        WHERE infra_storage.equipamento_ptr_id = 4""")
    lista_id_grupo_divisao = cursor.fetchall()
except Exception as e:
    print(e)
    conexao_banco_dados.rollback()

# Contexto SSL
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    # Legacy Python that doesn't verify HTTPS certificates by default
    pass
else:
    # Handle target environment that doesn't support HTTPS verification
    ssl._create_default_https_context = _create_unverified_https_context

for svm in list_svm:
    storage = NaServer(env("NETAPP"), 1, 20)
    storage.set_server_type("FILER")
    storage.set_transport_type("HTTPS")
    storage.set_port(443)
    storage.set_style("LOGIN")
    storage.set_admin_user(env("NETAPP_USER"), env("NETAPP_PASSWORD"))
    storage.set_vserver(svm)
    tag = ""
    records_to_insert = []
    sql_insert_query = """insert into monitoramento_area \
                            (id, area, snap, porcentagem_snap, snapshot_autodelete, snapshot_size_used, snapshot_policy, total_disco, disco, \
                            disco_used, porcentagem_disco_used, path, node, export_policy, deduplication, porcentagem_deduplication, aggregate, svm_name, storage_grupo_trabalho_id) values \
                            (null, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);"""
    while tag != None:
        if not tag:
            result = storage.invoke('volume-get-iter', 'max-records', 1)
        else:
            result = storage.invoke('volume-get-iter', 'tag', tag, 'max-records', 1)

        if result.results_status() == "failed":
            reason = result.results_reason()
            print(reason + "\n")
            sys.exit(2)
        if result.child_get_int('num-records') == 0:
            break
        else:
            tag = result.child_get_string('next-tag')
            for volume in result.child_get('attributes-list').children_get():
                name = volume.child_get('volume-id-attributes').child_get_string('name')
                name_array = name.split("_")
                if (len(name_array)) > 3:
                    try:
                        lista_id = list(
                            filter(lambda tup: name_array[3] in tup, filter(lambda tup: dict_divisao[name_array[2]] in tup, lista_id_grupo_divisao)))
                        if (len(lista_id)) == 1:
                            monitoramento_storageareagrupotrabalho_id = lista_id[0][0]
                            record_insert = (volume.child_get('volume-id-attributes').child_get_string('name'),
                                             volume.child_get('volume-space-attributes').child_get_string('snapshot-reserve-size'),
                                             volume.child_get('volume-space-attributes').child_get_string('percentage-snapshot-reserve'),
                                             volume.child_get('volume-snapshot-autodelete-attributes').child_get_string('is-autodelete-enabled'),
                                             volume.child_get('volume-space-attributes').child_get_string('percentage-snapshot-reserve-used'),
                                             volume.child_get('volume-snapshot-attributes').child_get_string('snapshot-policy'),
                                             volume.child_get('volume-space-attributes').child_get_string('size'),
                                             volume.child_get('volume-space-attributes').child_get_string('size-total'),
                                             volume.child_get('volume-space-attributes').child_get_string('size-used'),
                                             volume.child_get('volume-space-attributes').child_get_string('percentage-size-used'),
                                             volume.child_get('volume-id-attributes').child_get_string('junction-path'),
                                             volume.child_get('volume-id-attributes').child_get_string('node'),
                                             volume.child_get('volume-export-attributes').child_get_string('policy'),
                                             volume.child_get('volume-sis-attributes').child_get_string('total-space-saved'),
                                             volume.child_get('volume-sis-attributes').child_get_string('percentage-total-space-saved'),
                                             volume.child_get('volume-id-attributes').child_get_string('containing-aggregate-name'),
                                             svm,
                                             monitoramento_storageareagrupotrabalho_id,
                                             )
                            records_to_insert.append(record_insert)
                        else:
                            erros.append('SVM: %-15s Divisao: %-15s Grupo: %-25s Disco: %s ''' % (svm, name_array[2], name_array[3], name))
                    except Exception as e:
                        erros.append("SVM: %-15s     Disco: %s """ % (svm, name))
                else:
                    erros.append("SVM: %-15s     Disco: %s """ % (svm, name))

    # Insere novos registros
    try:
        result = cursor.executemany(sql_insert_query, records_to_insert)
        conexao_banco_dados.commit()
    except Exception as e:
        print(e)
        conexao_banco_dados.rollback()# conecta servidor de email

server_email = smtplib.SMTP(env("EMAIL_HOST"), 587)
server_email.ehlo()
server_email.starttls()
server_email.login(env("EMAIL_HOST_USER"), env("EMAIL_HOST_PASSWORD"))
message_email = "Erro na coleta de dados do Netaap: \n"
# lista os erros
if len(erros) > 0:
    message_email = "Erro na coleta de dados do Netaap: \n"
    for erro in erros:
        message_email += erro + "\n"
else:
    message_email = "Coleta de dados do Netaap: OK \n"
# envia email
message_header = '\r\n'.join([f'From: {env("EMAIL_HOST_USER")}', f'To:{env("EMAIL_SYSADMIN")}, {env("EMAIL_SUPORTE")} ', f'Subject: Portal - Coleta de dados do Netapp', '', message_email])
try:
    server_email.sendmail(env("EMAIL_HOST_USER"), [env("EMAIL_SYSADMIN"),env("EMAIL_SUPORTE")], message_header)
except Exception as e:
    print(e)
    print('error sending mail')
server_email.quit()


# Gerando Historico
sql_insert_query = """insert monitoramento_storagehistorico \
                      (id, storage_grupo_trabalho_id, disco_used, atualizacao) values \
                      (null, %s, %s, %s);"""

try:
    cursor.execute("""SELECT monitoramento_area.storage_grupo_trabalho_id, sum(monitoramento_area.disco_used) as disco_used \
                    FROM monitoramento_area group by monitoramento_area.storage_grupo_trabalho_id """)
    historico_id_grupo_divisao = cursor.fetchall()

    records_to_insert = []
    for row in historico_id_grupo_divisao:
        record_insert = (row[0], row[1], now.strftime('%Y-%m-%d'))
        records_to_insert.append(record_insert)
    result = cursor.executemany(sql_insert_query, records_to_insert)
    conexao_banco_dados.commit()
except Exception as e:
    print(e)
    conexao_banco_dados.rollback()

# fechando as conecoes
cursor.close()
conexao_banco_dados.close()
