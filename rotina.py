# Python Script, API Version = V252
# -*- coding: utf-8 -*-
import math
import json
import os
from SpaceClaim.Api.V252 import Command

# ==========================================
# 1. PARÂMETROS DO VASO (LIDOS DO JSON)
# ==========================================
# Procura o JSON: 1) caminho enviado pela interface (VASO_JSON),
# 2) mesma pasta deste script, 3) diretório atual.
def _localizar_json():
    candidatos = []
    if os.environ.get("VASO_JSON"):
        candidatos.append(os.environ["VASO_JSON"])
    try:
        candidatos.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "parametros_vaso.json"))
    except NameError:
        pass
    candidatos.append(os.path.join(os.getcwd(), "parametros_vaso.json"))
    for c in candidatos:
        if os.path.isfile(c):
            return c
    raise IOError("parametros_vaso.json nao encontrado. Procurado em: " + "; ".join(candidatos))

caminho_json = _localizar_json()
print("Lendo parametros de: " + caminho_json)

with open(caminho_json, "r") as f:
    dados = json.load(f)

CostadoDiametro = dados["CostadoDiametro"]
CostadoRaio = CostadoDiametro / 2.0
CostadoComprimento = dados["CostadoComprimento"]
SF = dados["SF"]

esp_costado = dados["esp_costado"]
esp_tampo_sup = dados["esp_tampo_sup"]
esp_tampo_inf = dados["esp_tampo_inf"]

lista_costado = dados["lista_costado"]
lista_tampo_sup = dados["lista_tampo_sup"]
lista_tampo_inf = dados["lista_tampo_inf"]

TipoTampoSup = dados.get("TipoTampoSup", "Elipsoidal 2:1")
TipoTampoInf = dados.get("TipoTampoInf", "Elipsoidal 2:1")
AnguloCone = dados.get("AnguloCone", 30.0)

R = CostadoRaio
L = CostadoComprimento
Y0 = (L / 2.0) + SF

# ==========================================
# 2. CÁLCULO MATEMÁTICO DOS TAMPOS
# ==========================================
def calc_tampo_params(tipo, R, Y0, ang_cone_deg):
    D = 2 * R
    alpha = math.radians(ang_cone_deg)
    is_conical = "Cônico" in tipo or "Toricônico" in tipo

    if tipo == "Cônico":
        TX, TY = R, Y0
        Y_top = Y0 + R / math.tan(alpha)
        return is_conical, None, None, None, TX, TY, Y_top, 0.0
    elif tipo == "Toricônico":
        KR = 0.06 * D
        CXk, CYk = R - KR, Y0
        TX = CXk + KR * math.sin(alpha)
        TY = CYk + KR * math.cos(alpha)
        Y_top = TY + TX / math.tan(alpha)
        return is_conical, None, CXk, CYk, TX, TY, Y_top, KR
    elif "Hemis" in tipo:
        CR = 0.5 * D
        return is_conical, Y0, 0, Y0, 0, Y0 + CR, Y0 + CR, CR
    else: # Torisféricos ou Elipsoidal
        if "6%" in tipo: CR, KR = D, 0.06 * D
        elif "10%" in tipo: CR, KR = D, 0.10 * D
        else: CR, KR = 0.90 * D, 0.17 * D

        dist_y = math.sqrt((CR - KR) ** 2 - (R - KR) ** 2)
        CYc, CXk, CYk = Y0 - dist_y, R - KR, Y0
        u_x, u_y = CXk / (CR - KR), (CYk - CYc) / (CR - KR)
        TX, TY = CXk + KR * u_x, CYk + KR * u_y
        return is_conical, CYc, CXk, CYk, TX, TY, CYc + CR, KR

# Obtém os parâmetros com base na escolha
is_con_sup, CYc_sup, CXk_sup, CYk_sup, TX_sup, TY_sup, Y_top_sup, KR_sup = calc_tampo_params(TipoTampoSup, R, Y0, AnguloCone)
is_con_inf, CYc_inf, CXk_inf, CYk_inf, TX_inf, TY_inf, Y_bot_abs, KR_inf = calc_tampo_params(TipoTampoInf, R, Y0, AnguloCone)

Y_costado_sup, Y_costado_inf = L / 2.0, -L / 2.0
Y_sf_sup, Y_sf_inf = Y0, -Y0

def get_tampo_y_sup(r):
    if is_con_sup:
        if TipoTampoSup == "Cônico": return Y_top_sup - r / math.tan(math.radians(AnguloCone))
        if r <= TX_sup: return Y_top_sup - r / math.tan(math.radians(AnguloCone))
        return CYk_sup + math.sqrt(max(0, KR_sup**2 - (r - CXk_sup)**2))
    else:
        if "Hemis" in TipoTampoSup: return Y0 + math.sqrt(max(0, (Y_top_sup - Y0)**2 - r**2))
        if r <= TX_sup: return CYc_sup + math.sqrt(max(0, (Y_top_sup - CYc_sup)**2 - r**2))
        return CYk_sup + math.sqrt(max(0, KR_sup**2 - (r - CXk_sup)**2))

def get_tampo_y_inf(r):
    if is_con_inf:
        if TipoTampoInf == "Cônico": return Y_bot_abs - r / math.tan(math.radians(AnguloCone))
        if r <= TX_inf: return Y_bot_abs - r / math.tan(math.radians(AnguloCone))
        return CYk_inf + math.sqrt(max(0, KR_inf**2 - (r - CXk_inf)**2))
    else:
        if "Hemis" in TipoTampoInf: return Y0 + math.sqrt(max(0, (Y_bot_abs - Y0)**2 - r**2))
        if r <= TX_inf: return CYc_inf + math.sqrt(max(0, (Y_bot_abs - CYc_inf)**2 - r**2))
        return CYk_inf + math.sqrt(max(0, KR_inf**2 - (r - CXk_inf)**2))

# ==========================================
# 3. GERAÇÃO DAS SUPERFÍCIES DO VASO
# ==========================================
sectionPlane = Plane.PlaneXY
ViewHelper.SetSketchPlane(sectionPlane, None)

p_c_inf = Point2D.Create(MM(R), MM(Y_costado_inf))
p_c_sup = Point2D.Create(MM(R), MM(Y_costado_sup))
p_sf_sup = Point2D.Create(MM(R), MM(Y_sf_sup))
p_top = Point2D.Create(MM(0), MM(Y_top_sup))
p_sf_inf = Point2D.Create(MM(R), MM(Y_sf_inf))
p_bot = Point2D.Create(MM(0), MM(-Y_bot_abs))

SketchLine.Create(p_c_inf, p_c_sup) # Costado
SketchLine.Create(p_c_sup, p_sf_sup) # SF Sup

# Tampo Superior
if TipoTampoSup == "Cônico":
    SketchLine.Create(p_sf_sup, p_top)
elif TipoTampoSup == "Toricônico":
    SketchArc.Create(Point2D.Create(MM(CXk_sup), MM(CYk_sup)), p_sf_sup, Point2D.Create(MM(TX_sup), MM(TY_sup)))
    SketchLine.Create(Point2D.Create(MM(TX_sup), MM(TY_sup)), p_top)
elif "Hemis" in TipoTampoSup:
    SketchArc.Create(Point2D.Create(0, MM(Y0)), p_sf_sup, p_top)
else:
    SketchArc.Create(Point2D.Create(MM(CXk_sup), MM(CYk_sup)), p_sf_sup, Point2D.Create(MM(TX_sup), MM(TY_sup)))
    SketchArc.Create(Point2D.Create(0, MM(CYc_sup)), Point2D.Create(MM(TX_sup), MM(TY_sup)), p_top)

SketchLine.Create(p_sf_inf, p_c_inf) # SF Inf

# Tampo Inferior
if TipoTampoInf == "Cônico":
    SketchLine.Create(p_bot, p_sf_inf)
elif TipoTampoInf == "Toricônico":
    SketchLine.Create(p_bot, Point2D.Create(MM(TX_inf), MM(-TY_inf)))
    SketchArc.Create(Point2D.Create(MM(CXk_inf), MM(-CYk_inf)), Point2D.Create(MM(TX_inf), MM(-TY_inf)), p_sf_inf)
elif "Hemis" in TipoTampoInf:
    SketchArc.Create(Point2D.Create(0, MM(-Y0)), p_bot, p_sf_inf)
else:
    SketchArc.Create(Point2D.Create(MM(CXk_inf), MM(-CYk_inf)), Point2D.Create(MM(TX_inf), MM(-TY_inf)), p_sf_inf)
    SketchArc.Create(Point2D.Create(0, MM(-CYc_inf)), p_bot, Point2D.Create(MM(TX_inf), MM(-TY_inf)))

ViewHelper.SetViewMode(InteractionMode.Solid, None)
curves = GetRootPart().Curves
rev_axis = Line.Create(Point.Create(0, 0, 0), Direction.DirY)

def revolve_and_rename(sel_curves, name):
    body_count = GetRootPart().Bodies.Count
    sel = Selection.Create(sel_curves)
    RevolveEdges.Execute(sel, rev_axis, DEG(360), False, ExtrudeType.ForceIndependent)
    RenameObject.Execute(Selection.Create(GetRootPart().Bodies[body_count]), name)

idx = 0
revolve_and_rename([curves[idx]], "Costado"); idx += 1
revolve_and_rename([curves[idx]], "SF Sup"); idx += 1

curvas_sup = 1 if (TipoTampoSup == "Cônico" or "Hemis" in TipoTampoSup) else 2
revolve_and_rename([curves[i] for i in range(idx, idx+curvas_sup)], "Tampo Superior"); idx += curvas_sup

revolve_and_rename([curves[idx]], "SF Inf"); idx += 1

curvas_inf = 1 if (TipoTampoInf == "Cônico" or "Hemis" in TipoTampoInf) else 2
revolve_and_rename([curves[i] for i in range(idx, idx+curvas_inf)], "Tampo Inferior")
# ==========================================
# 5. GERAÇÃO DOS BOCAIS E 6. LIMPEZA BOOLEANA
# ==========================================
def criar_bocal_vessel(bocal, loc):
    diam = bocal["diametro"]
    pescoco = bocal["pescoco"]
    nome = bocal["nome"]
    theta = math.radians(bocal.get("angulo", 0))
    nx, nz = math.cos(theta), math.sin(theta)

    # --- 5.1 Cálculo de Posicionamento ---
    if loc == "Costado":
        TipX, TipY, TipZ = (R + pescoco) * nx, bocal["altura_y"], (R + pescoco) * nz
        InnerX, InnerY, InnerZ = (R - 500.0) * nx, bocal["altura_y"], (R - 500.0) * nz
    elif loc == "Tampo Superior":
        r_off = bocal["raio_offset"]
        surf_y = get_tampo_y_sup(r_off)
        TipX, TipY, TipZ = r_off * nx, surf_y + pescoco, r_off * nz
        InnerX, InnerY, InnerZ = TipX, surf_y - 1000.0, TipZ
    elif loc == "Tampo Inferior":
        r_off = bocal["raio_offset"]
        surf_y = -get_tampo_y_inf(r_off)
        TipX, TipY, TipZ = r_off * nx, surf_y - pescoco, r_off * nz
        InnerX, InnerY, InnerZ = TipX, surf_y + 1000.0, TipZ

    # --- 5.2 Geometria e Extrusão ---
    tip_pt = Point.Create(MM(TipX), MM(TipY), MM(TipZ))
    vec = [InnerX - TipX, InnerY - TipY, InnerZ - TipZ]
    mag = math.sqrt(vec[0] ** 2 + vec[1] ** 2 + vec[2] ** 2)
    dir_inward = Direction.Create(vec[0] / mag, vec[1] / mag, vec[2] / mag)

    plane = Plane.Create(Frame.Create(tip_pt, dir_inward))
    ViewHelper.SetSketchPlane(plane, None)
    SketchCircle.Create(Point2D.Create(0, 0), MM(diam / 2.0))
    ViewHelper.SetViewMode(InteractionMode.Solid, None)

    tubo = GetRootPart().Bodies[-1]
    RenameObject.Execute(Selection.Create(tubo), "Tampo " + nome)

    ExtrudeEdges.Execute(Selection.Create(tubo.Edges[0]), Selection.Create(tubo.Faces[0]),
                         MM(-mag), ExtrudeEdgeOptions(ExtrudeType=ExtrudeType.ForceIndependent))

    tubo = GetRootPart().Bodies[-1]
    RenameObject.Execute(Selection.Create(tubo), "Bocal " + nome)

    # --- 6. Booleanas (Corte e Limpeza) ---
    target_shell = [b for b in GetRootPart().Bodies if b.Name == loc][0]

    # Fura o Vaso
    Combine.Intersect(Selection.Create(target_shell), Selection.Create(tubo), MakeSolidsOptions())
    Delete.Execute(Selection.Create(target_shell))
    ultima_regiao = GetRootPart().Bodies[-1]
    RenameObject.Execute(Selection.Create(ultima_regiao), loc)
    target_shell = [b for b in GetRootPart().Bodies if b.Name == loc][0]

    # B. Interseção: Usar Casco (já furado) para cortar o Tubo (Remove a sobra interna)
    try:
        Combine.Intersect(Selection.Create(tubo), Selection.Create(target_shell), MakeSolidsOptions())
    except:
        pass

    ultima_regiao = GetRootPart().Bodies[-1]
    Delete.Execute(Selection.Create(ultima_regiao))


def criar_pad(bocal, loc):
    # Verifica se o bocal atual possui a instrução para gerar um pad
    if "pad_diametro" not in bocal:
        return

    pad_diam = bocal["pad_diametro"]
    nome = bocal["nome"]
    pescoco = bocal["pescoco"]
    theta = math.radians(bocal.get("angulo", 0))
    nx, nz = math.cos(theta), math.sin(theta)

    # --- 1. Cálculo do Posicionamento e Vetores (Baseado na tampa) ---
    if loc == "Costado":
        TipX, TipY, TipZ = (R + pescoco) * nx, bocal["altura_y"], (R + pescoco) * nz
        InnerX, InnerY, InnerZ = 0.0, bocal["altura_y"], 0.0
    elif loc == "Tampo Superior":
        r_off = bocal["raio_offset"]
        surf_y = get_tampo_y_sup(r_off)
        TipX, TipY, TipZ = r_off * nx, surf_y + pescoco, r_off * nz
        InnerX, InnerY, InnerZ = TipX, surf_y - 1000.0, TipZ
    elif loc == "Tampo Inferior":
        r_off = bocal["raio_offset"]
        surf_y = -get_tampo_y_inf(r_off)
        TipX, TipY, TipZ = r_off * nx, surf_y - pescoco, r_off * nz
        InnerX, InnerY, InnerZ = TipX, surf_y + 1000.0, TipZ

    tip_pt = Point.Create(MM(TipX), MM(TipY), MM(TipZ))
    vec = [InnerX - TipX, InnerY - TipY, InnerZ - TipZ]
    mag = math.sqrt(vec[0] ** 2 + vec[1] ** 2 + vec[2] ** 2)
    dir_inward = Direction.Create(vec[0] / mag, vec[1] / mag, vec[2] / mag)

    # --- 2. Criar a superfície do esboço do pad ---
    plane = Plane.Create(Frame.Create(tip_pt, dir_inward))
    ViewHelper.SetSketchPlane(plane, None)
    SketchCircle.Create(Point2D.Create(0, 0), MM(pad_diam / 2.0))
    ViewHelper.SetViewMode(InteractionMode.Solid, None)

    esboco_pad = GetRootPart().Bodies[-1]

    # --- 3. Simular Projeção (Extrusão do contorno + Split Face) ---
    target_shell = [b for b in GetRootPart().Bodies if b.Name == loc][0]

    # Extruda a aresta do esboço transformando-a numa superfície que atravessa o casco
    ExtrudeEdges.Execute(Selection.Create(esboco_pad.Faces[0].Edges[0]),
                         Selection.Create(esboco_pad.Faces[0]),
                         MM(-mag * 1.5),  # Força a travessia completa do casco
                         ExtrudeEdgeOptions(ExtrudeType=ExtrudeType.ForceIndependent))

    cilindro_projecao = GetRootPart().Bodies[-1]
    RenameObject.Execute(Selection.Create(cilindro_projecao), "Cilindro Projecao")

    # Usa o cilindro criado para dividir (fatiar) as faces do casco
    try:
        Combine.Intersect(Selection.Create(target_shell), Selection.Create(cilindro_projecao), MakeSolidsOptions())
    except:
        pass

    # Limpa os corpos auxiliares gerados para a projeção
    Delete.Execute(Selection.Create(esboco_pad))
    Delete.Execute(Selection.Create(cilindro_projecao))
    corpo_alvo = [b for b in GetRootPart().Bodies if b.Name == loc][0]

    # 2. Renomeia esse corpo original para "Pad Bocal [Nome]"
    novo_nome_pad = "Pad " + bocal["nome"]
    RenameObject.Execute(Selection.Create(corpo_alvo), novo_nome_pad)

    # 3. Pega a última superfície/corpo criado (o resultado do seu Detach)
    ultima_superficie = GetRootPart().Bodies[-1]

    # 4. Renomeia essa última superfície para o nome original que estava em 'loc'
    RenameObject.Execute(Selection.Create(ultima_superficie), loc)


# Dicionário que servirá de backup para as espessuras de cada componente
mapa_espessuras = {
    "Costado": esp_costado,
    "Tampo Superior": esp_tampo_sup,
    "Tampo Inferior": esp_tampo_inf,
    "SF Sup": esp_costado,  # Straight Flange costuma seguir o costado
    "SF Inf": esp_costado
}

# Juntamos as listas temporariamente apenas para ler os dados de input
todos_bocais = lista_costado + lista_tampo_sup + lista_tampo_inf

for bocal in todos_bocais:
    # Registra a espessura do bocal (usa 10.0 como fallback de segurança se o usuário não preencher)
    mapa_espessuras["Bocal " + bocal["nome"]] = bocal.get("espessura", 10.0)

    # Se o bocal tiver pad, registra a espessura do pad
    if "pad_diametro" in bocal:
        mapa_espessuras["Pad " + bocal["nome"]] = bocal.get("esp_pad", 10.0)

    mapa_espessuras["Tampo " + bocal["nome"]] = bocal.get("esp_tampa", 10.0)

# Loop enquanto houver qualquer bocal em qualquer lista
while lista_costado or lista_tampo_sup or lista_tampo_inf:

    # Variável que conterá a rodada atual (até 3 bocais)
    rodada_atual = []

    if lista_costado:
        rodada_atual.append({"data": lista_costado.pop(0), "loc": "Costado"})

    if lista_tampo_sup:
        rodada_atual.append({"data": lista_tampo_sup.pop(0), "loc": "Tampo Superior"})

    if lista_tampo_inf:
        rodada_atual.append({"data": lista_tampo_inf.pop(0), "loc": "Tampo Inferior"})

    # Executa a modelagem da rodada
    for item in rodada_atual:
        print("Modelando: " + item["data"]["nome"] + " em " + item["loc"])
        criar_bocal_vessel(item["data"], item["loc"])
        criar_pad(item["data"], item["loc"])

# ==========================================
# 7. CONECTIVIDADE DA MALHA (SHARE TOPOLOGY)
# ==========================================
options_topo = ShareTopologyOptions()
options_topo.Tolerance = MM(0.2)
ShareTopology.FindAndFix(options_topo)

# ==========================================
# 8. ATRIBUIÇÃO DE ESPESSURAS (SHELL THICKNESS)
# ==========================================
print("Iniciando conversão para superfícies médias (Midsurface)...")

corpos_convertidos = 0

# Criamos uma lista estática (snapshot) dos corpos atuais.
# Isso é obrigatório porque o comando Midsurface exclui o sólido original e cria uma superfície nova.
corpos_originais = list(GetRootPart().Bodies)

for corpo in corpos_originais:
    nome = corpo.Name

    # Verifica se o nome do corpo está no nosso backup de espessuras
    if nome in mapa_espessuras:
        esp_alvo = mapa_espessuras[nome]

        try:
            # Seleciona o corpo atual
            selecao_corpo = Selection.Create(corpo)

            # Executa o comando correto apontado por você
            result = Midsurface.Convert(selecao_corpo, MM(esp_alvo))

            corpos_convertidos += 1
            print("-> Midsurface extraída para: " + nome + " (Espessura: " + str(esp_alvo) + "mm)")

        except Exception as e:
            print("Erro ao converter o corpo " + nome + ": " + str(e))
    else:
        # Corpos que não estão na lista de backup
        print("-> Aviso: Corpo '" + nome + "' ignorado (sem espessura mapeada).")

print("Conversão concluída. Total de componentes convertidos para shell: " + str(corpos_convertidos))

# ==========================================
# 9. INVERSÃO DE NORMAIS (APONTAR PARA DENTRO)
# ==========================================
print("Iniciando inversão de normais...")

# Limpa qualquer seleção pendente
Selection.Clear()

for corpo in GetRootPart().Bodies:
    nome = corpo.Name

    # Filtra apenas as peças tubulares (adicione mais nomes se precisar, ex: "Pescoço")
    if "Bocal" in nome:
        for face in corpo.Faces:
            try:
                # 1. Seleciona a face atual
                Selection.Create(face).SetActive()

                # 2. Chama a ferramenta de Análise de Normal do SpaceClaim
                Command.Execute("AnalysisNormal")

                # 3. Executa o comando de inverter a normal
                Command.Execute("ReverseFaceNormal")

            except Exception as e:
                print("Erro ao inverter a normal na face do corpo " + nome + ": " + str(e))

        print("-> Normal invertida para: " + nome)

# Volta para a ferramenta de seleção padrão (Seta) e limpa a tela
Command.Execute("Select")
Selection.Clear()

print("Inversão de normais concluída.")
