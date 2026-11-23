#!/usr/bin/env python3
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]

DATA = json.loads(
    (ROOT / "models/models-and-runtime.json").read_text(
        encoding="utf-8"
    )
)

ENGINES = ("omnivoice", "xtts", "chatterbox", "piper", "voice")

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(
            lambda: stream.read(4 * 1024 * 1024), b""
        ):
            h.update(block)
    return h.hexdigest()

def select(raw):
    if raw == "all":
        return list(ENGINES)

    names = [x.strip() for x in raw.split(",")]

    if not names or any(x not in ENGINES for x in names):
        raise ValueError("Nieprawidlowe silniki")

    return list(dict.fromkeys(names))

def base(engine):
    model = DATA["models"][engine]

    if engine in ("omnivoice", "chatterbox"):
        repo = model["repository"].replace("/", "--")
        return (
            ROOT / "assets/hf/hub"
            / ("models--" + repo)
            / "snapshots"
            / model["revision"]
        )

    if engine == "xtts":
        return ROOT / "assets/models/xtts_v2"

    return ROOT / "assets/models/piper"

def records(engine):
    if engine == "voice":
        return [
            (ROOT / "assets/voices/Arek.wav", DATA["voice"])
        ]

    result = []

    for item in DATA["models"][engine]["files"]:
        relative = PurePosixPath(item["name"])

        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Nieprawidlowa sciezka modelu")

        path = base(engine).joinpath(*relative.parts)
        result.append((path, item))

    return result

def verify(engine):
    ok = True

    for path, item in records(engine):
        if not path.is_file():
            print("MISSING", engine, path.relative_to(ROOT))
            ok = False
            continue

        if (
            path.stat().st_size != item["bytes"]
            or sha256(path) != item["sha256"]
        ):
            print("MISMATCH", engine, path.relative_to(ROOT))
            ok = False

    print(engine.upper(), "PASS" if ok else "FAIL")
    return ok


def download(engine):
    if engine == "voice":
        print(
            "VOICE: SKIP. Prywatny Arek.wav nalezy dostarczyc "
            "samodzielnie."
        )
        return

    try:
        from huggingface_hub import (
            snapshot_download,
            hf_hub_download,
        )
    except ImportError as exc:
        raise RuntimeError(
            "Zainstaluj zaleznosci z "
            "tools/requirements-model-assets.txt "
            "w osobnym srodowisku Python."
        ) from exc

    cache = ROOT / "assets/hf/hub"
    cache.mkdir(parents=True, exist_ok=True)

    model = DATA["models"][engine]
    repository = model["repository"]
    revision = model["revision"]

    if engine in ("omnivoice", "chatterbox"):
        snapshot_download(
            repo_id=repository,
            revision=revision,
            cache_dir=str(cache),
            allow_patterns=[
                item["name"]
                for item in model["files"]
            ],
        )

        # Offline loader moze pytac o "main".
        # W tym pakiecie alias wskazuje na przypiety commit.
        repo_dir = (
            cache / (
                "models--" + repository.replace("/", "--")
            )
        )
        reference = repo_dir / "refs/main"
        reference.parent.mkdir(parents=True, exist_ok=True)

        if reference.is_symlink():
            raise RuntimeError(
                "Niedozwolony symlink refs/main"
            )

        # Bez koncowego znaku nowej linii.
        reference.write_text(revision, encoding="utf-8")

    else:
        for target, item in records(engine):
            if target.exists():
                if (
                    target.is_file()
                    and target.stat().st_size == item["bytes"]
                    and sha256(target) == item["sha256"]
                ):
                    print("ALREADY VERIFIED:", target.name)
                    continue

                raise RuntimeError(
                    "Istniejacy plik jest niezgodny: "
                    + str(target)
                )

            filename = item["name"]

            if engine == "piper":
                filename = (
                    "pl/pl_PL/gosia/medium/" + filename
                )

            downloaded = Path(
                hf_hub_download(
                    repo_id=repository,
                    filename=filename,
                    revision=revision,
                    cache_dir=str(cache),
                )
            )

            if (
                downloaded.stat().st_size != item["bytes"]
                or sha256(downloaded) != item["sha256"]
            ):
                raise RuntimeError(
                    "Niezgodna suma pobranego modelu: "
                    + filename
                )

            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(downloaded, target)

    if not verify(engine):
        raise RuntimeError(
            "Nieprawidlowe pliki modelu: " + engine
        )

    if engine == "xtts":
        print(
            "XTTS: modele pobrane. "
            "Akceptacja licencji jest osobnym krokiem. "
            "Nie utworzono tos_agreed.txt."
        )

parser = argparse.ArgumentParser()

parser.add_argument(
    "action",
    choices=("status", "verify", "download"),
)

parser.add_argument(
    "--engines",
    default="all",
)

parser.add_argument(
    "--accept-model-terms",
    action="store_true",
)

args = parser.parse_args()

try:
    selected = select(args.engines)

    if args.action == "status":
        for engine in selected:
            model = DATA["models"].get(engine, {})

            print(
                engine,
                "source=" + model.get(
                    "repository",
                    model.get("source", "local/manual")
                ),
                "files=" + str(len(records(engine))),
            )

    elif args.action == "verify":
        results = [verify(e) for e in selected]
        sys.exit(0 if all(results) else 1)

    else:
        if not args.accept_model_terms:
            raise ValueError(
                "Najpierw zapoznaj sie z licencjami modeli. "
                "Wymagane --accept-model-terms"
            )

        if "voice" in selected:
            print(
                "VOICE: Arek.wav jest prywatny i nie bedzie pobierany."
            )

        for engine in selected:
            download(engine)

except (ValueError, RuntimeError, OSError) as exc:
    sys.exit("STOP: " + str(exc))
