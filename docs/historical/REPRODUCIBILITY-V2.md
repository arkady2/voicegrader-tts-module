# SoftwareX — poprawki kandydata v2

## Zweryfikowane przed przygotowaniem v2

- Wszystkie cztery modele pobrano niezaleznie i zweryfikowano SHA-256.
- Wszystkie cztery silniki przeszly test syntezy w izolowanych
  kontenerach na ksmvm1: Piper, XTTS, Chatterbox, OmniVoice.
- Testy wykorzystywaly istniejace obrazy Docker, nie obrazy
  zbudowane od zera z tego pakietu.

## Modele

- Piper: rhasspy/piper-voices, revision e9ab671f2a0e50a701b34361136ba3e6a3a9eb0c.
- XTTS: coqui/XTTS-v2, revision 6c2b0d75eae4b7047358e3b6bd9325f857d43f77.
- Chatterbox: ResembleAI/chatterbox, revision 05e904af2b5c7f8e482687a9d7336c5c824467d9.
- OmniVoice: k2-fsa/OmniVoice, revision c5fdb5ccb189668d56333f77ba2629f4cd7535f4.

Instalator korzysta z huggingface_hub==0.36.0 w osobnym venv.
Po pobraniu wymagane jest `verify --engines all`.

## HF cache

Modele Chatterbox i OmniVoice przechowywane sa jako snapshoty
Hugging Face z przypietymi commitami. Alias refs/main jest ustawiany
na sprawdzony commit, aby loader offline mogl odnalezc snapshot.

## Licencje i pliki prywatne

- Arek.wav NIE jest dolaczony do pakietu i nie jest pobierany.
- Akceptacja licencji XTTS pozostaje decyzja operatora.
- Instalator NIE tworzy tos_agreed.txt.
- COQUI_TOS_AGREED jest domyslnie 0; operator moze ustawic 1
  dopiero po zapoznaniu sie z warunkami i ich zaakceptowaniu.
- Ograniczenia licencji poszczegolnych modeli trzeba zweryfikowac
  przed publikacja lub zastosowaniem komercyjnym.

## Porty izolowane

OmniVoice 19805, XTTS 19864, Chatterbox 19867, Piper 19869.
Istniejace serwery laboratoryjne nie sa modyfikowane.

## Zakres potwierdzenia

- Sprawdzenie struktury i sum pakietu: weryfikowane lokalnie.
- Pobranie przy uzyciu nowego instalatora: NIEPRZETESTOWANE.
- Budowanie nowych obrazow: NIEPRZETESTOWANE.
- Synteza z nowo zbudowanych obrazow: NIEPRZETESTOWANA.
- REST API i n8n: skopiowane bez zmian; integracja w nowej
  dystrybucji wymaga osobnej walidacji.

Do czasu zakonczonego testu odtworzenia jest to KANDYDAT v2,
a nie finalne wydanie reprodukowalne.
