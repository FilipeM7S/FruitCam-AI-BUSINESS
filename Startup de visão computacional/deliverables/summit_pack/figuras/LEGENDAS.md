# Legendas das figuras

Geradas por `assets/figures/make_figures.py`. Cada figura traz no canto inferior direito o rótulo da origem dos dados; mantenha esse rótulo e a legenda ao usar a figura.

## Figura 1. Da câmera à estatística da linha

Rótulo: **Esquema, sem dados**. Arquivos: `fig1-pipeline.svg` (vetorial) e `fig1-pipeline.png` (300 dpi, 183 mm de largura).

Caminho de cada fruta, do quadro de vídeo à estatística da linha. Só a etapa 4 é aprendida (MobileNetV3-Small com 3 classes: boa, baixa qualidade e podre). A segmentação, o rastreamento e a contagem na linha são código determinístico; a decisão manda para revisão manual as frutas com confiança abaixo do limiar calibrado. Esquema, sem dados.

Texto alternativo: Diagrama em sete etapas: câmera, segmentação, rastreamento, classificador (a única etapa de IA), decisão, registro e estatística, com o dado que passa entre cada etapa.

## Figura 2. O que o classificador recebe e devolve

Rótulo: **Exemplo real, não é métrica**. Arquivos: `fig2-classificacao.svg` (vetorial) e `fig2-classificacao.png` (300 dpi, 183 mm de largura).

(a) Foto real de caju, de terceiros, com o recorte da fruta, como a esteira produziria. (b) A entrada do modelo: o recorte reduzido a 128×128 px, com o mapa Grad-CAM da classe prevista; o mapa mostra onde o gradiente se concentra e não prova causa. (c) Probabilidades calibradas devolvidas pelo modelo atual (belt_v3). Para este caju, que parece maduro e são, o modelo responde “boa” com 0,98. Mesmo assim a fruta iria para conferência manual: nenhum corte de confiança está ligado, porque o modelo ainda não foi medido em esteira real. (d) Uma elipse escura sintética, fora da distribuição de treino, recebe “baixa qualidade” com 0,63: o modelo responde com alguma classe mesmo para o que não é fruta. Exemplos individuais; não são métrica de desempenho.

Texto alternativo: Quatro painéis: foto real de um caju com o recorte da fruta marcado; o recorte reduzido à entrada do modelo com o mapa Grad-CAM; as probabilidades das três classes para o recorte e para uma imagem sintética; e a imagem sintética, uma elipse escura.

## Figura 3. Como um evento vira estatística

Rótulo: **Dados sintéticos**. Arquivos: `fig3-evento-estatistica.svg` (vetorial) e `fig3-evento-estatistica.png` (300 dpi, 183 mm de largura).

(a) Cada análise vira uma linha de evento com data, setor, fruta, veredito e defeito; o modelo atual só registra “podre” como defeito. (b) As linhas são contadas por semana completa; o número acima de cada barra é n. (c) A proporção semanal de podres com intervalo de confiança de 95% de Wilson; a linha tracejada é a proporção do período inteiro. Dados sintéticos de um setor, só caju.

Texto alternativo: Três painéis: uma tabela com as primeiras linhas de eventos; barras empilhadas de frutas boas e podres por semana com o total de cada semana; e a proporção semanal de podres com intervalos de confiança de 95%.

## Figura 4. Previsão e incerteza

Rótulo: **Dados sintéticos**. Arquivos: `fig4-previsao.svg` (vetorial) e `fig4-previsao.png` (300 dpi, 183 mm de largura).

(a) Série sintética com tendência conhecida: pontos com IC 95% de Wilson, reta de mínimos quadrados e intervalo de previsão de 95% para a semana seguinte; o losango é o valor verdadeiro da semana seguinte. (b) O mesmo processo com 10 semanas de 60 frutas: o intervalo fica muito mais largo e o painel marca a previsão como não confiável. (c) Teste retroativo de origem móvel em 20 séries simuladas: fração das previsões de um passo cujo valor real caiu no intervalo; a faixa cinza é a variação esperada se a cobertura verdadeira fosse 95%. Dados sintéticos.

Texto alternativo: Três painéis: proporção semanal de podres com reta ajustada e intervalo de previsão de 95% para a semana seguinte; o mesmo com poucas semanas e poucas frutas, com intervalo muito mais largo; e a cobertura medida do intervalo em vinte séries simuladas.

## Figura 5. Ajuste gaussiano e teste de normalidade

Rótulo: **Dados sintéticos**. Arquivos: `fig5-gaussiana.svg` (vetorial) e `fig5-gaussiana.png` (300 dpi, 183 mm de largura).

(a) Proporção semanal de podres de um setor gerado como normal, com a normal ajustada, média e faixas de ±1σ e ±2σ. (b) Gráfico Q-Q com envelope pontual de 95% obtido por simulação de amostras normais do mesmo tamanho. (c) Setor assimétrico: a curva ajustada invade proporções negativas (área hachurada, impossível). (d) Seus pontos saem do envelope e o teste de Shapiro-Wilk rejeita a normalidade, então o painel mostra “ajuste ruim”. Dados sintéticos.

Texto alternativo: Quatro painéis em duas linhas: histograma de um setor com curva normal ajustada e faixas de mais ou menos um e dois desvios, e seu gráfico Q-Q dentro do envelope de 95%; depois um setor assimétrico em que a curva invade valores impossíveis abaixo de zero e os pontos do Q-Q saem do envelope.

## Figura 6. Qualidade do modelo no conjunto de teste

Rótulo: **Medição real (teste)**. Arquivos: `fig6-qualidade.svg` (vetorial) e `fig6-qualidade.png` (300 dpi, 183 mm de largura).

Medição real com models/belt_v3.pt em recortes de teste: fotos de origem que não aparecem no treino nem na validação (divisão por foto). Os dados são fotos de cajueiros de Gana e do segundo lote de Uganda (14.033 recortes no treino, 3.335 na validação e 3.016 no teste); o primeiro lote de Uganda (1.589 fotos) ficou de fora porque seus rótulos não batem com os dos outros lotes. (a) Matriz de confusão; cada célula mostra a contagem e a fração da linha. (b) Sensibilidade e precisão por classe (IC 95% de Wilson) e acurácia (IC 95% por bootstrap de fotos), contra o palpite “sempre baixa qualidade”, a classe mais comum do teste (67%). A precisão de “podre” é baixa (45%): há poucas frutas estragadas, e mais da metade dos alarmes de “podre” é fruta de outra classe. (c) Diagrama de confiabilidade após a calibração por temperatura, ajustada na validação. (d) Acerto entre as frutas decididas automaticamente conforme a fração decidida. O losango marca o corte de confiança escolhido na validação para 95% de acerto (0,76): no teste ele cobre 85% das frutas com 94,8% de acerto. Esse corte não está ligado; todas as frutas vão para revisão. Limitações: as fotos são de cajus no pé (campo), não de esteira; “baixa qualidade” corresponde a frutos imaturos ou verdes; desempenho em esteira real não avaliado.

Texto alternativo: Quatro painéis: matriz de confusão de três classes no teste; sensibilidade e precisão por classe com intervalos de confiança e a acurácia comparada ao palpite da classe mais comum; diagrama de confiabilidade após a calibração; e a curva de acerto conforme a fração decidida automaticamente, com o corte de confiança medido e a nota de que ele não está ligado.

## Figura 7. Estatística da linha: carta de controle e aceite de lote

Rótulo: **Dados sintéticos**. Arquivos: `fig7-linha.svg` (vetorial) e `fig7-linha.png` (300 dpi, 183 mm de largura).

(a) Proporção de podres por janela completa de 15 min em uma linha simulada de 8 h; a faixa é o limite superior p′ de Laney (3σ, mediana como centro), que considera a variação entre janelas além do acaso; losangos marcam alarmes. O lote L-03 foi gerado com 35% de podres em vez de 14%. (b) Proporção de podres por lote com IC 95% de Wilson contra o máximo de 18%: aprovado se o intervalo inteiro fica abaixo, reprovado se fica acima, inconclusivo se cruza. Dados sintéticos com resposta conhecida.

Texto alternativo: Dois painéis: a proporção de podres em janelas de 15 minutos ao longo de 8 horas, com a faixa sob controle e losangos de alarme no lote com mais podres; e a proporção de podres de cada lote com intervalo de confiança comparada ao máximo da especificação.

## Figura 8. Validação da câmera em esteira simulada

Rótulo: **Simulação**. Arquivos: `fig8-esteira.svg` (vetorial) e `fig8-esteira.png` (300 dpi, 183 mm de largura).

O pipeline completo da câmera (segmentação, separação de frutas encostadas, rastreamento, contagem na linha e o classificador belt_v3) rodando em uma esteira simulada que carrega frutas reais de teste, nunca usadas no treino, recortadas sem as folhas e em proporção 1:1:1. (a) Contagem: frutas que cruzaram a linha, contadas, distintas e contadas duas vezes (0 em 891, com a regra do rastreador que conta como uma só duas manchas coladas da mesma fruta; sem ela eram 2). (b) Matriz de confusão ponta a ponta. (c) Acerto com a primeira vista e com a média das vistas; nenhuma fruta é decidida sozinha, porque nenhum corte de confiança está ligado. Na simulação cada fruta mantém a mesma imagem enquanto anda, então as vistas extras trazem pouca informação nova; numa esteira real a fruta gira e a luz varia. O acerto aqui é menor que o do teste em fotos porque a fruta aparece pequena, recortada do fundo original e colada sobre a esteira. Simulação, não é medição em esteira real.

Texto alternativo: Três painéis: barras comparando frutas que cruzaram a linha, frutas contadas, frutas distintas e contagens duplicadas; matriz de confusão da classificação ponta a ponta; e o acerto com uma vista e com a média de várias vistas, sem frutas decididas automaticamente.

## Figura 9. Alarme de podre: confiança, precisão e o corte que não passou

Rótulo: **Medição real (teste)**. Arquivos: `fig9-podre.svg` (vetorial) e `fig9-podre.png` (300 dpi, 183 mm de largura).

Medição real com models/belt_v3.pt nos 3.016 recortes de teste, de fotos de fruto no pé. (a) Para cada faixa da probabilidade de “podre” dada pelo modelo, a fração de frutas que eram mesmo podres (IC 95% de Wilson). Quando o modelo diz de 90% a 100%, 74% eram podres (n = 157). A calibração por temperatura acerta a confiança da resposta em geral, mas não a da classe rara. (b) Precisão contra sensibilidade da classe “podre” conforme se exige mais probabilidade para dar o alarme. O círculo é a regra atual, que responde a classe mais provável; o losango é o corte de 0,80 escolhido na validação. (c) Podres chamadas de boas para cada corte (IC 95%). Com 0,80 a taxa no teste foi 5,8%, acima do limite de 5% fixado antes de medir; por isso a regra não mudou. O teste tem 207 frutas podres: os intervalos são largos, e nem a regra atual pode ser garantida abaixo de 5%. Desempenho em esteira real não avaliado.

Texto alternativo: Três painéis: a fração de frutas realmente podres em cada faixa de probabilidade de podre dada pelo modelo, abaixo da diagonal; a curva de precisão contra sensibilidade da classe podre com a regra atual e o corte testado marcados; e a taxa de podres chamadas de boas para cada corte, com o limite de 5% e o corte testado acima dele.
