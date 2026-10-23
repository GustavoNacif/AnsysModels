# AnsysModels — Gerador Paramétrico de Vasos de Pressão

Ferramenta para gerar a geometria de vasos de pressão no **ANSYS SpaceClaim** a partir de parâmetros informados numa interface gráfica.

A interface (CustomTkinter) coleta as dimensões do casco, os tipos de tampo e a lista de bocais, salva tudo em `parametros_vaso.json` e abre o SpaceClaim executando a rotina `rotina.py`, que constrói o modelo.

## Arquivos

| Arquivo | Função |
|---|---|
| `interface.py` | Interface gráfica: entrada de parâmetros, cadastro de bocais e disparo do SpaceClaim |
| `rotina.py` | Script do SpaceClaim (API V252): lê o JSON e gera costado, tampos, bocais e PADs |
| `parametros_vaso.json` | Parâmetros do vaso (gerado pela interface; o do repositório serve de exemplo) |

## Requisitos

- Windows
- ANSYS 2025 R2 (v252) com SpaceClaim instalado
- Python 3 com as dependências de `requirements.txt`

## Instalação

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Uso

1. Execute a interface **a partir da pasta do projeto** (os caminhos do JSON e da rotina são relativos ao diretório atual):
   ```bash
   python interface.py
   ```
2. Na aba **1. Parâmetros do Casco**, preencha diâmetro, comprimento, *straight flange*, espessuras, ângulo do cone e o tipo de cada tampo.
3. Na aba **2. Gerenciar Bocais**, escolha o local (costado, tampo superior ou inferior), preencha as dimensões e clique em **Adicionar à Lista**. Marque a opção de PAD para incluir chapa de reforço.
4. Clique em **Gerar Geometria no SpaceClaim**.

### Tipos de tampo suportados

Torisférico ASME 6%, Torisférico ASME 10%, Elipsoidal 2:1, Hemisférico, Cônico e Toricônico.

## Parâmetros (`parametros_vaso.json`)

Todas as dimensões em mm e ângulos em graus.

| Chave | Descrição |
|---|---|
| `CostadoDiametro` | Diâmetro do costado |
| `CostadoComprimento` | Comprimento do costado |
| `SF` | *Straight flange* dos tampos |
| `esp_costado`, `esp_tampo_sup`, `esp_tampo_inf` | Espessuras |
| `AnguloCone` | Meio-ângulo do cone (tampos cônico/toricônico) |
| `TipoTampoSup`, `TipoTampoInf` | Tipo de cada tampo |
| `lista_costado`, `lista_tampo_sup`, `lista_tampo_inf` | Listas de bocais |

Cada bocal tem `nome`, `diametro`, `pescoco`, `angulo`, `espessura` e `esp_tampa`, mais `altura_y` (bocais no costado) ou `raio_offset` (bocais nos tampos). Bocais com PAD incluem `pad_diametro` e `esp_pad`.

## Configuração

O caminho do SpaceClaim está fixo em `interface.py`:

```python
caminho_spaceclaim = r"C:\Program Files\ANSYS Inc\v252\scdm\SpaceClaim.exe"
```

Ajuste se a sua instalação estiver em outro local ou versão. Ao mudar de versão do ANSYS, atualize também o import da API no início de `rotina.py` (`SpaceClaim.Api.V252`).
