import ctypes
import sys
from datetime import datetime

from repositorio import RepositorioManutencao


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
    except (AttributeError, OSError):
        # ctypes.windll só existe no Windows
        # Se falhar, tenta mostrar na consola
        print(f"\n{titulo}")
        print(mensagem)
        print("-" * 50)

def verificar_alertas():
    try:
        maquinas_atrasadas = RepositorioManutencao().pendentes_ate()

        if not maquinas_atrasadas:
            agora = datetime.now().strftime('%d/%m/%Y %H:%M')
            print(f"Nenhuma máquina precisa de manutenção hoje. {agora}")
            return

        # Preparar mensagem
        if len(maquinas_atrasadas) == 1:
            titulo = "⚠ Alerta de Manutenção"
            msg_principal = "1 máquina necessita de atenção:\n\n"
        else:
            titulo = "⚠ Alertas de Manutenção"
            msg_principal = f"{len(maquinas_atrasadas)} máquinas necessitam de atenção:\n\n"

        mensagem = msg_principal
        for maq in maquinas_atrasadas:
            nome = maq.nome_maquina
            dias = dias_atrasados(maq.data_limite)

            if dias == 0:
                status = "🔴 MANUTENÇÃO HOJE!"
            elif dias == 1:
                status = "🟠 1 dia de atraso"
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
