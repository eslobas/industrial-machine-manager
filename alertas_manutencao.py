import sqlite3
from datetime import datetime, timedelta
import os
import sys
import ctypes

# Caminho da base de dados
PASTA_ATUAL = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(PASTA_ATUAL, "manutencao.db")

def dias_atrasados(data_limite_str):
    hoje = datetime.now().date()
    data_limite = datetime.strptime(data_limite_str, "%Y-%m-%d").date()
    diferenca = (hoje - data_limite).days
    return diferenca

def mostrar_notificacao(titulo, mensagem):
    """Mostra uma notificação usando a API do Windows (não precisa de win10toast)"""
    try:
        # Usa a MessageBox do Windows para notificações simples
        ctypes.windll.user32.MessageBoxW(0, mensagem, titulo, 1)
    except:
        # Se falhar, tenta mostrar na consola
        print(f"\n{titulo}")
        print(mensagem)
        print("-" * 50)

def verificar_alertas():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        hoje_str = datetime.now().strftime("%Y-%m-%d")
       
        # Buscar máquinas com manutenção em atraso ou para hoje
        cursor.execute('''
            SELECT id, nome_maquina, data_limite
            FROM manutencao
            WHERE concluida = 0 AND data_limite <= ?
            ORDER BY data_limite
        ''', (hoje_str,))
       
        maquinas_atrasadas = cursor.fetchall()
        conn.close()

        if not maquinas_atrasadas:
            print(f"Nenhuma máquina precisa de manutenção hoje. {datetime.now().strftime('%d/%m/%Y %H:%M')}")
            return

        # Preparar mensagem
        if len(maquinas_atrasadas) == 1:
            titulo = "⚠ Alerta de Manutenção"
            msg_principal = "1 máquina necessita de atenção:\n\n"
        else:
            titulo = f"⚠ Alertas de Manutenção"
            msg_principal = f"{len(maquinas_atrasadas)} máquinas necessitam de atenção:\n\n"

        mensagem = msg_principal
        for maq in maquinas_atrasadas:
            id_maq, nome, data_limite = maq
            dias = dias_atrasados(data_limite)
           
            if dias == 0:
                status = "🔴 MANUTENÇÃO HOJE!"
            elif dias == 1:
                status = f"🟠 1 dia de atraso"
            elif dias <= 7:
                status = f"🟡 {dias} dias de atraso"
            else:
                status = f"🔴 {dias} dias de atraso"
           
            mensagem += f"• {nome}: {status}\n"

        mensagem += f"\nData: {datetime.now().strftime('%d/%m/%Y %H:%M')}"

        # Mostrar notificação
        print(mensagem)  # Para ver na consola
        mostrar_notificacao(titulo, mensagem)

        # Guardar log do alerta
        with open("alertas_log.txt", "a", encoding='utf-8') as log:
            log.write(f"{datetime.now()} - {len(maquinas_atrasadas)} alertas\n")

    except Exception as e:
        print(f"Erro ao verificar alertas: {e}")

if __name__ == "__main__":
    print("Verificando alertas de manutenção...")
    verificar_alertas()
   
    # Pausa para ver a mensagem se executado diretamente
    if len(sys.argv) > 1 and sys.argv[1] == "--pausa":
        input("\nPressione Enter para sair...")
