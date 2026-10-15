# Calibração e ponto de operação do belt_v3

Gerado por `python tools/calibration_v3.py`. Explicação em [docs/guides/model_checks.md](../../guides/model_checks.md).

**Tudo aqui é medido em fotos de fruto no pé, não em esteira.** O ponto de operação é uma proposta; o app não mudou.

## Dados

| Conjunto | Recortes | Fotos | boa | baixa qualidade | podre |
|---|---|---|---|---|---|
| Validação (ajuste) | 3335 | 451 | 779 | 2373 | 183 |
| Teste (relato) | 3016 | 417 | 775 | 2034 | 207 |

Divisão por foto. Fotos presentes nos dois conjuntos: 0.

### Cópias quase iguais entre treino e teste

Cada um dos 3016 recortes de teste foi comparado com os 14033 de treino por um hash de diferença de 64 bits. Distância pequena quer dizer imagem quase idêntica.

| Distância máxima | Recortes de teste com cópia no treino | Acurácia sem eles | Acurácia balanceada sem eles | n restante |
|---|---|---|---|---|
| 0 bits | 0 | 89,6% | 89,2% | 3016 |
| 4 bits | 31 | 89,5% | 89,1% | 2985 |
| 8 bits | 192 | 89,2% | 88,7% | 2824 |

O que este teste não cobre: o mesmo fruto fotografado de outra posição não é uma imagem quase idêntica, e as fotos não trazem posição para conferir isso.

## Calibração

Temperatura ajustada só na validação: **1,403** (a gravada no modelo é 1,402).

| No teste (n = 3016) | Antes | Depois |
|---|---|---|
| ECE, 15 faixas | 0,040 (IC 95% 0,030 a 0,055) | 0,012 (IC 95% 0,010 a 0,026) |
| Log-verossimilhança negativa | 0,297 | 0,273 |
| Confiança média | 93,6% | 90,3% |
| Acurácia | 89,6% | 89,6% |

Redução do ECE: IC 95% de 0,014 a 0,033 (bootstrap por foto).

### Confiabilidade depois da calibração

| Faixa de confiança | n | Confiança média | Acerto observado (IC 95%) |
|---|---|---|---|
| 30% a 40% | 1 | 38,3% | 0,0% (0,0% a 79,3%) |
| 40% a 50% | 28 | 46,5% | 35,7% (20,7% a 54,2%) |
| 50% a 60% | 145 | 55,2% | 53,1% (45,0% a 61,0%) |
| 60% a 70% | 169 | 64,8% | 64,5% (57,0% a 71,3%) |
| 70% a 80% | 184 | 75,0% | 71,2% (64,3% a 77,3%) |
| 80% a 90% | 360 | 85,4% | 85,0% (80,9% a 88,3%) |
| 90% a 100% | 2129 | 97,5% | 97,2% (96,4% a 97,8%) |

### A probabilidade de podre diz a verdade?

| Probabilidade de podre | n | Média | Fração que era podre (IC 95%) |
|---|---|---|---|
| 0% a 10% | 2190 | 1,4% | 0,5% (0,2% a 0,8%) |
| 10% a 20% | 198 | 14,3% | 1,5% (0,5% a 4,4%) |
| 20% a 30% | 101 | 24,7% | 5,9% (2,8% a 12,4%) |
| 30% a 40% | 83 | 35,1% | 3,6% (1,2% a 10,1%) |
| 40% a 50% | 58 | 44,6% | 8,6% (3,7% a 18,6%) |
| 50% a 60% | 56 | 55,1% | 12,5% (6,2% a 23,6%) |
| 60% a 70% | 47 | 64,9% | 17,0% (8,9% a 30,1%) |
| 70% a 80% | 48 | 74,5% | 20,8% (11,7% a 34,3%) |
| 80% a 90% | 78 | 85,5% | 50,0% (39,2% a 60,8%) |
| 90% a 100% | 157 | 95,9% | 73,9% (66,5% a 80,1%) |

## Precisão média por classe (curva precisão × sensibilidade, teste)

| Classe | Positivos | n | Precisão média |
|---|---|---|---|
| boa | 775 | 3016 | 96,7% |
| baixa_qualidade | 2034 | 3016 | 98,9% |
| podre | 207 | 3016 | 72,3% |

## Ponto de operação para "podre"

Regra testada: responder "podre" só quando a probabilidade de podre passa de um corte; abaixo dele, responder a mais provável das outras duas classes.
Limite: no máximo 5% das podres chamadas de boas. O corte é escolhido na validação e relatado no teste.

### No teste (n = 3016)

| Regra | Precisão de podre | Sensibilidade de podre | Podres chamadas de boas | Boas chamadas de podres | Acurácia balanceada |
|---|---|---|---|---|---|
| maior probabilidade (atual) | 45,3% (182 de 402; IC 95% 40,5% a 50,2%) | 87,9% (182 de 207; IC 95% 82,8% a 91,7%) | 3,9% (8 de 207; IC 95% 2,0% a 7,4%) | 47 de 775 | 89,2% |
| corte 0,30 | 35,7% (188 de 527; IC 95% 31,7% a 39,9%) | 90,8% (188 de 207; IC 95% 86,1% a 94,0%) | 2,9% (6 de 207; IC 95% 1,3% a 6,2%) | 75 de 775 | 87,7% |
| corte 0,35 | 37,8% (185 de 489; IC 95% 33,6% a 42,2%) | 89,4% (185 de 207; IC 95% 84,4% a 92,9%) | 2,9% (6 de 207; IC 95% 1,3% a 6,2%) | 67 de 775 | 87,9% |
| corte 0,40 | 41,7% (185 de 444; IC 95% 37,2% a 46,3%) | 89,4% (185 de 207; IC 95% 84,4% a 92,9%) | 2,9% (6 de 207; IC 95% 1,3% a 6,2%) | 58 de 775 | 88,7% |
| corte 0,45 | 44,7% (184 de 412; IC 95% 39,9% a 49,5%) | 88,9% (184 de 207; IC 95% 83,9% a 92,5%) | 3,4% (7 de 207; IC 95% 1,6% a 6,8%) | 49 de 775 | 89,3% |
| corte 0,50 | 46,6% (180 de 386; IC 95% 41,7% a 51,6%) | 87,0% (180 de 207; IC 95% 81,7% a 90,9%) | 4,3% (9 de 207; IC 95% 2,3% a 8,1%) | 42 de 775 | 89,1% |
| corte 0,55 | 49,2% (177 de 360; IC 95% 44,0% a 54,3%) | 85,5% (177 de 207; IC 95% 80,1% a 89,7%) | 4,3% (9 de 207; IC 95% 2,3% a 8,1%) | 35 de 775 | 89,1% |
| corte 0,60 | 52,4% (173 de 330; IC 95% 47,0% a 57,8%) | 83,6% (173 de 207; IC 95% 77,9% a 88,0%) | 4,3% (9 de 207; IC 95% 2,3% a 8,1%) | 28 de 775 | 89,0% |
| corte 0,65 | 54,8% (167 de 305; IC 95% 49,1% a 60,2%) | 80,7% (167 de 207; IC 95% 74,8% a 85,5%) | 4,8% (10 de 207; IC 95% 2,6% a 8,7%) | 23 de 775 | 88,4% |
| corte 0,70 | 58,3% (165 de 283; IC 95% 52,5% a 63,9%) | 79,7% (165 de 207; IC 95% 73,7% a 84,6%) | 4,8% (10 de 207; IC 95% 2,6% a 8,7%) | 18 de 775 | 88,5% |
| corte 0,75 | 62,4% (161 de 258; IC 95% 56,4% a 68,1%) | 77,8% (161 de 207; IC 95% 71,6% a 82,9%) | 4,8% (10 de 207; IC 95% 2,6% a 8,7%) | 15 de 775 | 88,3% |
| **corte 0,80 (escolhido na validação)** | 66,0% (155 de 235; IC 95% 59,7% a 71,7%) | 74,9% (155 de 207; IC 95% 68,6% a 80,3%) | 5,8% (12 de 207; IC 95% 3,3% a 9,9%) | 14 de 775 | 87,6% |
| corte 0,85 | 70,2% (139 de 198; IC 95% 63,5% a 76,1%) | 67,1% (139 de 207; IC 95% 60,5% a 73,2%) | 6,3% (13 de 207; IC 95% 3,7% a 10,4%) | 12 de 775 | 85,5% |
| corte 0,90 | 73,9% (116 de 157; IC 95% 66,5% a 80,1%) | 56,0% (116 de 207; IC 95% 49,2% a 62,6%) | 6,3% (13 de 207; IC 95% 3,7% a 10,4%) | 10 de 775 | 82,1% |
| corte 0,95 | 80,6% (83 de 103; IC 95% 71,9% a 87,1%) | 40,1% (83 de 207; IC 95% 33,7% a 46,9%) | 9,2% (19 de 207; IC 95% 6,0% a 13,9%) | 7 de 775 | 77,2% |

### Na validação (onde o corte foi escolhido)

| Regra | Precisão de podre | Sensibilidade de podre | Podres chamadas de boas |
|---|---|---|---|
| maior probabilidade | 39,4% (160 de 406; IC 95% 34,8% a 44,2%) | 87,4% (160 de 183; IC 95% 81,8% a 91,5%) | 2,7% (5 de 183; IC 95% 1,2% a 6,2%) |
| corte 0,30 | 31,6% (168 de 531; IC 95% 27,8% a 35,7%) | 91,8% (168 de 183; IC 95% 86,9% a 95,0%) | 1,1% (2 de 183; IC 95% 0,3% a 3,9%) |
| corte 0,35 | 33,8% (165 de 488; IC 95% 29,8% a 38,1%) | 90,2% (165 de 183; IC 95% 85,0% a 93,7%) | 1,6% (3 de 183; IC 95% 0,6% a 4,7%) |
| corte 0,40 | 36,0% (164 de 456; IC 95% 31,7% a 40,5%) | 89,6% (164 de 183; IC 95% 84,4% a 93,3%) | 2,2% (4 de 183; IC 95% 0,9% a 5,5%) |
| corte 0,45 | 38,7% (162 de 419; IC 95% 34,1% a 43,4%) | 88,5% (162 de 183; IC 95% 83,1% a 92,4%) | 2,7% (5 de 183; IC 95% 1,2% a 6,2%) |
| corte 0,50 | 40,3% (159 de 395; IC 95% 35,5% a 45,2%) | 86,9% (159 de 183; IC 95% 81,2% a 91,0%) | 2,7% (5 de 183; IC 95% 1,2% a 6,2%) |
| corte 0,55 | 42,6% (156 de 366; IC 95% 37,7% a 47,7%) | 85,2% (156 de 183; IC 95% 79,4% a 89,7%) | 2,7% (5 de 183; IC 95% 1,2% a 6,2%) |
| corte 0,60 | 45,8% (151 de 330; IC 95% 40,5% a 51,2%) | 82,5% (151 de 183; IC 95% 76,4% a 87,3%) | 2,7% (5 de 183; IC 95% 1,2% a 6,2%) |
| corte 0,65 | 49,2% (145 de 295; IC 95% 43,5% a 54,8%) | 79,2% (145 de 183; IC 95% 72,8% a 84,5%) | 3,3% (6 de 183; IC 95% 1,5% a 7,0%) |
| corte 0,70 | 51,4% (142 de 276; IC 95% 45,6% a 57,3%) | 77,6% (142 de 183; IC 95% 71,0% a 83,0%) | 3,3% (6 de 183; IC 95% 1,5% a 7,0%) |
| corte 0,75 | 54,0% (136 de 252; IC 95% 47,8% a 60,0%) | 74,3% (136 de 183; IC 95% 67,5% a 80,1%) | 3,8% (7 de 183; IC 95% 1,9% a 7,7%) |
| corte 0,80 | 57,2% (127 de 222; IC 95% 50,6% a 63,5%) | 69,4% (127 de 183; IC 95% 62,4% a 75,6%) | 4,9% (9 de 183; IC 95% 2,6% a 9,1%) |
| corte 0,85 | 63,1% (123 de 195; IC 95% 56,1% a 69,5%) | 67,2% (123 de 183; IC 95% 60,1% a 73,6%) | 5,5% (10 de 183; IC 95% 3,0% a 9,8%) |
| corte 0,90 | 70,5% (105 de 149; IC 95% 62,7% a 77,2%) | 57,4% (105 de 183; IC 95% 50,1% a 64,3%) | 7,1% (13 de 183; IC 95% 4,2% a 11,8%) |
| corte 0,95 | 83,3% (75 de 90; IC 95% 74,3% a 89,6%) | 41,0% (75 de 183; IC 95% 34,1% a 48,2%) | 8,7% (16 de 183; IC 95% 5,5% a 13,7%) |

## Leitura

- Com o corte escolhido na validação (0,80), a precisão de podre no teste vai de 45,3% para 66,0%. Diferença: IC 95% de 16,7% a 25,0% (bootstrap por foto).
- O preço: a sensibilidade de podre cai de 87,9% para 74,9%, e as podres chamadas de boas vão de 3,9% para 5,8% (IC 95% por foto: 2,5% a 9,8%).
- **Resultado negativo: o limite de 5% não se manteve no teste.** O corte escolhido na validação não é proposto, e fica a regra atual.
- Mesmo a regra atual não permite afirmar o limite: 8 de 207 podres chamadas de boas dá IC 95% de 2,0% a 7,4%. Com 207 frutas podres no teste, nenhuma regra pode ser certificada abaixo de 5%.
- Lidos depois de ver o teste, e por isso só indicativos: os cortes 0,50, 0,55, 0,60, 0,65, 0,70, 0,75 ficam dentro do limite na estimativa pontual e têm precisão maior que a atual. Escolher um deles agora seria escolher olhando o teste.
- Nada disso foi medido em esteira. O app continua respondendo a classe mais provável e mandando toda fruta para conferência.
