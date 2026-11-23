# Zasoby wymagane przed uruchomieniem

Ten pakiet jest kandydatem instalacyjnym.
Nie zawiera wag modeli ani pliku glosu Arek.

Wymagany uklad:

- assets/hf/
  Pelny cache Hugging Face, razem z katalogami
  hub/models--*, snapshots, blobs i refs.
  Nie wystarczy skopiowanie samych linkow snapshots.

- assets/models/xtts_v2/
  Lokalny model XTTS v2 z ksmvm1.

- assets/models/piper/
  pl_PL-gosia-medium.onnx
  pl_PL-gosia-medium.onnx.json

- assets/voices/Arek.wav
  Próbka glosu, wykorzystywana przez trzy silniki.

Szczegolowe sumy SHA256:
models/models-and-runtime.json

Chatterbox musi uzywac rewizji:
05e904af2b5c7f8e482687a9d7336c5c824467d9

Rewizja OmniVoice zaladowana podczas pracy
nie zostala jeszcze ostatecznie potwierdzona.

UWAGA:
- nie uruchamiac tego Compose na aktywnym ksmvm1;
- porty pokrywaja sie z dzialajacymi silnikami;
- Dockerfile pochodza ze starszych receptur;
- ich poprawne budowanie nie zostalo przetestowane;
- konfiguracja nie obejmuje jeszcze REST i n8n;
- zgodnosc z GPU 8 GB nie zostala potwierdzona.
