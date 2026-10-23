# -*- coding: utf-8 -*-
"""Interface do Gerador Paramétrico de Vasos de Pressão (ANSYS SpaceClaim).

Layout:
  - Coluna esquerda: dados do casco, tampos e formulário do bocal.
  - Direita: pré-visualização ao vivo (elevação + planta), tabela de bocais,
    painel de validação e botão para gerar no SpaceClaim.
"""
import glob
import json
import math
import os
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import customtkinter as ctk

import vaso_geom as vg

# ------------------------------------------------------------------ caminhos
PASTA_PROJETO = os.path.dirname(os.path.abspath(__file__))
CAMINHO_JSON = os.path.join(PASTA_PROJETO, "parametros_vaso.json")
CAMINHO_ROTINA = os.path.join(PASTA_PROJETO, "rotina.py")
CAMINHO_CONFIG = os.path.join(PASTA_PROJETO, "config_interface.json")
SPACECLAIM_PADRAO = os.environ.get(
    "SPACECLAIM_EXE", r"C:\Program Files\ANSYS Inc\v252\scdm\SpaceClaim.exe")

# ------------------------------------------------------------------ visual
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

C = {
    "bg": "#121418", "painel": "#171a1f", "card": "#1e2128", "borda": "#2c313b",
    "campo": "#15181d", "texto": "#e6e8eb", "fraco": "#8a919c", "acento": "#3b82f6",
    "acento2": "#2563eb", "ok": "#22c55e", "ok2": "#16a34a", "aviso": "#f59e0b",
    "erro": "#ef4444", "casco": "#cfd6df", "casco_fill": "#1c2430", "bocal": "#38bdf8",
    "bocal_fill": "#0b3a52", "pad": "#a78bfa", "grade": "#252a33", "sel": "#facc15",
}
FONTE = "Segoe UI"
# Teclas que não alteram o conteúdo de um campo (não devem disparar atualização)
TECLAS_NEUTRAS = {"Return", "KP_Enter", "Escape", "Tab", "ISO_Left_Tab", "Shift_L", "Shift_R",
                  "Control_L", "Control_R", "Alt_L", "Alt_R", "Left", "Right", "Up", "Down",
                  "Home", "End", "Caps_Lock"}


def fonte(tam=12, peso="normal"):
    return ctk.CTkFont(family=FONTE, size=tam, weight=peso)


# ------------------------------------------------------------------ widgets
class Dica:
    """Tooltip simples ao passar o mouse."""

    def __init__(self, widget, texto):
        self.widget, self.texto, self.tip = widget, texto, None
        widget.bind("<Enter>", self._mostrar, add="+")
        widget.bind("<Leave>", self._esconder, add="+")

    def _mostrar(self, _=None):
        if self.tip or not self.texto:
            return
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry("+%d+%d" % (x, y))
        tk.Label(self.tip, text=self.texto, justify="left", bg="#0b0d10", fg=C["texto"],
                 relief="solid", bd=1, padx=9, pady=6, wraplength=330,
                 font=(FONTE, 9)).pack()

    def _esconder(self, _=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


class CampoNum(ctk.CTkFrame):
    """Rótulo + campo numérico + unidade. Aceita vírgula ou ponto."""

    def __init__(self, master, rotulo, unidade="mm", dica=None, on_change=None, largura=110):
        super().__init__(master, fg_color="transparent")
        self.columnconfigure(0, weight=1)
        self.lbl = ctk.CTkLabel(self, text=rotulo, anchor="w", font=fonte(12))
        self.lbl.grid(row=0, column=0, sticky="w")
        self.entry = ctk.CTkEntry(self, width=largura, justify="right", font=fonte(12),
                                  fg_color=C["campo"], border_color=C["borda"])
        self.entry.grid(row=0, column=1, padx=(8, 4), pady=2)
        self.un = ctk.CTkLabel(self, text=unidade, width=26, anchor="w",
                               text_color=C["fraco"], font=fonte(11))
        self.un.grid(row=0, column=2)
        if dica:
            Dica(self.lbl, dica)
        if on_change:
            self.entry.bind("<KeyRelease>",
                            lambda e: None if e.keysym in TECLAS_NEUTRAS else on_change(), add="+")

    def get(self):
        return vg.parse_num(self.entry.get())

    def valor(self, marcar=True):
        try:
            v = self.get()
            if marcar:
                self.marcar(True)
            return v
        except ValueError:
            if marcar:
                self.marcar(False)
            return None

    def set(self, v):
        self.entry.delete(0, "end")
        self.entry.insert(0, vg.fmt(v) if isinstance(v, (int, float)) else str(v))

    def marcar(self, ok):
        self.entry.configure(border_color=C["borda"] if ok else C["erro"])

    def habilitar(self, sim):
        self.entry.configure(state="normal" if sim else "disabled",
                             text_color=C["texto"] if sim else C["fraco"])
        self.lbl.configure(text_color=C["texto"] if sim else C["fraco"])


def criar_card(master, titulo, subtitulo=None):
    f = ctk.CTkFrame(master, fg_color=C["card"], corner_radius=10,
                     border_width=1, border_color=C["borda"])
    cab = ctk.CTkFrame(f, fg_color="transparent")
    cab.pack(fill="x", padx=14, pady=(12, 2))
    t = ctk.CTkLabel(cab, text=titulo, font=fonte(14, "bold"), anchor="w")
    t.pack(side="left")
    if subtitulo:
        ctk.CTkLabel(f, text=subtitulo, text_color=C["fraco"], font=fonte(11),
                     wraplength=320, justify="left", anchor="w").pack(fill="x", padx=14)
    corpo = ctk.CTkFrame(f, fg_color="transparent")
    corpo.pack(fill="x", padx=14, pady=(6, 12))
    f.titulo, f.cab = t, cab
    return f, corpo


# ------------------------------------------------------------------ app
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Gerador de Vasos de Pressão — ANSYS SpaceClaim")
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry("%dx%d+10+10" % (min(1480, sw - 40), min(900, sh - 90)))
        self.minsize(1100, 640)
        self.after(0, self._maximizar)
        self.configure(fg_color=C["bg"])

        self.bocais = []
        self.editando = None      # índice do bocal em edição
        self.selecionado = None   # índice do bocal selecionado
        self.arquivo = None
        self.sujo = False
        self.msgs = []
        self.modelo_atual = None
        self._agendado = None
        self._carregando = False
        self._form_ativo = False   # mostra o "fantasma" só quando o formulário está sendo usado
        self.config_app = self._ler_config()

        self._estilo_tabela()
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._montar_cabecalho()
        self._montar_esquerda()
        self._montar_direita()
        self._montar_rodape()
        self._atalhos()

        if os.path.isfile(CAMINHO_JSON):
            self._carregar_arquivo(CAMINHO_JSON, silencioso=True)
        else:
            self._aplicar(dict(vg.VASO_PADRAO), [], False)
        self.protocol("WM_DELETE_WINDOW", self._fechar)

    def _maximizar(self):
        try:
            self.state("zoomed")  # Windows
        except tk.TclError:
            pass

    # ============================================================== montagem
    def _estilo_tabela(self):
        st = ttk.Style(self)
        st.theme_use("clam")
        st.configure("Vaso.Treeview", background=C["painel"], fieldbackground=C["painel"],
                     foreground=C["texto"], rowheight=28, borderwidth=0, font=(FONTE, 10))
        st.map("Vaso.Treeview", background=[("selected", C["acento2"])],
               foreground=[("selected", "#ffffff")])
        st.configure("Vaso.Treeview.Heading", background=C["card"], foreground=C["fraco"],
                     relief="flat", borderwidth=0, font=(FONTE, 9, "bold"), padding=(6, 6))
        st.map("Vaso.Treeview.Heading", background=[("active", C["borda"])])
        st.layout("Vaso.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    def _montar_cabecalho(self):
        cab = ctk.CTkFrame(self, fg_color=C["painel"], corner_radius=0, height=64)
        cab.grid(row=0, column=0, columnspan=2, sticky="ew")
        cab.grid_columnconfigure(1, weight=1)

        tit = ctk.CTkFrame(cab, fg_color="transparent")
        tit.grid(row=0, column=0, padx=18, pady=10, sticky="w")
        ctk.CTkLabel(tit, text="Gerador de Vasos de Pressão", font=fonte(18, "bold")).pack(anchor="w")
        self.lbl_arquivo = ctk.CTkLabel(tit, text="", text_color=C["fraco"], font=fonte(11))
        self.lbl_arquivo.pack(anchor="w")

        bts = ctk.CTkFrame(cab, fg_color="transparent")
        bts.grid(row=0, column=2, padx=14, sticky="e")

        def bt(txt, cmd, dica):
            b = ctk.CTkButton(bts, text=txt, command=cmd, width=92, height=32, font=fonte(12),
                              fg_color=C["card"], hover_color=C["borda"],
                              border_width=1, border_color=C["borda"])
            b.pack(side="left", padx=3)
            Dica(b, dica)
            return b

        bt("Novo", self._novo, "Começar um vaso novo (Ctrl+N)")
        bt("Abrir…", self._abrir, "Abrir um projeto .json (Ctrl+O)")
        bt("Salvar", self._salvar, "Salvar o projeto (Ctrl+S)")
        bt("Salvar como…", lambda: self._salvar(como=True), "Salvar o projeto em outro arquivo")

        self.bt_sc = ctk.CTkButton(bts, text="", command=self._dialogo_config, height=32,
                                   font=fonte(12), fg_color="transparent", hover_color=C["borda"],
                                   border_width=1, border_color=C["borda"], width=210)
        self.bt_sc.pack(side="left", padx=(14, 0))
        Dica(self.bt_sc, "Clique para configurar o caminho do SpaceClaim.exe")
        self._atualizar_status_sc()

    def _montar_esquerda(self):
        esq = ctk.CTkScrollableFrame(self, width=370, fg_color=C["bg"],
                                     scrollbar_button_color=C["borda"])
        self.esq = esq
        esq.grid(row=1, column=0, sticky="nsw", padx=(12, 6), pady=12)
        mud = self._mudou

        # ---------------- Casco
        card, c = criar_card(esq, "1 · Casco")
        card.pack(fill="x", pady=(0, 10))
        self.f_D = CampoNum(c, "Diâmetro do costado", dica="Diâmetro do costado. Veja a opção "
                            "'diâmetros externos' abaixo.", on_change=mud)
        self.f_L = CampoNum(c, "Comprimento do costado", dica="Comprimento da parte cilíndrica, "
                            "sem os straight flanges. O costado vai de Y = −L/2 a +L/2.", on_change=mud)
        self.f_SF = CampoNum(c, "Straight flange (SF)", dica="Trecho reto dos tampos, entre o "
                             "costado e a curvatura do tampo.", on_change=mud)
        self.f_esp_c = CampoNum(c, "Espessura do costado", dica="Espessura usada na casca do "
                                "costado e dos SFs (já descontada a corrosão, se for o caso).", on_change=mud)
        for f in (self.f_D, self.f_L, self.f_SF, self.f_esp_c):
            f.pack(fill="x", pady=1)

        self.var_ext = ctk.BooleanVar(value=False)
        chk = ctk.CTkCheckBox(c, text="Diâmetros informados são externos", variable=self.var_ext,
                              command=mud, font=fonte(12), checkbox_width=18, checkbox_height=18)
        chk.pack(anchor="w", pady=(10, 0))
        Dica(chk, "Marque se o Ø do costado e o Ø dos bocais são EXTERNOS. A casca é modelada na "
                  "superfície média, então a interface envia D − t para a rotina.")
        self.lbl_medio = ctk.CTkLabel(c, text="", text_color=C["fraco"], font=fonte(11), anchor="w")
        self.lbl_medio.pack(fill="x")

        # ---------------- Tampos
        card, c = criar_card(esq, "2 · Tampos")
        card.pack(fill="x", pady=(0, 10))
        for rot, attr, attr_esp, chave in (("Superior", "cb_sup", "f_esp_ts", "sup"),
                                           ("Inferior", "cb_inf", "f_esp_ti", "inf")):
            ctk.CTkLabel(c, text="Tampo " + rot.lower(), font=fonte(12), text_color=C["fraco"],
                         anchor="w").pack(fill="x", pady=(4, 0))
            cb = ctk.CTkOptionMenu(c, values=vg.TIPOS_TAMPO, command=lambda _v: self._mudou(),
                                   font=fonte(12), fg_color=C["campo"], button_color=C["borda"],
                                   button_hover_color=C["acento2"], dynamic_resizing=False)
            cb.pack(fill="x", pady=(2, 2))
            setattr(self, attr, cb)
            f = CampoNum(c, "Espessura", on_change=mud)
            f.pack(fill="x")
            setattr(self, attr_esp, f)
        self.f_ang = CampoNum(c, "Meio-ângulo do cone", unidade="°", on_change=mud,
                              dica="Usado só nos tampos Cônico e Toricônico. Meio-ângulo do "
                                   "vértice, medido a partir do eixo do vaso.")
        self.f_ang.pack(fill="x", pady=(8, 0))
        self.lbl_alturas = ctk.CTkLabel(c, text="", text_color=C["fraco"], font=fonte(11),
                                        justify="left", anchor="w")
        self.lbl_alturas.pack(fill="x", pady=(6, 0))

        # ---------------- Bocal
        self.card_bocal, c = criar_card(esq, "3 · Novo bocal")
        self.card_bocal.pack(fill="x", pady=(0, 10))
        self.seg_local = ctk.CTkSegmentedButton(
            c, values=["Costado", "Tampo Sup.", "Tampo Inf."], command=lambda _v: (self._form_mudou(), self._local_mudou()),
            font=fonte(12), selected_color=C["acento2"], selected_hover_color=C["acento"])
        self.seg_local.set("Costado")
        self.seg_local.pack(fill="x", pady=(0, 8))

        linha = ctk.CTkFrame(c, fg_color="transparent")
        linha.pack(fill="x", pady=1)
        linha.columnconfigure(0, weight=1)
        ctk.CTkLabel(linha, text="Nome / tag", font=fonte(12), anchor="w").grid(row=0, column=0, sticky="w")
        self.e_nome = ctk.CTkEntry(linha, width=140, font=fonte(12), fg_color=C["campo"],
                                   border_color=C["borda"])
        self.e_nome.grid(row=0, column=1, padx=(8, 30), pady=2)
        self.e_nome.bind("<KeyRelease>",
                         lambda e: None if e.keysym in TECLAS_NEUTRAS else self._form_mudou(), add="+")

        fb = self._form_mudou  # só redesenha o "fantasma"
        self.f_b = {
            "diametro": CampoNum(c, "Diâmetro", on_change=fb),
            "pescoco": CampoNum(c, "Pescoço (projeção)", on_change=fb,
                                dica="Comprimento do bocal para fora do casco, até a tampa."),
            "posicao": CampoNum(c, "Altura Y", on_change=fb),
            "angulo": CampoNum(c, "Ângulo (orientação)", unidade="°", on_change=fb,
                               dica="Orientação em planta: 0° = +X, 90° = +Z (veja a vista em planta)."),
            "espessura": CampoNum(c, "Espessura do tubo", on_change=fb),
            "esp_tampa": CampoNum(c, "Espessura da tampa", on_change=fb,
                                  dica="Espessura da tampa/flange cego na ponta do bocal."),
        }
        for f in self.f_b.values():
            f.pack(fill="x", pady=1)
        self.lbl_pos_dica = ctk.CTkLabel(c, text="", text_color=C["fraco"], font=fonte(11),
                                         wraplength=330, justify="left", anchor="w")
        self.lbl_pos_dica.pack(fill="x", pady=(2, 4))

        self.var_pad = ctk.BooleanVar(value=False)
        sw = ctk.CTkSwitch(c, text="Chapa de reforço (PAD)", variable=self.var_pad,
                           command=lambda: (self._form_mudou(), self._toggle_pad()), font=fonte(12))
        sw.pack(anchor="w", pady=(6, 2))
        self.frame_pad = ctk.CTkFrame(c, fg_color=C["painel"], corner_radius=8)
        self.f_pad_d = CampoNum(self.frame_pad, "Diâmetro do pad", on_change=fb)
        self.f_pad_e = CampoNum(self.frame_pad, "Espessura total", on_change=fb,
                                dica="Espessura TOTAL da região do pad (casco + chapa). "
                                     "Ex.: 78,4 + 65 = 143,4 mm.")
        self.f_pad_d.pack(fill="x", padx=10, pady=(8, 1))
        self.f_pad_e.pack(fill="x", padx=10, pady=(1, 8))
        self.ancora_pad = ctk.CTkFrame(c, fg_color="transparent", height=1)
        self.ancora_pad.pack(fill="x")

        self.lbl_form_erro = ctk.CTkLabel(c, text="", text_color=C["erro"], font=fonte(11),
                                          wraplength=330, justify="left", anchor="w")
        self.lbl_form_erro.pack(fill="x")

        bts = ctk.CTkFrame(c, fg_color="transparent")
        bts.pack(fill="x", pady=(8, 0))
        self.bt_add = ctk.CTkButton(bts, text="＋  Adicionar bocal", command=self._adicionar_ou_salvar,
                                    height=36, font=fonte(13, "bold"), fg_color=C["acento2"],
                                    hover_color=C["acento"])
        self.bt_add.pack(side="left", fill="x", expand=True)
        self.bt_cancelar = ctk.CTkButton(bts, text="Cancelar", command=self._cancelar_edicao, width=90,
                                         height=36, font=fonte(12), fg_color=C["card"],
                                         hover_color=C["borda"], border_width=1, border_color=C["borda"])
        ctk.CTkLabel(c, text="Enter adiciona · Esc cancela a edição", text_color=C["fraco"],
                     font=fonte(10)).pack(anchor="w", pady=(4, 0))

        for w in [self.e_nome] + [f.entry for f in self.f_b.values()] + [self.f_pad_d.entry, self.f_pad_e.entry]:
            w.bind("<Return>", lambda e: self._adicionar_ou_salvar(), add="+")
            w.bind("<Escape>", lambda e: self._cancelar_edicao(), add="+")

    def _montar_direita(self):
        dir_ = ctk.CTkFrame(self, fg_color="transparent")
        dir_.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=12)
        dir_.grid_columnconfigure(0, weight=1)
        dir_.grid_rowconfigure(0, weight=5)
        dir_.grid_rowconfigure(1, weight=3)

        # ---------------- Pré-visualização
        prev = ctk.CTkFrame(dir_, fg_color=C["card"], corner_radius=10, border_width=1,
                            border_color=C["borda"])
        prev.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        prev.grid_columnconfigure(0, weight=3)
        prev.grid_columnconfigure(1, weight=2)
        prev.grid_rowconfigure(0, weight=1)
        self.cv_elev = tk.Canvas(prev, bg=C["painel"], highlightthickness=0)
        self.cv_plan = tk.Canvas(prev, bg=C["painel"], highlightthickness=0)
        self.cv_elev.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)
        self.cv_plan.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=8)
        for cv in (self.cv_elev, self.cv_plan):
            cv.bind("<Configure>", lambda e: self._desenhar())
            cv.bind("<Button-1>", self._clique_canvas)
            cv.bind("<Double-Button-1>", self._duplo_clique_canvas)

        # ---------------- Tabela
        tab = ctk.CTkFrame(dir_, fg_color=C["card"], corner_radius=10, border_width=1,
                           border_color=C["borda"])
        tab.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        barra = ctk.CTkFrame(tab, fg_color="transparent")
        barra.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(10, 6))
        self.lbl_tab = ctk.CTkLabel(barra, text="Bocais", font=fonte(14, "bold"))
        self.lbl_tab.pack(side="left")
        ctk.CTkLabel(barra, text="   duplo clique para editar · Del remove", text_color=C["fraco"],
                     font=fonte(11)).pack(side="left")
        for txt, cmd, cor in (("Remover", self._remover_sel, C["erro"]),
                              ("Duplicar", self._duplicar_sel, None),
                              ("Editar", self._editar_sel, None)):
            ctk.CTkButton(barra, text=txt, command=cmd, width=84, height=28, font=fonte(12),
                          fg_color=C["painel"], hover_color=C["borda"], border_width=1,
                          border_color=cor or C["borda"], text_color=cor or C["texto"]).pack(side="right", padx=3)

        cols = [("st", "", 34), ("nome", "Nome", 80), ("local", "Local", 110), ("d", "Ø", 70),
                ("pesc", "Pescoço", 70), ("pos", "Posição", 110), ("ang", "Ângulo", 64),
                ("esp", "Esp.", 60), ("tampa", "Tampa", 60), ("pad", "PAD Ø × esp.", 120)]
        self.tree = ttk.Treeview(tab, style="Vaso.Treeview", columns=[c[0] for c in cols],
                                 show="headings", selectmode="browse")
        for cid, txt, w in cols:
            self.tree.heading(cid, text=txt)
            self.tree.column(cid, width=w, minwidth=30, anchor="center" if cid != "nome" else "w",
                             stretch=cid not in ("st",))
        self.tree.tag_configure("erro", foreground="#fca5a5")
        self.tree.tag_configure("aviso", foreground="#fcd34d")
        self.tree.grid(row=1, column=0, sticky="nsew", padx=(12, 0), pady=(0, 12))
        sb = ctk.CTkScrollbar(tab, command=self.tree.yview, button_color=C["borda"])
        sb.grid(row=1, column=1, sticky="ns", padx=(0, 6), pady=(0, 12))
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<<TreeviewSelect>>", self._sel_tabela)
        self.tree.bind("<Double-1>", lambda e: self._editar_sel())
        self.tree.bind("<Delete>", lambda e: self._remover_sel())
        self.lbl_vazio = ctk.CTkLabel(tab, text="Nenhum bocal ainda. Preencha o formulário à "
                                                "esquerda e clique em  ＋ Adicionar bocal.",
                                      text_color=C["fraco"], font=fonte(12), fg_color=C["painel"])

        # ---------------- Validação + gerar
        base = ctk.CTkFrame(dir_, fg_color="transparent")
        base.grid(row=2, column=0, sticky="ew")
        base.grid_columnconfigure(0, weight=1)
        val = ctk.CTkFrame(base, fg_color=C["card"], corner_radius=10, border_width=1,
                           border_color=C["borda"])
        val.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.lbl_val = ctk.CTkLabel(val, text="", font=fonte(13, "bold"), anchor="w")
        self.lbl_val.pack(fill="x", padx=12, pady=(8, 0))
        self.txt_val = ctk.CTkTextbox(val, height=64, font=fonte(12), fg_color=C["painel"],
                                      wrap="word", activate_scrollbars=True)
        self.txt_val.pack(fill="both", expand=True, padx=8, pady=8)
        self.txt_val.tag_config("erro", foreground="#fca5a5")
        self.txt_val.tag_config("aviso", foreground="#fcd34d")
        self.txt_val.tag_config("ok", foreground="#86efac")
        self.txt_val.configure(state="disabled")

        ger = ctk.CTkFrame(base, fg_color="transparent")
        ger.grid(row=0, column=1, sticky="ns")
        self.bt_gerar = ctk.CTkButton(ger, text="▶  Gerar no SpaceClaim", command=self._gerar,
                                      width=260, height=58, font=fonte(16, "bold"),
                                      fg_color=C["ok2"], hover_color=C["ok"], corner_radius=10)
        self.bt_gerar.pack(fill="both", expand=True)
        ctk.CTkLabel(ger, text="Salva parametros_vaso.json e abre o SpaceClaim",
                     text_color=C["fraco"], font=fonte(10)).pack(pady=(4, 0))

    def _montar_rodape(self):
        rod = ctk.CTkFrame(self, fg_color=C["painel"], corner_radius=0, height=28)
        rod.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.lbl_status = ctk.CTkLabel(rod, text="Pronto.", text_color=C["fraco"], font=fonte(11))
        self.lbl_status.pack(side="left", padx=14)
        ctk.CTkLabel(rod, text="Ctrl+N novo · Ctrl+O abrir · Ctrl+S salvar · F5 gerar",
                     text_color=C["fraco"], font=fonte(11)).pack(side="right", padx=14)

    def _atalhos(self):
        self.bind("<Control-s>", lambda e: self._salvar())
        self.bind("<Control-o>", lambda e: self._abrir())
        self.bind("<Control-n>", lambda e: self._novo())
        self.bind("<F5>", lambda e: self._gerar())

    # ============================================================== leitura
    def _local_atual(self):
        return {"Costado": "Costado", "Tampo Sup.": "Tampo Superior",
                "Tampo Inf.": "Tampo Inferior"}[self.seg_local.get()]

    def _ler_vaso(self, marcar=True):
        campos = {"CostadoDiametro": self.f_D, "CostadoComprimento": self.f_L, "SF": self.f_SF,
                  "esp_costado": self.f_esp_c, "esp_tampo_sup": self.f_esp_ts,
                  "esp_tampo_inf": self.f_esp_ti}
        v = {"TipoTampoSup": self.cb_sup.get(), "TipoTampoInf": self.cb_inf.get()}
        ok = True
        for k, f in campos.items():
            v[k] = f.valor(marcar)
            ok = ok and v[k] is not None
        ang = self.f_ang.valor(marcar and vg.usa_cone(v))
        if ang is None and vg.usa_cone(v):
            ok = False
        v["AnguloCone"] = ang if ang is not None else 30.0
        return v if ok else None

    def _ler_form(self, marcar=True):
        """Lê o formulário do bocal. Retorna (bocal | None, mensagem de erro)."""
        b = {"nome": self.e_nome.get().strip(), "local": self._local_atual(), "pad": self.var_pad.get()}
        faltando = []
        for k, f in self.f_b.items():
            b[k] = f.valor(marcar)
            if b[k] is None:
                faltando.append(f.lbl.cget("text"))
        if b["pad"]:
            b["pad_diametro"] = self.f_pad_d.valor(marcar)
            b["esp_pad"] = self.f_pad_e.valor(marcar)
            if b["pad_diametro"] is None:
                faltando.append("Diâmetro do pad")
            if b["esp_pad"] is None:
                faltando.append("Espessura do pad")
        else:
            b["pad_diametro"], b["esp_pad"] = 0.0, 0.0
        if faltando:
            return None, "Valor inválido em: " + ", ".join(faltando) + "."
        if not b["nome"]:
            return None, "Dê um nome (tag) ao bocal."
        return b, ""

    # ============================================================== estado
    def _aplicar(self, vaso, bocais, ext):
        self._carregando = True
        self.f_D.set(vaso["CostadoDiametro"])
        self.f_L.set(vaso["CostadoComprimento"])
        self.f_SF.set(vaso["SF"])
        self.f_esp_c.set(vaso["esp_costado"])
        self.f_esp_ts.set(vaso["esp_tampo_sup"])
        self.f_esp_ti.set(vaso["esp_tampo_inf"])
        self.f_ang.habilitar(True)
        self.f_ang.set(vaso.get("AnguloCone", 30.0))
        for cb, k in ((self.cb_sup, "TipoTampoSup"), (self.cb_inf, "TipoTampoInf")):
            cb.set(vaso[k] if vaso[k] in vg.TIPOS_TAMPO else "Elipsoidal 2:1")
        self.var_ext.set(bool(ext))
        self.bocais = [dict(b) for b in bocais]
        self.editando = self.selecionado = None
        self._modo_edicao(None)
        self._limpar_form()
        self._form_ativo = False
        self._carregando = False
        self._atualizar()

    def _mudou(self):
        if not self._carregando:
            self.sujo = True
        self._agendar()

    def _agendar(self):
        if self._agendado:
            self.after_cancel(self._agendado)
        self._agendado = self.after(120, self._atualizar)

    def _atualizar(self):
        self._agendado = None
        vaso = self._ler_vaso()
        self.modelo_atual = None
        if vaso:
            v, bs = vg.modelo(vaso, self.bocais, self.var_ext.get())
            self.msgs = vg.validar(v, bs)
            self.modelo_atual = (v, bs)
            ps, pi = vg.perfis(v) if v["CostadoDiametro"] > 0 else (None, None)
            if ps:
                total = v["CostadoComprimento"] + 2 * v["SF"] + ps.altura + pi.altura
                self.lbl_alturas.configure(
                    text="Altura do tampo: sup. %s mm · inf. %s mm\nComprimento total: %s mm"
                         % (vg.fmt(round(ps.altura, 1)), vg.fmt(round(pi.altura, 1)), vg.fmt(round(total, 1))))
            self.lbl_medio.configure(
                text=("Modelado no Ø médio = %s mm (bocais: Ø − esp. do tubo)" % vg.fmt(round(v["CostadoDiametro"], 2)))
                if self.var_ext.get() else "Modelado no Ø informado (superfície média)")
            self.f_ang.habilitar(vg.usa_cone(vaso))
            if not vg.usa_cone(vaso):
                self.f_ang.marcar(True)
        else:
            self.msgs = [(vg.ERRO, None, "Corrija os campos destacados em vermelho (casco/tampos).")]
            self.lbl_alturas.configure(text="")
        self._atualizar_tabela()
        self._atualizar_validacao()
        self._atualizar_titulo()
        self._desenhar()

    def _atualizar_titulo(self):
        nome = os.path.basename(self.arquivo) if self.arquivo else "projeto sem nome"
        self.lbl_arquivo.configure(text=("● " if self.sujo else "") + nome +
                                   ("  — alterações não salvas" if self.sujo else ""))
        self.title(("* " if self.sujo else "") + nome + " — Gerador de Vasos de Pressão")

    def _atualizar_tabela(self):
        st = vg.status_por_bocal(self.msgs, len(self.bocais))
        self.tree.delete(*self.tree.get_children())
        for i, b in enumerate(self.bocais):
            if b["local"] == "Costado":
                pos = "Y = " + vg.fmt(b["posicao"])
                loc = "Costado"
            else:
                pos = "r = " + vg.fmt(b["posicao"])
                loc = "Tampo sup." if b["local"] == "Tampo Superior" else "Tampo inf."
            pad = (vg.fmt(b["pad_diametro"]) + " × " + vg.fmt(b["esp_pad"])) if b.get("pad") else "—"
            icone = {"erro": "✖", "aviso": "⚠"}.get(st[i], "✔")
            self.tree.insert("", "end", iid=str(i), tags=(st[i] or "ok",), values=(
                icone, b["nome"], loc, vg.fmt(b["diametro"]), vg.fmt(b["pescoco"]), pos,
                vg.fmt(b["angulo"]) + "°", vg.fmt(b["espessura"]), vg.fmt(b["esp_tampa"]), pad))
        if self.selecionado is not None and self.selecionado < len(self.bocais):
            self.tree.selection_set(str(self.selecionado))
            self.tree.see(str(self.selecionado))
        n = len(self.bocais)
        self.lbl_tab.configure(text="Bocais (%d)" % n)
        if n == 0:
            self.lbl_vazio.place(relx=0.5, rely=0.55, anchor="center")
        else:
            self.lbl_vazio.place_forget()

    def _atualizar_validacao(self):
        ne = sum(1 for m in self.msgs if m[0] == vg.ERRO)
        na = sum(1 for m in self.msgs if m[0] == vg.AVISO)
        t = self.txt_val
        t.configure(state="normal")
        t.delete("1.0", "end")
        if not self.msgs:
            self.lbl_val.configure(text="✔  Tudo certo — pronto para gerar", text_color=C["ok"])
            t.insert("end", "Nenhum problema encontrado na geometria e nos bocais.", "ok")
        else:
            partes = []
            if ne:
                partes.append("%d erro%s" % (ne, "s" if ne > 1 else ""))
            if na:
                partes.append("%d aviso%s" % (na, "s" if na > 1 else ""))
            self.lbl_val.configure(text=("✖  " if ne else "⚠  ") + " · ".join(partes),
                                   text_color=C["erro"] if ne else C["aviso"])
            for nivel, _i, msg in sorted(self.msgs, key=lambda m: m[0] != vg.ERRO):
                t.insert("end", ("✖ " if nivel == vg.ERRO else "⚠ ") + msg + "\n", nivel)
        t.configure(state="disabled")

    # ============================================================== formulário
    def _form_mudou(self):
        self._form_ativo = True
        self._agendar()

    def _local_mudou(self):
        loc = self._local_atual()
        if loc == "Costado":
            self.f_b["posicao"].lbl.configure(text="Altura Y")
            self.lbl_pos_dica.configure(text="Altura do centro do bocal medida a partir do MEIO do "
                                             "costado (Y = 0). Positivo para cima.")
        else:
            self.f_b["posicao"].lbl.configure(text="Raio a partir do eixo")
            self.lbl_pos_dica.configure(text="Distância horizontal do eixo do vaso até o centro do "
                                             "bocal. 0 = bocal centrado no tampo.")
        self._agendar()

    def _toggle_pad(self):
        if self.var_pad.get():
            self.frame_pad.pack(fill="x", pady=(2, 4), before=self.ancora_pad)
        else:
            self.frame_pad.pack_forget()
        self._agendar()

    def _limpar_form(self, base=None):
        b = dict(vg.BOCAL_PADRAO)
        if base:
            b.update(base)
            b["nome"] = vg.proximo_nome(base["nome"], [x["nome"] for x in self.bocais])
        elif self.bocais:
            ult = self.bocais[-1]
            b.update(ult)
            b["nome"] = vg.proximo_nome(ult["nome"], [x["nome"] for x in self.bocais])
        self._preencher_form(b)

    def _preencher_form(self, b):
        loc_seg = {"Costado": "Costado", "Tampo Superior": "Tampo Sup.", "Tampo Inferior": "Tampo Inf."}
        self.seg_local.set(loc_seg[b["local"]])
        self.e_nome.delete(0, "end")
        self.e_nome.insert(0, b["nome"])
        for k, f in self.f_b.items():
            f.set(b[k])
            f.marcar(True)
        self.var_pad.set(bool(b.get("pad")))
        self.f_pad_d.set(b["pad_diametro"] if b.get("pad") else "")
        self.f_pad_e.set(b["esp_pad"] if b.get("pad") else "")
        self.f_pad_d.marcar(True)
        self.f_pad_e.marcar(True)
        self.lbl_form_erro.configure(text="")
        self._toggle_pad()
        self._local_mudou()

    def _modo_edicao(self, idx):
        self.editando = idx
        if idx is None:
            self.card_bocal.titulo.configure(text="3 · Novo bocal")
            self.bt_add.configure(text="＋  Adicionar bocal")
            self.bt_cancelar.pack_forget()
        else:
            self.card_bocal.titulo.configure(text="3 · Editando bocal " + self.bocais[idx]["nome"])
            self.bt_add.configure(text="✔  Salvar alterações")
            self.bt_cancelar.pack(side="left", padx=(6, 0))

    def _adicionar_ou_salvar(self):
        b, erro = self._ler_form()
        if not b:
            self.lbl_form_erro.configure(text=erro)
            return
        nomes = [x["nome"] for i, x in enumerate(self.bocais) if i != self.editando]
        if b["nome"] in nomes:
            self.lbl_form_erro.configure(text="Já existe um bocal chamado '%s'." % b["nome"])
            return
        self.lbl_form_erro.configure(text="")
        if self.editando is not None:
            self.bocais[self.editando] = b
            self.selecionado = self.editando
            self._status("Bocal %s atualizado." % b["nome"])
            self._modo_edicao(None)
        else:
            self.bocais.append(b)
            self.selecionado = len(self.bocais) - 1
            self._status("Bocal %s adicionado." % b["nome"])
        self.sujo = True
        self._limpar_form(base=b)
        self._form_ativo = False
        self._atualizar()
        self.e_nome.focus_set()

    def _cancelar_edicao(self):
        if self.editando is not None:
            self._modo_edicao(None)
            self._limpar_form()
        self._form_ativo = False
        self._agendar()

    # ============================================================== tabela
    def _idx_sel(self):
        s = self.tree.selection()
        return int(s[0]) if s else None

    def _sel_tabela(self, _=None):
        i = self._idx_sel()
        if i != self.selecionado:
            self.selecionado = i
            self._desenhar()

    def _editar_sel(self):
        i = self._idx_sel()
        if i is None:
            self._status("Selecione um bocal na tabela para editar.")
            return
        self._preencher_form(self.bocais[i])
        self._modo_edicao(i)
        self._form_ativo = True
        self.after(50, lambda: self.esq._parent_canvas.yview_moveto(1.0))  # rola até o formulário
        self.e_nome.focus_set()
        self._agendar()

    def _duplicar_sel(self):
        i = self._idx_sel()
        if i is None:
            self._status("Selecione um bocal na tabela para duplicar.")
            return
        novo = dict(self.bocais[i])
        novo["nome"] = vg.proximo_nome(novo["nome"], [x["nome"] for x in self.bocais])
        self.bocais.insert(i + 1, novo)
        self.selecionado = i + 1
        if self.editando is not None and self.editando > i:
            self.editando += 1
        self.sujo = True
        self._status("Bocal duplicado como %s — ajuste a posição." % novo["nome"])
        self._atualizar()

    def _remover_sel(self):
        i = self._idx_sel()
        if i is None:
            return
        nome = self.bocais[i]["nome"]
        if not messagebox.askyesno("Remover bocal", "Remover o bocal %s?" % nome, parent=self):
            return
        del self.bocais[i]
        if self.editando == i:
            self._modo_edicao(None)
        elif self.editando is not None and self.editando > i:
            self.editando -= 1
        self.selecionado = min(i, len(self.bocais) - 1) if self.bocais else None
        self.sujo = True
        self._status("Bocal %s removido." % nome)
        self._atualizar()

    def _clique_canvas(self, ev):
        cv = ev.widget
        for item in reversed(cv.find_overlapping(ev.x - 3, ev.y - 3, ev.x + 3, ev.y + 3)):
            for tag in cv.gettags(item):
                if tag.startswith("b") and tag[1:].isdigit():
                    self.selecionado = int(tag[1:])
                    self.tree.selection_set(tag[1:])
                    self.tree.see(tag[1:])
                    self._desenhar()
                    return
        self.selecionado = None
        if self.tree.selection():
            self.tree.selection_remove(*self.tree.selection())
        self._desenhar()

    def _duplo_clique_canvas(self, ev):
        self._clique_canvas(ev)
        if self.selecionado is not None:
            self._editar_sel()

    # ============================================================== desenho
    def _fantasma(self):
        """Bocal do formulário (ainda não adicionado), para pré-visualizar."""
        if not self._form_ativo:
            return None
        b, _ = self._ler_form(marcar=False)
        if not b or not self.modelo_atual:
            return None
        if self.var_ext.get():
            b = dict(b)
            b["diametro"] -= b["espessura"]
        return b

    def _ordem_desenho(self, n, fan):
        """Índices a desenhar: o selecionado por último; o bocal em edição é substituído pelo fantasma."""
        ordem = [i for i in range(n) if i != self.selecionado and not (fan and i == self.editando)]
        if self.selecionado is not None and self.selecionado < n and not (fan and self.selecionado == self.editando):
            ordem.append(self.selecionado)
        return ordem

    def _cor_bocal(self, i, st):
        if i is not None and i == self.selecionado:
            return C["sel"], 3
        if st == vg.ERRO:
            return C["erro"], 2
        if st == vg.AVISO:
            return C["aviso"], 2
        return C["bocal"], 1.5

    def _cabecalho_canvas(self, cv, titulo, sub):
        cv.create_text(14, 14, text=titulo, anchor="nw", fill=C["texto"], font=(FONTE, 10, "bold"))
        cv.create_text(14, 31, text=sub, anchor="nw", fill=C["fraco"], font=(FONTE, 9))

    def _desenhar(self):
        try:
            self._desenhar_elevacao()
            self._desenhar_planta()
        except Exception as e:  # nunca deixar a pré-visualização travar a interface
            self._status("Pré-visualização: " + str(e))

    def _desenhar_elevacao(self):
        cv = self.cv_elev
        cv.delete("all")
        w, h = cv.winfo_width(), cv.winfo_height()
        if w < 60 or h < 60:
            return
        self._cabecalho_canvas(cv, "ELEVAÇÃO", "bocais rebatidos para o plano do desenho · Y para cima")
        if not self.modelo_atual or self.modelo_atual[0]["CostadoDiametro"] <= 0 \
                or self.modelo_atual[0]["CostadoComprimento"] <= 0:
            cv.create_text(w / 2, h / 2, text="Preencha os dados do casco", fill=C["fraco"], font=(FONTE, 11))
            return
        v, bs = self.modelo_atual
        st = vg.status_por_bocal(self.msgs, len(bs))
        fan = self._fantasma()
        R, L = v["CostadoDiametro"] / 2.0, v["CostadoComprimento"]
        Y0 = L / 2.0 + v["SF"]
        ps, pi = vg.perfis(v)

        xmax, ymax, ymin = R, ps.Yfim, -pi.Yfim
        for b in bs + ([fan] if fan else []):
            if b["local"] == "Costado":
                xmax = max(xmax, R + b["pescoco"])
                ymax = max(ymax, b["posicao"] + b["diametro"] / 2)
                ymin = min(ymin, b["posicao"] - b["diametro"] / 2)
            elif b["local"] == "Tampo Superior":
                ymax = max(ymax, ps.y(b["posicao"]) + b["pescoco"])
                xmax = max(xmax, abs(b["posicao"]) + b["diametro"] / 2)
            else:
                ymin = min(ymin, -pi.y(b["posicao"]) - b["pescoco"])
                xmax = max(xmax, abs(b["posicao"]) + b["diametro"] / 2)

        topo, base, lat = 56, 18, 100
        s = min((w - 2 * lat) / (2 * xmax), (h - topo - base) / (ymax - ymin))
        oy = topo + ((h - topo - base) - (ymax - ymin) * s) / 2

        def T(x, y):
            return w / 2 + x * s, oy + (ymax - y) * s

        # Contorno do vaso
        dir_ = [(r, -y) for r, y in reversed(pi.pontos())]          # fundo: r de 0 a R
        dir_ += [(R, -Y0), (R, -L / 2), (R, L / 2), (R, Y0)]
        dir_ += ps.pontos()                                          # topo: r de R a 0
        esq = [(-x, y) for x, y in reversed(dir_)]
        pts = []
        for x, y in dir_ + esq:
            pts.extend(T(x, y))
        cv.create_polygon(pts, fill=C["casco_fill"], outline=C["casco"], width=2)

        # Linhas de referência
        xa, _ = T(0, 0)
        cv.create_line(xa, T(0, ymax)[1] - 6, xa, T(0, ymin)[1] + 6, fill=C["fraco"], dash=(8, 3, 2, 3))
        # Fim do costado (onde a rotina deixa de furar) e linhas de tangência (LT)
        for y, costado in ((L / 2, True), (-L / 2, True), (Y0, False), (-Y0, False)):
            x1, yy = T(-R - 20 / s, y)
            x2, _ = T(R + 20 / s, y)
            cv.create_line(x1, yy, x2, yy, fill=C["fraco"] if costado else C["borda"], dash=(3, 3))
            if costado:
                cv.create_text(x1 - 6, yy, text="Y=%+g" % round(y, 1), anchor="e",
                               fill=C["fraco"], font=(FONTE, 8))
            elif v["SF"] * s > 12:  # só escreve "LT" se houver espaço em relação ao fim do costado
                cv.create_text(x1 - 6, yy, text="LT", anchor="e", fill=C["fraco"], font=(FONTE, 8))
        x0, y0 = T(-R, 0)
        cv.create_line(x0 - 8, y0, x0, y0, fill=C["fraco"])
        cv.create_text(x0 - 10, y0, text="Y=0", anchor="e", fill=C["fraco"], font=(FONTE, 8))

        # Bocais (o selecionado por último, por cima)
        ordem = self._ordem_desenho(len(bs), fan)
        self._rotulos = []
        for i in ordem:
            self._bocal_elev(cv, T, bs[i], i, st[i], R, ps, pi, s)
        if fan:
            self._bocal_elev(cv, T, fan, None, None, R, ps, pi, s, fantasma=True)
        self._desenhar_rotulos(cv, h)

    def _desenhar_rotulos(self, cv, h, passo=14):
        """Desenha os rótulos laterais afastando os que ficariam sobrepostos (com linha de chamada)."""
        for lado in (1, -1):
            grupo = sorted([r for r in self._rotulos if r[0] == lado], key=lambda r: r[2])
            ys = []
            for r in grupo:
                ys.append(max(r[2], ys[-1] + passo) if ys else r[2])
            excesso = (ys[-1] - (h - 10)) if ys else 0
            if excesso > 0:  # empurra de volta para cima se passou do fim do canvas
                for k in range(len(ys) - 1, -1, -1):
                    lim = (h - 10) - (len(ys) - 1 - k) * passo
                    ys[k] = min(ys[k], lim)
            for (ld, x, y, txt, cor, tag), yy in zip(grupo, ys):
                xt = x + ld * 22
                if abs(yy - y) > 1:
                    cv.create_line(x + ld * 3, y, xt - ld * 3, yy, fill=C["fraco"], tags=tag)
                else:
                    cv.create_line(x + ld * 3, y, xt - ld * 3, yy, fill=C["borda"], tags=tag)
                cv.create_text(xt, yy, text=txt, anchor="w" if ld > 0 else "e", fill=cor,
                               font=(FONTE, 9, "bold"), tags=tag)

    def _bocal_elev(self, cv, T, b, i, st, R, ps, pi, s, fantasma=False):
        cor, larg = (C["acento"], 1.5) if fantasma else self._cor_bocal(i, st)
        tag = ("b%d" % i,) if i is not None else ()
        dash = (5, 3) if fantasma else None
        d, p = b["diametro"], b["pescoco"]
        sgn = 1 if math.cos(math.radians(b["angulo"])) >= -1e-9 else -1
        rot = "%s  %s°" % (b["nome"] or "?", vg.fmt(b["angulo"]))

        if b["local"] == "Costado":
            y = b["posicao"]
            if b.get("pad") and b["pad_diametro"] > 0:
                (xa, ya), (xb, yb) = T(sgn * R, y - b["pad_diametro"] / 2), T(sgn * R, y + b["pad_diametro"] / 2)
                cv.create_line(xa, ya, xb, yb, fill=C["pad"], width=6, tags=tag, dash=dash)
            pts = [T(sgn * R, y - d / 2), T(sgn * (R + p), y - d / 2),
                   T(sgn * (R + p), y + d / 2), T(sgn * R, y + d / 2)]
            cv.create_polygon([c for pt in pts for c in pt], fill="" if fantasma else C["bocal_fill"],
                              outline=cor, width=larg, tags=tag, dash=dash)
            (xt, yt1), (_, yt2) = T(sgn * (R + p), y - d / 2), T(sgn * (R + p), y + d / 2)
            cv.create_line(xt, yt1, xt, yt2, fill=cor, width=3, tags=tag)
            xl, yl = T(sgn * (R + p), y)
            self._rotulos.append((sgn, xl, yl, rot,
                                  cor if (fantasma or st or i == self.selecionado) else C["texto"], tag))
            return

        sup = b["local"] == "Tampo Superior"
        perf = ps if sup else pi
        k = 1 if sup else -1
        xc = sgn * b["posicao"]
        if b.get("pad") and b["pad_diametro"] > 0:
            linha = []
            for n in range(25):
                x = xc - b["pad_diametro"] / 2 + b["pad_diametro"] * n / 24.0
                x = max(-R, min(R, x))
                linha.extend(T(x, k * perf.y(x)))
            cv.create_line(linha, fill=C["pad"], width=6, tags=tag, dash=dash)
        y_sup = k * perf.y(xc)
        y_base = k * min(perf.y(xc - d / 2), perf.y(xc + d / 2), perf.y(xc))
        y_tip = y_sup + k * p
        pts = [T(xc - d / 2, y_base), T(xc - d / 2, y_tip), T(xc + d / 2, y_tip), T(xc + d / 2, y_base)]
        cv.create_polygon([c for pt in pts for c in pt], fill="" if fantasma else C["bocal_fill"],
                          outline=cor, width=larg, tags=tag, dash=dash)
        (xa, yt), (xb, _) = T(xc - d / 2, y_tip), T(xc + d / 2, y_tip)
        cv.create_line(xa, yt, xb, yt, fill=cor, width=3, tags=tag)
        cv.create_text((xa + xb) / 2, yt - k * 10, text=rot, anchor="s" if sup else "n",
                       fill=cor if (fantasma or st or i == self.selecionado) else C["texto"],
                       font=(FONTE, 9, "bold"), tags=tag)

    def _desenhar_planta(self):
        cv = self.cv_plan
        cv.delete("all")
        w, h = cv.winfo_width(), cv.winfo_height()
        if w < 60 or h < 60:
            return
        self._cabecalho_canvas(cv, "PLANTA", "vista de cima (+Y) · orientação dos bocais")
        if not self.modelo_atual or self.modelo_atual[0]["CostadoDiametro"] <= 0:
            return
        v, bs = self.modelo_atual
        st = vg.status_por_bocal(self.msgs, len(bs))
        fan = self._fantasma()
        R = v["CostadoDiametro"] / 2.0
        rmax = R
        for b in bs + ([fan] if fan else []):
            if b["local"] == "Costado":
                rmax = max(rmax, R + b["pescoco"])
        topo, base = 52, 30
        util = h - topo - base - 2 * 24          # 24 px para os rótulos de ângulo
        s = min(w - 90, util) / (2 * rmax)
        cx, cy = w / 2, topo + 24 + util / 2

        def P(x, z):
            return cx + x * s, cy + z * s

        # Referências de ângulo
        rr = rmax * s + 12
        x0, y0 = P(-R, -R)
        x1, y1 = P(R, R)
        cv.create_oval(x0, y0, x1, y1, outline=C["casco"], width=2, fill=C["casco_fill"])
        for ang in range(0, 360, 30):
            a = math.radians(ang)
            xs, ys = P(R * math.cos(a), R * math.sin(a))
            cv.create_line(cx, cy, xs, ys, fill=C["grade"])
        for ang in (0, 90, 180, 270):
            a = math.radians(ang)
            cv.create_line(cx, cy, cx + rr * math.cos(a), cy + rr * math.sin(a),
                           fill=C["borda"], dash=(2, 3))
            ri = max(R * s - 16, 10)   # rótulos de ângulo por dentro do casco (não colidem com os bocais)
            cv.create_text(cx + ri * math.cos(a), cy + ri * math.sin(a),
                           text="%d°" % ang, fill=C["fraco"], font=(FONTE, 9))
        cv.create_text(cx + rr + 2, cy + 12, text="+X", fill=C["fraco"], font=(FONTE, 8), anchor="w")
        cv.create_text(cx + 14, cy + rr + 10, text="+Z", fill=C["fraco"], font=(FONTE, 8), anchor="w")

        ordem = self._ordem_desenho(len(bs), fan)
        itens = [(bs[i], i, st[i], False) for i in ordem]
        if fan:
            itens.append((fan, None, None, True))
        rot_ang = {}   # ângulo -> [nomes] (bocais do costado no mesmo ângulo)
        for b, i, sti, fantasma in itens:
            cor, larg = (C["acento"], 1.5) if fantasma else self._cor_bocal(i, sti)
            tag = ("b%d" % i,) if i is not None else ()
            dash = (5, 3) if fantasma else None
            a = math.radians(b["angulo"])
            u, n = (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))
            d = b["diametro"]
            if b["local"] == "Costado":
                if b.get("pad") and b["pad_diametro"] > 0:
                    meia = math.degrees(b["pad_diametro"] / 2 / R)
                    cv.create_arc(x0, y0, x1, y1, start=-b["angulo"] - meia, extent=2 * meia,
                                  style="arc", outline=C["pad"], width=6, tags=tag)
                r2 = R + b["pescoco"]
                cant = [(R * u[0] + d / 2 * n[0], R * u[1] + d / 2 * n[1]),
                        (r2 * u[0] + d / 2 * n[0], r2 * u[1] + d / 2 * n[1]),
                        (r2 * u[0] - d / 2 * n[0], r2 * u[1] - d / 2 * n[1]),
                        (R * u[0] - d / 2 * n[0], R * u[1] - d / 2 * n[1])]
                cv.create_polygon([c for pt in cant for c in P(*pt)], fill="" if fantasma else C["bocal_fill"],
                                  outline=cor, width=larg, tags=tag, dash=dash)
                chave = round(b["angulo"] % 360.0, 1)
                g = rot_ang.setdefault(chave, {"r": r2, "u": u, "nomes": [], "cor": C["texto"], "tag": tag})
                g["r"] = max(g["r"], r2)
                g["nomes"].append(b["nome"] or "?")
                if fantasma or sti or i == self.selecionado:
                    g["cor"], g["tag"] = cor, tag
            else:
                px, pz = b["posicao"] * u[0], b["posicao"] * u[1]
                if b.get("pad") and b["pad_diametro"] > 0:
                    q0, q1 = P(px - b["pad_diametro"] / 2, pz - b["pad_diametro"] / 2), \
                             P(px + b["pad_diametro"] / 2, pz + b["pad_diametro"] / 2)
                    cv.create_oval(*q0, *q1, outline=C["pad"], width=3, tags=tag)
                q0, q1 = P(px - d / 2, pz - d / 2), P(px + d / 2, pz + d / 2)
                sup = b["local"] == "Tampo Superior"
                cv.create_oval(*q0, *q1, outline=cor, width=larg,
                               fill=(C["bocal_fill"] if sup and not fantasma else ""),
                               dash=(4, 2) if (not sup or fantasma) else None, tags=tag)
                cv.create_text((q0[0] + q1[0]) / 2, q0[1] - 8, text=(b["nome"] or "?") + (" ↑" if sup else " ↓"),
                               fill=cor if (fantasma or sti) else C["texto"], font=(FONTE, 9, "bold"), tags=tag)

        for g in rot_ang.values():
            u = g["u"]
            xl, yl = P(g["r"] * u[0], g["r"] * u[1])
            xl, yl = xl + 16 * u[0], yl + 16 * u[1]
            anc = "w" if u[0] > 0.3 else ("e" if u[0] < -0.3 else ("n" if u[1] > 0 else "s"))
            cv.create_text(xl, yl, text=" · ".join(g["nomes"]), anchor=anc, fill=g["cor"],
                           font=(FONTE, 9, "bold"), tags=g["tag"])

        cv.create_text(14, h - 8, anchor="sw", fill=C["fraco"], font=(FONTE, 8),
                       text="▭ costado   ● tampo sup. ↑   ◌ tampo inf. ↓   ▬ pad   tracejado azul = bocal em edição")

    # ============================================================== arquivos
    def _json_atual(self):
        vaso = self._ler_vaso()
        if not vaso:
            return None
        v, bs = vg.modelo(vaso, self.bocais, self.var_ext.get())
        entrada = {"vaso": vaso, "bocais": self.bocais, "diametros_externos": self.var_ext.get()}
        return vg.para_json_rotina(v, bs, entrada)

    def _escrever(self, caminho, data):
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)  # ASCII: seguro p/ o Python do SpaceClaim

    def _confirmar_descartar(self):
        if not self.sujo:
            return True
        r = messagebox.askyesnocancel("Alterações não salvas",
                                      "Deseja salvar as alterações antes de continuar?", parent=self)
        if r is None:
            return False
        if r:
            return self._salvar()
        return True

    def _novo(self):
        if not self._confirmar_descartar():
            return
        self.arquivo = None
        self.sujo = False
        self._aplicar(dict(vg.VASO_PADRAO), [], False)
        self._status("Novo projeto.")

    def _abrir(self):
        if not self._confirmar_descartar():
            return
        caminho = filedialog.askopenfilename(parent=self, initialdir=PASTA_PROJETO, title="Abrir projeto",
                                             filetypes=[("Projeto do vaso", "*.json"), ("Todos", "*.*")])
        if caminho:
            self._carregar_arquivo(caminho)

    def _carregar_arquivo(self, caminho, silencioso=False):
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                data = json.load(f)
            vaso, bocais, ext = vg.de_json(data)
        except Exception as e:
            if not silencioso:
                messagebox.showerror("Erro ao abrir", "Não foi possível ler o arquivo:\n%s" % e, parent=self)
            self._aplicar(dict(vg.VASO_PADRAO), [], False)
            return
        self.arquivo = caminho
        self.sujo = False
        self._aplicar(vaso, bocais, ext)
        self._status("Aberto: %s (%d bocais)" % (os.path.basename(caminho), len(bocais)))

    def _salvar(self, como=False):
        data = self._json_atual()
        if data is None:
            messagebox.showerror("Dados inválidos", "Corrija os campos destacados em vermelho antes de salvar.",
                                 parent=self)
            return False
        caminho = self.arquivo
        if como or not caminho:
            caminho = filedialog.asksaveasfilename(parent=self, initialdir=PASTA_PROJETO, title="Salvar projeto",
                                                   defaultextension=".json", initialfile="vaso.json",
                                                   filetypes=[("Projeto do vaso", "*.json")])
            if not caminho:
                return False
        try:
            self._escrever(caminho, data)
        except OSError as e:
            messagebox.showerror("Erro ao salvar", str(e), parent=self)
            return False
        self.arquivo = caminho
        self.sujo = False
        self._atualizar_titulo()
        self._status("Salvo em %s" % caminho)
        return True

    def _fechar(self):
        if self._confirmar_descartar():
            self.destroy()

    # ============================================================== SpaceClaim
    def _ler_config(self):
        cfg = {}
        try:
            with open(CAMINHO_CONFIG, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except (OSError, ValueError):
            pass
        if not cfg.get("spaceclaim") or not os.path.isfile(cfg["spaceclaim"]):
            cfg["spaceclaim"] = SPACECLAIM_PADRAO if os.path.isfile(SPACECLAIM_PADRAO) \
                else (self._detectar_spaceclaim() or cfg.get("spaceclaim") or SPACECLAIM_PADRAO)
        return cfg

    @staticmethod
    def _detectar_spaceclaim():
        achados = []
        for raiz in (os.environ.get("ProgramFiles", r"C:\Program Files"), r"C:\Program Files"):
            achados += glob.glob(os.path.join(raiz, "ANSYS Inc", "v*", "scdm", "SpaceClaim.exe"))
        return sorted(set(achados))[-1] if achados else None

    def _salvar_config(self):
        try:
            with open(CAMINHO_CONFIG, "w", encoding="utf-8") as f:
                json.dump(self.config_app, f, indent=2)
        except OSError:
            pass

    def _atualizar_status_sc(self):
        ok = os.path.isfile(self.config_app.get("spaceclaim", ""))
        self.bt_sc.configure(text=("●  SpaceClaim encontrado" if ok else "●  SpaceClaim: configurar"),
                             text_color=C["ok"] if ok else C["erro"])

    def _dialogo_config(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Configurar SpaceClaim")
        dlg.geometry("640x210")
        dlg.configure(fg_color=C["card"])
        dlg.transient(self)
        dlg.after(50, dlg.grab_set)
        ctk.CTkLabel(dlg, text="Caminho do SpaceClaim.exe", font=fonte(14, "bold")).pack(anchor="w", padx=16, pady=(16, 4))
        ctk.CTkLabel(dlg, text="Se usar outra versão do ANSYS, a rotina ainda importa a API V252 "
                               "(veja o início de rotina.py).", text_color=C["fraco"], font=fonte(11)).pack(anchor="w", padx=16)
        linha = ctk.CTkFrame(dlg, fg_color="transparent")
        linha.pack(fill="x", padx=16, pady=10)
        e = ctk.CTkEntry(linha, font=fonte(12), fg_color=C["campo"])
        e.insert(0, self.config_app.get("spaceclaim", ""))
        e.pack(side="left", fill="x", expand=True)

        def procurar():
            p = filedialog.askopenfilename(parent=dlg, title="Localizar SpaceClaim.exe",
                                           filetypes=[("SpaceClaim", "SpaceClaim.exe"), ("Executáveis", "*.exe")])
            if p:
                e.delete(0, "end")
                e.insert(0, os.path.normpath(p))

        def detectar():
            p = self._detectar_spaceclaim()
            if p:
                e.delete(0, "end")
                e.insert(0, p)
            else:
                messagebox.showinfo("Detectar", "Nenhuma instalação encontrada em Program Files\\ANSYS Inc.", parent=dlg)

        ctk.CTkButton(linha, text="Procurar…", width=90, command=procurar, fg_color=C["painel"],
                      hover_color=C["borda"]).pack(side="left", padx=(6, 0))
        ctk.CTkButton(linha, text="Detectar", width=80, command=detectar, fg_color=C["painel"],
                      hover_color=C["borda"]).pack(side="left", padx=(6, 0))

        def ok():
            self.config_app["spaceclaim"] = e.get().strip().strip('"')
            self._salvar_config()
            self._atualizar_status_sc()
            dlg.destroy()

        ctk.CTkButton(dlg, text="Salvar", command=ok, width=120, fg_color=C["acento2"],
                      hover_color=C["acento"]).pack(anchor="e", padx=16, pady=(6, 16))

    def _gerar(self):
        data = self._json_atual()
        if data is None:
            messagebox.showerror("Dados inválidos", "Corrija os campos destacados em vermelho.", parent=self)
            return
        erros = [m for m in self.msgs if m[0] == vg.ERRO]
        if erros:
            lista = "\n".join("• " + m[2] for m in erros[:6]) + ("\n…" if len(erros) > 6 else "")
            if not messagebox.askyesno("Há erros na configuração",
                                       "%d erro(s) encontrados — a geometria provavelmente não será gerada:\n\n%s"
                                       "\n\nGerar mesmo assim?" % (len(erros), lista), icon="warning", parent=self):
                return
        if not self.bocais and not messagebox.askyesno(
                "Sem bocais", "Nenhum bocal cadastrado. Gerar só o casco?", parent=self):
            return
        try:
            self._escrever(CAMINHO_JSON, data)
        except OSError as e:
            messagebox.showerror("Erro ao salvar", str(e), parent=self)
            return
        if self.arquivo and os.path.normcase(os.path.abspath(self.arquivo)) == os.path.normcase(CAMINHO_JSON):
            self.sujo = False
            self._atualizar_titulo()

        exe = self.config_app.get("spaceclaim", "")
        if not os.path.isfile(exe):
            messagebox.showwarning("SpaceClaim não encontrado",
                                   "Os parâmetros foram salvos em:\n%s\n\nMas o SpaceClaim não foi encontrado em:\n%s"
                                   "\n\nConfigure o caminho correto." % (CAMINHO_JSON, exe), parent=self)
            self._dialogo_config()
            return
        try:
            env = os.environ.copy()
            env["VASO_JSON"] = CAMINHO_JSON
            subprocess.Popen([exe, "/RunScript=" + CAMINHO_ROTINA], cwd=PASTA_PROJETO, env=env)
        except Exception as e:
            messagebox.showerror("Erro de execução", "Falha ao abrir o SpaceClaim:\n%s" % e, parent=self)
            return
        self._status("SpaceClaim iniciado — a geometria será gerada ao abrir (%d bocais)." % len(self.bocais))
        self.bt_gerar.configure(state="disabled", text="Abrindo SpaceClaim…")
        self.after(4000, lambda: self.bt_gerar.configure(state="normal", text="▶  Gerar no SpaceClaim"))

    # ============================================================== util
    def _status(self, txt):
        self.lbl_status.configure(text=txt)


# Mantém o nome antigo para quem importava a classe
AppVasoPressao = App

if __name__ == "__main__":
    App().mainloop()
