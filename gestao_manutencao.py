import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import datetime, timedelta
import os

# ========== CONFIGURAÇÃO DA BASE DE DADOS ==========
PASTA_ATUAL = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(PASTA_ATUAL, "manutencao.db")

def criar_tabelas():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        # Tabela principal de manutenções (cada registo é uma intervenção)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS manutencao (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome_maquina TEXT NOT NULL,
                data_manutencao TEXT NOT NULL,
                dias_para_proxima INTEGER NOT NULL,
                data_limite TEXT NOT NULL,
                concluida INTEGER DEFAULT 0,
                data_conclusao TEXT,
                notas TEXT,
                pecas_trocadas TEXT
            )
        ''')
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"ERRO ao criar tabelas: {e}")
        return False

# ========== FUNÇÕES AUXILIARES ==========
def calcular_data_limite(data_manutencao, dias):
    data = datetime.strptime(data_manutencao, "%Y-%m-%d")
    data_limite = data + timedelta(days=dias)
    return data_limite.strftime("%Y-%m-%d")

def adicionar_manutencao(nome_maquina, data_manutencao, dias_para_proxima, notas="", pecas=""):
    try:
        data_limite = calcular_data_limite(data_manutencao, int(dias_para_proxima))
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO manutencao
            (nome_maquina, data_manutencao, dias_para_proxima, data_limite, concluida, notas, pecas_trocadas)
            VALUES (?, ?, ?, ?, 0, ?, ?)
        ''', (nome_maquina, data_manutencao, dias_para_proxima, data_limite, notas, pecas))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        messagebox.showerror("Erro", f"Não foi possível adicionar: {e}")
        return False

def concluir_manutencao(manutencao_id, data_conclusao, notas, pecas):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE manutencao
            SET concluida = 1, data_conclusao = ?, notas = ?, pecas_trocadas = ?
            WHERE id = ?
        ''', (data_conclusao, notas, pecas, manutencao_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao concluir: {e}")
        return False

def eliminar_manutencao(manutencao_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM manutencao WHERE id = ?", (manutencao_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao eliminar: {e}")
        return False

def obter_todas_manutencoes():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, nome_maquina, data_manutencao, dias_para_proxima,
                   data_limite, concluida, data_conclusao, notas, pecas_trocadas
            FROM manutencao
            ORDER BY data_manutencao DESC
        ''')
        resultados = cursor.fetchall()
        conn.close()
        return resultados
    except Exception as e:
        print(f"Erro ao obter dados: {e}")
        return []

def obter_historico_maquina(nome_maquina, ordem='DESC'):
    """Retorna o histórico de manutenções de uma máquina, ordenado por data"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(f'''
            SELECT data_manutencao, data_conclusao, dias_para_proxima, notas, pecas_trocadas
            FROM manutencao
            WHERE nome_maquina = ?
            ORDER BY data_manutencao {ordem}
        ''', (nome_maquina,))
        resultados = cursor.fetchall()
        conn.close()
        return resultados
    except Exception as e:
        print(f"Erro ao obter histórico: {e}")
        return []

# ========== INTERFACE GRÁFICA ==========
class Aplicacao:
    def __init__(self, root):
        self.root = root
        self.root.title("Gestão de Manutenção de Máquinas")
       
        largura = 1200
        altura = 700
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        x = (screen_width - largura) // 2
        y = (screen_height - altura) // 2
        root.geometry(f"{largura}x{altura}+{x}+{y}")
       
        self.criar_widgets()
        self.carregar_dados()
       
    def criar_widgets(self):
        # ========== FRAME DE INSERÇÃO ==========
        frame_inserir = ttk.LabelFrame(self.root, text="Registar Nova Manutenção", padding=10)
        frame_inserir.pack(fill="x", padx=10, pady=5)

        # Linha 0: Máquina e Data
        ttk.Label(frame_inserir, text="Máquina:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.entry_nome = ttk.Entry(frame_inserir, width=30)
        self.entry_nome.grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(frame_inserir, text="Data da Manutenção (AAAA-MM-DD):").grid(row=0, column=2, sticky="w", padx=5, pady=2)
        self.entry_data = ttk.Entry(frame_inserir, width=15)
        self.entry_data.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.entry_data.grid(row=0, column=3, padx=5, pady=2)

        # Linha 1: Dias e Notas (agora com Text em várias linhas)
        ttk.Label(frame_inserir, text="Dias até à próxima:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.entry_dias = ttk.Entry(frame_inserir, width=10)
        self.entry_dias.grid(row=1, column=1, padx=5, pady=2, sticky="w")

        ttk.Label(frame_inserir, text="Notas/Peças trocadas:").grid(row=1, column=2, sticky="nw", padx=5, pady=2)

        # Frame para conter o Text e scrollbar (várias linhas)
        frame_notas_inicial = ttk.Frame(frame_inserir)
        frame_notas_inicial.grid(row=1, column=3, columnspan=2, padx=5, pady=2, sticky="w")

        scrollbar_notas = ttk.Scrollbar(frame_notas_inicial)
        scrollbar_notas.pack(side='right', fill='y')

        self.text_notas_inicial = tk.Text(frame_notas_inicial,
                                           height=4,        # 4 linhas de altura
                                           width=50,        # largura
                                           yscrollcommand=scrollbar_notas.set,
                                           font=('Arial', 9),
                                           wrap='word')
        self.text_notas_inicial.pack(side='left', fill='both', expand=True)

        scrollbar_notas.config(command=self.text_notas_inicial.yview)

        # Botão registar
        self.btn_adicionar = ttk.Button(frame_inserir, text="Registar", command=self.adicionar)
        self.btn_adicionar.grid(row=2, column=0, columnspan=4, pady=10)

        # ========== FRAME DE LISTAGEM ==========
        frame_lista = ttk.LabelFrame(self.root, text="Registos de Manutenção", padding=10)
        frame_lista.pack(fill="both", expand=True, padx=10, pady=5)

        # Treeview com scrollbars
        frame_tree = ttk.Frame(frame_lista)
        frame_tree.pack(fill="both", expand=True)

        vsb = ttk.Scrollbar(frame_tree, orient="vertical")
        hsb = ttk.Scrollbar(frame_tree, orient="horizontal")

        colunas = ("id", "maquina", "data_manutencao", "dias", "data_limite", "concluida", "data_conclusao", "notas")
        self.tree = ttk.Treeview(frame_tree, columns=colunas, show="headings",
                                 yscrollcommand=vsb.set, xscrollcommand=hsb.set, height=15)

        # Cabeçalhos
        self.tree.heading("id", text="ID")
        self.tree.heading("maquina", text="Máquina")
        self.tree.heading("data_manutencao", text="Data Manutenção")
        self.tree.heading("dias", text="Intervalo")
        self.tree.heading("data_limite", text="Data Limite")
        self.tree.heading("concluida", text="Concluída")
        self.tree.heading("data_conclusao", text="Concluída em")
        self.tree.heading("notas", text="Notas")

        # Larguras
        self.tree.column("id", width=40)
        self.tree.column("maquina", width=150)
        self.tree.column("data_manutencao", width=110)
        self.tree.column("dias", width=60)
        self.tree.column("data_limite", width=110)
        self.tree.column("concluida", width=60)
        self.tree.column("data_conclusao", width=110)
        self.tree.column("notas", width=250)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        frame_tree.grid_rowconfigure(0, weight=1)
        frame_tree.grid_columnconfigure(0, weight=1)

        vsb.config(command=self.tree.yview)
        hsb.config(command=self.tree.xview)

        # ========== FRAME DE BOTÕES ==========
        frame_botoes = ttk.Frame(frame_lista)
        frame_botoes.pack(fill="x", pady=10)

        self.btn_concluir = ttk.Button(frame_botoes, text="✓ Concluir Manutenção", command=self.concluir, width=20)
        self.btn_concluir.pack(side="left", padx=5)

        self.btn_historico = ttk.Button(frame_botoes, text="📋 Ver Histórico da Máquina", command=self.ver_historico, width=25)
        self.btn_historico.pack(side="left", padx=5)

        self.btn_eliminar = ttk.Button(frame_botoes, text="✗ Eliminar Registo", command=self.eliminar, width=18)
        self.btn_eliminar.pack(side="left", padx=5)

        self.btn_atualizar = ttk.Button(frame_botoes, text="↻ Atualizar", command=self.carregar_dados, width=15)
        self.btn_atualizar.pack(side="left", padx=5)

        self.btn_sair = ttk.Button(frame_botoes, text="Sair", command=self.sair, width=10)
        self.btn_sair.pack(side="right", padx=5)

        # Barra de status
        self.status_bar = ttk.Label(self.root, text="Pronto", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def atualizar_status(self, mensagem):
        self.status_bar.config(text=mensagem)
        self.root.update()

    def adicionar(self):
        nome = self.entry_nome.get().strip()
        data = self.entry_data.get().strip()
        dias = self.entry_dias.get().strip()
        notas = self.text_notas_inicial.get("1.0", tk.END).strip()  # Lê do Text

        if not nome or not data or not dias:
            messagebox.showwarning("Campos vazios", "Preencha máquina, data e dias.")
            return

        try:
            datetime.strptime(data, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Data inválida", "Use AAAA-MM-DD")
            return

        try:
            dias_int = int(dias)
            if dias_int <= 0:
                messagebox.showerror("Dias inválidos", "Número positivo.")
                return
        except ValueError:
            messagebox.showerror("Dias inválidos", "Digite um número inteiro.")
            return

        if adicionar_manutencao(nome, data, dias_int, notas):
            messagebox.showinfo("Sucesso", "Manutenção registada!")
            self.entry_nome.delete(0, tk.END)
            self.entry_data.delete(0, tk.END)
            self.entry_data.insert(0, datetime.now().strftime("%Y-%m-%d"))
            self.entry_dias.delete(0, tk.END)
            self.text_notas_inicial.delete("1.0", tk.END)  # Limpa o Text
            self.carregar_dados()

    def carregar_dados(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
       
        manutencoes = obter_todas_manutencoes()
        for m in manutencoes:
            (id_, nome, data_m, dias, data_lim, concluida, data_conc, notas, pecas) = m
            concluida_str = "Sim" if concluida else "Não"
            data_conc = data_conc if data_conc else ""
            # Mostra notas resumidas
            notas_mostrar = (notas or "")[:50] + "..." if len(notas or "") > 50 else (notas or "")
            self.tree.insert("", tk.END, values=(id_, nome, data_m, f"{dias} dias", data_lim, concluida_str, data_conc, notas_mostrar))
       
        self.atualizar_status(f"Total: {len(manutencoes)} registos")

    def concluir(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Selecione", "Selecione um registo.")
            return
       
        item = self.tree.item(selected[0])
        valores = item['values']
        manutencao_id = valores[0]
        nome_maquina = valores[1]
        concluida = valores[5]
       
        if concluida == "Sim":
            messagebox.showinfo("Info", "Esta manutenção já foi concluída.")
            return
       
        # Abrir janela para adicionar notas e peças
        self.janela_concluir(manutencao_id, nome_maquina)

    def janela_concluir(self, manutencao_id, nome_maquina):
        janela = tk.Toplevel(self.root)
        janela.title(f"Concluir Manutenção - {nome_maquina}")
        janela.geometry("700x650")
        janela.transient(self.root)
        janela.grab_set()
       
        # Título
        ttk.Label(janela, text=f"Máquina: {nome_maquina}",
                  font=('Arial', 12, 'bold')).pack(pady=10)
       
        # Separador
        ttk.Separator(janela, orient='horizontal').pack(fill='x', padx=20, pady=5)
       
        # Frame para data
        frame_data = ttk.Frame(janela)
        frame_data.pack(fill='x', padx=20, pady=10)
       
        ttk.Label(frame_data, text="Data de conclusão:",
                  font=('Arial', 10)).pack(side='left', padx=5)
        entry_data_conc = ttk.Entry(frame_data, width=15, font=('Arial', 10))
        entry_data_conc.insert(0, datetime.now().strftime("%Y-%m-%d"))
        entry_data_conc.pack(side='left', padx=5)
       
        # Separador
        ttk.Separator(janela, orient='horizontal').pack(fill='x', padx=20, pady=5)
       
        # Frame para notas
        frame_notas = ttk.LabelFrame(janela, text="📋 DESCRIÇÃO DETALHADA DO SERVIÇO", padding=10)
        frame_notas.pack(fill='both', expand=True, padx=20, pady=10)
       
        # Text area com scrollbar para notas
        text_frame = ttk.Frame(frame_notas)
        text_frame.pack(fill='both', expand=True)
       
        scrollbar_notas = ttk.Scrollbar(text_frame)
        scrollbar_notas.pack(side='right', fill='y')
       
        self.text_notas = tk.Text(text_frame,
                                   height=12,
                                   width=80,
                                   yscrollcommand=scrollbar_notas.set,
                                   font=('Arial', 10),
                                   wrap='word')
        self.text_notas.pack(side='left', fill='both', expand=True)
       
        scrollbar_notas.config(command=self.text_notas.yview)
       
        ttk.Label(frame_notas, text="✏️ Descreva aqui os trabalhos realizados, observações, etc.",
                  foreground='gray').pack(anchor='w', pady=2)
       
        # Frame para peças
        frame_pecas = ttk.LabelFrame(janela, text="🔧 PEÇAS TROCADAS", padding=10)
        frame_pecas.pack(fill='x', padx=20, pady=10)
       
        # Text area para peças
        pecas_frame = ttk.Frame(frame_pecas)
        pecas_frame.pack(fill='x')
       
        scrollbar_pecas = ttk.Scrollbar(pecas_frame)
        scrollbar_pecas.pack(side='right', fill='y')
       
        self.text_pecas = tk.Text(pecas_frame,
                                  height=6,
                                  width=80,
                                  yscrollcommand=scrollbar_pecas.set,
                                  font=('Arial', 10),
                                  wrap='word')
        self.text_pecas.pack(side='left', fill='both', expand=True)
       
        scrollbar_pecas.config(command=self.text_pecas.yview)
       
        ttk.Label(frame_pecas, text="🔩 Liste as peças substituídas (quantidade, referência, etc.)",
                  foreground='gray').pack(anchor='w', pady=2)
       
        # Frame para botões
        frame_botoes = ttk.Frame(janela)
        frame_botoes.pack(fill='x', padx=20, pady=20)
       
        def guardar():
            data_conc = entry_data_conc.get().strip()
            try:
                datetime.strptime(data_conc, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Data inválida", "Formato AAAA-MM-DD")
                return
           
            notas = self.text_notas.get("1.0", tk.END).strip()
            pecas = self.text_pecas.get("1.0", tk.END).strip()
           
            if concluir_manutencao(manutencao_id, data_conc, notas, pecas):
                messagebox.showinfo("Sucesso", "Manutenção concluída com sucesso!")
                janela.destroy()
                self.carregar_dados()
            else:
                messagebox.showerror("Erro", "Não foi possível concluir.")
       
        btn_guardar = ttk.Button(frame_botoes, text="💾 GUARDAR", command=guardar, width=20)
        btn_guardar.pack(side='left', padx=10)
       
        btn_cancelar = ttk.Button(frame_botoes, text="✖ CANCELAR", command=janela.destroy, width=20)
        btn_cancelar.pack(side='right', padx=10)

    def ver_historico(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Selecione", "Selecione uma máquina para ver o histórico.")
            return
       
        item = self.tree.item(selected[0])
        nome_maquina = item['values'][1]
       
        self.janela_historico(nome_maquina)

    def janela_historico(self, nome_maquina):
        janela = tk.Toplevel(self.root)
        janela.title(f"Histórico - {nome_maquina}")
        janela.geometry("800x500")
       
        # Frame para botões de ordenação
        frame_ordem = ttk.Frame(janela)
        frame_ordem.pack(fill="x", padx=10, pady=5)
       
        ttk.Label(frame_ordem, text="Ordenar por data:").pack(side="left", padx=5)
       
        ordem_var = tk.StringVar(value="DESC")
       
        def carregar_historico():
            # Limpar tree
            for row in tree_hist.get_children():
                tree_hist.delete(row)
            # Buscar dados com a ordem selecionada
            historico = obter_historico_maquina(nome_maquina, ordem_var.get())
            for reg in historico:
                data_m, data_conc, dias, notas, pecas = reg
                tree_hist.insert("", tk.END, values=(data_m, data_conc, f"{dias} dias", notas or "", pecas or ""))
       
        ttk.Radiobutton(frame_ordem, text="Mais recente primeiro", variable=ordem_var, value="DESC", command=carregar_historico).pack(side="left", padx=5)
        ttk.Radiobutton(frame_ordem, text="Mais antigo primeiro", variable=ordem_var, value="ASC", command=carregar_historico).pack(side="left", padx=5)
       
        # Treeview para histórico
        frame_tree = ttk.Frame(janela)
        frame_tree.pack(fill="both", expand=True, padx=10, pady=5)
       
        vsb = ttk.Scrollbar(frame_tree, orient="vertical")
        hsb = ttk.Scrollbar(frame_tree, orient="horizontal")
       
        colunas = ("data_manutencao", "data_conclusao", "intervalo", "notas", "pecas")
        tree_hist = ttk.Treeview(frame_tree, columns=colunas, show="headings",
                                  yscrollcommand=vsb.set, xscrollcommand=hsb.set)
       
        tree_hist.heading("data_manutencao", text="Data da Manutenção")
        tree_hist.heading("data_conclusao", text="Concluída em")
        tree_hist.heading("intervalo", text="Intervalo")
        tree_hist.heading("notas", text="Notas")
        tree_hist.heading("pecas", text="Peças Trocadas")
       
        tree_hist.column("data_manutencao", width=120)
        tree_hist.column("data_conclusao", width=120)
        tree_hist.column("intervalo", width=80)
        tree_hist.column("notas", width=250)
        tree_hist.column("pecas", width=200)
       
        tree_hist.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
       
        frame_tree.grid_rowconfigure(0, weight=1)
        frame_tree.grid_columnconfigure(0, weight=1)
       
        vsb.config(command=tree_hist.yview)
        hsb.config(command=tree_hist.xview)
       
        # Carregar dados iniciais
        carregar_historico()
       
        ttk.Button(janela, text="Fechar", command=janela.destroy).pack(pady=10)

    def eliminar(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Selecione", "Selecione um registo.")
            return
       
        item = self.tree.item(selected[0])
        valores = item['values']
        manutencao_id = valores[0]
        nome_maquina = valores[1]
        data_m = valores[2]
       
        if messagebox.askyesno("Confirmar", f"Eliminar registo de {nome_maquina} de {data_m}?"):
            if eliminar_manutencao(manutencao_id):
                self.carregar_dados()
                messagebox.showinfo("Sucesso", "Registo eliminado.")

    def sair(self):
        if messagebox.askokcancel("Sair", "Deseja sair?"):
            self.root.quit()
            self.root.destroy()

# ========== MAIN ==========
def main():
    if not criar_tabelas():
        input("Erro na base de dados. Pressione Enter para sair...")
        return
    root = tk.Tk()
    app = Aplicacao(root)
    root.protocol("WM_DELETE_WINDOW", app.sair)
    root.mainloop()

if __name__ == "__main__":
    main()


