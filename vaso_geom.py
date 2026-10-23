# -*- coding: utf-8 -*-
"""Geometria e validação do vaso de pressão.

Espelha a matemática de rotina.py (que roda dentro do SpaceClaim) para que a
interface consiga desenhar a pré-visualização e detectar problemas antes de
gerar a geometria. Não depende do SpaceClaim nem de bibliotecas externas.

Convenções (iguais às da rotina):
  - Eixo do vaso = Y. Y = 0 no meio do costado.
  - Costado de -L/2 a +L/2; straight flange (SF) até ±(L/2 + SF); tampos além disso.
  - Ângulo dos bocais medido no plano XZ: 0° = +X, 90° = +Z.
  - Bocais no costado: posição = altura Y. Bocais nos tampos: posição = raio a partir do eixo.
"""
import math
import re
from collections import Counter

TIPOS_TAMPO = [
    "Torisférico ASME 6%",
    "Torisférico ASME 10%",
    "Elipsoidal 2:1",
    "Hemisférico",
    "Cônico",
    "Toricônico",
]
LOCAIS = ["Costado", "Tampo Superior", "Tampo Inferior"]
CHAVES_VASO = ["CostadoDiametro", "CostadoComprimento", "SF", "esp_costado",
               "esp_tampo_sup", "esp_tampo_inf", "AnguloCone"]
LISTA_POR_LOCAL = {"Costado": "lista_costado", "Tampo Superior": "lista_tampo_sup",
                   "Tampo Inferior": "lista_tampo_inf"}

VASO_PADRAO = {
    "CostadoDiametro": 1400.0, "CostadoComprimento": 7460.0, "SF": 103.0,
    "esp_costado": 78.4, "esp_tampo_sup": 78.4, "esp_tampo_inf": 78.4,
    "AnguloCone": 30.0, "TipoTampoSup": "Elipsoidal 2:1", "TipoTampoInf": "Elipsoidal 2:1",
}
BOCAL_PADRAO = {
    "nome": "N1", "local": "Costado", "diametro": 200.0, "pescoco": 300.0,
    "posicao": 0.0, "angulo": 0.0, "espessura": 12.0, "esp_tampa": 50.0,
    "pad": False, "pad_diametro": 0.0, "esp_pad": 0.0,
}


# ------------------------------------------------------------------ números
def parse_num(texto):
    """Converte texto em float aceitando vírgula ou ponto como decimal."""
    if isinstance(texto, (int, float)):
        return float(texto)
    s = str(texto).strip().replace(" ", "")
    if not s:
        raise ValueError("campo vazio")
    if "," in s and "." in s:      # 1.234,5 -> 1234.5
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    v = float(s)
    if math.isnan(v) or math.isinf(v):
        raise ValueError("valor inválido")
    return v


def fmt(v, casas=6):
    """Formata número sem zeros desnecessários (154.4, 300, 12.67)."""
    if v is None:
        return ""
    s = ("%." + str(casas) + "g") % v
    return s


def proximo_nome(nome, existentes):
    """N1 -> N2, 3A -> 3B, X -> X_2 ... garantindo que não repita."""
    existentes = set(existentes)
    m = re.match(r"^(.*?)(\d+)$", nome)
    candidatos = []
    if m:
        base, n = m.group(1), int(m.group(2))
        candidatos = [base + str(n + k) for k in range(1, 500)]
    elif nome and nome[-1].isalpha() and nome[-1].upper() < "Z":
        base = nome[:-1]
        c = nome[-1]
        candidatos = [base + chr(ord(c) + k) for k in range(1, ord("Z") - ord(c.upper()) + 1)]
    candidatos += [(nome or "N") + "_" + str(k) for k in range(2, 500)]
    for c in candidatos:
        if c not in existentes:
            return c
    return nome


# ------------------------------------------------------------------ tampos
def calc_tampo_params(tipo, R, Y0, ang_cone_deg):
    """Mesma formulação de rotina.py. Retorna
    (is_conico, CYc, CXk, CYk, TX, TY, Y_fim, KR)."""
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
        # Ponto de tangência entre a junta tórica e o cone (meio-ângulo alpha)
        TX = CXk + KR * math.cos(alpha)
        TY = CYk + KR * math.sin(alpha)
        Y_top = TY + TX / math.tan(alpha)
        return is_conical, None, CXk, CYk, TX, TY, Y_top, KR
    elif "Hemis" in tipo:
        CR = 0.5 * D
        return is_conical, Y0, 0, Y0, 0, Y0 + CR, Y0 + CR, CR
    else:  # Torisféricos ou Elipsoidal (aproximação 0,9D / 0,17D)
        if "6%" in tipo:
            CR, KR = D, 0.06 * D
        elif "10%" in tipo:
            CR, KR = D, 0.10 * D
        else:
            CR, KR = 0.90 * D, 0.17 * D
        dist_y = math.sqrt((CR - KR) ** 2 - (R - KR) ** 2)
        CYc, CXk, CYk = Y0 - dist_y, R - KR, Y0
        u_x, u_y = CXk / (CR - KR), (CYk - CYc) / (CR - KR)
        TX, TY = CXk + KR * u_x, CYk + KR * u_y
        return is_conical, CYc, CXk, CYk, TX, TY, CYc + CR, KR


class Perfil:
    """Perfil meridional de um tampo (valores de Y positivos, a partir de Y0)."""

    def __init__(self, tipo, R, Y0, ang_cone):
        self.tipo, self.R, self.Y0, self.ang = tipo, R, Y0, ang_cone
        (self.conico, self.CYc, self.CXk, self.CYk, self.TX, self.TY,
         self.Yfim, self.KR) = calc_tampo_params(tipo, R, Y0, ang_cone)

    @property
    def altura(self):
        return self.Yfim - self.Y0

    def y(self, r):
        r = min(abs(r), self.R)
        if self.conico:
            t = math.tan(math.radians(self.ang))
            if self.tipo == "Cônico" or r <= self.TX:
                return self.Yfim - r / t
            return self.CYk + math.sqrt(max(0.0, self.KR ** 2 - (r - self.CXk) ** 2))
        if "Hemis" in self.tipo:
            return self.Y0 + math.sqrt(max(0.0, (self.Yfim - self.Y0) ** 2 - r ** 2))
        if r <= self.TX:
            return self.CYc + math.sqrt(max(0.0, (self.Yfim - self.CYc) ** 2 - r ** 2))
        return self.CYk + math.sqrt(max(0.0, self.KR ** 2 - (r - self.CXk) ** 2))

    def pontos(self, n=90):
        """Pontos (r, y) de r = R até r = 0, incluindo o ponto de tangência."""
        rs = [self.R * (1 - i / float(n)) for i in range(n + 1)]
        if 0 < self.TX < self.R:
            rs.append(self.TX)
            rs.sort(reverse=True)
        return [(r, self.y(r)) for r in rs]


def perfis(vaso):
    R = vaso["CostadoDiametro"] / 2.0
    Y0 = vaso["CostadoComprimento"] / 2.0 + vaso["SF"]
    ang = vaso.get("AnguloCone", 30.0)
    return (Perfil(vaso["TipoTampoSup"], R, Y0, ang),
            Perfil(vaso["TipoTampoInf"], R, Y0, ang))


def usa_cone(vaso):
    return any(t in ("Cônico", "Toricônico") for t in (vaso["TipoTampoSup"], vaso["TipoTampoInf"]))


# ------------------------------------------------------------------ modelo
def modelo(vaso, bocais, diametros_externos):
    """Retorna (vaso, bocais) com os valores que de fato vão para a rotina.

    Se os diâmetros informados forem externos, converte para a superfície
    média (D - t), que é onde a casca é modelada."""
    v = dict(vaso)
    bs = [dict(b) for b in bocais]
    if diametros_externos:
        v["CostadoDiametro"] = vaso["CostadoDiametro"] - vaso["esp_costado"]
        for b in bs:
            b["diametro"] = b["diametro"] - b["espessura"]
    return v, bs


def para_json_rotina(v, bs, entrada=None):
    """Monta o dicionário no formato lido por rotina.py."""
    out = {k: float(v[k]) for k in CHAVES_VASO}
    for chave in LISTA_POR_LOCAL.values():
        out[chave] = []
    for b in bs:
        d = {
            "nome": b["nome"].strip(),
            "diametro": b["diametro"],
            "pescoco": b["pescoco"],
            "angulo": b["angulo"],
            "espessura": b["espessura"],
            "esp_tampa": b["esp_tampa"],
        }
        if b["local"] == "Costado":
            d["altura_y"] = b["posicao"]
        else:
            d["raio_offset"] = b["posicao"]
        if b.get("pad"):
            d["pad_diametro"] = b["pad_diametro"]
            d["esp_pad"] = b["esp_pad"]
        out[LISTA_POR_LOCAL[b["local"]]].append(d)
    out["TipoTampoSup"] = v["TipoTampoSup"]
    out["TipoTampoInf"] = v["TipoTampoInf"]
    if entrada is not None:
        # Estado original da interface (ignorado pela rotina), para reabrir o projeto
        out["_entrada"] = entrada
    return out


def de_json(data):
    """Lê um JSON (salvo pela interface nova ou antiga). Retorna (vaso, bocais, diam_externos)."""
    if isinstance(data.get("_entrada"), dict):
        e = data["_entrada"]
        vaso = dict(VASO_PADRAO)
        vaso.update(e.get("vaso", {}))
        bocais = []
        for b in e.get("bocais", []):
            nb = dict(BOCAL_PADRAO)
            nb.update(b)
            bocais.append(nb)
        return vaso, bocais, bool(e.get("diametros_externos", False))

    vaso = dict(VASO_PADRAO)
    for k in CHAVES_VASO + ["TipoTampoSup", "TipoTampoInf"]:
        if k in data:
            vaso[k] = data[k]
    bocais = []
    for local, chave in LISTA_POR_LOCAL.items():
        for b in data.get(chave, []):
            tem_pad = "pad_diametro" in b
            bocais.append({
                "nome": str(b.get("nome", "")),
                "local": local,
                "diametro": float(b.get("diametro", 0)),
                "pescoco": float(b.get("pescoco", 0)),
                "posicao": float(b.get("altura_y", b.get("raio_offset", 0))),
                "angulo": float(b.get("angulo", 0)),
                "espessura": float(b.get("espessura", 10.0)),
                "esp_tampa": float(b.get("esp_tampa", 10.0)),
                "pad": tem_pad,
                "pad_diametro": float(b.get("pad_diametro", 0)) if tem_pad else 0.0,
                "esp_pad": float(b.get("esp_pad", 0)) if tem_pad else 0.0,
            })
    return vaso, bocais, False


# ------------------------------------------------------------------ validação
ERRO, AVISO = "erro", "aviso"


def _raio_externo(b):
    r = b["diametro"] / 2.0
    if b.get("pad") and b.get("pad_diametro", 0) > 0:
        r = max(r, b["pad_diametro"] / 2.0)
    return r


def validar(v, bs):
    """Retorna lista de (nivel, indice | (i, j) | None, mensagem)."""
    msgs = []

    def add(nivel, i, m):
        msgs.append((nivel, i, m))

    D, L, SF = v["CostadoDiametro"], v["CostadoComprimento"], v["SF"]
    R = D / 2.0
    if D <= 0:
        add(ERRO, None, "O diâmetro do costado deve ser maior que zero.")
    if L <= 0:
        add(ERRO, None, "O comprimento do costado deve ser maior que zero.")
    if SF < 0:
        add(ERRO, None, "O straight flange (SF) não pode ser negativo.")
    for k, rot in (("esp_costado", "costado"), ("esp_tampo_sup", "tampo superior"),
                   ("esp_tampo_inf", "tampo inferior")):
        if v[k] <= 0:
            add(ERRO, None, "A espessura do %s deve ser maior que zero." % rot)
        elif R > 0 and v[k] >= R:
            add(ERRO, None, "A espessura do %s é maior que o raio do vaso." % rot)
    if usa_cone(v) and not (5.0 <= v["AnguloCone"] <= 85.0):
        add(ERRO, None, "O meio-ângulo do cone deve estar entre 5° e 85°.")
    if any(m[0] == ERRO for m in msgs):
        return msgs  # sem casco válido não dá para checar os bocais

    ps, pi = perfis(v)
    nomes = Counter(b["nome"].strip() for b in bs)
    validos = []

    for i, b in enumerate(bs):
        nm = b["nome"].strip() or "#%d" % (i + 1)
        ok = True
        if not b["nome"].strip():
            add(ERRO, i, "Bocal #%d está sem nome." % (i + 1))
        elif nomes[b["nome"].strip()] > 1:
            add(ERRO, i, "%s: nome repetido. A rotina identifica os corpos pelo nome." % nm)
        d = b["diametro"]
        if d <= 0:
            add(ERRO, i, "%s: diâmetro deve ser maior que zero." % nm)
            continue
        if b["pescoco"] <= 0:
            add(ERRO, i, "%s: pescoço deve ser maior que zero." % nm)
            ok = False
        if b["espessura"] <= 0:
            add(ERRO, i, "%s: espessura do tubo deve ser maior que zero." % nm)
        elif b["espessura"] >= d / 2.0:
            add(ERRO, i, "%s: espessura do tubo maior que o raio do bocal." % nm)
        if b["esp_tampa"] <= 0:
            add(ERRO, i, "%s: espessura da tampa deve ser maior que zero." % nm)

        esp_base = {"Costado": v["esp_costado"], "Tampo Superior": v["esp_tampo_sup"],
                    "Tampo Inferior": v["esp_tampo_inf"]}[b["local"]]
        if b.get("pad"):
            if b["pad_diametro"] <= d:
                add(ERRO, i, "%s: Ø do pad (%s) deve ser maior que o Ø do bocal (%s)."
                    % (nm, fmt(b["pad_diametro"]), fmt(d)))
            if b["esp_pad"] <= 0:
                add(ERRO, i, "%s: espessura do pad deve ser maior que zero." % nm)
            elif b["esp_pad"] <= esp_base:
                add(AVISO, i, "%s: esp. do pad (%s) ≤ esp. do casco (%s). Informe a espessura TOTAL "
                              "da região (casco + chapa)." % (nm, fmt(b["esp_pad"]), fmt(esp_base)))

        ext = _raio_externo(b)
        oque = "o pad" if (b.get("pad") and b["pad_diametro"] / 2.0 >= d / 2.0) else "o furo"
        if b["local"] == "Costado":
            if d >= D:
                add(ERRO, i, "%s: diâmetro do bocal maior que o do costado." % nm)
                ok = False
            y = b["posicao"]
            lo, hi = y - ext, y + ext
            if hi > L / 2.0 or lo < -L / 2.0:
                lado = "superior" if hi > L / 2.0 else "inferior"
                lim = (L / 2.0 - ext) if hi > L / 2.0 else (-L / 2.0 + ext)
                add(ERRO, i, "%s: %s vai de Y=%s a Y=%s e passa da borda %s do costado (Y=%s). "
                             "A rotina só fura o costado. Use altura %s %s."
                    % (nm, oque, fmt(lo, 5), fmt(hi, 5), lado, fmt(L / 2.0 if hi > L / 2.0 else -L / 2.0, 5),
                       "≤" if hi > L / 2.0 else "≥", fmt(round(lim, 1), 6)))
        else:
            r = b["posicao"]
            if r < 0:
                add(ERRO, i, "%s: o raio a partir do eixo não pode ser negativo." % nm)
                ok = False
            elif r + ext > R:
                add(ERRO, i, "%s: %s chega a r=%s, além da borda do tampo (R=%s). Use raio ≤ %s."
                    % (nm, oque, fmt(r + ext, 5), fmt(R, 5), fmt(round(R - ext, 1), 6)))
        if ok:
            validos.append(i)

    # Sobreposição entre bocais no mesmo local
    for a_pos, i in enumerate(validos):
        for j in validos[a_pos + 1:]:
            bi, bj = bs[i], bs[j]
            if bi["local"] != bj["local"]:
                continue
            ri, rj = _raio_externo(bi), _raio_externo(bj)
            if bi["local"] == "Costado":
                dth = abs((bi["angulo"] - bj["angulo"] + 180.0) % 360.0 - 180.0)
                arco = R * math.radians(dth)
                dist = math.hypot(arco, bi["posicao"] - bj["posicao"])
            else:
                ti, tj = math.radians(bi["angulo"]), math.radians(bj["angulo"])
                dist = math.hypot(bi["posicao"] * math.cos(ti) - bj["posicao"] * math.cos(tj),
                                  bi["posicao"] * math.sin(ti) - bj["posicao"] * math.sin(tj))
            if dist < ri + rj - 1e-6:
                ni, nj = bi["nome"].strip() or "#%d" % (i + 1), bj["nome"].strip() or "#%d" % (j + 1)
                txt = "%s e %s se sobrepõem (centros a %s mm; mínimo %s mm)." % (
                    ni, nj, fmt(round(dist), 6), fmt(round(ri + rj), 6))
                add(ERRO, (i, j), txt)
    return msgs


def status_por_bocal(msgs, n):
    st = [None] * n
    for nivel, idx, _ in msgs:
        if idx is None:
            continue
        for i in (idx if isinstance(idx, tuple) else (idx,)):
            if i < n and (nivel == ERRO or st[i] is None):
                st[i] = nivel
    return st
