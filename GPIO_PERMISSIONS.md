# GPIO-behörigheter på Raspberry Pi

## Problemet

`RPi.GPIO`-biblioteket kräver root-behörighet för att komma åt GPIO-pinnarna på Raspberry Pi. Detta beror på att GPIO-gränssnitten i Linux normalt endast är tillgängliga för root-användaren av säkerhetsskäl.

## Lösningar

### Alternativ 1: Kör med sudo (snabbast, men mindre säkert)

Det enklaste sättet är att köra skriptet med `sudo`:

```bash
sudo .venv/bin/python hotword.py
```

**Nackdelar:**
- Skriptet körs med full root-behörighet, vilket kan vara en säkerhetsrisk
- Du måste ange lösenord varje gång du startar skriptet
- Inte lämpligt för produktionsmiljöer eller automatisk start

### Alternativ 2: Konfigurera udev-regel (rekommenderas)

En bättre lösning är att konfigurera systemet så att användare i gruppen `gpio` får tillgång till GPIO-pinnarna utan att behöva root-behörighet.

#### Steg-för-steg instruktioner

1. **Lägg till din användare i gpio-gruppen:**

   ```bash
   sudo usermod -a -G gpio $USER
   ```

   Detta ger din användare tillgång till GPIO när udev-reglerna är installerade.

2. **Installera udev-regeln:**

   Detta projekt innehåller filen `99-gpio.rules` som konfigurerar rätt behörigheter. Kopiera den till systemets udev-katalog:

   ```bash
   sudo cp 99-gpio.rules /etc/udev/rules.d/
   ```

3. **Ladda om udev-reglerna:**

   För att aktivera de nya reglerna utan omstart:

   ```bash
   sudo udevadm control --reload-rules
   sudo udevadm trigger
   ```

4. **Aktivera gruppmedlemskapet:**

   För att din användare ska få de nya gruppbehörigheterna måste du antingen:

   **Alternativ A:** Logga ut och logga in igen
   
   **Alternativ B:** Starta om Raspberry Pi:
   ```bash
   sudo reboot
   ```

5. **Verifiera installationen:**

   Kontrollera att du är medlem i gpio-gruppen:

   ```bash
   groups
   ```

   Du bör se `gpio` i listan av grupper.

   Testa att köra skriptet utan sudo:

   ```bash
   source .venv/bin/activate
   python hotword.py
   ```

   Om knappen reagerar och LED:en fungerar är allt korrekt konfigurerat!

## Vad gör udev-regeln?

Filen `99-gpio.rules` innehåller regler som:

1. Ger gruppen `gpio` läs- och skrivbehörighet till `/dev/gpiomem`
2. Sätter rätt behörigheter på GPIO export/unexport-gränssnitten
3. Sätter rätt behörigheter på individuella GPIO-pinnar när de aktiveras

Detta gör att program som använder `RPi.GPIO` kan komma åt GPIO-pinnarna utan root-behörighet, så länge användaren är medlem i `gpio`-gruppen.

## Felsökning

### "Permission denied" när skriptet körs

- Kontrollera att du är medlem i gpio-gruppen: `groups`
- Om gpio inte visas, kontrollera att du lagt till användaren: `sudo usermod -a -G gpio $USER`
- Logga ut och logga in igen, eller starta om

### "RuntimeError: Not running on a RPi"

- Detta är ett annat problem som inte är relaterat till behörigheter
- Kontrollera att du kör på en riktig Raspberry Pi, inte en annan Linux-maskin

### Knappen reagerar inte

- Kontrollera hårdvaruanslutningen: knappen ska vara mellan GPIO 17 och GND
- Testa med sudo först för att bekräfta att hårdvaran fungerar: `sudo .venv/bin/python hotword.py`
- Om det fungerar med sudo men inte utan, kör igenom stegen för udev-regeln igen

## Automatisk start vid uppstart

Om du vill att skriptet ska starta automatiskt när Raspberry Pi startar, se till att:

1. Udev-regeln är installerad (alternativ 2 ovan)
2. Användaren som kör skriptet är medlem i gpio-gruppen
3. Konfigurera en systemd-tjänst

### Exempel på systemd-tjänst

Skapa filen `/etc/systemd/system/hanson-assistant.service`:

```ini
[Unit]
Description=Hanson Voice Assistant
After=network.target sound.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/Hanson
Environment="PATH=/home/pi/Hanson/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="ELEVENLABS_API_KEY=your_api_key_here"
Environment="ELEVENLABS_AGENT_ID=your_agent_id_here"
ExecStart=/home/pi/Hanson/.venv/bin/python /home/pi/Hanson/hotword.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Aktivera och starta tjänsten:

```bash
sudo systemctl daemon-reload
sudo systemctl enable hanson-assistant.service
sudo systemctl start hanson-assistant.service
```

Kontrollera status:

```bash
sudo systemctl status hanson-assistant.service
```

**Observera:** Ersätt `/home/pi/Hanson` med sökvägen till ditt projekt och uppdatera API-nycklarna.
