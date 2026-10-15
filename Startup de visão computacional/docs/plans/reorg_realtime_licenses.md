# Plano: organização, tempo real e licenças (2026-10-11)

Três tarefas pedidas, mais um bloqueio de ambiente encontrado no caminho. Este arquivo é o plano escrito antes da execução; o que mudou durante a execução fica na seção 6.

---

## 0. Bloqueio encontrado: o Windows passou a bloquear o torchvision

- **Sintoma:** nenhum comando do projeto iniciava (`RuntimeError: operator torchvision::nms does not exist`).
- **Causa:** o Controle Inteligente de Aplicativos do Windows 11 (Smart App Control) está ligado e bloqueia o arquivo nativo `_C.pyd` do torchvision (`WinError 4551`). As versões instaladas não mudaram desde abril. Todas as outras bibliotecas, o node, o vite, o ffmpeg e o navegador de testes continuam funcionando.
- **O que não foi feito:** desligar a proteção. Essa decisão é do dono da máquina, e a proteção não pode ser religada sem reinstalar o Windows.
- **Solução no projeto:** o site e a câmera só usavam o torchvision para definir a arquitetura MobileNetV3-Small. Ela foi escrita em PyTorch puro em `belt/mobilenet.py`, com os mesmos nomes de camadas dos pesos treinados.
- **Prova:**
  - carregamento estrito dos 3 checkpoints (244 tensores cada);
  - nos 649 recortes de teste, a maior diferença para as probabilidades gravadas no treino (feito com torchvision) é 5,3e-06, que é o arredondamento do arquivo;
  - mesma classe em 649 de 649.
  - Virou o teste permanente `test_model_reproduces_the_stored_test_predictions`.
- **Onde o torchvision continua:** só nos scripts de treino (`train.py`, `train_belt.py`), importado dentro das funções que treinam. Um teste que compara com a transformação do torchvision é pulado, com o motivo escrito, quando ele não carrega.

---

## 1. Tarefa 1: organizar pastas e documentos

### Estado atual

A raiz do projeto tem cerca de 65 itens misturados:
- 11 documentos `.md`;
- 13 scripts Python soltos;
- 8 saídas de teste `.txt`;
- 5 pastas de dados;
- o banco de dados, uploads e arquivos de execução.

### Estrutura alvo

| Pasta | Conteúdo | De onde vem |
|---|---|---|
| `README.md` | Visão geral, mapa das pastas, como rodar | novo |
| `LICENSES.md` | Único lugar de licenças e créditos (Tarefa 3) | novo |
| `fruitcam/`, `core/`, `belt/`, `frontend/`, `config/` | Aplicação (projeto Django, app, pipeline da câmera, interface, configuração) | ficam |
| `core/tests/` | Todos os testes do app | `core/tests.py`, `core/test_*.py` |
| `analytics/` | Estatística de frutas, registros, verificação, figuras de demonstração, protótipo antigo de logs | `fruit_analytics.py`, `records.py`, `test_fruit_analytics.py`, `analytics_demo_synthetic/`, `logs/` |
| `training/` | Treino e avaliação do modelo, scripts originais | `train.py`, `train_belt.py`, `infer.py`, `crop_dataset.py`, `data_synth.py`, `audit_small_boxes.py`, `size_test.py`, `visualize.py`, `test_pipeline.py`, `test_vizualise` |
| `core/bbox.py` | Caixa por limiarização (usada em produção pela inspeção por foto) | `Bbox.py` |
| `tools/`, `scripts/` | Ferramentas de mídia, modelos e dados; lançadores | ficam |
| `docs/guides/` | Como cada parte funciona | `WEBAPP.md`, `DASHBOARD.md`, `ANALYTICS.md`, `CAMERA.md`, `CERTIFICATE.md`, `MEDIA.md`, `DESIGN.md`, `SHOWCASE.md`, `docs/control_and_motion.md`, `docs/dataset_and_layout.md` |
| `docs/data/` | Coleta e pedidos de dados, relatórios dos conjuntos | `DATA_COLLECTION.md`, `DATA_REQUESTS.md`, `docs/datasets/` |
| `docs/plans/` | Planos escritos antes de cada trabalho | `docs/layout/plan.md`, `docs/control_plan.md`, este arquivo |
| `docs/reports/` | Saídas reais de teste, capturas de tela, desempenho | `*_test_output.txt`, `bundle_*.txt`, `docs/layout/`, `docs/visual/` |
| `docs/architecture/` | Arquitetura de tempo real (Tarefa 2) | novo |
| `datasets/` | Dados versionados: fotos e rótulos de caju, recortes, cache de máscaras | `images/`, `Labels/`, `data_real/`, `data_cropped_out/`, `data_cache/` |
| `data/` | Downloads externos (ignorados pelo git) | fica |
| `models/` | Checkpoints e avaliações | + `model.pt` |
| `assets/` | Marca, fontes das mídias, figuras científicas | `brand/`, `media_src/`, `figures/` |
| `deliverables/` | Pacotes prontos para entregar | `summit_pack/` |
| `var/` | Estado de execução, ignorado pelo git: banco, uploads, quadros da câmera | `db.sqlite3`, `uploads/`, `run/` |

### Como será feito

1. **Cópia de segurança** de todo o código e dos documentos (sem os dados) antes de mover.
2. **Mapa de movimentação** (`docs/reports/reorg/move_map.json`): cada origem com seu destino, aplicado por script. Também serve para desfazer.
3. **Reescrita de referências** por script:
   - imports Python;
   - caminhos `ROOT / "..."`;
   - padrões das configurações;
   - links relativos entre documentos;
   - comandos citados nos documentos.
4. **`.gitignore`** completo: `var/`, `__pycache__/`, `node_modules/`, `frontend/dist/`.
5. **Verificação:**
   - todos os módulos importam;
   - nenhum caminho antigo sobra no código;
   - todos os links dos documentos resolvem;
   - o frontend constrói;
   - a suíte completa passa;
   - os comandos principais rodam (`seed_showcase`, `run_camera`, `runserver`).

### O que não muda

- A lógica de `infer.py`, do modelo e da matemática das estatísticas. Só mudam linhas de import.
- O nome da pasta raiz do projeto, para que os comandos que você já usa continuem valendo.
- O índice do git. Nada é adicionado, removido ou commitado; o git verá as movimentações quando você decidir commitar.

---

## 2. Tarefa 3: um único lugar para licenças e créditos

### Estado atual

Menções de licença e autoria aparecem em mais de 40 arquivos:
- **Na interface:** linhas de crédito sob banners, cartões de fruta, guia de foto, login e câmera simulada; legendas de vídeo.
- **Em 5 documentos.**
- **Em dados e geradores:** `summit_pack/LICENCAS.md`, `scripts/datasets.json`, `media_src/sources.json`, textos OFL das fontes em 2 pastas, e textos fixos dentro de ferramentas.

### Alvo

- **Um registro:** `legal/registry.json`, a única fonte, com fotos, vídeos, conjuntos de dados, fontes tipográficas, recortes da esteira simulada, material próprio e bibliotecas de software.
- **Textos das licenças:** `legal/texts/`, uma cópia de cada (OFL, CC, etc.).
- **Um documento:** `LICENSES.md` na raiz, gerado do registro.
- **Uma página:** "Créditos e licenças" no site, gerada do mesmo registro e ligada no rodapé de todas as páginas.
- **Tudo o mais sai:**
  - linhas de crédito e links de licença nas outras páginas;
  - tabelas de licença nos outros documentos, trocadas por um ponteiro para `LICENSES.md`;
  - textos de atribuição fixos em ferramentas, que passam a ler do registro.
- **Exceção:** o pacote `summit_pack` é entregue sozinho, então precisa levar o próprio arquivo de licenças. Ele passa a ser gerado do mesmo registro.

### O que fica nas páginas

Os avisos de honestidade, que não são licenças: "Imagem ilustrativa", "SIMULAÇÃO", "DEMO".

### Base legal

CC BY e CC BY-SA pedem atribuição "razoável ao meio". Uma página de créditos única, com autor, licença, fonte e modificações, acessível por link em todas as páginas, é prática aceita. A licença OFL exige que o texto da licença acompanhe a fonte; ele fica em `legal/texts/` e é servido pelo site.

### Verificação

- Nenhuma página além de Créditos mostra texto de licença.
- Todo arquivo de terceiros publicado tem entrada no registro, sem órfãos.
- `LICENSES.md` é idêntico ao que o gerador produz.

---

## 3. Tarefa 2: arquitetura de tempo real, 24 horas

### Estado atual

| Parte | Hoje | Problema em operação contínua |
|---|---|---|
| Câmera | Um laço: lê quadro, processa, grava. Eventos pendentes ficam na memória | Queda de energia ou travamento perde frutas contadas. Se o processamento atrasa, a latência cresce sem limite |
| Supervisão | Nenhuma: um comando por câmera, à mão | Se o processo cai, a linha fica sem contagem até alguém perceber |
| Linha (estatística) | Cada consulta relê os eventos da janela e recalcula com pandas | 24 h de uma câmera são cerca de 170 mil eventos por consulta |
| Página Linha | Pergunta ao servidor a cada 15 s | Atraso de até 15 s; alarmes chegam tarde |
| Painel | Cada consulta carrega todos os eventos na memória | Um ano de uma câmera são dezenas de milhões de eventos |

### Alvo

**A. Serviço de câmera resiliente (`belt/service.py`, comando `run_camera`)**
- **Captura sem atraso:** para câmeras ao vivo, uma thread de captura mantém só o quadro mais recente. Se o processamento atrasar, quadros velhos são descartados e contados. A latência fica limitada.
- **Gravação durável, exatamente uma vez:**
  - cada fruta contada vai primeiro para um arquivo de fila em disco (spool), com um identificador único;
  - uma thread gravadora envia em lotes ao banco;
  - depois de uma queda, o que não foi confirmado é reenviado;
  - o identificador único impede duplicatas.
- **Estado de saúde:** quadros por segundo, latência, fila, quadros descartados, último erro.
- **Parada limpa:** ao receber Ctrl+C ou sinal de término, esvazia a fila antes de sair.

**B. Supervisor (`run_line`)**
- Sobe todas as câmeras do arquivo de configuração.
- Reinicia qualquer uma que cair, com espera crescente.

**C. Agregados incrementais**
- `MinuteStat`: por câmera, minuto e lote, guarda contagens por classe, soma e histograma de tamanho, primeiro e último instante. É atualizado na mesma transação em que o evento é gravado.
- `DayCount`: por dia, setor, fruta e classe, guarda as contagens que o Painel usa. Também na mesma transação.
- **Guarda de consistência:**
  - gatilhos no banco contam toda alteração na tabela de eventos;
  - se algo alterar eventos por fora do caminho oficial, a estatística cai automaticamente no cálculo completo, que é o de hoje;
  - o comando `rebuild_rollups` refaz os agregados a partir dos eventos.
  - Os eventos continuam sendo a verdade.

**D. Estatística sobre agregados, com a mesma matemática**
- **Linha:** as janelas, a carta de controle e os lotes passam a ser montados de `MinuteStat`. As funções `p_chart`, `wilson` e `lot_verdict` não mudam.
- **Painel:** os 4 redutores de `fruit_analytics` (contagens, defeitos, frutas, proporção por setor) aceitam linhas com peso. Todo o resto da matemática fica igual.
- **Prova:** testes de paridade. O resultado pelos agregados tem de ser igual ao resultado pelos eventos, em todas as estatísticas e janelas.

**E. Entrega ao vivo**
- `/api/line/live`: fluxo SSE (Server-Sent Events) que empurra o resumo da linha assim que muda, no máximo 1 vez por segundo.
- A página Linha usa o fluxo quando a câmera está ligada e volta à consulta periódica se o fluxo cair.

**F. Operação**
- `/api/health`: banco, câmeras, atraso, fila.
- `prune_events`: retenção. Apaga eventos brutos mais antigos que N dias; os agregados ficam.
- Documento de implantação: processos, servidor com threads, variáveis de ambiente.

### Verificação

- **Paridade:** agregados e eventos dão o mesmo resultado.
- **Durabilidade:** matar o serviço no meio e reiniciar não perde nem duplica fruta.
- **Banco travado:** falhas de gravação injetadas não perdem fruta.
- **Carga:** simulação acelerada de várias horas. Mede eventos por segundo, latência e tempo de resposta da linha e do painel antes e depois.
- **Fluxo ao vivo:** o navegador recebe atualizações em menos de 2 s depois da fruta cruzar a linha.

---

## 4. Ordem de execução

1. Bloqueio do torchvision (feito).
2. Suíte completa de base.
3. Tarefa 1, depois suíte completa.
4. Tarefa 3, depois testes de mídia, layout e créditos.
5. Tarefa 2 em etapas (agregados → serviço → fluxo ao vivo), com testes novos em cada etapa.
6. Suíte completa final, medições e documentos.

---

## 5. Riscos e cuidados

- **Trabalho não commitado:** tudo desde o commit `2161599` está só no disco. Por isso a cópia de segurança antes de mover e o mapa de movimentação reversível.
- **OneDrive:** pode recusar renomear pastas sincronizadas. Cada movimentação é atômica; se falhar, nada fica pela metade.
- **Nunca reconstruir o frontend enquanto os testes de navegador rodam.**
- **Máquina com pouca memória:** a suíte completa leva de 15 a 20 minutos e roda sozinha.

---

## 6. Desvios durante a execução

Registro do que saiu diferente do plano e do que apareceu pelo caminho. Resultados e medições estão em [architecture/realtime.md](../architecture/realtime.md) e em [legal/README.md](../../legal/README.md).

### Tarefa 1 (pastas)

- Dois arquivos mudaram de lugar depois da primeira movimentação, por causa da Tarefa 3: o relatório da busca de conjuntos de dados foi para `legal/reports/dataset_search.md`, porque seu conteúdo é a análise de licenças, e a saída do módulo de testes de dados foi para `docs/reports/tests/datasets_module_test_output.txt`, junto das outras saídas de teste.
- `requirements.txt` não listava o OpenCV, embora `belt/` o use; uma instalação nova falharia. A linha `opencv-python==4.13.0.92` (a versão instalada nesta máquina) foi acrescentada.

### Tarefa 3 (licenças)

- A página Créditos lê `legal/site.json` diretamente da pasta `legal/`, fora de `frontend/`. Assim não sobra nenhuma cópia de dados de licença dentro da interface.
- O registro ganhou duas seções que o plano não previa: **software de código aberto** (22 bibliotecas, conferidas contra `requirements.txt` e `package.json` por teste) e **código próprio**, com a anotação honesta de que a equipe ainda não escolheu a licença.
- Regra do teste que procura menções: palavras de licença são proibidas em todo lugar fora de `legal/` e `LICENSES.md`. Nomes de autores e fontes são proibidos no código, na interface e nas fichas, mas permitidos nos guias em texto corrido, porque contar de onde veio um conjunto de dados não é repetir o crédito.
- Exceções mantidas de propósito: o kit do Summit (sai do repositório sozinho e leva o próprio arquivo de créditos, agora gerado do registro), os registros datados (`docs/reports`, `docs/plans`, relatórios em `models/`) e os dados de terceiros.
- A mídia foi regenerada por completo com `tools/build_media.py`. Mudaram só as legendas dos dois vídeos gravados (o texto perdeu as menções) e o arquivo WebM do fundo do login, porque o codificador não produz bytes idênticos a cada execução. As demais 15 mídias saíram idênticas.
- `tools/build_summit_pack.py` falhou na primeira execução: o OneDrive segurou uma pasta, a ferramenta apagou os arquivos do kit e parou. A ferramenta passou a apagar só arquivos, como `build_media.py` já fazia, e o kit foi gerado de novo.

### Tarefa 2 (tempo real)

- **Tamanho da fruta.** Mediana e percentis passaram a vir de um histograma com faixas de 0,5 mm, nos dois caminhos de leitura. O número pode diferir do exato em até 0,25 mm, menos que um pixel da câmera configurada. A tela mostra milímetros inteiros.
- **Painel.** Além dos quatro redutores previstos, o construtor `overview` de `core/stats.py` foi reescrito para aceitar pesos. A igualdade com o caminho antigo foi provada em 252 comparações e pelos testes do Painel que já existiam.
- **Certificado em PDF.** Continua lendo os eventos um a um. Ele precisa da hora exata do primeiro e do último evento, que os agregados diários não guardam.
- **Sem escrita em leituras.** O plano cogitava reconstruir os agregados na primeira leitura depois de uma divergência. Ficou decidido que uma consulta nunca escreve: ela recua para os eventos, e quem reconstrói é o lado que grava (serviço de câmera, comandos de carga, migração).
- **Gravador.** Roda em thread própria na operação normal e no mesmo passo da análise quando há uma transação aberta por fora ou com `--fast`.
- **Retenção.** O comando `prune_events` entrou, com data de corte registrada, mas nunca roda sozinho.

### Defeitos encontrados e corrigidos no caminho

- **Painel puxava o usuário de volta.** Quem saía do Painel antes de ele terminar de escolher a fonte de dados era trazido de volta, porque a troca de endereço do Painel cancelava a navegação em curso. Era a causa do erro intermitente no teste de navegação.
- **"Reduzir movimento" deixava transições de 0,01 ms.** Elas duravam um quadro e às vezes eram flagradas pelo teste. Agora as transições são desligadas por completo, e a tela de abertura é removida sem transição nesse modo.
- **Teste de recarga dependia do relógio.** Duas cargas seguidas só davam o mesmo total se caíssem no mesmo minuto. O teste passou a fixar o relógio.
- **Câmera "caía" por um instante na tela.** No teste com navegador, a página fechou o fluxo ao vivo uma vez em 90 s. A leitura do arquivo de estado falhava quando coincidia com a troca do arquivo, e a resposta era "fora do ar". A leitura passou a tentar de novo, e a página só aceita "fora do ar" depois de três avisos seguidos. Em 120 s do teste repetido, uma única conexão e nenhuma queda.
- **Regra do orçamento de movimento.** A primeira versão da correção de "reduzir movimento" usava uma forma de CSS que o teste de orçamento de movimento rejeita. A suíte completa acusou; a regra foi reescrita e a suíte rodou de novo.

### O que ficou sem verificação

Lista completa na seção 7 de [architecture/realtime.md](../architecture/realtime.md). Em resumo: câmera real, operação por dias seguidos, queda de energia, muitos usuários no fluxo ao vivo e registro como serviço do sistema operacional.
