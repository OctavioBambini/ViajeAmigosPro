"""Portable ZIP backups for trips, events, friends, places and photos.

No cloud service and no third-party dependencies. Limits prevent unbounded
archives from exhausting application storage on import.
"""
import json
import re
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

MAX_PHOTOS = 100
MAX_PHOTO_SIZE = 20 * 1024 * 1024
MAX_ARCHIVE_SIZE = 150 * 1024 * 1024
VALID_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def export_trip(store, trip_id):
    trip = store.trip(trip_id)
    if not trip:
        raise ValueError("No hay ningún viaje seleccionado.")
    folder = store.data_dir / "exportaciones"
    folder.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", trip["title"]).strip("_")[:32] or "viaje"
    output = folder / f"{slug}_{datetime.now():%Y%m%d_%H%M%S_%f}.zip"
    data = {"format": "ViajeAmigosPro", "version": 1, "title": trip["title"],
            "members": [{"name": m["name"], "lat": m["lat"], "lon": m["lon"]}
                        for m in store.members(trip_id)],
            "events": [{k: e[k] for k in ("title", "date", "time", "description")}
                       for e in store.events(trip_id)],
            "places": [{k: p[k] for k in ("title", "lat", "lon")}
                       for p in store.places(trip_id)], "photos": []}
    total = 0
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for photo in store.photos(trip_id)[:MAX_PHOTOS]:
            path = Path(photo["path"])
            if path.suffix.lower() not in VALID_IMAGE_EXTENSIONS:
                continue
            size = path.stat().st_size
            if size > MAX_PHOTO_SIZE or total + size > MAX_ARCHIVE_SIZE:
                continue
            total += size
            entry = f"photos/{len(data['photos']) + 1:03d}{path.suffix.lower()}"
            archive.write(path, entry)
            data["photos"].append(entry)
        archive.writestr("manifest.json", json.dumps(data, ensure_ascii=False, indent=2))
    return output


def import_trip(store, zip_path):
    file = Path(zip_path)
    if not file.is_file() or file.suffix.lower() != ".zip":
        raise ValueError("Seleccioná un archivo .zip válido.")
    if file.stat().st_size > MAX_ARCHIVE_SIZE:
        raise ValueError("El archivo supera el tamaño permitido (150 MB).")
    with zipfile.ZipFile(file, "r") as archive:
        contents = archive.infolist()
        if len(contents) > MAX_PHOTOS + 1:
            raise ValueError("El respaldo contiene demasiados archivos.")
        if "manifest.json" not in archive.namelist():
            raise ValueError("El ZIP no es un respaldo de ViajeAmigos Pro.")
        info = archive.getinfo("manifest.json")
        if info.file_size > 256_000:
            raise ValueError("El archivo de datos del respaldo es demasiado grande.")
        payload = json.loads(archive.read("manifest.json").decode("utf-8"))
        if not isinstance(payload, dict) or payload.get("format") != "ViajeAmigosPro" or payload.get("version") != 1:
            raise ValueError("El formato de respaldo no es compatible.")
        title = payload.get("title", "")
        if not isinstance(title, str) or len(title.strip()) < 3 or len(title) > 70:
            raise ValueError("El respaldo tiene un nombre de viaje inválido.")
        members = payload.get("members", [])
        events = payload.get("events", [])
        places = payload.get("places", [])
        photos = payload.get("photos", [])
        if not all(isinstance(x, list) for x in (members, events, places, photos)):
            raise ValueError("El respaldo tiene listas de datos inválidas.")
        if any(len(x) > max_count for x,max_count in ((members,150),(events,500),(places,100),(photos,MAX_PHOTOS))):
            raise ValueError("El respaldo supera la cantidad de registros permitida.")
        # Validate archive sizes / paths before creating the trip.
        declared = set()
        total = 0
        for name in photos:
            if not isinstance(name, str) or not re.fullmatch(r"photos/[0-9]{3}\.(jpg|jpeg|png)", name):
                raise ValueError("El respaldo contiene una ruta de foto inválida.")
            if name in declared:
                raise ValueError("El respaldo tiene una foto duplicada.")
            declared.add(name)
            if name not in archive.namelist():
                raise ValueError("Falta una foto en el respaldo.")
            size = archive.getinfo(name).file_size
            if size > MAX_PHOTO_SIZE:
                raise ValueError("Una fotografía es demasiado grande.")
            total += size
            if total > MAX_ARCHIVE_SIZE:
                raise ValueError("El respaldo ocupa demasiado espacio al extraerse.")
        # Check all text/coordinates/date values before changing the database.
        for m in members:
            if not isinstance(m, dict) or not isinstance(m.get("name"), str) or not 2 <= len(m["name"].strip()) <= 45:
                raise ValueError("Un integrante tiene datos inválidos.")
            if m.get("lat") is not None or m.get("lon") is not None:
                store.validate_coords(m.get("lat"), m.get("lon"))
        from datetime import datetime as dt
        for e in events:
            if not isinstance(e, dict) or not isinstance(e.get("title"), str) or not 3 <= len(e["title"].strip()) <= 100:
                raise ValueError("Una actividad tiene datos inválidos.")
            try:
                if dt.strptime(e["date"], "%Y-%m-%d").strftime("%Y-%m-%d") != e["date"]:
                    raise ValueError()
                if dt.strptime(e["time"], "%H:%M").strftime("%H:%M") != e["time"]:
                    raise ValueError()
            except (KeyError, TypeError, ValueError):
                raise ValueError("Una actividad tiene fecha u hora inválida.")
            if not isinstance(e.get("description", ""), str):
                raise ValueError("La descripción de una actividad es inválida.")
        for p in places:
            if not isinstance(p, dict) or not isinstance(p.get("title"), str) or not 2 <= len(p["title"].strip()) <= 70:
                raise ValueError("Un punto del mapa tiene datos inválidos.")
            store.validate_coords(p.get("lat"), p.get("lon"))

        trip_id = store.create_trip(title)
        for m in members:
            store.add_member(trip_id, m["name"], m.get("lat"), m.get("lon"))
        for e in events:
            store.add_event(trip_id, e["title"], e["date"], e["time"], e.get("description", ""))
        for p in places:
            store.add_place(trip_id, p["title"], p["lat"], p["lon"])
        folder = store.data_dir / "fotos" / trip_id
        folder.mkdir(parents=True, exist_ok=True)
        for i, name in enumerate(photos):
            dest = folder / f"respaldo_{datetime.now():%Y%m%d%H%M%S}_{i:03d}{Path(name).suffix}"
            with archive.open(name, "r") as source, dest.open("wb") as output:
                shutil.copyfileobj(source, output, 64 * 1024)
            store.add_photo(trip_id, dest)
    return trip_id
