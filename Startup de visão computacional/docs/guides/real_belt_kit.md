# Kit de gravação e medição em esteira real

Escrito em 2026-10-12. O checklist de uma página para o dia da gravação está em [docs/data/collection.md](../data/collection.md). Este guia explica o porquê e como as duas ferramentas funcionam.

**Estado:** as ferramentas foram testadas com vídeo gravado e com a esteira simulada. Nenhuma câmera ao vivo foi ligada e nada foi medido numa esteira de caju.

---

## 1. O problema que o kit resolve

O classificador foi treinado e medido com fotos de fruto no pé. Para saber quanto ele acerta numa esteira, é preciso ter imagens da esteira com a resposta certa ao lado. Rotular imagem por imagem é lento e sujeito a erro.

A saída é rotular **antes** de filmar: pessoas separam as frutas em bandejas (boa, baixa qualidade, podre), e cada bandeja passa sozinha na esteira. Tudo o que a câmera vê naquela passagem tem o rótulo da bandeja.

O kit tem duas ferramentas:

| Ferramenta | Quando | O que faz |
|---|---|---|
| `tools/capture_tray.py` | Na fábrica | Grava uma bandeja, com rótulo, sessão, ajustes da câmera e somas de verificação |
| `tools/eval_real_belt.py` | Depois | Mede um modelo nas bandejas gravadas |

---

## 2. Conceitos

- **Sessão**: uma visita, com uma câmera numa posição, uma luz e um conjunto de ajustes. Mexeu na câmera, é outra sessão.
- **Bandeja**: um grupo físico de frutas com um rótulo só. É a unidade de divisão dos dados.
- **Execução**: uma passagem da bandeja pela esteira. A mesma bandeja pode passar mais de uma vez.
- **Recorte**: o quadrado em volta de uma fruta num quadro. Cada fruta deixa até 6 recortes (vistas).
- **Soma de verificação (SHA-256)**: um número calculado a partir do conteúdo do arquivo. Se um byte muda, o número muda. Serve para provar que os arquivos medidos são os gravados.
- **Por que dividir por bandeja e não por quadro**: os 6 recortes de uma fruta são quase iguais. Se um vai para o ajuste e outro para a medição, o modelo é testado em algo que praticamente já viu, e o número sai inflado. Por isso a unidade de medida é a fruta e a unidade de divisão é a bandeja.

---

## 3. Gravar: `tools/capture_tray.py`

```powershell
python tools/capture_tray.py --session 2026-10-20-fabrica-a --sector recepcao --tray podre-A --label podre --source 0 --px-per-mm 1.6 --exposure -8 --gain 0 --white-balance 4500 --preview
```

### O que ele recusa

A gravação não começa, e nada é criado em disco, se faltar:

- `--session`, `--tray` ou `--label` (o rótulo tem de ser `boa`, `baixa_qualidade` ou `podre`);
- `--px-per-mm`;
- com câmera ao vivo, `--exposure`, `--gain` ou `--white-balance`.

Também recusa regravar uma bandeja com outro rótulo, e misturar numa sessão outro produto, outro setor ou gravação de teste com gravação de verdade.

### De onde ele lê

| Fonte | Como indicar | Verificado? |
|---|---|---|
| Arquivo de vídeo | caminho do arquivo | Sim, com vídeo da simulação e com os clipes reais |
| Câmera USB | o número dela (`0`, `1`) | Não: nenhuma câmera foi ligada |
| Câmera IP | `rtsp://usuário:senha@endereço/...` | Não |
| Câmera GigE | só pelo driver DirectShow do fabricante ou por uma ponte RTSP | Não |

Sobre GigE: o OpenCV instalado aqui tem FFMPEG, DirectShow e Media Foundation, mas não tem GStreamer, que é o caminho usual para câmeras GigE Vision. Sem o driver do fabricante, o programa não abre esse tipo de câmera.

A senha de um endereço RTSP nunca é gravada: o endereço entra no manifesto como `rtsp://***@endereço/...`.

### Ajustes da câmera

O programa guarda três coisas, lado a lado:

1. o que o operador declarou (`--exposure`, `--gain`, `--white-balance`);
2. o que o driver informa antes e depois;
3. se os dois batem.

Com `--apply-settings` ele também tenta gravar os valores na câmera pelo driver. Isso depende da câmera e do driver, e não foi testado em nenhuma câmera. O que vale é o valor fixado na câmera e anotado pelo operador; quando o driver discorda, o programa avisa.

Nas câmeras USB do Windows, a exposição costuma ser uma potência de 2: `-8` quer dizer 1/256 s. Em câmeras IP os valores são os da página de configuração da câmera.

### Geometria

- `--px-per-mm`: escala, medida com a régua.
- `--belt-rows A B`: primeira e última linha da imagem que são esteira.
- `--roi X0 Y0 X1 Y1`: parte do quadro a usar, em frações de 0 a 1.
- `--rotate 90`: para câmera montada de lado. O programa espera a fruta andando na horizontal.
- `--direction -1`: fruta andando da direita para a esquerda.
- `--count-line 0.62`: posição da linha de contagem.

### O que fica gravado

```
belt_sessions/<sessão>/
  session.json                     quem é a sessão e a lista de execuções
  manifest.csv                     uma linha por recorte
  <bandeja>/<rótulo>/*.jpg         os recortes
  <bandeja>/frames/*.jpg           um quadro inteiro a cada 2 s
  <bandeja>/video/*.avi            o vídeo bruto (só câmera ao vivo)
  <bandeja>/runs/<execução>.json   a ficha da execução
```

A ficha da execução traz sessão, bandeja, rótulo, produto, setor, operador, fonte, hora de início e de fim com fuso, os ajustes da câmera, a geometria, as versões do programa e a lista de todos os arquivos gravados com tamanho e SHA-256. Para um arquivo de vídeo, traz também o SHA-256 do vídeo de origem.

A pasta padrão é `FruitCamData\belt_sessions` na pasta do usuário, fora do repositório e fora do OneDrive. As imagens são da empresa onde foram gravadas.

### Conferir

```powershell
python tools/capture_tray.py --verify <pasta da sessão>
```

Recalcula tudo e aponta arquivo alterado, arquivo faltando e recorte que está no manifesto mas em nenhuma ficha.

---

## 4. Medir: `tools/eval_real_belt.py`

```powershell
python tools/eval_real_belt.py <pasta da sessão> [outra sessão ...] --model models/belt_v3.pt
```

Antes de qualquer conta ele confere as somas de verificação e recusa a sessão se algo mudou.

### O que sai

| Saída | Como é calculada |
|---|---|
| Sensibilidade e precisão por classe | Por fruta, com IC 95% de Wilson e o n ao lado |
| Matriz de confusão | Linhas: rótulo da bandeja. Colunas: resposta do modelo |
| Acurácia balanceada | Média da sensibilidade das classes presentes, com IC 95% por bootstrap |
| Podres chamadas de boas | k de n, com IC 95% |
| Cobertura × acerto | Para cada corte de confiança: quantas frutas seriam decididas e com que acerto |
| Corte em bandejas separadas | O corte é escolhido em metade das bandejas e medido na outra metade |
| Cópias | Recortes idênticos em duas bandejas, e pares quase iguais entre as duas metades |

A resposta de uma fruta é a média das probabilidades das suas vistas, como o app faz.

### O intervalo de confiança

Frutas da mesma bandeja se parecem: mesma luz, mesmo lote, mesmo momento. Um bootstrap que sorteia frutas soltas finge que elas são independentes e devolve um intervalo estreito demais.

Por isso o programa sorteia **bandejas inteiras** dentro de cada classe. Quando alguma classe tem uma bandeja só, isso não é possível; ele então sorteia frutas dentro de cada bandeja e avisa, na saída, que o intervalo está otimista.

Um teste mostra a diferença: com 12 bandejas cujo acerto varia de 55% a 95%, o intervalo por bandeja saiu 4 vezes mais largo que o por fruta (0,224 contra 0,056).

Com 2 ou 3 bandejas por classe, mesmo o intervalo por bandeja é grosseiro. É mais uma razão para gravar 6 ou mais.

### O corte de confiança

A tabela de cobertura × acerto usa todas as frutas. Escolher o corte olhando para ela e relatar o acerto dela é otimista: o corte foi ajustado aos mesmos dados.

O bloco "corte medido em bandejas separadas" faz o certo: divide as bandejas de cada classe em duas metades, escolhe o menor corte que chega a 95% de acerto numa metade e relata o resultado na outra. Precisa de pelo menos 2 bandejas por classe.

**O programa só mede.** Ele não liga nenhum corte no app.

---

## 5. Depois da medição

Se a medição mostrar que o modelo precisa melhorar na esteira, as bandejas servem de treino:

```powershell
python tools/finetune_belt.py --data <pasta da sessão> --init models/belt_v3.pt --out models/belt_ft.pt --mix-field
```

Ele separa bandejas de treino, validação e teste, mostra o acerto antes e depois **nas mesmas bandejas de teste**, e escreve `models/belt_ft_eval.json`. Use o modelo novo só se ele for melhor ali.

Sem rótulos, dá para adaptar as estatísticas de normalização da rede às imagens da esteira (`tools/adapt_bn.py`), mas isso só pode ser conferido com bandejas rotuladas.

---

## 6. O ensaio de ponta a ponta

Relatório em [docs/reports/real_belt_kit/pipeline_test.md](../reports/real_belt_kit/pipeline_test.md). Seis "bandejas" de mentira tiradas dos clipes reais de batata, cítricos e maçã: 93 objetos, 344 recortes, 371 arquivos conferidos, avaliação completa. É um teste do programa; os rótulos não valem e nenhum número é desempenho.

A lição prática do ensaio: com produto amontoado, o detector por cor quase não acha objetos isolados. Na gravação de verdade, as frutas têm de passar espalhadas.

---

## 7. Testes

[core/tests/test_real_belt_kit.py](../../core/tests/test_real_belt_kit.py), 8 testes. Eles gravam seis bandejas a partir de vídeos da esteira simulada e conferem:

| Teste | O que prova |
|---|---|
| `..._refuses_to_start_without_label_session_or_fixed_camera_settings` | Sem rótulo, sessão, escala ou ajustes de câmera ao vivo, nada começa e nada é criado |
| `..._one_tray_keeps_one_label_and_one_session_keeps_one_product` | Bandeja não muda de rótulo; sessão não muda de produto |
| `..._every_saved_file_is_listed_with_a_checksum_and_changes_are_caught` | Um byte a mais ou um arquivo apagado é apontado |
| `..._camera_password_never_reaches_the_manifest` | A senha do endereço RTSP não é gravada |
| `..._evaluation_counts_fruit_and_keeps_trays_apart` | A unidade é a fruta; nenhuma bandeja fica nas duas metades |
| `..._evaluation_refuses_a_session_whose_files_changed` | Sessão alterada não é medida |
| `..._a_pipeline_test_session_is_marked_in_every_output` | O aviso de teste aparece em tudo e não se mistura com sessão real |
| `..._tray_bootstrap_is_wider_than_a_fruit_bootstrap_when_trays_differ` | O intervalo por bandeja é mais largo quando as bandejas diferem |

Nesses testes o modelo acerta 100% das frutas desenhadas da simulação. Isso não quer dizer nada: são desenhos de cores bem separadas.

---

## 8. Não verificado

- Nenhuma câmera ao vivo foi ligada. O caminho USB, RTSP e GigE, a gravação do vídeo bruto e a aplicação de ajustes pelo driver não foram exercitados.
- Nenhuma esteira de caju, nenhuma luz de fábrica, nenhum operador.
- As regras de exposição do checklist são prática geral de fotografia, não medições nossas.
- A tabela de "quantas frutas" supõe frutas independentes; a margem real é maior.
