"""ViajeAmigos Pro | Edición local para Android y Windows.

Todo el contenido se guarda en SQLite del dispositivo. No usa Firebase,
cuentas ni sincronización. Los puntos de amigos son manuales, nunca GPS vivo.
"""
from __future__ import annotations

import shutil
import time
from datetime import datetime
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.camera import Camera
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.utils import platform

from backup import export_trip, import_trip
from storage import LocalStore

try:
    from kivy_garden.mapview import MapMarker, MapMarkerPopup, MapView
except ImportError:
    MapMarker = MapMarkerPopup = MapView = None
try:
    from plyer import gps
except ImportError:
    gps = None

BG = (.055, .081, .13, 1)
PANEL = (.085, .12, .185, 1)
PANEL2 = (.11, .165, .23, 1)
WHITE = (.96, .97, .99, 1)
MUTED = (.66, .74, .83, 1)
CYAN = (.18, .83, .77, 1)
RED = (.95, .41, .45, 1)


def label(text, size=14, color=WHITE, height=None, bold=False, align='left'):
    out = Label(text=str(text), font_size=dp(size), color=color, bold=bold,
                halign=align, valign='middle')
    out.bind(size=lambda obj, _: setattr(obj, 'text_size', (obj.width, obj.height)))
    if height is not None:
        out.size_hint_y = None
        out.height = dp(height)
    return out


def button(text, handler, secondary=False, danger=False, height=44):
    color = RED if danger else (PANEL2 if secondary else CYAN)
    out = Button(text=text, size_hint_y=None, height=dp(height), bold=True,
                 font_size=dp(13), color=WHITE if secondary or danger else BG,
                 background_normal='', background_down='', background_color=color)
    out.bind(on_release=lambda *_: handler())
    return out


def field(hint, initial='', multiline=False):
    return TextInput(text=str(initial), hint_text=hint, multiline=multiline,
                     size_hint_y=None, height=dp(77 if multiline else 44),
                     background_normal='', background_active='',
                     background_color=PANEL2, foreground_color=WHITE,
                     hint_text_color=MUTED, cursor_color=CYAN, font_size=dp(14),
                     padding=[dp(10), dp(9)])


class Panel(BoxLayout):
    def __init__(self, shade=PANEL, **kwargs):
        kwargs.setdefault('orientation', 'vertical')
        kwargs.setdefault('padding', dp(15))
        kwargs.setdefault('spacing', dp(9))
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(*shade)
            self.bg_shape = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(16)])
        self.bind(pos=self.recolor, size=self.recolor)

    def recolor(self, *_):
        self.bg_shape.pos = self.pos
        self.bg_shape.size = self.size


class ViajeAmigosApp(App):
    title = 'ViajeAmigos Pro - Local'

    def build(self):
        Window.clearcolor = BG
        if platform != 'android':
            Window.size = (430, 780)
        self.store = LocalStore(self.user_data_dir)
        self.page = 'Inicio'
        self.trip = self.store.active_trip()
        self.map_view = None
        self.map_markers = []
        self.gps_active = False
        self.own_coords = None
        self.camera_widget = None
        self.camera_panel = None
        self.photo_stack = None

        root = BoxLayout(orientation='vertical')
        top = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(85),
                        padding=[dp(19), dp(8)])
        top.add_widget(label('VIAJEAMIGOS  /  PRO', 19, CYAN, 37, bold=True))
        self.subtitle = label('', 11, MUTED, 25)
        top.add_widget(self.subtitle)
        root.add_widget(top)
        self.page_area = BoxLayout(orientation='vertical')
        root.add_widget(self.page_area)
        nav = BoxLayout(size_hint_y=None, height=dp(65), padding=[dp(5), dp(5)], spacing=dp(4))
        self.nav_items = {}
        for name in ('Inicio', 'Mapa', 'Fotos', 'Agenda', 'Grupo'):
            item = Button(text=name, font_size=dp(12), color=MUTED, background_normal='',
                          background_down='', background_color=PANEL)
            item.bind(on_release=lambda _, to=name: self.show(to))
            nav.add_widget(item)
            self.nav_items[name] = item
        root.add_widget(nav)
        self.show('Inicio')
        return root

    def on_pause(self):
        # Allow the Android camera application to temporarily come to the foreground.
        return True

    def on_resume(self):
        pass

    def on_stop(self):
        self.stop_camera()
        self.stop_gps()

    def show(self, page):
        if self.page == 'Fotos' and page != 'Fotos':
            self.stop_camera()
        self.trip = self.store.active_trip()
        self.page = page
        self.page_area.clear_widgets()
        self.map_view = None
        self.map_markers.clear()
        self.subtitle.text = (self.trip['title'] + '  |  ') if self.trip else ''
        self.subtitle.text += 'Edición local · Sin cuentas'
        for name, item in self.nav_items.items():
            item.background_color = PANEL2 if name == page else PANEL
            item.color = CYAN if name == page else MUTED
        {'Inicio': self.home, 'Mapa': self.map_page, 'Fotos': self.photos_page,
         'Agenda': self.agenda_page, 'Grupo': self.group_page}[page]()

    def scroll(self):
        holder = ScrollView(do_scroll_x=False, bar_width=dp(4))
        stack = BoxLayout(orientation='vertical', padding=[dp(16), dp(14), dp(16), dp(28)],
                          spacing=dp(14), size_hint_y=None)
        stack.bind(minimum_height=stack.setter('height'))
        holder.add_widget(stack)
        self.page_area.add_widget(holder)
        return stack

    @staticmethod
    def heading(parent, title, subtitle=''):
        parent.add_widget(label(title, 22, WHITE, 40, bold=True))
        if subtitle:
            parent.add_widget(label(subtitle, 12, MUTED, 49))

    def alert(self, title, message):
        content = BoxLayout(orientation='vertical', padding=dp(14), spacing=dp(12))
        content.add_widget(label(message, 13))
        popup = Popup(title=title, content=content, size_hint=(.91, None), height=dp(260))
        content.add_widget(button('Aceptar', popup.dismiss))
        popup.open()

    def error(self, exception):
        self.alert('No se pudo completar', str(exception))

    def require_trip(self):
        if self.trip is not None:
            return True
        self.alert('Primero creá un viaje', 'Entrá en Grupo y creá tu primer viaje para organizar fotos, actividades y lugares.')
        return False

    def confirm(self, title, msg, callback):
        box = BoxLayout(orientation='vertical', padding=dp(14), spacing=dp(12))
        box.add_widget(label(msg, 13))
        popup = Popup(title=title, content=box, size_hint=(.92, None), height=dp(270))
        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        row.add_widget(button('Cancelar', popup.dismiss, secondary=True))
        def accept():
            popup.dismiss()
            try:
                callback()
            except Exception as exc:
                self.error(exc)
        row.add_widget(button('Eliminar', accept, danger=True))
        box.add_widget(row)
        popup.open()

    def home(self):
        col = self.scroll()
        self.heading(col, 'Tu próxima aventura', 'Todos los datos se guardan en este dispositivo.')
        pane = Panel(size_hint_y=None, height=dp(195))
        pane.add_widget(label('VIAJE ACTUAL', 11, CYAN, 22, bold=True))
        pane.add_widget(label(self.trip['title'] if self.trip else 'Todavía no hay un viaje', 20, WHITE, 48, bold=True))
        pane.add_widget(label('Organización 100% local, sin Firebase.' if self.trip else 'Creá un viaje para comenzar.',
                              12, MUTED, 28))
        pane.add_widget(button('Administrar viajes y amigos', lambda: self.show('Grupo'), height=39))
        col.add_widget(pane)
        cards = [
            ('01 / MAPA', 'Mapa y ubicaciones', 'Explorá el mapa y marcá destinos o posiciones manuales de tus amigos.', 'Mapa'),
            ('02 / RECUERDOS', 'Fotos del viaje', 'Sacá fotos desde la cámara y guardalas en el dispositivo.', 'Fotos'),
            ('03 / PLANIFICACIÓN', 'Agenda de actividades', 'Organizá actividades con fechas y horarios; no necesitás internet.', 'Agenda'),
        ]
        for tag, title, text, dest in cards:
            card = Panel(size_hint_y=None, height=dp(189))
            card.add_widget(label(tag, 11, CYAN, 20, bold=True))
            card.add_widget(label(title, 18, WHITE, 32, bold=True))
            card.add_widget(label(text, 12, MUTED, 50))
            card.add_widget(button('Abrir ' + dest.lower(), lambda d=dest: self.show(d), secondary=True, height=36))
            col.add_widget(card)

    def group_page(self):
        col = self.scroll()
        self.heading(col, 'Viajes y amigos', 'Todo queda guardado localmente en este teléfono o PC.')
        creation = Panel(size_hint_y=None, height=dp(164))
        creation.add_widget(label('Crear un nuevo viaje', 17, WHITE, 30, bold=True))
        trip_input = field('Ej. Viaje a las sierras')
        creation.add_widget(trip_input)
        def create():
            try:
                self.store.create_trip(trip_input.text)
                self.show('Grupo')
            except ValueError as exc:
                self.error(exc)
        creation.add_widget(button('+ Crear viaje', create))
        col.add_widget(creation)
        trips = self.store.trips()
        if trips:
            col.add_widget(label('MIS VIAJES', 12, CYAN, 27, bold=True))
        for item in trips:
            line = Panel(size_hint_y=None, height=dp(124), shade=PANEL2 if self.trip and self.trip['id'] == item['id'] else PANEL)
            line.add_widget(label(item['title'] + ('  · ACTUAL' if self.trip and self.trip['id'] == item['id'] else ''),
                                  16, WHITE, 39, bold=True))
            row = BoxLayout(size_hint_y=None, height=dp(39), spacing=dp(7))
            row.add_widget(button('Seleccionar', lambda ident=item['id']: self.select_trip(ident), secondary=True, height=39))
            row.add_widget(button('Eliminar', lambda ident=item['id']: self.confirm(
                'Eliminar viaje', 'Se borrarán todos los integrantes, actividades y lugares de este viaje. ¿Continuar?',
                lambda: (self.store.delete_trip(ident), self.show('Grupo'))), danger=True, height=39))
            line.add_widget(row)
            col.add_widget(line)
        if not self.trip:
            return
        col.add_widget(label('INTEGRANTES DEL VIAJE', 12, CYAN, 28, bold=True))
        col.add_widget(button('+ Agregar un amigo', self.add_member_dialog))
        members = self.store.members(self.trip['id'])
        if not members:
            col.add_widget(label('Todavía no agregaste integrantes.', 13, MUTED, 50))
        for member in members:
            pane = Panel(size_hint_y=None, height=dp(130))
            pane.add_widget(label(member['name'], 16, WHITE, 29, bold=True))
            coord = 'Ubicación ingresada manualmente' if member['lat'] is not None else 'Sin ubicación cargada'
            pane.add_widget(label(coord, 11, MUTED, 24))
            row = BoxLayout(size_hint_y=None, height=dp(37), spacing=dp(7))
            row.add_widget(button('Ubicación', lambda m=member: self.member_location_dialog(m), secondary=True, height=37))
            row.add_widget(button('Quitar', lambda m=member: self.confirm('Quitar integrante',
                f'¿Eliminar a {m["name"]} del viaje?', lambda: (self.store.delete_member(self.trip['id'], m['id']), self.show('Grupo'))), danger=True, height=37))
            pane.add_widget(row)
            col.add_widget(pane)
        backup_pane = Panel(size_hint_y=None, height=dp(158))
        backup_pane.add_widget(label('Copia de seguridad', 17, WHITE, 30, bold=True))
        backup_pane.add_widget(label('Exportá un ZIP con actividades, fotos y lugares. En Android queda en el espacio privado de la app.',
                                     11, MUTED, 48))
        backup_pane.add_widget(button('Exportar copia ZIP', self.export_backup, secondary=True, height=37))
        col.add_widget(backup_pane)
        if platform != 'android':
            col.add_widget(button('Importar viaje desde ZIP', self.import_backup, secondary=True))

    def select_trip(self, trip_id):
        try:
            self.store.select_trip(trip_id)
            self.show('Inicio')
        except ValueError as exc:
            self.error(exc)

    def add_member_dialog(self):
        if not self.require_trip():
            return
        body = BoxLayout(orientation='vertical', spacing=dp(11), padding=dp(14))
        name = field('Nombre del amigo')
        body.add_widget(label('Nombre del integrante', 14, WHITE, 40))
        body.add_widget(name)
        popup = Popup(title='Agregar integrante', content=body, size_hint=(.91, None), height=dp(240))
        def save():
            try:
                self.store.add_member(self.trip['id'], name.text)
                popup.dismiss()
                self.show('Grupo')
            except ValueError as exc:
                self.error(exc)
        body.add_widget(button('Guardar integrante', save))
        popup.open()

    def member_location_dialog(self, member):
        body = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(9))
        body.add_widget(label(f'Coordenadas de {member["name"]} (manuales)', 13, MUTED, 37))
        lat = field('Latitud: -32.6', '' if member['lat'] is None else member['lat'])
        lon = field('Longitud: -62.8', '' if member['lon'] is None else member['lon'])
        body.add_widget(lat)
        body.add_widget(lon)
        popup = Popup(title='Ubicación manual', content=body, size_hint=(.92, None), height=dp(305))
        def save():
            try:
                self.store.set_member_position(self.trip['id'], member['id'], lat.text, lon.text)
                popup.dismiss()
                self.show('Grupo')
            except ValueError as exc:
                self.error(exc)
        body.add_widget(button('Guardar punto', save))
        body.add_widget(button('Quitar punto', lambda: (self.store.clear_member_position(self.trip['id'], member['id']), popup.dismiss(), self.show('Grupo')),
                               secondary=True, height=37))
        popup.open()

    def map_page(self):
        head = BoxLayout(orientation='vertical', padding=[dp(15), dp(1), dp(15), dp(8)],
                         spacing=dp(4), size_hint_y=None, height=dp(172))
        head.add_widget(label('Mapa del viaje', 22, WHITE, 37, bold=True))
        head.add_widget(label('Puntos de amigos: manuales  |  Mi GPS: solo en este equipo', 11, MUTED, 28))
        first_row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(7))
        first_row.add_widget(button('Detener GPS' if self.gps_active else 'Mi GPS', self.toggle_gps,
                                    danger=self.gps_active, height=42))
        first_row.add_widget(button('+ Guardar lugar', self.new_place_dialog, secondary=True, height=42))
        head.add_widget(first_row)
        second_row = BoxLayout(size_hint_y=None, height=dp(38))
        second_row.add_widget(button('Ver lista de lugares', self.places_dialog, secondary=True, height=38))
        head.add_widget(second_row)
        self.page_area.add_widget(head)
        if MapView is None:
            self.page_area.add_widget(label('Instalá: pip install kivy_garden.mapview', 14, MUTED))
            return
        initial = self.own_coords or (-32.597, -62.791)
        try:
            self.map_view = MapView(zoom=11, lat=initial[0], lon=initial[1])
            self.page_area.add_widget(self.map_view)
            self.render_map_markers()
        except Exception as exc:
            self.page_area.add_widget(label('No se pudo cargar el mapa: ' + str(exc), 13, MUTED))
        self.page_area.add_widget(label('© OpenStreetMap contributors  ·  El mapa requiere internet para zonas nuevas',
                                        10, MUTED, 30, align='center'))

    def render_map_markers(self):
        if not self.map_view or MapMarker is None:
            return
        for pin in self.map_markers:
            try:
                self.map_view.remove_marker(pin)
            except Exception:
                pass
        self.map_markers.clear()
        positions = []
        if self.trip:
            positions.extend((m['lat'], m['lon'], 'Amigo: ' + m['name']) for m in self.store.members(self.trip['id']) if m['lat'] is not None)
            positions.extend((p['lat'], p['lon'], 'Lugar: ' + p['title']) for p in self.store.places(self.trip['id']))
        if self.own_coords:
            positions.append((*self.own_coords, 'Mi ubicación GPS'))
        for lat, lon, caption in positions:
            try:
                pin = MapMarkerPopup(lat=float(lat), lon=float(lon))
                pin.add_widget(label(caption, 12, BG, 55, bold=True))
                self.map_view.add_marker(pin)
                self.map_markers.append(pin)
            except Exception:
                continue

    def new_place_dialog(self):
        if not self.require_trip():
            return
        box = BoxLayout(orientation='vertical', padding=dp(13), spacing=dp(9))
        name = field('Lugar: Camping Los Aromos')
        lat = field('Latitud: -32.6')
        lon = field('Longitud: -62.8')
        for item in (name, lat, lon):
            box.add_widget(item)
        popup = Popup(title='Guardar lugar en mapa', content=box, size_hint=(.94, None), height=dp(305))
        def save():
            try:
                self.store.add_place(self.trip['id'], name.text, lat.text, lon.text)
                popup.dismiss()
                self.show('Mapa')
            except ValueError as exc:
                self.error(exc)
        box.add_widget(button('Guardar lugar', save))
        popup.open()

    def places_dialog(self):
        if not self.require_trip():
            return
        places = self.store.places(self.trip['id'])
        if not places:
            self.alert('Lugares', 'Todavía no guardaste ningún lugar en el mapa.')
            return
        box = BoxLayout(orientation='vertical', spacing=dp(7), padding=dp(9))
        scroller = ScrollView()
        inner = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(8))
        inner.bind(minimum_height=inner.setter('height'))
        scroller.add_widget(inner)
        box.add_widget(scroller)
        popup = Popup(title='Lugares guardados', content=box, size_hint=(.95, .82))
        for p in places:
            inner.add_widget(label(f'{p["title"]}  ({p["lat"]:.3f}, {p["lon"]:.3f})', 13, WHITE, 33))
            line = BoxLayout(size_hint_y=None, height=dp(37), spacing=dp(6))
            def go(place=p):
                popup.dismiss()
                if self.map_view:
                    self.map_view.center_on(place['lat'], place['lon'])
            line.add_widget(button('Ver en mapa', go, secondary=True, height=37))
            def delete(place=p):
                self.store.delete_place(self.trip['id'], place['id'])
                popup.dismiss()
                self.show('Mapa')
            line.add_widget(button('Quitar', delete, danger=True, height=37))
            inner.add_widget(line)
        popup.open()

    def toggle_gps(self):
        if self.gps_active:
            self.stop_gps()
            self.show('Mapa')
            return
        if platform != 'android':
            self.alert('GPS en Android', 'En Windows podés usar el mapa y agregar coordenadas manualmente. El GPS del celular se activa al instalar el APK.')
            return
        if gps is None:
            self.alert('GPS no disponible', 'No se encontró Plyer GPS.')
            return
        try:
            from android.permissions import Permission, request_permissions
            request_permissions([Permission.ACCESS_FINE_LOCATION, Permission.ACCESS_COARSE_LOCATION],
                                self.gps_permission_callback)
        except Exception as exc:
            self.error(exc)

    def gps_permission_callback(self, _, grants):
        Clock.schedule_once(lambda __: self.start_gps() if any(grants) else self.alert(
            'Permiso requerido', 'Autorizá ubicación para que el mapa muestre tu posición.'), 0)

    def start_gps(self):
        try:
            gps.configure(on_location=self.receive_gps, on_status=lambda **kw: None)
            gps.start(minTime=3000, minDistance=5)
            self.gps_active = True
            self.show('Mapa')
        except Exception as exc:
            self.gps_active = False
            self.error(exc)

    def receive_gps(self, **data):
        try:
            lat, lon = float(data['lat']), float(data['lon'])
            self.store.validate_coords(lat, lon)
        except (ValueError, TypeError, KeyError):
            return
        Clock.schedule_once(lambda _: self.update_gps(lat, lon), 0)

    def update_gps(self, lat, lon):
        if not self.gps_active:
            return
        self.own_coords = lat, lon
        if self.page == 'Mapa' and self.map_view:
            self.map_view.center_on(lat, lon)
            self.render_map_markers()

    def stop_gps(self):
        if gps and self.gps_active:
            try:
                gps.stop()
            except Exception:
                pass
        self.gps_active = False

    def photos_page(self):
        col = self.scroll()
        self.heading(col, 'Recuerdos del viaje', 'Fotos privadas, guardadas únicamente en este dispositivo.')
        bar = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(7))
        bar.add_widget(button('Abrir cámara', self.open_camera))
        bar.add_widget(button('Importar foto', self.import_photo, secondary=True))
        col.add_widget(bar)
        self.photo_stack = col
        if not self.trip:
            col.add_widget(label('Para guardar fotos, primero creá un viaje en Grupo.', 13, MUTED, 56))
            return
        photos = self.store.photos(self.trip['id'])
        if not photos:
            col.add_widget(label('Todavía no hay fotos del viaje.', 13, MUTED, 55))
        for item in photos[:50]:
            pane = Panel(size_hint_y=None, height=dp(260))
            pane.add_widget(Image(source=item['path'], fit_mode='contain'))
            pane.add_widget(label(item['created_at'], 11, MUTED, 24))
            pane.add_widget(button('Quitar de la galería', lambda obj=item: self.confirm(
                'Quitar foto', '¿Quitar esta foto de la galería? El archivo original no se borra.',
                lambda: (self.store.delete_photo(self.trip['id'], obj['id']), self.show('Fotos'))),
                secondary=True, height=36))
            col.add_widget(pane)

    def open_camera(self):
        if not self.require_trip():
            return
        if platform != 'android':
            self.open_desktop_camera()
            return
        try:
            from android.permissions import Permission, request_permissions
            request_permissions([Permission.CAMERA], self.camera_permission_callback)
        except Exception as exc:
            self.error(exc)

    def camera_permission_callback(self, _, grants):
        Clock.schedule_once(lambda __: self.launch_android_camera() if all(grants) else self.alert(
            'Permiso necesario', 'Se necesita autorización para tomar fotografías.'), 0)

    def launch_android_camera(self):
        if not self.trip:
            return
        folder = Path(self.user_data_dir) / 'fotos' / self.trip['id']
        folder.mkdir(parents=True, exist_ok=True)
        self.pending_photo = folder / f'viaje_{datetime.now():%Y%m%d_%H%M%S_%f}.jpg'
        try:
            from android_camera import take_picture
            take_picture(str(self.pending_photo), self.camera_finished)
        except Exception as exc:
            self.error(exc)

    def camera_finished(self, result):
        Clock.schedule_once(lambda _: self.complete_photo(result), 0)

    def complete_photo(self, result):
        file = Path(result) if result else getattr(self, 'pending_photo', None)
        if file and file.is_file() and file.stat().st_size:
            try:
                self.store.add_photo(self.trip['id'], file)
                self.show('Fotos')
                self.alert('Foto guardada', 'La foto se guardó en este dispositivo.')
            except Exception as exc:
                self.error(exc)
        else:
            self.alert('Cámara', 'No se tomó la foto o se canceló la cámara.')

    def open_desktop_camera(self):
        if self.camera_widget:
            return
        try:
            self.camera_widget = Camera(play=True, resolution=(640, 480),
                                        size_hint_y=None, height=dp(270))
            self.camera_panel = Panel(size_hint_y=None, height=dp(350))
            self.camera_panel.add_widget(self.camera_widget)
            self.camera_panel.add_widget(button('Guardar fotografía', self.capture_desktop_photo))
            self.photo_stack.add_widget(self.camera_panel, index=len(self.photo_stack.children))
        except Exception as exc:
            self.camera_widget = None
            self.error(exc)

    def capture_desktop_photo(self):
        if not self.camera_widget or not self.camera_widget.texture:
            self.alert('Cámara iniciando', 'Esperá a que aparezca la imagen de la cámara.')
            return
        folder = Path(self.user_data_dir) / 'fotos' / self.trip['id']
        folder.mkdir(parents=True, exist_ok=True)
        image = folder / f'viaje_{datetime.now():%Y%m%d_%H%M%S_%f}.png'
        try:
            self.camera_widget.texture.save(str(image), flipped=False)
            self.store.add_photo(self.trip['id'], image)
            self.stop_camera()
            self.show('Fotos')
        except Exception as exc:
            self.error(exc)

    def stop_camera(self):
        if self.camera_widget:
            try:
                self.camera_widget.play = False
            except Exception:
                pass
        self.camera_widget = None
        self.camera_panel = None

    def import_photo(self):
        if not self.require_trip():
            return
        if platform == 'android':
            self.alert('Fotos en Android', 'Usá Abrir cámara para sacar fotografías. En esta versión la importación de la galería se realiza desde Windows.')
            return
        self.choose_file('Seleccionar foto', ['*.jpg', '*.jpeg', '*.png'], self.handle_photo_file)

    def handle_photo_file(self, file):
        if file.suffix.lower() not in ('.jpg', '.jpeg', '.png'):
            raise ValueError('Solo se admiten imágenes JPG o PNG.')
        folder = Path(self.user_data_dir) / 'fotos' / self.trip['id']
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / f'importada_{datetime.now():%Y%m%d_%H%M%S_%f}{file.suffix.lower()}'
        shutil.copy2(file, dest)
        self.store.add_photo(self.trip['id'], dest)
        self.show('Fotos')

    def agenda_page(self):
        col = self.scroll()
        self.heading(col, 'Agenda del viaje', 'Actividades locales con fechas, horarios y notas.')
        col.add_widget(button('+ Nueva actividad', self.new_event_dialog))
        if not self.trip:
            col.add_widget(label('Creá un viaje en Grupo para empezar tu agenda.', 13, MUTED, 70))
            return
        events = self.store.events(self.trip['id'])
        if not events:
            col.add_widget(label('Todavía no hay actividades programadas.', 13, MUTED, 55))
        for event in events:
            card = Panel(size_hint_y=None, height=dp(181))
            card.add_widget(label(event['date'] + '  ·  ' + event['time'], 12, CYAN, 26, bold=True))
            card.add_widget(label(event['title'], 17, WHITE, 38, bold=True))
            card.add_widget(label(event['description'] or 'Sin descripción', 12, MUTED, 39))
            card.add_widget(button('Eliminar actividad', lambda obj=event: self.confirm(
                'Eliminar actividad', '¿Eliminar esta actividad del viaje?',
                lambda: (self.store.delete_event(self.trip['id'], obj['id']), self.show('Agenda'))),
                secondary=True, height=34))
            col.add_widget(card)

    def new_event_dialog(self):
        if not self.require_trip():
            return
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(13))
        title = field('Actividad: visitar el museo')
        day = field('Fecha AAAA-MM-DD', datetime.now().strftime('%Y-%m-%d'))
        hour = field('Hora HH:MM', '09:00')
        note = field('Descripción opcional', multiline=True)
        for control in (title, day, hour, note):
            content.add_widget(control)
        popup = Popup(title='Nueva actividad', content=content, size_hint=(.94, None), height=dp(386))
        def save():
            try:
                self.store.add_event(self.trip['id'], title.text, day.text, hour.text, note.text)
                popup.dismiss()
                self.show('Agenda')
            except ValueError as exc:
                self.error(exc)
        content.add_widget(button('Guardar actividad', save))
        popup.open()

    def export_backup(self):
        if not self.require_trip():
            return
        try:
            target = export_trip(self.store, self.trip['id'])
            if platform == 'android':
                self.alert('Copia creada', 'Respaldo guardado dentro de la app en:\n' + str(target) +
                           '\nPara pasarlo a otra persona necesitarías extraer o compartir ese archivo manualmente.')
            else:
                self.alert('Copia creada', 'ZIP guardado en:\n' + str(target))
        except Exception as exc:
            self.error(exc)

    def import_backup(self):
        if platform == 'android':
            self.alert('Solo desde PC', 'La importación ZIP de esta edición está disponible en Windows.')
            return
        self.choose_file('Importar respaldo ZIP', ['*.zip'], self.handle_backup_file)

    def handle_backup_file(self, file):
        ident = import_trip(self.store, file)
        self.store.select_trip(ident)
        self.show('Inicio')
        self.alert('Viaje importado', 'Se agregó el viaje con su agenda, integrantes, lugares y fotos.')

    def choose_file(self, title, filters, handler):
        chooser = FileChooserListView(path=str(Path.home()), filters=filters)
        body = BoxLayout(orientation='vertical', padding=dp(9), spacing=dp(8))
        body.add_widget(chooser)
        popup = Popup(title=title, content=body, size_hint=(.95, .88))
        def accept():
            if not chooser.selection:
                self.alert('Seleccioná un archivo', 'Elegí un archivo de la lista.')
                return
            selected = Path(chooser.selection[0])
            if not selected.is_file():
                self.alert('Archivo inválido', 'Elegí un archivo existente.')
                return
            try:
                handler(selected)
                popup.dismiss()
            except Exception as exc:
                self.error(exc)
        body.add_widget(button('Usar archivo seleccionado', accept))
        popup.open()


if __name__ == '__main__':
    ViajeAmigosApp().run()
