import customtkinter as ctk
import json
import subprocess
import os
import tkinter.messagebox as messagebox

# Configurações visuais do CustomTkinter
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class AppVasoPressao(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Gerador Paramétrico de Vasos de Pressão - ANSYS")
        self.geometry("600x750")

        self.label_titulo = ctk.CTkLabel(self, text="Configuração do Vaso de Pressão",
                                         font=ctk.CTkFont(size=20, weight="bold"))
        self.label_titulo.pack(pady=(15, 5))

        # --- Sistema de Abas ---
        self.tabview = ctk.CTkTabview(self, width=550, height=550)
        self.tabview.pack(padx=20, pady=10, fill="both", expand=True)

        self.tab_vaso = self.tabview.add("1. Parâmetros do Casco")
        self.tab_bocais = self.tabview.add("2. Gerenciar Bocais")

        # --- Listas Internas para armazenar os bocais ---
        self.lista_costado = []
        self.lista_tampo_sup = []
        self.lista_tampo_inf = []

        self.setup_aba_vaso()
        self.setup_aba_bocais()

        # --- Botão de Geração Final ---
        self.btn_gerar = ctk.CTkButton(self, text="Gerar Geometria no SpaceClaim", command=self.executar_rotina,
                                       height=40, fg_color="#28a745", hover_color="#218838")
        self.btn_gerar.pack(pady=(0, 20))

    def setup_aba_vaso(self):
        self.inputs_vaso = {}

        campos = [
            ("Diâmetro do Costado (mm):", "5000.0", "CostadoDiametro"),
            ("Comprimento do Costado (mm):", "7000.0", "CostadoComprimento"),
            ("Straight Flange (SF) (mm):", "15.0", "SF"),
            ("Espessura do Costado (mm):", "15.0", "esp_costado"),
            ("Espessura do Tampo Sup (mm):", "12.0", "esp_tampo_sup"),
            ("Espessura do Tampo Inf (mm):", "12.0", "esp_tampo_inf"),
            ("Ângulo do Cone (Meio Âng. º):", "30.0", "AnguloCone")
        ]

        # Gera os campos numéricos
        for texto, padrao, chave in campos:
            frame_linha = ctk.CTkFrame(self.tab_vaso, fg_color="transparent")
            frame_linha.pack(fill="x", pady=8, padx=20)
            ctk.CTkLabel(frame_linha, text=texto, width=200, anchor="w").pack(side="left")
            entry = ctk.CTkEntry(frame_linha, width=150)
            entry.insert(0, padrao)
            entry.pack(side="right")
            self.inputs_vaso[chave] = entry

        # --- NOVOS CAMPOS PARA OS TAMPOS ---
        opcoes_tampos = [
            "Torisférico ASME 6%",
            "Torisférico ASME 10%",
            "Elipsoidal 2:1",
            "Hemisférico",
            "Cônico",
            "Toricônico"
        ]

        frame_tsup = ctk.CTkFrame(self.tab_vaso, fg_color="transparent")
        frame_tsup.pack(fill="x", pady=8, padx=20)
        ctk.CTkLabel(frame_tsup, text="Tipo de Tampo Sup:", width=200, anchor="w").pack(side="left")
        self.cb_tipo_sup = ctk.CTkComboBox(frame_tsup, values=opcoes_tampos, width=150)
        self.cb_tipo_sup.set("Elipsoidal 2:1")
        self.cb_tipo_sup.pack(side="right")

        frame_tinf = ctk.CTkFrame(self.tab_vaso, fg_color="transparent")
        frame_tinf.pack(fill="x", pady=8, padx=20)
        ctk.CTkLabel(frame_tinf, text="Tipo de Tampo Inf:", width=200, anchor="w").pack(side="left")
        self.cb_tipo_inf = ctk.CTkComboBox(frame_tinf, values=opcoes_tampos, width=150)
        self.cb_tipo_inf.set("Elipsoidal 2:1")
        self.cb_tipo_inf.pack(side="right")

    def setup_aba_bocais(self):
        self.inputs_bocal = {}

        # 1. Localização
        frame_loc = ctk.CTkFrame(self.tab_bocais, fg_color="transparent")
        frame_loc.pack(fill="x", pady=5, padx=10)
        ctk.CTkLabel(frame_loc, text="Local do Bocal:", width=150, anchor="w").pack(side="left")
        self.cb_local = ctk.CTkComboBox(frame_loc, values=["Costado", "Tampo Superior", "Tampo Inferior"], width=180,
                                        command=self.atualizar_label_posicao)
        self.cb_local.pack(side="left")

        # Função auxiliar para criar campos do bocal
        def criar_campo(texto, chave, frame_pai=self.tab_bocais, valor_padrao=""):
            frame = ctk.CTkFrame(frame_pai, fg_color="transparent")
            frame.pack(fill="x", pady=3, padx=10)
            lbl = ctk.CTkLabel(frame, text=texto, width=150, anchor="w")
            lbl.pack(side="left")
            ent = ctk.CTkEntry(frame, width=180)
            ent.insert(0, valor_padrao)
            ent.pack(side="left")
            self.inputs_bocal[chave] = ent
            return lbl  # Retorna o label caso precise alterar o texto dinamicamente

        criar_campo("Nome do Bocal:", "nome", valor_padrao="N1")
        criar_campo("Diâmetro (mm):", "diametro", valor_padrao="600")
        criar_campo("Pescoço/Altura (mm):", "pescoco", valor_padrao="500")

        # O Label de posição muda dependendo de onde o bocal vai ficar (Altura Y ou Raio Offset)
        self.lbl_posicao = criar_campo("Altura Y (mm):", "posicao", valor_padrao="1500")

        criar_campo("Ângulo (graus):", "angulo", valor_padrao="45")
        criar_campo("Espessura Tubo (mm):", "espessura", valor_padrao="8")
        criar_campo("Esp. Tampa (mm):", "esp_tampa", valor_padrao="50")

        # --- Seção do PAD ---
        self.frame_pad = ctk.CTkFrame(self.tab_bocais)
        self.frame_pad.pack(fill="x", pady=10, padx=10)

        self.var_tem_pad = ctk.BooleanVar(value=False)
        self.chk_pad = ctk.CTkCheckBox(self.frame_pad, text="Adicionar Chapa de Reforço (PAD)",
                                       variable=self.var_tem_pad, command=self.toggle_pad)
        self.chk_pad.pack(pady=5, padx=10, anchor="w")

        self.inputs_bocal["pad_diametro"] = ctk.CTkEntry(self.frame_pad, width=120, placeholder_text="Diâmetro do Pad")
        self.inputs_bocal["esp_pad"] = ctk.CTkEntry(self.frame_pad, width=120, placeholder_text="Espessura do Pad")

        # --- Botão Adicionar e Lista ---
        btn_add = ctk.CTkButton(self.tab_bocais, text="➕ Adicionar à Lista", command=self.adicionar_bocal)
        btn_add.pack(pady=10)

        self.caixa_texto = ctk.CTkTextbox(self.tab_bocais, height=120)
        self.caixa_texto.pack(fill="x", padx=10, pady=5)
        self.caixa_texto.insert("0.0", "Lista de Bocais Vazia.\n")
        self.caixa_texto.configure(state="disabled")

    def atualizar_label_posicao(self, escolha):
        if escolha == "Costado":
            self.lbl_posicao.configure(text="Altura Y (mm):")
        else:
            self.lbl_posicao.configure(text="Raio Offset (mm):")

    def toggle_pad(self):
        if self.var_tem_pad.get():
            self.inputs_bocal["pad_diametro"].pack(side="left", padx=10, pady=5)
            self.inputs_bocal["esp_pad"].pack(side="left", padx=10, pady=5)
        else:
            self.inputs_bocal["pad_diametro"].pack_forget()
            self.inputs_bocal["esp_pad"].pack_forget()

    def adicionar_bocal(self):
        local = self.cb_local.get()

        try:
            # Monta o dicionário base do bocal
            novo_bocal = {
                "nome": self.inputs_bocal["nome"].get(),
                "diametro": float(self.inputs_bocal["diametro"].get()),
                "pescoco": float(self.inputs_bocal["pescoco"].get()),
                "angulo": float(self.inputs_bocal["angulo"].get()),
                "espessura": float(self.inputs_bocal["espessura"].get()),
                "esp_tampa": float(self.inputs_bocal["esp_tampa"].get())
            }

            # Trata a variável de posição dependendo de onde está
            posicao_val = float(self.inputs_bocal["posicao"].get())
            if local == "Costado":
                novo_bocal["altura_y"] = posicao_val
            else:
                novo_bocal["raio_offset"] = posicao_val

            # Adiciona os dados do PAD se estiver marcado
            if self.var_tem_pad.get():
                novo_bocal["pad_diametro"] = float(self.inputs_bocal["pad_diametro"].get())
                novo_bocal["esp_pad"] = float(self.inputs_bocal["esp_pad"].get())

            # Direciona para a lista correta
            if local == "Costado":
                self.lista_costado.append(novo_bocal)
            elif local == "Tampo Superior":
                self.lista_tampo_sup.append(novo_bocal)
            elif local == "Tampo Inferior":
                self.lista_tampo_inf.append(novo_bocal)

            # Atualiza o visor de texto
            self.atualizar_visor()
            messagebox.showinfo("Sucesso", f"Bocal {novo_bocal['nome']} adicionado ao {local}.")

        except ValueError:
            messagebox.showerror("Erro",
                                 "Certifique-se de preencher os campos dimensionais com valores numéricos (use '.' para decimais).")

    def atualizar_visor(self):
        self.caixa_texto.configure(state="normal")
        self.caixa_texto.delete("0.0", "end")

        texto = f"Bocais Costado: {len(self.lista_costado)}\n"
        texto += f"Bocais Tampo Sup: {len(self.lista_tampo_sup)}\n"
        texto += f"Bocais Tampo Inf: {len(self.lista_tampo_inf)}\n\n"

        for b in self.lista_costado + self.lista_tampo_sup + self.lista_tampo_inf:
            pad_status = "(Com PAD)" if "pad_diametro" in b else ""
            texto += f"-> {b['nome']} | D={b['diametro']} {pad_status}\n"

        self.caixa_texto.insert("0.0", texto)
        self.caixa_texto.configure(state="disabled")

    def executar_rotina(self):
        dados_json = {}
        try:
            # Coleta dados do casco
            for chave, entry in self.inputs_vaso.items():
                dados_json[chave] = float(entry.get())
        except ValueError:
            messagebox.showerror("Erro", "Verifique os valores numéricos na aba do Vaso.")
            return

        # Insere as listas de bocais preenchidas pelo usuário
        dados_json["lista_costado"] = self.lista_costado
        dados_json["lista_tampo_sup"] = self.lista_tampo_sup
        dados_json["lista_tampo_inf"] = self.lista_tampo_inf
        dados_json["TipoTampoSup"] = self.cb_tipo_sup.get()
        dados_json["TipoTampoInf"] = self.cb_tipo_inf.get()

        # Salva o arquivo JSON
        caminho_json = os.path.join(os.getcwd(), "parametros_vaso.json")
        with open(caminho_json, "w", encoding='utf-8') as f:
            json.dump(dados_json, f, indent=4)

        # Chama o SpaceClaim (Ajuste o caminho se necessário)
        caminho_spaceclaim = r"C:\Program Files\ANSYS Inc\v252\scdm\SpaceClaim.exe"
        caminho_script = os.path.join(os.getcwd(), "Rotina.py")

        try:
            comando = f'"{caminho_spaceclaim}" /RunScript="{caminho_script}"'
            subprocess.Popen(comando, shell=True)
            messagebox.showinfo("Iniciando", "Geometria sendo gerada! Aguarde o SpaceClaim.")
        except Exception as e:
            messagebox.showerror("Erro de Execução", f"Falha ao abrir SpaceClaim:\n{str(e)}")


if __name__ == "__main__":
    app = AppVasoPressao()
    app.mainloop()