import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
LEGAL = ROOT / "legal"
REGISTRY = LEGAL / "registry.json"
USAGE = LEGAL / "usage.json"
SITE = LEGAL / "site.json"
DOCUMENT = ROOT / "LICENSES.md"
NL = chr(10)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, text):
    path.write_bytes(text.encode("utf-8"))


def dump(value):
    return json.dumps(value, ensure_ascii=False, indent=1) + NL


def registry():
    return read(REGISTRY)


def usage():
    return read(USAGE) if USAGE.exists() else {}


def allowed_media(name):
    return bool(re.match(registry()["policy"]["media"], name))


def attribution(title, credit_name, author, license_name, page):
    plain = title.removeprefix("File:").rsplit(".", 1)[0]
    terms = "dedicada ao domínio público (CC0)" if license_name == "CC0" else "em domínio público (Public domain)" if license_name.lower() == "public domain" else license_name
    return f"“{plain}”, por {credit_name} ({author}), {terms}, via Wikimedia Commons: {unquote(page)}"


def modifications(entry, use):
    clip = use.get("clip")
    if clip:
        text = f"Trecho de {clip['duration']:g} s a partir de {str(clip['start']).replace('.', ',')} s, recortado para excluir mãos e rostos, reduzido para {clip['width']} px de largura, sem áudio; convertido para WebM (VP9) e MP4 (H.264); quadro central como pôster em AVIF, WebP e JPEG."
    else:
        text = "Original reduzido para no máximo 2560 px e sem metadados" + ("; recortado" if use.get("cropped") else "") + "; convertido para AVIF, WebP e JPEG em várias larguras."
    if "SA" in entry["license"]:
        text += " Os derivados seguem a mesma licença (CC BY-SA)."
    return text


def media():
    used = usage()
    out = []
    for entry in registry()["media"]:
        use = used.get(entry["id"])
        if not use:
            continue
        out.append({**entry, "modifications": modifications(entry, use), "used_in": use["used_in"], "files": use["files"]})
    return out


def own():
    used = usage()
    return [{**entry, "files": used.get(entry["id"], {}).get("files", [])} for entry in registry()["own"]]


def published():
    return {f for entry in media() + own() for f in entry["files"]}


def dependencies():
    names = [re.split(r"[=<>~!\[; ]", line.strip())[0] for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]
    package = read(ROOT / "frontend" / "package.json")
    return {"python": names, "npm": [*package.get("dependencies", {}), *package.get("devDependencies", {})]}


def missing_software():
    listed = {(s["ecosystem"], s["name"].lower()) for s in registry()["software"]}
    return sorted(f"{eco}:{name}" for eco, names in dependencies().items() for name in names if (eco, name.lower()) not in listed)


def site():
    reg = registry()
    pick = lambda entry, keys: {k: entry[k] for k in keys if entry.get(k) not in (None, "", [])}
    return {
        "own": [{**pick(e, ("id", "title", "license", "source", "note")), "files": len(e["files"])} for e in own()],
        "media": [{**pick(e, ("id", "title", "author", "license", "license_url", "source_url", "date", "retrieved", "attribution", "modifications", "used_in")), "files": len(e["files"])} for e in media()],
        "datasets": [{**pick(e, ("id", "title", "authors", "license", "license_url", "page", "attribution", "use", "modifications")), "derived": [pick(d, ("title", "used_in", "modifications", "note")) for d in e.get("derived", [])]} for e in reg["datasets"]],
        "fonts": [pick(e, ("id", "title", "author", "license", "license_url", "source_url", "modifications", "used_in")) for e in reg["fonts"]],
        "software": [pick(e, ("name", "license", "url", "role", "note")) for e in reg["software"]],
        "rules": reg["policy"]["rules"],
    }


def cell(text):
    return str(text).replace("|", "/").replace(NL, " ")


def markdown():
    reg = registry()
    rows = [
        "# Licenças, créditos e direitos autorais",
        "",
        "Este é o único lugar do projeto com licenças, créditos e avisos de direitos autorais. Nenhuma outra página, documento ou arquivo de código repete essas informações: eles apontam para cá.",
        "",
        "Arquivo gerado por `python tools/build_legal.py` a partir de [`legal/registry.json`](legal/registry.json). Não edite à mão: mude o registro e gere de novo. No site, o mesmo conteúdo está na página **Créditos e licenças** (`/creditos`).",
        "",
        "| Seção | Itens |",
        "|---|---|",
        f"| [1. Material próprio](#1-material-próprio) | {len(reg['own'])} |",
        f"| [2. Fotos e vídeos de terceiros](#2-fotos-e-vídeos-de-terceiros) | {len(media())} |",
        f"| [3. Conjuntos de dados](#3-conjuntos-de-dados) | {len(reg['datasets'])} usados, {len(reg['datasets_not_used'])} avaliados e não usados |",
        f"| [4. Tipografia](#4-tipografia) | {len(reg['fonts'])} |",
        f"| [5. Software de código aberto](#5-software-de-código-aberto) | {len(reg['software'])} |",
        "| [6. Regras](#6-regras) | |",
        "| [7. Como manter](#7-como-manter) | |",
        "",
        "---",
        "",
        "## 1. Material próprio",
        "",
        "| Item | Licença | Origem | Observação | Arquivos publicados |",
        "|---|---|---|---|---|",
    ]
    for e in own():
        rows.append(f"| {cell(e['title'])} (`{e['id']}`) | {cell(e['license'])} | {cell(e['source'])} | {cell(e['note'])} | {len(e['files'])} |")
    rows += ["", "---", "", "## 2. Fotos e vídeos de terceiros", ""]
    for e in media():
        rows += [
            f"### {e['title']} (`{e['id']}`)",
            "",
            f"- Crédito: {e['attribution']}",
            f"- Autor: {e['author']}",
            f"- Licença: [{e['license']}]({e['license_url']})",
            f"- Fonte: {e['source_url']}",
            f"- Arquivo original: {e['file_url']}",
            f"- Data original: {e['date'] or '—'}; obtida em {e['retrieved']}",
            f"- Modificações: {e['modifications']}",
            f"- Onde aparece: {'; '.join(e['used_in'])}",
            f"- Arquivos publicados: {len(e['files'])}",
            "",
        ]
    rows += ["---", "", "## 3. Conjuntos de dados", ""]
    for e in reg["datasets"]:
        rows += [
            f"### {e['title']} (`{e['id']}`)",
            "",
            f"- Atribuição exigida: {e['attribution']}",
            f"- Autores: {e['authors']}" + (f" ({e['institution']})" if e["institution"] else ""),
            f"- Versão: {e['version']}",
            f"- Página: {e['page']}",
            f"- DOI: {('https://doi.org/' + e['doi']) if e['doi'] else '—'}",
            f"- Licença: [{e['license']}]({e['license_url']})",
            f"- Licença como está escrita na fonte: {e['license_as_written']}",
            f"- Uso comercial: {e['commercial_use']}",
            f"- Uso neste projeto: {e['use']}",
            f"- Modificações: {e['modifications']}",
            f"- Citação: {e['citation']}",
        ]
        for d in e.get("derived", []):
            rows.append(f"- Material derivado: **{d['title']}** (`{d['where']}`), usado em: {d['used_in']}. {d['modifications']} {d['note']}")
        rows.append("")
    rows += ["### Conjuntos avaliados e não usados", "", "| Conjunto | Página | Licença como está escrita na fonte | Motivo |", "|---|---|---|---|"]
    for e in reg["datasets_not_used"]:
        rows.append(f"| {cell(e['title'])} | {e['page']} | {cell(e['licence_as_written'])} | {cell(e['reason'])} |")
    rows += ["", "---", "", "## 4. Tipografia", ""]
    for e in reg["fonts"]:
        rows += [
            f"### {e['title']} (`{e['id']}`)",
            "",
            f"- Autor: {e['author']}",
            f"- Licença: [{e['license']}]({e['license_url']}); texto completo em [`{e['text']}`]({e['text']})",
            f"- Fonte: {e['source_url']}",
            f"- Modificações: {e['modifications']}",
            f"- Onde aparece: {e['used_in']}",
            "",
        ]
    rows += ["---", "", "## 5. Software de código aberto", "", "As versões estão em `requirements.txt` e `frontend/package.json`.", "", "| Pacote | Origem | Licença | Papel | Observação |", "|---|---|---|---|---|"]
    for e in reg["software"]:
        rows.append(f"| [{e['name']}]({e['url']}) | {e['ecosystem']} | {e['license']} | {e['role']} | {cell(e.get('note', ''))} |")
    rows += ["", "---", "", "## 6. Regras", ""]
    rows += [f"- {rule}" for rule in reg["policy"]["rules"]]
    rows += [
        f"- Licenças aceitas para mídia: expressão `{reg['policy']['media']}`.",
        f"- Licenças aceitas para conjuntos de dados: {', '.join(reg['policy']['datasets'])}.",
        "",
        "---",
        "",
        "## 7. Como manter",
        "",
        "1. Entrou uma foto, um vídeo, um conjunto de dados, uma fonte ou uma biblioteca nova? Registre em `legal/registry.json`. As fotos da Wikimedia Commons são registradas por `python tools/fetch_media.py`.",
        "2. Rode `python tools/build_media.py` se a mídia mudou; ele atualiza `legal/usage.json` (onde cada item aparece e quais arquivos publicados vêm dele).",
        "3. Rode `python tools/build_legal.py`. Ele reescreve este arquivo e `legal/site.json`, que alimenta a página Créditos.",
        "4. Rode `python manage.py test core.tests.test_legal`. Os testes falham se algum arquivo publicado ficar sem registro, se este arquivo estiver desatualizado ou se uma licença for citada fora daqui.",
        "",
    ]
    return NL.join(rows)


def pack(placed):
    entries = {e["id"]: e for e in media()}
    rows = ["# Licenças e créditos do kit", "", "Tudo neste kit é material próprio da FruitCam, exceto as fotos de terceiros abaixo, todas da Wikimedia Commons com licença que permite este uso. Ao publicar uma foto de terceiros, ou uma captura em que ela apareça, inclua o crédito indicado. Fotos CC BY-SA: adaptações delas devem ser distribuídas sob a mesma licença.", "", "## Fotos de terceiros", ""]
    for asset, where in sorted(placed.items()):
        e = entries[asset]
        rows += [f"### {e['title']}", "", f"- Crédito: {e['attribution']}", f"- Autor: {e['author']}", f"- Licença: [{e['license']}]({e['license_url']})", f"- Fonte: {e['source_url']}", f"- Data original: {e['date'] or '—'}; obtida em {e['retrieved']}", f"- Modificações no app: {e['modifications']}", f"- Neste kit: {'; '.join(where)}", ""]
    rows += ["## Material próprio", ""]
    rows += [f"- **{e['title']}**: {e['license']}. {e['note']}" for e in own() if e["files"]]
    rows += ["", "Fonte deste arquivo: `legal/registry.json` (gerado por `tools/build_legal.py`).", ""]
    return NL.join(rows)


def outputs():
    return {DOCUMENT: markdown(), SITE: dump(site())}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    stale = [path for path, text in outputs().items() if not path.exists() or path.read_bytes() != text.encode("utf-8")]
    missing = missing_software()
    if args.check:
        for path in stale:
            print(f"desatualizado: {path.relative_to(ROOT).as_posix()}")
        for name in missing:
            print(f"sem registro em legal/registry.json: {name}")
        sys.exit(1 if stale or missing else 0)
    for path, text in outputs().items():
        write(path, text)
    reg = registry()
    print(f"LICENSES.md e legal/site.json escritos: {len(reg['own'])} próprios, {len(media())} mídias, {len(reg['datasets'])} conjuntos, {len(reg['fonts'])} fontes, {len(reg['software'])} bibliotecas")
    for name in missing:
        print(f"atenção: sem registro em legal/registry.json: {name}")


if __name__ == "__main__":
    main()
