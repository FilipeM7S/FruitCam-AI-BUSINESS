# Data requests: drafts ready to send

Seven drafts, in the order they matter. Fill in the bracketed fields (name, role, e-mail, phone) before sending. Contact details below were checked on the sources linked on 2026-10-04; where no address is public, the draft says which channel to use instead. Nothing here has been sent.

| # | To | Why | Channel (verified) | Language |
|---|---|---|---|---|
| 1 | Makerere University (cashew dataset authors) | Our current training data. Class numbering differs in 1,466 of its 3,098 label files; ask for the correct order | joyce.nabende@mak.ac.ug (corresponding author, [Data in Brief 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC10788206/)) | English |
| 2 | FruitRoll-360 authors (Guoqi Shan, Wenzhuo Zhang, Fan Wang, Hao Tian, Hu Jie) | Real factory-line citrus videos with exactly our three classes; research-only licence | [IEEE DataPort page](https://ieee-dataport.org/documents/fruitroll-360) says to use the e-mail in the original publication (not public yet); send through DataPort or once the paper is out | English |
| 3 | Radwa Hussein, German International University (Oranges Classification) | Top-down belt frames of oranges; no licence stated | [IEEE DataPort page](https://ieee-dataport.org/documents/oranges-classification) (no e-mail on the page) | English |
| 4 | UFES, Sisfrutos Papaya authors | Packing-house papaya images; non-commercial licence | [GitHub repository](https://github.com/jhony2507/Sisfrutos-Papaya) (links on request) or the corresponding author of *Yolo-Papaya* (Electronics, 2023) | Portuguese |
| 5 | Embrapa Agroindústria Tropical (Fortaleza) | Brazil's cashew research centre; possible images, expertise and access to processors | sac@embrapa.br, +55 (85) 3391-7100 ([contact page](https://www.embrapa.br/en/agroindustria-tropical/contato)) | Portuguese |
| 6 | Cashew processors running optical sorters | Real belt footage and reject streams (our poor/rotten classes) | Template, no company named; send to the processors you already know | Portuguese |
| 7 | University of Pardubice (Potatoes Dataset authors) | Courtesy note: duplicates across their official splits; ask about full frames | Zenodo record [17494608](https://zenodo.org/records/17494608) (creators: Štursa, Doležel, Ksiažek); no e-mail on the record | English |

Attachments referred to below:
- `docs/datasets/cashew_label_audit/files.csv` and `summary.json` (produced by `python tools/audit_cashew_labels.py`)
- `docs/datasets/potatoes/potato_eval.json` (produced by `python tools/eval_potatoes.py`)

---

## 1. Makerere University: class numbering in the cashew labels

**To:** joyce.nabende@mak.ac.ug
**Subject:** Coffee and Cashew Nut Dataset: class-ID order differs in 1,466 cashew label files

Dear Dr. Nakatumba-Nabende,

Thank you for publishing the Coffee and Cashew Nut Dataset (doi:10.17632/r46c6bpfpf.1). We are a small startup in Ceará, Brazil, building a camera system that grades cashew apples on sorting belts, and we use the cashew part under its CC BY 4.0 licence, with attribution.

While auditing the labels we found that the class-ID order seems to differ between two groups of files:

- In 1,632 files, class 0 boxes are whole trees (median longer side 99.8% of the image), as described in the paper (0 tree, 1 flower, 2 premature, 3 unripe, 4 ripe, 5 spoilt).
- In the other 1,466 files, class 5 is used for the whole-tree boxes (median longer side 99.9% of the image, 1,804 boxes), and class 0 for much smaller objects (median 13.5% of the image) that look like flower panicles.

So the "Spoilt: 25,820" count in Table 2 seems to include about 1,804 tree boxes, and some of the other classes in those files are probably shifted too. We guess those files were exported from Makesense with a different label order, but we could not recover that order with confidence from the images alone.

Could you tell us the class order used in those 1,466 files, or whether a corrected version exists? We attach the list of files (`files.csv`, one row per label file with its group and box counts per ID) and a short summary. We are happy to share the audit script.

Thank you for your time and for making the data open.

Kind regards,
[Your name]
[Role], FruitCam_ai, Fortaleza, Brazil
[e-mail] · [phone]

---

## 2. FruitRoll-360: permission for commercial use

**To:** Guoqi Shan and co-authors, via IEEE DataPort ([FruitRoll-360](https://ieee-dataport.org/documents/fruitroll-360)), or the e-mail in the published paper
**Subject:** FruitRoll-360: request for permission for commercial use

Dear Dr. Shan and co-authors,

We read the description of FruitRoll-360 with great interest. We are an early-stage startup in Brazil developing camera-based grading of fruit on sorting belts (starting with cashew apples). Your sound / substandard / rotten scheme is exactly the three-class standard we use, and real factory-line footage is what the field is missing.

We understand the dataset is released for academic and research use, and that commercial use needs your written permission. We would like to ask whether you would grant it, and on what terms, for:

1. using FruitRoll-360 as an evaluation benchmark for our belt-grading models; and
2. if possible, using it to pre-train those models before fine-tuning on our own cashew data.

We would not redistribute the data or any part of it, would cite your paper in any publication or public material, and would be glad to share our results on it with you. If a licence fee or a collaboration agreement is the right form, we are open to discussing it.

Kind regards,
[Your name]
[Role], FruitCam_ai, Fortaleza, Brazil
[e-mail] · [phone]

---

## 3. Oranges Classification: licence terms

**To:** Radwa Hussein (German International University), via IEEE DataPort ([Oranges Classification](https://ieee-dataport.org/documents/oranges-classification))
**Subject:** Oranges Classification dataset (doi:10.21227/fm4f-1n74): licence and commercial use

Dear Ms. Hussein,

Thank you for publishing the Oranges Classification dataset, frames from a camera above a packing-house conveyor. We are a small startup in Brazil building camera-based fruit grading for sorting belts, and top-down belt imagery like yours is rare.

The dataset page does not state a licence. Could you tell us under which terms the data may be used, and whether commercial use (training and evaluating a product model, without redistributing the images) would be allowed? We would also like to know what the included .txt files contain (bounding boxes or per-frame labels?).

We would cite the dataset in any material that uses it.

Kind regards,
[Your name]
[Role], FruitCam_ai, Fortaleza, Brazil
[e-mail] · [phone]

---

## 4. UFES, Sisfrutos Papaya: licença para uso comercial

**Para:** autores do Sisfrutos Papaya (repositório no [GitHub](https://github.com/jhony2507/Sisfrutos-Papaya)) ou autor correspondente do artigo *Yolo-Papaya* (Electronics, 2023)
**Assunto:** Sisfrutos Papaya: pedido de licença para uso comercial ou parceria

Prezados autores,

Somos uma startup em fase inicial em Fortaleza (CE) que desenvolve classificação de frutas por câmera em esteiras de seleção, começando pelo caju. Conhecemos o Sisfrutos Papaya e o trabalho Yolo-Papaya, e o conjunto de imagens captadas em packing house é muito relevante para nós.

Sabemos que a licença atual proíbe uso comercial. Gostaríamos de perguntar se seria possível uma licença específica para uso comercial (treinar e avaliar nossos modelos, sem redistribuir as imagens) ou uma parceria de pesquisa com a UFES, nos termos que vocês considerarem adequados. Também temos interesse em saber se as imagens foram feitas em esteira e com qual câmera e iluminação.

Ficamos à disposição para uma conversa.

Atenciosamente,
[Seu nome]
[Cargo], FruitCam_ai, Fortaleza (CE)
[e-mail] · [telefone]

---

## 5. Embrapa Agroindústria Tropical: imagens de caju e cooperação

**Para:** sac@embrapa.br (Embrapa Agroindústria Tropical, Fortaleza)
**Assunto:** Startup de visão computacional para classificação de caju em esteira: pedido de orientação e possível cooperação

Prezados,

Somos uma startup em fase inicial em Fortaleza que desenvolve um sistema de câmera para classificar pedúnculos de caju em esteiras de seleção (boa, baixa qualidade e podre) e gerar a estatística da linha (frutas por minuto, porcentagem de podres, aceite de lotes). Hoje treinamos com fotos de campo de um conjunto público de Uganda, e nossos testes mostram que isso não basta para a esteira: precisamos de imagens de caju em condições de beneficiamento, classificadas por especialistas.

Gostaríamos de saber:

1. se a Embrapa Agroindústria Tropical tem imagens de pedúnculos de caju classificados por qualidade que possam ser compartilhadas, e em que termos;
2. se há pesquisadores trabalhando com qualidade pós-colheita do caju ou visão computacional com quem poderíamos conversar;
3. se existe interesse em uma cooperação técnica (por exemplo, coleta conjunta de imagens em uma unidade de beneficiamento, com protocolo e ferramentas nossos).

Já temos o protocolo e o software de coleta prontos: cada bandeja de frutas separadas à mão passa pela esteira e todas as imagens recebem o rótulo da bandeja. Podemos apresentar o trabalho quando for conveniente.

Atenciosamente,
[Seu nome]
[Cargo], FruitCam_ai, Fortaleza (CE)
[e-mail] · [telefone]

---

## 6. Beneficiadoras de caju com seleção óptica (modelo)

**Para:** [nome da empresa], [contato]
**Assunto:** Pedido de visita para filmar a esteira de seleção de caju (sem custo, dados confidenciais)

Prezado(a) [nome],

Somos uma startup em Fortaleza que desenvolve classificação de caju por câmera em esteiras (boa, baixa qualidade e podre) e estatística da linha em tempo real. Para treinar e validar o sistema precisamos de imagens reais de esteira, que não existem em bases públicas.

Gostaríamos de pedir permissão para uma visita curta à sua unidade para:

1. filmar a esteira de seleção por algumas horas com uma câmera nossa, sem interferir na operação; e
2. se possível, filmar separadamente bandejas de frutas já separadas pela equipe de vocês (boas, de baixa qualidade e podres), incluindo o fluxo de rejeito da seleção óptica, se houver.

Em troca, oferecemos: confidencialidade (as imagens não serão publicadas nem mostram pessoas), cópia de todas as imagens para a empresa, e um relatório com a estatística da linha medida pelo nosso sistema durante a visita. Não há custo para a empresa.

Podemos conversar por telefone ou presencialmente quando for melhor para vocês.

Atenciosamente,
[Seu nome]
[Cargo], FruitCam_ai, Fortaleza (CE)
[e-mail] · [telefone]

---

## 7. University of Pardubice: duplicates across the Potatoes Dataset splits (optional)

**To:** Dominik Štursa, Petr Doležel, Jakub Ksiažek (University of Pardubice), via the contact listed in their publication or the university directory
**Subject:** Potatoes Dataset (Zenodo 17494608): duplicates across splits, and a question about full frames

Dear Dr. Štursa, Dr. Doležel and Mr. Ksiažek,

Thank you for publishing the Potatoes Dataset under CC BY 4.0. It is one of very few open datasets from a real sorting line, and we used it to test our belt pipeline.

While preparing our own leak-free split, we noticed that the official splits share many images: of the 4,145 files, 1,294 are unique pixel-for-pixel and 757 are unique when rotations and flips are counted as copies. 224 of the 288 distinct objects in the three test sets also appear in train or validation. Results on the official test sets may therefore be optimistic. We are happy to share our audit script and the list of duplicate groups.

We would also like to ask whether full frames or video from the same line exist, and whether they could be shared under the same licence. Single-object crops let us test classification, but not segmentation, tracking or counting.

Kind regards,
[Your name]
[Role], FruitCam_ai, Fortaleza, Brazil
[e-mail] · [phone]
