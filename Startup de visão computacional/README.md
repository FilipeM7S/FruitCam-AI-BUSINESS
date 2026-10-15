# FruitCam_ai

Inspeção visual de frutas em esteira. Uma câmera fixa filma a esteira de cima; o sistema conta cada fruta, classifica em **boa**, **baixa qualidade** ou **podre**, mede o tamanho e transforma isso em estatística por linha, lote e setor, em tempo real. O primeiro foco é o caju.

Este arquivo é o mapa do projeto: o que há em cada pasta e como rodar.

---

## Como rodar

No PowerShell, a partir desta pasta:

```powershell
$env:DJANGO_SECRET_KEY = "<um-texto-longo-seu>"
$env:DJANGO_HTTPS = "0"
python manage.py migrate
python manage.py runserver
```

Depois abra http://127.0.0.1:8000.

| Para | Comando |
|---|---|
| Subir o site e as câmeras simuladas juntos (pitch) | `powershell -ExecutionPolicy Bypass -File scripts\pitch.ps1 -Seed` |
| Manter todas as câmeras no ar, sem pausas (reinicia a que cair) | `python manage.py run_line` |
| Parar as câmeras com calma, sem perder contagem | `python manage.py run_line --stop` |
| Ligar só uma câmera (real ou simulada, conforme `config/cameras.json`) | `python manage.py run_camera linha-1` |
| Ver a saúde do sistema | abrir `http://127.0.0.1:8000/api/health` depois de entrar no site |
| Refazer os agregados por minuto e por dia a partir dos eventos | `python manage.py rebuild_rollups` |
| Apagar eventos brutos de câmera antigos, mantendo o histórico agregado | `python manage.py prune_events --days 90` (só mostra; com `--yes` apaga) |
| Gerar de novo o `LICENSES.md` e a página Créditos | `python tools/build_legal.py` |
| Recriar os dados de demonstração | `python manage.py seed_showcase` |
| Criar um usuário | `python manage.py adduser <nome>` |
| Reconstruir a interface depois de mudar `frontend/src` | `cd frontend; npm run build; cd ..` |
| Gravar uma bandeja separada à mão na esteira | `python tools/capture_tray.py --session <sessão> --tray <bandeja> --label <rótulo> --source <câmera ou vídeo> --px-per-mm <escala>` (checklist em [docs/data/collection.md](docs/data/collection.md)) |
| Conferir as somas de verificação de uma sessão gravada | `python tools/capture_tray.py --verify <pasta da sessão>` |
| Medir um modelo nas bandejas gravadas | `python tools/eval_real_belt.py <pasta da sessão>` |
| Refazer a calibração e a tabela do alarme de podre | `python tools/calibration_v3.py` |
| Refazer o diagnóstico do lote excluído de Uganda | `python tools/diagnose_uganda.py` |
| Medir erros de contagem na esteira simulada | `python tools/count_errors.py` |
| Rodar o experimento de autotreino (módulo desligado no app) | `python tools/ttst_experiment.py` |
| Rodar todos os testes (15 a 30 min, usa o Edge) | `python manage.py test core -v 2` |
| Rodar as verificações da estatística | `python -m analytics.test_fruit_analytics` |
| Medir leitura por eventos contra leitura por agregados | `python scripts/bench_realtime.py` |
| Conferir o fluxo ao vivo num navegador de verdade (usa o Edge) | `python scripts/check_live.py` |

---

## Mapa das pastas

### Aplicação

| Pasta | O que é |
|---|---|
| `fruitcam/` | Projeto Django: configurações, rotas, WSGI |
| `core/` | App Django: modelo de dados, API, serviço de câmera, agregados em tempo real, estatísticas do painel, certificado em PDF, comandos de gerenciamento |
| `core/tests/` | Todos os testes automáticos do app |
| `belt/` | Pipeline da câmera: captura, detecção, rastreamento, classificação, fila durável em disco, estatística da linha, simulador de esteira |
| `analytics/` | Estatística de frutas (crescimento, defeitos, previsão, ajuste gaussiano) e suas verificações |
| `frontend/` | Interface (Vue 3 + Vite). O site servido é `frontend/dist` |
| `config/` | Configuração das câmeras (`cameras.json`) |

### Modelo e dados

| Pasta | O que é |
|---|---|
| `training/` | Treino e avaliação do classificador, e os scripts originais de inferência por foto |
| `models/` | Checkpoints treinados e relatórios de avaliação |
| `datasets/` | Dados versionados: fotos e rótulos de caju, recortes, cache de máscaras |
| `data/` | Conjuntos externos baixados (ignorados pelo git; só as fichas `SOURCE.md` são versionadas). As fotos grandes de caju e os recortes de treino ficam fora do repositório, em `FruitCamData` na pasta do usuário, ou onde a variável `FRUITCAM_DATA_STORE` indicar |

### Mídia e entregas

| Pasta | O que é |
|---|---|
| `assets/brand/` | Logotipo original, regras da marca e fontes |
| `assets/media_src/` | Fontes das mídias: fotos licenciadas, gravações do app, recortes da esteira simulada |
| `assets/figures/` | Gerador e saídas das figuras científicas |
| `deliverables/` | Pacotes prontos para entregar (kit do Summit) |

### Ferramentas e documentos

| Pasta | O que é |
|---|---|
| `tools/` | Ferramentas de construção: marca, fontes, mídia, gravações, avaliação de modelos |
| `scripts/` | Lançadores e utilitários: pitch, capturas de tela, medição de desempenho, conjuntos externos |
| `docs/` | Documentação. Comece por [docs/README.md](docs/README.md) |
| `legal/` | Fonte única de licenças e créditos: `registry.json`, textos completos das licenças e relatórios de licença |
| `legacy/` | Protótipos antigos, guardados só para consulta |
| `var/` | Estado de execução (ignorado pelo git): banco de dados, fotos enviadas, quadros das câmeras, cópias de segurança |

---

## Licenças e créditos

Tudo fica em um único lugar: [LICENSES.md](LICENSES.md) no repositório e a página **Créditos e licenças** no site. Os dois são gerados de [legal/registry.json](legal/registry.json) por `python tools/build_legal.py`. Nenhum outro arquivo repete licença ou crédito; um teste automático (`core/tests/test_legal.py`) falha se alguém repetir.

---

## Estado atual, sem enfeite

- É um protótipo. O classificador atual (`belt_v3`) tem 89% de acurácia balanceada em fotos de fruto no pé, contra 33% do acaso e 56% do modelo anterior nos mesmos recortes. Ele ainda não foi medido em esteira real, e por isso toda fruta classificada vai para conferência manual. Contagem, tamanho, carta de controle e aceite de lote não dependem do classificador. Detalhes em [docs/guides/model_v3.md](docs/guides/model_v3.md).
- Os dados de treino são fotos públicas de cajueiros de Gana e de Uganda. Não foi encontrado nenhum vídeo aberto de fruta em esteira com rótulo de qualidade; os vídeos reais de linhas de seleção que foram baixados não têm rótulos e servem só de fundo.
- Os painéis de demonstração usam dados sintéticos, sempre marcados como DEMO ou SIMULAÇÃO.
- O desempenho em esteira real ainda não foi avaliado.
- A operação contínua (serviço de câmera, fila em disco, supervisor, agregados) foi testada com a esteira simulada e com uma câmera falsa que cai e volta. Ainda não foi testada com uma câmera RTSP ou USB de verdade.
