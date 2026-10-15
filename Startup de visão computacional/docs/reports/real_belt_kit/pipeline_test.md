# Ensaio de ponta a ponta do kit de esteira (teste do programa, não desempenho)

Feito em 2026-10-12. Saída completa em [pipeline_test_output.txt](pipeline_test_output.txt).

**O que este ensaio é.** Um teste de que as duas ferramentas funcionam com vídeo gravado de verdade: abrir o arquivo, achar objetos, salvar recortes, escrever o manifesto com somas de verificação, conferir as somas e produzir o relatório de avaliação.

**O que ele não é.** Não é medição de nada. As "bandejas" são trechos de vídeos de batata, cítricos e maçã, e os rótulos foram atribuídos por nós sem relação com a fruta. A sessão foi gravada com `--pipeline-test`, e todo arquivo e toda saída carregam o aviso.

## O que foi usado

| "Bandeja" | Rótulo de mentira | Vídeo (conjunto) | Trecho |
|---|---|---|---|
| boa-A | boa | classificadora de maçãs (`apple_grading_video`) | 0 a 8,5 s |
| boa-B | boa | o mesmo | 8,5 s ao fim |
| baixa_qualidade-A | baixa qualidade | galpão de cítricos (`usda_line_videos`) | 122 a 134 s |
| baixa_qualidade-B | baixa qualidade | o mesmo | 134 a 147 s |
| podre-A | podre | esteira de batata, clipe 0921 (`usda_line_videos`) | inteiro |
| podre-B | podre | esteira de batata, clipe 0920 (`usda_line_videos`) | inteiro |

Os recortes ficaram em `FruitCamData\belt_sessions\teste-pipeline-clipes`, fora do repositório. Nenhuma imagem desses vídeos foi copiada para o projeto.

## O que aconteceu

| Etapa | Resultado |
|---|---|
| Gravação | 6 execuções; 93 objetos cruzaram a linha; 344 recortes; 20 quadros inteiros |
| Bandeja sem nenhum objeto | boa-B: 0 objetos. O programa avisou e pediu para conferir escala, região e direção |
| Somas de verificação | 371 arquivos conferidos, todos íntegros |
| Avaliação | Rodou em 85 objetos com recorte, de 5 bandejas; imprimiu n em cada linha |
| Intervalo de confiança | Caiu para reamostragem por fruta e avisou, porque "boa" ficou com uma bandeja só |
| Corte em bandejas separadas | Recusado com explicação, pelo mesmo motivo |
| Recortes idênticos em duas bandejas | 0 |

## O que o ensaio ensinou

- **O detector por cor não separa produto amontoado.** Nos vídeos, a esteira está coberta de produto, a cor mediana do quadro é a do próprio produto, e quase nada é reconhecido como objeto isolado. Foi preciso procurar região, rotação e direção em cada clipe para alguma coisa cruzar a linha. É o mesmo limite já medido na esteira de batata. Na gravação de verdade, as frutas precisam passar espalhadas.
- **A rotação e a região do quadro fazem falta.** Entraram no programa (`--rotate`, `--roi`) por causa deste ensaio.
- **Fruta contada sem recorte.** 8 dos 93 objetos cruzaram a linha sem deixar recorte utilizável. A avaliação agora mostra os dois números.
- **Curiosidade, sem valor de medida:** para esses objetos que não são caju, a confiança do modelo nunca passou de 75%.

## Não verificado

- Câmera ao vivo (USB, RTSP ou GigE): nenhuma foi ligada. O caminho de câmera ao vivo, a gravação do vídeo bruto e a leitura dos ajustes pelo driver não foram exercitados.
- Esteira real de caju, luz real, operador real.
