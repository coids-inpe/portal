import os
import subprocess
import argparse
from environ import Env
from django.conf import settings

env = Env()
env.read_env(os.path.join(settings.BASE_DIR,"prod.env"))

def comando_netapp(divisao, grupo, produto):
    try:
        AGGREGATE = env("NETAPP_AGGREGATE")
        user=env("NETAPP_ADMIN")
        volume = f"vol_int_{divisao}_{grupo}_dados".lower()
        montagem = f"/oper/dados/{grupo}".lower()
        password = env("NETAPP_PASSWORD_ADMIN")
        vserver = "svm_int"
        policy = env("NETAPP_POLICY")
        size = '5GB'
        permissions = '2750'
        snapshot = 'default'
        percentagen_snapshot = '5'

        cmd = f"sshpass -p '{password}' ssh -o StrictHostKeyChecking=no {user}@150.163.161.36 'vol show -vserver {vserver} -volume {volume}'"
        output = subprocess.getstatusoutput(cmd)

        if "There are no entries matching your query." in output[1]:
            print("\n-> Volume não existe, criando...")
            cmd = f'sshpass -p "{password}" ssh {user}@150.163.161.36 "vol create -volume {volume} -aggregate {AGGREGATE} -size {size} -state online -policy {policy} -unix-permissions {permissions} -type RW -snapshot-policy {snapshot} -foreground true -vserver {vserver} -junction-path {montagem} -percent-snapshot-space {percentagen_snapshot}"'
            print("\n-> Criando volume...")
            output = subprocess.getstatusoutput(cmd)
            print(f"\n->Output 1: {output}")
            cmd = f'sshpass -p "{password}" ssh {user}@150.163.161.36 "vol snapshot autodelete modify -vserver {vserver} -volume {volume} -enabled true -commitment try -defer-delete user_created -delete-order oldest_first -target-free-space 15% -trigger volume"'
            print("\n-> Ativando autodelete...")
            output = subprocess.getstatusoutput(cmd)
            print(f"\n->Output 2: {output}")
            cmd = f'sshpass -p "{password}" ssh {user}@150.163.161.36 "vol efficiency on -vserver {vserver} -volume {volume}"'
            print("\n-> Ativando dedup...")
            output = subprocess.getstatusoutput(cmd)
            print(f"\n->Output 3: {output}")
        else:
            print(f"--> O volume {volume} já existe no NetApp... Nada a fazer.")
            return False
    except Exception as err:
        print(f'Deu erro em segundo plano?: {err}')
    
