# Diagnóstico do primeiro lote de Uganda

Feito em 2026-10-12 com `python tools/diagnose_uganda.py`. Números completos em [stats.json](stats.json). Só diagnóstico: nada foi retreinado e o lote continua fora do treino e do teste.

## A pergunta

No primeiro lote de rótulos de Uganda (1.589 arquivos), o `belt_v3` responde "baixa qualidade" para 80% a 100% dos frutos, qualquer que seja o rótulo. Por quê? Três hipóteses:

1. **Ordem trocada**: os números de classe desse lote seguem outra ordem.
2. **Outra forma de fotografar**: as fotos são diferentes das dos outros lotes.
3. **Outro critério de anotação**: os mesmos nomes de classe foram usados para coisas diferentes.

## Conclusão

| Hipótese | O que a evidência diz |
|---|---|
| Ordem trocada | **Não sustentada.** Nas fotos originais olhadas, a classe 1 são flores e a classe 2 são frutos claros imaturos, como diz o artigo. Nenhuma troca simples de números arruma o lote. |
| Outra forma de fotografar | **Sustentada.** As caixas dos frutos são cerca de 2,5 vezes menores na foto, e só de 1% a 7% delas chegam aos 24 px que o treino exige. |
| Outro critério de anotação | **Sustentada.** Os recortes marcados "maduro" quase nunca são vermelhos ou amarelos, e "estragado" é a classe mais comum do lote, com 15 por foto. |

As duas últimas se somam, e não conseguimos separar quanto cada uma pesa. Também fica em aberto se o lote esconde mais de um sub-lote anotado por pessoas diferentes. **O lote continua excluído.**

Uma consequência: boa parte dos frutos desse lote parece mesmo imatura nas imagens. A resposta "baixa qualidade" do modelo discorda do rótulo, mas não necessariamente da fruta.

## Evidência

### 1. A tabela publicada soma as duas ordens

A tabela 2 do artigo do conjunto dá o número de caixas por classe. Ela bate, caixa por caixa, com a contagem por número de classe em todos os 3.098 arquivos, sem distinguir os lotes:

| Classe no artigo | Publicado | Caixas com esse número em todos os arquivos |
|---|---|---|
| árvore (0) | 5.347 | 5.347 |
| flor (1) | 23.169 | 23.169 |
| imaturo (2) | 21.200 | 21.200 |
| verde (3) | 5.347 | 5.347 |
| maduro (4) | 7.481 | 7.481 |
| estragado (5) | 25.820 | 25.820 |

Como o segundo lote usa a classe 5 para a árvore, a tabela publicada mistura as duas ordens. Ela não serve para conferir o significado de nenhuma classe.

### 2. A distribuição de rótulos do primeiro lote é implausível

Caixas por foto, lendo cada lote na sua ordem:

| Estágio | Gana (4.715 arquivos) | Uganda, segundo lote (1.440) | Uganda, primeiro lote (1.589) |
|---|---|---|---|
| flor | 3,6 | 2,5 | 12,6 |
| imaturo | 2,5 | 2,0 | 2,2 |
| verde | 0,9 | 11,9 | 3,3 |
| maduro | 2,5 | 0,1 | 3,7 |
| estragado | 0,1 | 1,1 | **15,0** |

Nos dois lotes confiáveis, fruto estragado é a classe mais rara. No primeiro lote é a mais comum, com 23.873 caixas.

Os números dos arquivos também separam os lotes: a mediana é 804 no primeiro e 2.320 no segundo. São duas levas de trabalho.

### 3. Os frutos são muito menores na foto

Tamanho mediano da caixa, em fração da foto:

| Estágio | Segundo lote (largura × altura) | Primeiro lote (largura × altura) |
|---|---|---|
| imaturo | 0,027 × 0,063 | 0,013 × 0,029 |
| verde | 0,025 × 0,065 | 0,010 × 0,027 |
| maduro | 0,035 × 0,089 | 0,012 × 0,025 |
| estragado | 0,028 × 0,071 | 0,014 × 0,034 |

Nas cópias de 640×480 que o projeto tem, uma caixa típica do primeiro lote mede cerca de 8 × 14 px. O treino exige 24 px no lado menor. Sobram 1.294 recortes de 430 fotos, que são os frutos mais próximos da câmera e não representam o lote.

As fotos em si não diferem muito: mesma resolução nas cópias, claridade média de 55,9 contra 54,7, saturação de 0,52 contra 0,54 (300 fotos de cada lote). Os originais são na maioria de 4032×3024 px (11 de 12 lidos no primeiro lote e 7 de 12 no segundo, pelo cabeçalho do arquivo; os demais têm 2016×1512 ou 2000×1125) e não trazem dados da câmera.

### 4. Pela cor, "maduro" não é maduro

Medimos oito números de cor dentro da máscara de cada fruto e atribuímos cada recorte ao estágio de cor mais parecida. Os centros foram ajustados em recortes de treino de Gana e do segundo lote.

Conferência em recortes de teste dos lotes confiáveis: acurácia balanceada de 51% com quatro estágios (o acaso dá 25%), e 48 de 67 recortes maduros reconhecidos como maduros (72%). É um instrumento grosseiro, mas enxerga fruto maduro.

No primeiro lote, pelos rótulos do arquivo:

| Rótulo no arquivo | n | Parece imaturo | Parece verde | Parece maduro | Parece estragado |
|---|---|---|---|---|---|
| imaturo | 121 | 30 | 54 | 5 | 32 |
| verde | 76 | 3 | 69 | 1 | 3 |
| maduro | 149 | 36 | 60 | **7** | 46 |
| estragado | 400 | 130 | 148 | 19 | 103 |

Só 7 dos 149 recortes marcados "maduro" (5%) têm cor de fruto maduro. A fração de pixels vermelhos confirma: 74% nos maduros de Gana, 17% nos "maduros" do primeiro lote, quase igual à dos "imaturos" do mesmo lote (11%).

Esta medida não usa o `belt_v3`. Ela chega à mesma conclusão que ele por outro caminho.

### 5. O que se vê nas imagens

Folhas de contato, 30 recortes sorteados por estágio e por origem:

- [recortes_premature.jpg](recortes_premature.jpg)
- [recortes_unripe.jpg](recortes_unripe.jpg)
- [recortes_ripe.jpg](recortes_ripe.jpg)
- [recortes_spoilt.jpg](recortes_spoilt.jpg)

Em "maduro", Gana e o segundo lote mostram cajus vermelhos e amarelos. O primeiro lote mostra castanhas verdes e roxas, frutos pequenos e flores. Em "estragado", o primeiro lote mostra sobretudo castanhas verdes com o pedúnculo ainda pequeno.

Para ver os frutos pequenos, baixamos 5 fotos originais de cada lote (37 MB, tamanho e CRC-32 conferidos) e recortamos as caixas em resolução cheia:

- [originais_uganda_a.jpg](originais_uganda_a.jpg): primeiro lote, por número de classe
- [originais_uganda_b.jpg](originais_uganda_b.jpg): segundo lote, por número de classe

Nessas 5 fotos do primeiro lote: a classe 1 são flores; a classe 2, frutos claros imaturos; a classe 4 mistura cajus vermelhos com castanhas roxas jovens; a classe 5 mistura castanhas escuras e secas com cachos de castanhas verdes pequenas. No segundo lote, castanha roxa jovem é "imaturo".

**Esta leitura das imagens é nossa, feita em poucas dezenas de recortes por classe.** Vale como indício, não como medida.

### 6. O que a documentação define

- O artigo do conjunto lista os números de classe (0 árvore, 1 flor, 2 imaturo, 3 verde, 4 maduro, 5 estragado) e diz que a categorização segue uma referência de 2010 sobre a produção do caju. Não descreve como reconhecer cada classe numa foto.
- O cartão do conjunto no repositório lista os nomes das classes e não traz contagens para Uganda.
- A ficha técnica em PDF não pôde ser lida por programa nesta máquina.

Não há, portanto, definição escrita contra a qual conferir os rótulos.

## O que não foi verificado

- Só 5 fotos originais de cada lote foram vistas em resolução cheia, escolhidas entre as que têm mais classes diferentes.
- Não testamos se o primeiro lote se divide em sub-lotes com critérios diferentes.
- Não treinamos nada com os originais do primeiro lote. Em resolução cheia os frutos teriam tamanho suficiente, mas os rótulos continuariam em dúvida.
- A sonda de cor acerta 51% nos lotes confiáveis; ela distingue bem fruto maduro e mal os outros estágios.

## Próximo passo

A pergunta aos autores ficou mais precisa e está em [docs/data/requests.md](../../data/requests.md), rascunho 1. Não foi enviada.
