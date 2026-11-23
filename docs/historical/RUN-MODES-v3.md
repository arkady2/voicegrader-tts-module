# TTSCompare - tryby uruchamiania

## Cel

Pakiet wspiera uruchamianie pojedynczych silnikow TTS.

| Profil | Silniki | GPU |
| --- | --- | --- |
| omnivoice | OmniVoice | Tak |
| xtts | XTTS | Tak |
| chatterbox | Chatterbox | Tak |
| piper | Piper | Nie |
| all | Wszystkie cztery | Tak, dla trzech silnikow |

## Proxmox - RTX 5060 8 GB

Zalecany wariant:
- Jeden aktywny silnik GPU jednoczesnie.
- Piper moze dzialac niezaleznie na CPU.
- Nie uruchamiac profilu all bez testow VRAM.
- Przed uruchomieniem kolejnego silnika GPU
  poprzedni powinien byc zatrzymany.

Profile Docker Compose NIE wymuszaja automatycznie
wzajemnego wykluczania silnikow.

Konieczny jest osobny mechanizm kontrolujacy,
aby nie uruchomic przypadkowo dwoch silnikow GPU.

## TASK - H100

Profil all jest przewidziany dla odpowiednio
wyposazonego srodowiska.

Nie potwierdzono jeszcze odtworzenia obrazow.

## Stan

DRAFT_VALIDATED_NOT_BUILT

Przeprowadzono tylko walidacje konfiguracji Compose.
Nie zbudowano nowych obrazow.
Nie uruchomiono kontenerow.

## Pozostale prace

- Dostosowanie Dockerfile do aktywnych implementacji.
- Przygotowanie modeli i zasobow glosowych.
- Test odtwarzania obrazow.
- Integracja REST i n8n.
- Ograniczenie capabilities do aktywnych silnikow.
- Testy uruchomienia na GPU 8 GB.
