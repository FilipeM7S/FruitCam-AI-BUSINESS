# Dados reais e o classificador belt_v3

Escrito em 2026-10-12. Este guia cobre a busca por vídeos e fotos reais de frutas, a conferência de cada download, o treino do classificador `belt_v3` e o que mudou no app. Os guias anteriores continuam valendo para o resto: [camera.md](camera.md) explica a câmera e o modelo anterior (`belt_v2`), e [dataset_and_layout.md](dataset_and_layout.md) explica os conjuntos de esteira de batata e limão.

**Depois deste guia (2026-10-12):** o kit para gravar e medir em esteira real está em [real_belt_kit.md](real_belt_kit.md); a calibração, o alarme de podre, o diagnóstico do lote excluído e os erros de contagem estão em [model_checks.md](model_checks.md); o autotreino em tempo de teste, em [ttst.md](ttst.md). Onde aqueles guias trazem números mais novos sobre contagem, valem os de lá.

Licenças, autores e créditos não aparecem aqui. Ficam em [LICENSES.md](../../LICENSES.md), seção 3. O relatório completo da busca, com o texto de licença de cada fonte, está em [legal/reports/dataset_search.md](../../legal/reports/dataset_search.md).

---

## 1. Resumo

| Pergunta | Resposta |
|---|---|
| Existe vídeo aberto de fruta em esteira, com rótulo de qualidade? | Não foi encontrado nenhum. |
| O que foi encontrado de útil? | As fotos originais de caju em resolução cheia, de dois países, com rótulos cuja ordem de classes pôde ser conferida. E vídeos reais de linhas de seleção, sem rótulos. |
| O modelo foi treinado com vídeo? | Os vídeos não têm rótulos, então não ensinam o que é fruta boa ou ruim. Quadros deles entraram como fundo real atrás dos recortes de caju. O que ensina a classe são as fotos rotuladas. |
| Resultado | Acurácia balanceada de 89,2% no teste (IC 95% de 86,7% a 91,5%), contra 56,4% do modelo anterior nos mesmos recortes. O acaso dá 33%. |
| O app decide sozinho agora? | Não. Toda fruta continua indo para conferência manual, porque as fotos são de fruto no pé e a esteira real ainda não foi medida. |

---

## 2. Conceitos usados neste guia

- **Recorte**: o quadrado da foto em volta de um fruto, que é o que o modelo recebe.
- **Acurácia balanceada**: a média do acerto de cada classe. Não deixa a classe mais comum esconder as outras. Com três classes, responder ao acaso dá 33%.
- **Divisão por foto**: todos os recortes de uma mesma foto ficam no mesmo conjunto (treino, validação ou teste). Sem isso, o modelo veria no teste frutos vizinhos dos que viu no treino.
- **Composição**: recortar o fruto do fundo original e colar sobre outro fundo (uma esteira desenhada ou um quadro de vídeo real). Serve para o modelo aprender a olhar para o fruto e não para as folhas.
- **Calibração por temperatura**: um único número, ajustado na validação, que corrige a confiança do modelo para ela corresponder ao acerto real.
- **CRC-32 e SHA**: somas de verificação. Se um único byte do arquivo muda, a soma muda.

---

## 3. A busca

Foram consultados o índice DataCite (que cobre Zenodo, Mendeley Data, Figshare e repositórios de universidades), Hugging Face, Zenodo, GitHub, Crossref, OpenAlex e a busca de vídeos do Wikimedia Commons. Cada fonte aceita foi aberta pela API do próprio repositório, para ler o campo de licença, o autor, as datas, os tamanhos e as somas de verificação.

### Aceitos

| Conjunto (id no projeto) | O que é | Uso |
|---|---|---|
| `cashew_drone_full` | Fotos de cajueiros tiradas de perto por drone em Gana (4.715 fotos de 1600×1300 px) e em Uganda (3.098 fotos), com caixas e estágio de cada fruto. É a fonte original do conjunto que o projeto já usava em versão reduzida. | Treino, validação e teste do `belt_v3` |
| `usda_line_videos` | 11 clipes de linhas reais de seleção e embalagem de batata-semente e de cítricos. Câmera na mão, pessoas no quadro, sem rótulos. | Fundos reais: os clipes de batata no treino, o de cítricos só no teste |
| `apple_grading_video` | 1 clipe de uma classificadora de maçãs. Sem rótulos. | Só teste, nunca treino |

### Rejeitados

Dez candidatos foram rejeitados e ficaram registrados com o motivo: sem licença, origem das imagens não declarada, página que recusou acesso (não deu para conferir), vídeos de terceiros tirados do YouTube, ou produto diferente demais. O mais próximo do nosso caso é um artigo de 2026 sobre castanha de caju em esteira; não foi possível ler se as imagens são públicas, e o próximo passo é pedir aos autores.

Sites de vídeo de banco de imagens não foram pesquisados: as licenças deles não estão entre as que o projeto aceita.

---

## 4. Como cada download foi conferido

| Conjunto | Tamanho baixado | Conferência |
|---|---|---|
| `usda_line_videos` | 11 arquivos, 236 MB | Baixados inteiros. O SHA-1 de cada arquivo é igual ao publicado pelo repositório. |
| `apple_grading_video` | 1 arquivo, 16 MB | Baixado inteiro. SHA-1 igual ao publicado. |
| `cashew_drone_full`, Gana | 1.712 das 4.715 fotos e todos os rótulos, 1,6 GB | Leitura parcial do arquivo ZIP (ver abaixo). Tamanho e CRC-32 de cada arquivo conferidos contra o índice do próprio ZIP. |
| `cashew_drone_full`, Uganda | Só os 3.098 arquivos de rótulo, 3,4 MB | Idem. As fotos de Uganda usadas são as que o projeto já tinha. |
| `cashew_drone_full`, ficha técnica | 1 PDF, 1,4 MB | SHA-256 igual ao publicado. |

**Leitura parcial do ZIP.** Os dois arquivos somam 15,4 GB e a rede daqui entrega cerca de 0,5 MB/s. Em vez de baixar tudo, [tools/remote_zip.py](../../tools/remote_zip.py) lê só o índice que fica no fim do ZIP e depois pede ao servidor os trechos de cada arquivo escolhido. Cada arquivo extraído é conferido pelo tamanho e pelo CRC-32 gravados nesse índice; se não bater, o arquivo não é gravado. O endereço usado aponta para uma revisão fixa do repositório, então o conteúdo não muda entre uma execução e outra.

**O que isso não confere.** O SHA-256 publicado vale para o ZIP inteiro, e o ZIP inteiro não foi baixado. A garantia aqui é mais fraca: revisão fixa, mais tamanho e CRC-32 por arquivo.

**Escolha das fotos de Gana.** A seleção usa só os rótulos: todas as fotos com algum fruto estragado, e depois as fotos mais ricas no estágio que estiver faltando, até cerca de 4.500 frutos maduros, 3.200 verdes e 3.200 imaturos com lado de pelo menos 2,2% da foto. [tools/fetch_cashew_drone.py](../../tools/fetch_cashew_drone.py) repete a mesma escolha e baixa só o que faltar. Consequência: a proporção de classes nesses dados não é a proporção natural do pomar.

**Conteúdo dos vídeos.** Foi olhado quadro a quadro, em folhas de contato. O vídeo de cítricos tem 60 s de drone fora do prédio e depois planos abertos com trabalhadores. Os clipes de batata são de carga e seleção ao ar livre. Nenhum mostra uma fruta por vez sob câmera fixa, e nenhum tem rótulo.

**Onde ficam os arquivos.** Os vídeos ficam em `data/external/` (ignorados pelo git; só as fichas `SOURCE.md` são versionadas). As fotos de Gana e os recortes ficam fora do repositório, em `C:\Users\<usuário>\FruitCamData`, ou na pasta indicada pela variável `FRUITCAM_DATA_STORE`.

---

## 5. A ordem das classes nos rótulos

Cada linha de um arquivo de rótulo começa com um número de classe. Os arquivos de Uganda usam duas ordens diferentes, e o projeto só confiava em uma. Os rótulos de Gana resolveram a outra.

O cartão do conjunto publica quantas caixas existem por classe em Gana. Contando as caixas por número nos arquivos, os totais só batem com o cartão em uma ordem, a alfabética:

| Número | Caixas nos arquivos de Gana | Classe do cartão com esse total |
|---|---|---|
| 0 | 16.757 | flor |
| 1 | 11.766 | imaturo |
| 2 | 4.244 | verde |
| 3 | 11.721 | maduro |
| 4 | 518 | estragado |
| 5 | 1.107 | árvore |

Com isso, os arquivos de Uganda ficam assim:

| Lote | Arquivos | Como se reconhece | Ordem | Situação |
|---|---|---|---|---|
| Segundo lote (`uganda_b`) | 1.440 | A caixa que ocupa a foto inteira (a árvore) é a classe 5 | Alfabética, igual à de Gana | Voltou para o treino |
| Primeiro lote (`uganda_a`) | 1.589 | A árvore é a classe 0 | A do artigo | Fora do treino e do teste |
| Sem identificação | 69 | Não há caixa de árvore utilizável | Desconhecida | Fora |

**Por que o primeiro lote ficou de fora.** Nele, o modelo novo responde "baixa qualidade" para quase todo fruto, qualquer que seja o rótulo. Medido nos 1.294 recortes de 430 fotos desse lote ([models/first_batch_v3.json](../../models/first_batch_v3.json)):

| Rótulo no arquivo (ordem do artigo) | Recortes | belt_v3 responde "baixa qualidade" |
|---|---|---|
| imaturo | 121 | 87% |
| verde | 76 | 100% |
| maduro | 149 | 85% |
| estragado | 948 | 80% |

Repare também que 948 dos 1.294 recortes estão marcados como estragados, uma proporção que não aparece em nenhum outro lote. Há duas explicações possíveis e não sabemos qual é a certa: o critério de anotação desse lote é outro, ou as fotos são diferentes das demais. O pedido de esclarecimento aos autores está em [docs/data/requests.md](../data/requests.md).

Esse lote era justamente o treino do modelo anterior. Ou seja, o `belt_v2` aprendeu com os dados em que hoje menos confiamos.

Tudo isso é verificado por teste automático ([core/tests/test_data_v3.py](../../core/tests/test_data_v3.py), `LabelOrderTests`).

---

## 6. Os dados de treino

[training/cashew_data.py](../../training/cashew_data.py) recorta cada fruto anotado: quadrado com 15% de margem, lado mínimo de 24 px na foto, reduzido para até 160 px. Para cada recorte ele também calcula a máscara do fruto (GrabCut em 21.634 recortes, elipse nos 44 em que o GrabCut falhou). As máscaras não foram conferidas à mão.

Os quatro estágios viram as três classes do produto:

| Estágio no conjunto | Classe no app |
|---|---|
| maduro | boa |
| imaturo, verde | baixa qualidade |
| estragado | podre |

Recortes usados pelo `belt_v3`, por classe:

| | boa | baixa qualidade | podre | total | fotos |
|---|---|---|---|---|---|
| Treino | 3.637 | 9.734 | 662 | 14.033 | 1.995 |
| Validação | 779 | 2.373 | 183 | 3.335 | 451 |
| Teste | 775 | 2.034 | 207 | 3.016 | 417 |

A divisão é por foto (70/15/15), decidida por um hash do nome do arquivo, então é sempre a mesma. No segundo lote de Uganda quase não há fruto maduro: 32 recortes no treino e 7 no teste.

---

## 7. O treino

[training/train_v3.py](../../training/train_v3.py):

- **Rede**: MobileNetV3-Small pré-treinada no ImageNet, entrada de 128×128 px. A mesma arquitetura do modelo anterior, para caber na CPU da linha.
- **Amostragem**: 10 épocas de 9.000 recortes sorteados com peso igual para cada classe e, dentro da classe, para cada origem. Sem isso, "baixa qualidade" dominaria.
- **Composição**: em metade dos recortes, o fruto é colado sobre outro fundo. Metade dessas colagens usa esteiras desenhadas de seis cores; a outra metade usa 82 quadros reais dos clipes de batata. As esteiras azuis e os quadros de cítricos e de maçã nunca entram no treino, para servirem de teste.
- **Escolha do modelo**: fica a época com melhor acurácia balanceada na validação (época 7, 89,5%).
- **Calibração**: temperatura 1,40, ajustada na validação.
- **Teste**: usado uma vez, no fim.
- **Tempo**: 36 minutos em CPU.

---

## 8. Resultados

### Teste em fotos de fruto no pé

3.016 recortes de 417 fotos que não aparecem no treino nem na validação.

| Medida | Valor |
|---|---|
| Acurácia | 89,6% (IC 95% de 87,8% a 91,2%, bootstrap por foto) |
| Acurácia balanceada | 89,2% (IC 95% de 86,7% a 91,5%) |
| Responder sempre a classe mais comum | 67,4% |
| Sensibilidade: boa, baixa qualidade, podre | 89,9%, 89,6%, 87,9% |
| Precisão: boa, baixa qualidade, podre | 93,8%, 97,4%, 45,3% |
| Podres classificadas como boas | 8 de 207 (3,9%; IC 95% de 2,0% a 7,4%) |
| Erro de calibração (ECE) | 0,040 antes e 0,011 depois da temperatura |

A precisão de "podre" é baixa: de cada 100 alarmes de podre, cerca de 45 estão certos. Há poucos frutos estragados nos dados, e a amostragem equilibrada deixa o modelo propenso a dar o alarme.

Por origem:

| Origem | Recortes | Fotos | Acurácia | Acurácia balanceada |
|---|---|---|---|---|
| Gana | 2.118 | 245 | 92,0% | 90,0% |
| Uganda, segundo lote | 898 | 172 | 84,0% | 76,7% |

A acurácia balanceada de Uganda depende de só 7 recortes de fruto maduro; leia esse número com cuidado.

### Comparação com o modelo anterior, nos mesmos recortes

[tools/eval_v3.py](../../tools/eval_v3.py) passa os dois modelos pelos mesmos 3.016 recortes, de três jeitos: como estão, colados sobre esteiras azuis nunca usadas em treino, e colados sobre 58 quadros reais dos clipes de cítricos e de maçã. Resultado em [models/compare_v3.json](../../models/compare_v3.json).

| Acurácia balanceada | belt_v2 | belt_v3 |
|---|---|---|
| Fotos como estão | 56,4% (53,4% a 59,5%) | 89,2% (86,7% a 91,5%) |
| Sobre esteiras azuis | 53,5% (50,8% a 56,1%) | 82,6% (79,9% a 85,3%) |
| Sobre quadros de vídeo real | 39,6% (38,0% a 41,2%) | 78,5% (75,9% a 81,0%) |

| Outras medidas | belt_v2 | belt_v3 |
|---|---|---|
| Mesma resposta com fundo azul e com o fundo original | 60,6% | 89,1% |
| Mesma resposta com fundo de vídeo real e com o fundo original | 36,7% | 81,6% |
| Podres chamadas de boas, fotos como estão | 29,5% | 3,9% |
| Podres chamadas de boas, sobre vídeo real | 83,6% | 2,9% |

**Leia esta comparação com uma ressalva.** O teste é feito de Gana e do segundo lote de Uganda, que o `belt_v2` nunca viu no treino. Ele joga fora de casa. No teste antigo do `belt_v2` (187 recortes do primeiro lote), os dois vão mal: 41,8% para o `belt_v2` e 31,7% para o `belt_v3`. O que os números sustentam é: nos dados cujos rótulos conseguimos conferir, o modelo novo é muito melhor; nos dados do primeiro lote, nenhum dos dois funciona.

### Corte de confiança

Na validação, respostas com confiança de pelo menos 76% cobrem 85,3% dos frutos e acertam 95,2%. No teste: 84,9% dos frutos e 94,8% de acerto.

Esse corte **não foi ligado**. Ele foi medido em fotos de fruto no pé, e ligá-lo faria o app decidir sozinho numa esteira em que nunca foi testado. O arquivo do modelo guarda `reject_below = None`, e o corte fica registrado em `field_photo_threshold` em [models/belt_v3_eval.json](../../models/belt_v3_eval.json), só como medida.

---

## 9. Esteira simulada

[tools/eval_belt.py](../../tools/eval_belt.py) roda o pipeline inteiro da câmera sobre uma esteira simulada que carrega os frutos de teste, recortados pelo contorno, em proporção 1:1:1, durante 8 minutos simulados.

| Medida | Valor |
|---|---|
| Frutas que cruzaram a linha | 891 |
| Frutas contadas | 893 |
| Contadas duas vezes | 2 |
| Acerto ponta a ponta, média das vistas | 79,4% (IC 95% de 76,6% a 81,9%) |
| Acerto com a primeira vista | 78,7% |
| Tamanho medido ÷ tamanho real (mediana) | 1,019 |

O acerto é menor que o do teste em fotos porque na esteira a fruta aparece pequena, sem o fundo original e colada sobre outro.

**As duas contagens a mais.** As duas são frutas podres com uma parte tão escura quanto a esteira cinza-escura da simulação. A separação por cor não enxerga essa parte, a fruta vira duas manchas, e cada mancha é contada. Isso acontece com ou sem a separação de frutas encostadas descrita abaixo. Não há correção no programa; o remédio conhecido é uma esteira de cor que contraste com o produto.

**Atualização de 2026-10-12.** O rastreador ganhou uma regra que conta como uma só duas manchas coladas que cruzam a linha juntas. Com ela a mesma simulação dá 891 contagens para 891 frutas, sem duplicadas. Detalhes e as outras tentativas em [model_checks.md](model_checks.md), seção 3.

Com o `belt_v2`, a mesma simulação deu 914 de 914 e 44% de acerto, mas com outros frutos (os do teste antigo), então as duas execuções não são comparáveis linha a linha.

---

## 10. Frutas encostadas

Antes, duas frutas que se tocavam viravam uma mancha só e eram contadas como uma. [belt/detect.py](../../belt/detect.py) agora tenta separá-las antes da contagem:

1. Calcula, para cada pixel da mancha, a distância até a borda. O centro de cada fruta é um pico dessa distância.
2. Se a mancha tem dois picos ou mais, cada pixel é atribuído ao pico mais próximo.
3. Duas regiões só são separadas se a passagem entre elas for estreita: menos de 70% da largura da menor (parâmetro `neck`). Um caju comprido tem dois picos fracos e uma passagem larga, e não é cortado.

Medido na esteira simulada com frutas desenhadas:

| Situação | Erro de contagem antes | Depois |
|---|---|---|
| Espaçamento normal | 0 | 0 |
| Sobreposição de até 25 mm, 6 frutas por segundo | −4,8% | −1,9% |
| Sobreposição de até 40 mm, 6 frutas por segundo | −33,8% | −21,9% |
| Sobreposição de até 40 mm, 10 frutas por segundo | −41,3% | −27,8% |

Com frutas reais em espaçamento normal, a contagem foi a mesma com a separação desligada e com `neck` em 0,7, 0,55 e 0,4 (354 frutas, 356 contagens nos quatro casos).

Frutas muito sobrepostas ainda viram uma só. Uma câmera vista de cima não resolve isso sozinha.

---

## 11. O que mudou no app

- O modelo padrão é `models/belt_v3.pt` (`fruitcam/settings.py`; a variável `FRUITCAM_MODEL_PATH` troca).
- As figuras 2, 6 e 8 e os números da página **Como funciona** e do certificado saem de `belt_v3_eval.json` e de `belt_eval.json`. A figura 6 mostra o corte de confiança como "medido, não ligado".
- Os textos de limites, a origem dos dados e a lista de pendências foram reescritos, iguais no site e no certificado.
- O aviso de revisão na inspeção por foto agora diz que o sistema não decide a fruta sozinho. Antes dizia que o modelo não tinha confiança suficiente, o que deixou de ser verdade.
- Os dois vídeos de demonstração foram regravados com o modelo novo. Para a foto de caju usada neles, a saída real é "boa" com 70,3%.
- `tools/record_demo.py` e `assets/figures/make_figures.py` deixaram de apagar pastas inteiras, porque o OneDrive às vezes bloqueia a pasta e a ferramenta parava no meio.
- `tools/finetune_belt.py` e `tools/adapt_bn.py` partem do `belt_v3`. A opção `--mix-field` do ajuste fino tinha um erro: misturava todos os arquivos de Uganda lidos na ordem do artigo, inclusive os que usam a outra ordem. Agora ela mistura só recortes de treino de Gana e do segundo lote de Uganda (600 por classe; `--field-per-class` muda). Foi testada de ponta a ponta com bandejas de mentira montadas com recortes de teste, só para ver a ferramenta rodar; isso não é uma medição.

---

## 12. Limites e o que não foi verificado

- **Esteira real.** Nada aqui foi medido com uma câmera sobre uma esteira de caju. É o limite principal.
- **O que "boa" significa.** As classes vêm do estágio de maturação. "Boa" é fruto maduro e "baixa qualidade" é fruto imaturo ou verde. Amassado, rachado e queimado não estão nos dados.
- **Fotos de drone, fruto no pé.** Luz do sol, folhas ao fundo, fruto preso ao galho. Na esteira a luz, o fundo e o ângulo são outros.
- **Primeiro lote de Uganda.** Não sabemos por que ele não bate com os outros.
- **Proporção de classes.** As fotos de Gana foram escolhidas pelos rótulos, então a mistura não é a do pomar.
- **Download parcial.** O SHA-256 dos dois ZIPs grandes não foi conferido.
- **Revisão dos vídeos no repositório de origem.** Em 2026-10-11, a revisão da licença dos 11 clipes pelos voluntários do repositório ainda estava pendente. O detalhe está em LICENSES.md.
- **Máscaras.** Feitas por algoritmo, sem conferência manual.
- **Castanha e melão.** O modelo nunca viu.

O próximo passo que mais vale é o mesmo de antes: gravar bandejas separadas à mão na esteira de verdade ([docs/data/collection.md](../data/collection.md)), medir o `belt_v3` nelas e só então decidir se o corte de confiança pode ser ligado.

---

## 13. Como reproduzir

Na pasta do projeto, com o ambiente Python instalado:

```
python scripts/fetch_datasets.py --only usda_line_videos apple_grading_video cashew_drone_full
python tools/fetch_cashew_drone.py
python -m training.cashew_data
python tools/video_backgrounds.py
python -m training.train_v3 --sources ghana uganda_b
python tools/eval_v3.py
python tools/eval_belt.py --model models/belt_v3.pt
python assets/figures/make_figures.py
```

| Comando | O que faz | Tempo nesta máquina |
|---|---|---|
| `fetch_datasets.py` | Baixa os vídeos e a ficha técnica, confere as somas e escreve as fichas `SOURCE.md` | depende da rede (252 MB) |
| `fetch_cashew_drone.py` | Baixa os rótulos e as 1.712 fotos de Gana por leitura parcial do ZIP. `--labels-only` baixa só os rótulos | cerca de 1 hora a 0,5 MB/s (estimativa pelo tamanho: 1,6 GB) |
| `training.cashew_data` | Recorta os frutos e calcula as máscaras | 5 minutos |
| `video_backgrounds.py` | Extrai os quadros de fundo dos vídeos | não medido |
| `training.train_v3` | Treina, calibra e avalia | 36 minutos |
| `eval_v3.py` | Compara `belt_v2` e `belt_v3` nos mesmos recortes | 1,5 minuto |
| `eval_belt.py` | Esteira simulada de 8 minutos | 11 minutos |
| `make_figures.py` | Refaz as figuras e os números do site | 15 segundos |

Depois de refazer as figuras: `python tools/build_media.py`, `python tools/build_legal.py` e, em `frontend/`, `npm run build`.

Para voltar ao modelo anterior sem mexer no código, defina `FRUITCAM_MODEL_PATH` com o caminho de `models/belt_v2.pt`. O certificado avisa quando o modelo configurado não é o que as figuras descrevem.

---

## 14. Testes

[core/tests/test_data_v3.py](../../core/tests/test_data_v3.py):

| Teste | O que prova |
|---|---|
| `RemoteArchiveTests` (3) | A leitura parcial do ZIP busca só os trechos pedidos, e um byte trocado é pego pelo CRC-32 sem gravar o arquivo |
| `LabelOrderTests` (3) | A ordem das classes é lida pela posição da caixa da árvore; os arquivos de Uganda se dividem em 1.589, 1.440 e 69; as contagens de Gana só batem com o cartão na ordem alfabética |
| `ModelV3Tests` (4) | O modelo configurado é o que o site descreve (mesmo arquivo, mesmo SHA-256, nenhum corte ligado); o primeiro lote de Uganda não está em nenhuma divisão; os números citados nos textos saem dos arquivos de resultado; o modelo reproduz as predições guardadas no treino |
| `RealBackgroundTests` (1) | A composição usa de fato os quadros de vídeo como fundo |
| `NewSourcesTests` (1) | Os três conjuntos novos estão no registro, com licença aceita e ficha |

Em [core/tests/test_belt.py](../../core/tests/test_belt.py), `test_touching_fruit_is_separated_before_counting` cobre a separação de frutas encostadas.

Os testes que precisam das fotos de Gana ou dos recortes são pulados, com uma mensagem, numa máquina que não os tenha.

Suíte completa em 2026-10-12, nesta máquina, com os dados presentes: **163 testes, todos passaram, nenhum pulado, em 26 minutos**. Saída real em [docs/reports/tests/model_v3_test_output.txt](../reports/tests/model_v3_test_output.txt).

---

## 15. Arquivos

| Arquivo | Papel |
|---|---|
| `tools/remote_zip.py` | Leitura parcial de um ZIP remoto, com conferência por CRC-32 |
| `tools/fetch_cashew_drone.py` | Escolha e download das fotos de Gana e dos rótulos |
| `tools/video_backgrounds.py` | Quadros de fundo a partir dos vídeos |
| `tools/eval_v3.py` | Comparação entre os dois modelos nos mesmos recortes |
| `tools/eval_belt.py` | Esteira simulada (agora escolhe os frutos de teste do modelo avaliado) |
| `training/cashew_data.py` | Recortes, máscaras, ordem das classes, divisão por foto |
| `training/train_v3.py` | Treino, calibração e avaliação |
| `belt/composite.py` | Colagem sobre esteiras desenhadas ou quadros reais |
| `belt/detect.py` | Segmentação por cor e separação de frutas encostadas |
| `scripts/datasets.json`, `scripts/fetch_datasets.py` | Lista dos conjuntos e download com conferência |
| `models/belt_v3.pt`, `models/belt_v3_eval.json`, `models/train_belt_v3.log` | Modelo, avaliação e registro do treino |
| `models/compare_v3.json`, `models/eval_belt_v3.log` | Comparação e registro da esteira simulada |
| `models/first_batch_v3.json` | Respostas dos dois modelos no primeiro lote de Uganda |
| `assets/figures/data/belt_eval.json` | Resultado da esteira simulada usado pelas figuras |
| `legal/registry.json` | Registro dos três conjuntos novos e dos dez rejeitados |
