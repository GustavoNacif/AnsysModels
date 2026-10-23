# AnsysModels — Gerador Paramétrico de Vasos de Pressão

Ferramenta para gerar a geometria de vasos de pressão no **ANSYS SpaceClaim** a partir de parâmetros informados numa interface gráfica.

A interface (CustomTkinter) coleta as dimensões do casco, os tipos de tampo e a lista de bocais, salva tudo em `parametros_vaso.json` e abre o SpaceClaim executando a rotina `rotina.py`, que constrói o modelo.

## Arquivos

| Arquivo | Função |
|---|---|
| `main.py` / `interface.py` | Interface gráfica: dados do vaso, cadastro de bocais, pré-visualização, validação e disparo do SpaceClaim |
| `vaso_geom.py` | Geometria dos tampos e validação (mesma matemática da rotina, sem depender do SpaceClaim) |
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

```bash
python main.py
```

- **Esquerda:** dados do casco e dos tampos, e o formulário do bocal. Números aceitam vírgula ou ponto.
- **Pré-visualização:** elevação e planta são atualizadas enquanto você digita. O bocal em edição aparece tracejado em azul. Clique num bocal para selecioná-lo; duplo clique para editar.
- **Tabela de bocais:** editar (duplo clique), duplicar ou remover (Del).
- **Validação:** aponta antes de gerar os bocais que saem do costado ou do tampo, sobreposições, nomes repetidos, pad menor que o bocal etc.
- **Projetos:** Novo / Abrir / Salvar (Ctrl+N, Ctrl+O, Ctrl+S). Ao abrir, a interface carrega o último `parametros_vaso.json`.
- **Gerar no SpaceClaim (F5):** salva `parametros_vaso.json` e abre o SpaceClaim executando `rotina.py`.
- **Diâmetros externos:** se marcado, o Ø do costado e dos bocais é convertido para a superfície média (D − t) antes de ir para a rotina.

Convenções: Y = 0 no meio do costado; bocais no costado são posicionados pela altura Y, nos tampos pelo raio a partir do eixo; ângulo em planta 0° = +X, 90° = +Z.

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

O caminho do SpaceClaim é detectado automaticamente em `C:\Program Files\ANSYS Inc\v*\scdm\`. Para mudar, clique no indicador **SpaceClaim** no topo da interface (fica salvo em `config_interface.json`) ou defina a variável de ambiente `SPACECLAIM_EXE`. Ao mudar de versão do ANSYS, atualize também o import da API no início de `rotina.py` (`SpaceClaim.Api.V252`).
