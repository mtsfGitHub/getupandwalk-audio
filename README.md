# Get up and Walk · in ascolto

Ogni notte questo programma prende il post del giorno da [Get up and Walk](https://getupandwalk.gesuiti.it/),
lo trasforma in una preghiera audio e la pubblica:

- **Pagina di ascolto:** https://mtsfgithub.github.io/getupandwalk-audio/
- **Feed podcast:** https://mtsfgithub.github.io/getupandwalk-audio/feed.xml
- **Gli MP3:** nella sezione *Releases* di questo repository, uno per giorno.

## Come funziona

1. Legge il post del giorno e ne ricava citazione, Vangelo, commento e domande.
2. Prende il giorno liturgico dalla pagina della CEI (se non risponde, lo calcola).
3. Monta tutto secondo **`modello.yaml`**: chi parla, cosa dice, le pause, la musica.
4. Fa leggere i testi alle voci italiane di Microsoft Edge (Diego per la struttura, Elsa per i contenuti).
   Se il servizio non risponde usa Nicola (Kokoro) e GitHub ti manda una mail.
5. Aggiunge la musica: un liuto sintetico. Per usare un brano vero, caricalo come `musica/brano.mp3`.

## Cambiare la preghiera

Apri `modello.yaml`, clicca la matita, modifica e salva («Commit changes»).
Dentro il file ci sono le istruzioni.

## Rifare l'audio di un giorno

Scheda **Actions** › **Audio del giorno** › **Run workflow** › scrivi la data (AAAA-MM-GG) oppure lascia vuoto per oggi.
