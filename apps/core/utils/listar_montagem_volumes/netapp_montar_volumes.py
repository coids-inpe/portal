#!../../env/bin/python3
import sys
import ssl
import math
import MySQLdb
import smtplib
import email
import configparser
from datetime import *
import pandas as pd
import os
from .sdk.NetApp.NaServer import NaServer
from environ import Env
from django.conf import settings
sys.path.append('./sdk/NetApp/')

env = Env()
env.read_env(os.path.join(settings.BASE_DIR,"prod.env"))

# Inicio as Configuracoes
erros = []
conexao_banco_dados = MySQLdb.connect(env("DB_HOST"), env("DB_USER"), env("DB_PASSWORD"), env("DB_NAME"))
cursor = conexao_banco_dados.cursor()
# Contexto SSL
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    # Legacy Python that doesn't verify HTTPS certificates by default
    pass
else:
    # Handle target environment that doesn't support HTTPS verification
    ssl._create_default_https_context = _create_unverified_https_context


# Deleto os dados atuais
try:
    cursor.execute("""DELETE FROM infra_storagegrupoacessomontagem
                        WHERE infra_storagegrupoacessomontagem.storage_id=4;""")
    conexao_banco_dados.commit()
except Exception as e:
    print(e)
    conexao_banco_dados.rollback()

try:
    cursor.execute("""  
		       WITH tdiscos AS ( 
				SELECT
					infra_storageareagrupotrabalho.grupo_id,
					core_grupotrabalho.grupo_sistema, 
					monitoramento_area.node, 
					monitoramento_area.path, 
					monitoramento_area.area, 
					monitoramento_area.svm_name,
					'auto.grupo' as automount,
					CASE
						WHEN monitoramento_area.area LIKE '%dev%' THEN 'DESENVOLVIMENTO'
						WHEN monitoramento_area.area LIKE '%doc%' THEN 'DOCUMENTO'
						WHEN monitoramento_area.area LIKE '%pesq%' THEN 'PESQUISA'
						WHEN monitoramento_area.area LIKE '%pesq_share%' THEN 'PESQUISA'
						WHEN monitoramento_area.area LIKE '%share%' THEN 'OPERACIONAL'
						WHEN monitoramento_area.area LIKE '%oper%' THEN 'OPERACIONAL'
						WHEN monitoramento_area.area LIKE 'vol_int_%\_%\_dados' THEN 'OPERACIONAL'
						ELSE NULL
					END as tipo,
					CASE
						WHEN monitoramento_area.path LIKE '/oper/%' THEN '/oper/dados/'  
						WHEN monitoramento_area.path LIKE '/oper/log/%' THEN '/oper/log/'  
						WHEN monitoramento_area.path LIKE '/oper/scripts/%' THEN '/oper/scripts/'  
						WHEN monitoramento_area.path LIKE '/dev/dados/%' THEN '/dev/dados/'  
						WHEN monitoramento_area.path LIKE '/dev/log/%' THEN '/dev/log/'  
						WHEN monitoramento_area.path LIKE '/dev/scripts/%' THEN '/dev/scripts/'
						WHEN monitoramento_area.path LIKE '/pesq/dados/%' THEN '/pesq/dados/'  
						WHEN monitoramento_area.path LIKE '/pesq/log/%' THEN '/pesq/log/'  
						WHEN monitoramento_area.path LIKE '/pesq/scripts/%' THEN '/pesq/scripts/' 
						WHEN monitoramento_area.path LIKE '/pesq/share/%' THEN '/pesq/share/' 
						WHEN monitoramento_area.path LIKE '/share/%' THEN '/share/'
						ELSE NULL
					END as namespace,
					CASE
						WHEN monitoramento_area.path LIKE '/oper/%' THEN '/dados/'  
						WHEN monitoramento_area.path LIKE '/oper/log/%' THEN '/log/'  
						WHEN monitoramento_area.path LIKE '/oper/scripts/%' THEN '/scripts/'  
						WHEN monitoramento_area.path LIKE '/dev/dados/%' THEN '/dados/'  
						WHEN monitoramento_area.path LIKE '/dev/log/%' THEN '/log/'  
						WHEN monitoramento_area.path LIKE '/dev/scripts/%' THEN '/scripts/'
						WHEN monitoramento_area.path LIKE '/pesq/dados/%' THEN '/dados/'  
						WHEN monitoramento_area.path LIKE '/pesq/log/%' THEN '/log/'  
						WHEN monitoramento_area.path LIKE '/pesq/scripts/%' THEN '/scripts/' 
						WHEN monitoramento_area.path LIKE '/pesq/share/%' THEN '/share/' 
						WHEN monitoramento_area.path LIKE '/share/%' THEN '/share/'
						ELSE NULL
					END as montagem
				FROM monitoramento_area, infra_storageareagrupotrabalho, core_grupotrabalho
				WHERE monitoramento_area.storage_grupo_trabalho_id = infra_storageareagrupotrabalho.id
				AND infra_storageareagrupotrabalho.grupo_id = core_grupotrabalho.id
			)
			SELECT 
				grupo_id, 
				grupo_sistema, 
				node, 
				svm_name, 
				tipo, 
				CONCAT(namespace,grupo_sistema) as 'namespace', 
				CONCAT(montagem,grupo_sistema) as 'montagem', 
				automount, 
				"-fstype=nfs4.0,rw" as parametro,
				path
			FROM tdiscos
			WHERE CONCAT(namespace,grupo_sistema) = path

			UNION  

			SELECT 
				grupo_id, 
				grupo_sistema, 
				node, 
				svm_name, 
				tipo, 
				CONCAT(namespace,grupo_sistema) as 'namespace', 
				CONCAT('/share/',grupo_sistema) as 'montagem', 
				automount, 
				"-fstype=nfs4.0,rw" as parametro,
				path
			FROM tdiscos
			WHERE CONCAT(namespace,grupo_sistema) = path
			AND tipo = 'DESENVOLVIMENTO' 
			AND path LIKE '/dev/dados/%'

			UNION

			SELECT 
				infra_storageareagrupotrabalho.grupo_id,
				core_grupotrabalho.grupo_sistema, 
				monitoramento_area.node,
				monitoramento_area.svm_name,
				"OPERACIONAL",
				CASE WHEN monitoramento_area.path = '/share' THEN '/&' ELSE '/oper/dados/&' END as namespace,
				CASE WHEN monitoramento_area.path = '/share' THEN 'share' ELSE  '*' END as montagem,
				"auto.oper" as automount,
				"-fstype=nfs4.0,ro" as parametro,
				monitoramento_area.path
			FROM monitoramento_area,infra_storageareagrupotrabalho, core_grupotrabalho
			WHERE monitoramento_area.storage_grupo_trabalho_id = infra_storageareagrupotrabalho.id
			AND infra_storageareagrupotrabalho.grupo_id = core_grupotrabalho.id
			AND (area = "vol_int_sesup_mount_oper" or area = "vol_share_sesup_mount_share")

			UNION

			SELECT   
				infra_storageareagrupotrabalho.grupo_id, 
				core_grupotrabalho.grupo_sistema,   
				monitoramento_area.node,  
				monitoramento_area.svm_name,  "OPERACIONAL",     
				CONCAT(monitoramento_area.path,'/&') as namespace,     
				"*" as montagem,      
				"auto.home" as automount,  
				"-fstype=nfs4.0,rw" as parametro,
				monitoramento_area.path  
			FROM monitoramento_area,infra_storageareagrupotrabalho, core_grupotrabalho 
			WHERE monitoramento_area.storage_grupo_trabalho_id = infra_storageareagrupotrabalho.id 
			AND infra_storageareagrupotrabalho.grupo_id = core_grupotrabalho.id 
			AND monitoramento_area.path = "/HOME";
		""")

    tdiscos = cursor.fetchall()
    
except Exception as e:
    print(e)
    conexao_banco_dados.rollback()

if not tdiscos:
	print("é necessário listar os volumes antes ./netapp_buscar_volumes.py")
df_discos = pd.DataFrame(tdiscos)
df_discos.columns = [ x[0] for x in cursor.description]
df_discos["key"] = df_discos["node"] + "_" +df_discos["svm_name"]

try:
    cursor.execute(""" SELECT * FROM infra_rede """)
    redes = cursor.fetchall()
except Exception as e:
    print(e)
    conexao_banco_dados.rollback()

df_redes = pd.DataFrame(redes)
df_redes.columns = [x[0] for x in cursor.description]

list_svm = ["svm_dmz", "svm_share", "svm_int"]
lifs = []
for svm in list_svm:
    storage = NaServer(env("NETAPP"), 1, 20)
    storage.set_server_type("FILER")
    storage.set_transport_type("HTTPS")
    storage.set_port(443)
    storage.set_style("LOGIN")
    storage.set_admin_user(env("NETAPP_USER"), env("NETAPP_PASSWORD"))
    storage.set_vserver(svm)
    result = storage.invoke('net-interface-get-iter') 
    if result.results_status() == "failed":
            reason = result.results_reason()
            print(reason + "\n")
            sys.exit(2)
    if result.child_get_int('num-records') != 0:
        for interface_svm in result.child_get('attributes-list').children_get():
            data = {}
            for lif in interface_svm.children_get():
                data[lif.element['name']] = lif.element['content']
            lifs.append(data)

df_lifs = pd.DataFrame(lifs, columns=['address', 'current-node', 'vserver'])
df_lifs.columns = ['address', 'node', 'svm_name']

def subtract_rede(ip):
    ip_split = ip.split(".")
    if ip_split[0] == "172":
        return f"{ip_split[0]}.{ip_split[1]}"
    else:
        return f"{ip_split[0]}.{ip_split[1]}.{ip_split[2]}"

df_lifs['ip'] = df_lifs['address'].apply(subtract_rede)
df_lifs["key"] = df_lifs["node"] + "_" + df_lifs["svm_name"]

df_lifs_redes = pd.merge(df_lifs, df_redes, on='ip')
df_lifs_redes_discos = pd.merge(df_discos, df_lifs_redes, on='key')

df_infra_storagegrupoacessomontagem = pd.DataFrame(df_lifs_redes_discos, columns= ['node_x', 'svm_name_x', 'address', 'path', 'id', 'grupo_id', 'namespace', 'montagem', 'tipo', 'automount', 'parametro'])
df_infra_storagegrupoacessomontagem.columns = ['node', 'svm_name', 'ip', 'path', 'rede_id', 'grupo_trabalho_id', 'namespace', 'montagem', 'tipo', 'automount', 'parametro']
records_to_insert = list(df_infra_storagegrupoacessomontagem.to_records(index=False))
# Gerando Historico
sql_insert_query = """insert infra_storagegrupoacessomontagem \
                    (id, storage_id, node, svm_name, ip, path, rede_id, grupo_trabalho_id, namespace, montagem,tipo, automount, parametro) values \
                    (NULL, 4, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);"""
try:
    result = cursor.executemany(sql_insert_query, records_to_insert)
    conexao_banco_dados.commit()
except Exception as e:
    print(e)
    conexao_banco_dados.rollback()

# fechando as conecoes
cursor.close()
conexao_banco_dados.close()
server_email = smtplib.SMTP(env("EMAIL_HOST"), 587)
server_email.ehlo()
server_email.starttls()
server_email.login(env("EMAIL_HOST_USER"), env("EMAIL_HOST_PASSWORD"))
message_email = "Coleta de dados do Netaap: Montagem Discos Padroes e lifs \n"
message_header = '\r\n'.join([f'From: {env("EMAIL_HOST_USER")}', f'To: {env("EMAIL_SYSADMIN")}, {env("EMAIL_SUPORTE")}', f'Subject: Portal - Coleta de dados do Netapp - Montagem Discos Padroes e lifs', '', message_email])
try:
    server_email.sendmail(env("EMAIL_HOST_USER"), [env("EMAIL_SYSADMIN"),env("EMAIL_SUPORTE")], message_header)
except Exception as e:
    print(e)
    print('error sending mail')
server_email.quit()


