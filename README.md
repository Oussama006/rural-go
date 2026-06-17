# Rural-GO MVP

Aplicación mínima (MVP) para el proyecto Rural-Go Viva.

Requisitos:
- Python 3.8+
- Crear un entorno virtual

Instalación y ejecución:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r "requirements.txt"
python3 "app.py"
```

La app escucha en `http://0.0.0.0:5000`.

Accesos demo incluidos:
- Admin: `admin@ruralgo.local` / `Admin1234!`
- TF: `tf@ruralgo.local` / `Tf1234!`
- Família: `familia@ruralgo.local` / `Fam1234!`
- Conductor 1: `driver1@ruralgo.local` / `Driver1234!`
- Conductor 2: `driver2@ruralgo.local` / `Driver2234!`

Funcionalitats incloses en el MVP:
- Autenticació amb rols (`family`, `tf`, `admin`)
- Reserva de trajectes vinculada a usuari
- Assignació bàsica de vehicle
- Panell d'administració i informes KPI
- Assistente AURA amb interpretació de frases naturals
- Panell familiar amb alertes i recomanacions
- Panell de conductor amb trajectes assignats
- Seguiment visual tipus mapa per trajecte
- Càlcul simple de preus amb descomptes (vulnerabilitat, Viva Pass)
- Interfície responsive pensada per ús mòbil

Rutes principals:
- `/dashboard` espai principal de l'usuari
- `/aura` assistent de veu simulat
- `/family` seguiment familiar
- `/driver` panell de conductor
- `/reports` KPIs per a admin i TF
- `/track/<id>` seguiment visual d'un trajecte

Properes millores suggerides:
- Integració amb geolocalització i rutes
- Recomanador (Domus Viva) integrat
- Autenticació i gestió d'usuaris
- API per conductors/voluntaris i seguiment en temps real
