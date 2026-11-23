# TTSCompare / SoftwareX — Source Candidate

Status: SOURCE_CANDIDATE_NOT_BUILT

## Zawartosc

- engines/ — aktywny kod czterech silnikow TTS
- orchestration/rest/ — REST API v0.7 REAL_ONLY
- orchestration/n8n/ — workflow n8n
- models/ — specyfikacja modeli i srodowiska
- tools/model_assets.py — obsluga modeli
- compose.engines.proxmox.yaml — profile dla Proxmox
- compose.engines.profiles.yaml — profile TASK/H100

## Sprawdzenie specyfikacji modeli

python3 tools/model_assets.py status

## Pobieranie wybranych modeli

Po zapoznaniu sie z warunkami licencji:

python3 -m venv .venv
.venv/bin/python -m pip install huggingface_hub==0.36.2

.venv/bin/python tools/model_assets.py download --engines omnivoice,chatterbox,piper --accept-model-terms

## Weryfikacja plikow

python3 tools/model_assets.py verify --engines omnivoice,chatterbox,piper

## XTTS v2

Model XTTS v2 musi zostac dostarczony osobno.
Dokladna rewizja upstream nie zostala potwierdzona.

Weryfikacja po dostarczeniu:

python3 tools/model_assets.py verify --engines xtts

## Arek.wav

Nagranie nie jest dystrybuowane w tym pakiecie.
Uprawniony uzytkownik dostarcza je osobno.

python3 tools/model_assets.py verify --engines voice

## Ograniczenia

- Dockerfile to kandydaci, jeszcze nieprzetestowani.
- Instalacja od zera nie zostala sprawdzona.
- REST i n8n nie zostaly jeszcze odtworzone razem.
- n8n moze wymagac zmiany adresow uslug.
- Nie potwierdzono dzialania na GPU 8 GB.
- Rewizja OmniVoice pochodzi z cache lokalnego.
- Piper pobierany jest z main, ale wymaga zgodnosci SHA-256.
- Modele, obrazy Docker i Arek.wav nie sa dolaczone.
- Przed publikacja wymagany jest przeglad licencji i sekretow.

Nie traktowac jako gotowego wydania produkcyjnego.


## Kandydat v2

Przed uzyciem przeczytaj [REPRODUCIBILITY-V2.md](REPRODUCIBILITY-V2.md). Nowe porty i zasady akceptacji licencji maja pierwszenstwo przed instrukcjami starszej wersji.
