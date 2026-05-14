# Guia de Upload de Catálogo — Agente 10

Como subir o catálogo da sua empresa pra classificação automática + descoberta
de fornecedores.

## 1. Formato aceito

- **Extensão:** `.csv` (UTF-8 ou Latin-1) ou `.xlsx`
- **Delimitador CSV:** `,`, `;` ou `\t` (auto-detectado)
- **Tamanho:** sem limite hard, mas catálogos >5.000 linhas demoram alguns
  minutos pra classificar (cada cluster faz 1 chamada Claude Haiku)

## 2. Coluna obrigatória

**Pelo menos uma** das seguintes precisa estar no header (nome exato, **case-
insensitive**, sem importar acentos):

| Nome aceito                                                          | Significado                               |
| -------------------------------------------------------------------- | ----------------------------------------- |
| `descricao_original`                                                 | Descrição do material/serviço (preferido) |
| `descricao`                                                          | idem                                      |
| `descricao do material`, `descricao do produto`, `descricao do item` | idem                                      |
| `objeto`                                                             | idem                                      |
| `material`                                                           | idem                                      |
| `produto`                                                            | idem                                      |
| `item`                                                               | idem                                      |

**Exemplo:**

```
descricao_original
Locação de motoniveladora 140K
Manutenção preventiva em transformador
Cabo de alumínio CAA 4/0 AWG
```

## 3. Colunas opcionais (enriquecem o resultado)

Todas opcionais. Aliases comuns funcionam:

| Campo                   | Aliases aceitos                                                  |
| ----------------------- | ---------------------------------------------------------------- |
| `agrupamento`           | grupo, grupo de material, grup. merc, categoria, familia, classe |
| `id_linha_origem`       | id, codigo, cod, codigo material                                 |
| `fornecedor_atual`      | fornecedor, razao social, razao social fornecedor                |
| `cnpj_fornecedor`       | cnpj, cnpj do fornecedor                                         |
| `valor_total`           | valor, total, valor total, preco, preco total                    |
| `quantidade`            | qtd, qtde, quant                                                 |
| `uf_solicitante`        | uf, estado                                                       |
| `municipio_solicitante` | municipio, cidade                                                |
| `centro_custo`          | centro de custo, cc                                              |
| `data_compra`           | data, data compra, data da compra                                |

Colunas que não batem com nenhum alias **não causam erro** — vão pra um campo
genérico `extras` (JSONB) sem afetar a classificação.

## 4. Template pronto pra usar

Baixe [upload_template.csv](upload_template.csv) — tem 5 linhas de exemplo
com todas as colunas opcionais preenchidas. Substitua pelo seu catálogo real.

## 5. O que NÃO funciona

- Arquivos `.xls` (Excel antigo) — converter pra `.xlsx`
- PDF ou imagens — só CSV/XLSX estruturado
- Header em mais de uma linha — só uma linha de header no topo
- Linhas em branco no meio são toleradas (puladas silenciosamente)
- Coluna de descrição vazia em alguma linha → essa linha rejeita o arquivo
  inteiro com erro. Limpe linhas sem descrição antes de subir.

## 6. Como interpretar o resultado

Depois do upload:

1. **Status pending → processing → done** (visível na lista de uploads)
2. **Clusters formados** agrupam descrições similares (ex: "Locação Motoniveladora 140K"
   e "Aluguel Motoniveladora Cat 14" viram um único cluster)
3. Cada cluster recebe um **CNAE** com confiança:
   - 🟢 **Verde (≥85%)**: classificação automática via retrieval
   - 🟡 **Amarelo (60-85%)**: curador IA decidiu entre top-5 candidatos
   - 🔴 **Vermelho (<60%)**: marcado como `manual_pending` — precisa revisor humano
4. Para clusters com CNAE confiável: **shortlist top-10 fornecedores** ordenada
   por capital social

## 7. Revisão humana

Clusters vermelhos abrem na UI com dropdown pra você selecionar o CNAE correto
da taxonomia oficial (1.331 subclasses CNAE 2.3 do IBGE). Após PATCH, a
shortlist é regerada automaticamente em background.

## 8. Problemas comuns

**"missing required column 'descricao_original'"** → seu arquivo não tem
nenhum dos nomes da seção 2. Renomeie a coluna principal pra `descricao`.

**Upload trava em 0%** → backend ainda processando OU caiu. Aguarde 5-10min
(catálogos grandes), depois confira a aba `status` na lista — se ficar `failed`,
o `erro` no detalhe do upload mostra a causa.

**Shortlists vazias** → o CNAE do cluster não está na nossa base de empresas
ATIVAS (atualmente coberto: ~118 CNAEs do piloto ELETROBRÁS — vai expandir).

**Encoding bizarro** (acentos quebrados) → salvar como UTF-8 no Excel:
_Salvar Como → CSV UTF-8 (delimitado por vírgulas)_.
