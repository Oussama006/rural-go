from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import UTC, datetime
from sqlalchemy.exc import OperationalError
from sqlalchemy import text
import os
import math
import re
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import or_
from urllib.parse import quote
from urllib.request import urlopen, Request
import json

app = Flask(__name__)
base_dir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(base_dir, 'ruralgo.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'ruralgo-dev-secret-key')
app.config['UPLOAD_FOLDER'] = os.path.join(base_dir, 'static', 'uploads', 'documents')
app.config['PROFILE_PHOTO_FOLDER'] = os.path.join(base_dir, 'static', 'uploads', 'profile_photos')
db = SQLAlchemy(app)


def utc_now():
    return datetime.now(UTC)


class Vehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64))
    wheelchair = db.Column(db.Boolean, default=False)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(32), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='family', nullable=False)
    profile_photo = db.Column(db.String(240), nullable=True)
    last_seen_at = db.Column(db.DateTime, nullable=True)
    online_visible = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utc_now)


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    ride_id = db.Column(db.Integer, db.ForeignKey('ride.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now)


class RideAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ride_id = db.Column(db.Integer, db.ForeignKey('ride.id'), unique=True, nullable=False)
    driver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now)


class RideLocation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ride_id = db.Column(db.Integer, db.ForeignKey('ride.id'), unique=True, nullable=False)
    driver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    speed_kmh = db.Column(db.Float, default=28.0)
    heading = db.Column(db.String(32), default='north-east')
    updated_at = db.Column(db.DateTime, default=utc_now)


class Ride(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    requester = db.Column(db.String(120))
    phone = db.Column(db.String(32))
    service_type = db.Column(db.String(64))
    origin = db.Column(db.String(200))
    destination = db.Column(db.String(200))
    wheelchair = db.Column(db.Boolean, default=False)
    vulnerable = db.Column(db.Boolean, default=False)
    viva_pass = db.Column(db.Boolean, default=False)
    support_needs = db.Column(db.Text, default='')
    distance_km = db.Column(db.Float, default=0.0)
    price = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(32), default='pending')
    assigned_vehicle = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=True)
    preferred_driver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now)


SUPPORT_NEEDS_OPTIONS = [
    {'value': 'walk_assistance', 'label': 'Ajuda per caminar'},
    {'value': 'accompany_home', 'label': 'Acompanyament fins a casa'},
    {'value': 'help_bags', 'label': 'Ajudar amb les bosses'},
    {'value': 'wait_during_visit', 'label': 'Espera durant la cita'},
    {'value': 'phone_support', 'label': 'Acompanyament telefònic'},
]


TRANSLATIONS = {
    'ca': {
        'Home': 'Inici',
        'Profile': 'Perfil',
        'Messages': 'Missatges',
        'Book': 'Reservar',
        'Services': 'Serveis',
        'History': 'Històric',
        'Driver': 'Conductor',
        'Admin': 'Admin',
        'Logout': 'Sortir',
        'Back': 'Tornar',
        'Message': 'Missatge',
        'Reply': 'Respondre',
        'Send reply': 'Enviar resposta',
        'User': 'Usuari',
        'Users': 'Usuaris',
        'Reservations': 'Reserves',
        'Average price': 'Preu mitjà',
        'Impact': 'Impacte',
        'Services breakdown': 'Serveis',
        'Quick read': 'Lectura ràpida',
        'Health': 'Salut',
        'Culture': 'Cultura',
        'Family': 'Família',
        'Community': 'Comunitat',
        'Nature': 'Natura',
        'Vulnerable': 'Vulnerables',
        'Route history': 'Històric de trajectes',
        'Latest count': 'Últims',
        'No rides yet': 'Encara no hi ha trajectes registrats.',
        'Clear service summary': 'Resum clar del servei i dels trajectes.',
        'Client': 'Client',
        'Route': 'Ruta',
        'Assistance': 'Assistència',
        'Distance': 'Distància',
        'Pending': 'Pendent',
        'Deleted user': 'Usuari eliminat',
        'Deleted driver': 'Conductor eliminat',
    },
    'es': {
        'Home': 'Inicio',
        'Profile': 'Perfil',
        'Messages': 'Mensajes',
        'Book': 'Reservar',
        'Services': 'Servicios',
        'History': 'Histórico',
        'Driver': 'Conductor',
        'Admin': 'Admin',
        'Logout': 'Salir',
        'Back': 'Volver',
        'Message': 'Mensaje',
        'Reply': 'Responder',
        'Send reply': 'Enviar respuesta',
        'User': 'Usuario',
        'Users': 'Usuarios',
        'Reservations': 'Reservas',
        'Average price': 'Precio medio',
        'Impact': 'Impacto',
        'Services breakdown': 'Servicios',
        'Quick read': 'Lectura rápida',
        'Health': 'Salud',
        'Culture': 'Cultura',
        'Family': 'Familia',
        'Community': 'Comunidad',
        'Nature': 'Naturaleza',
        'Vulnerable': 'Vulnerables',
        'Route history': 'Histórico de trayectos',
        'Latest count': 'Últimos',
        'No rides yet': 'Todavía no hay trayectos registrados.',
        'Clear service summary': 'Resumen claro del servicio y de los trayectos.',
        'Client': 'Cliente',
        'Route': 'Ruta',
        'Assistance': 'Asistencia',
        'Distance': 'Distancia',
        'Pending': 'Pendiente',
        'Deleted user': 'Usuario eliminado',
        'Deleted driver': 'Conductor eliminado',
    },
}


def get_current_lang():
    return session.get('lang', 'ca')


def translate(label, lang=None):
    lang = lang or get_current_lang()
    return TRANSLATIONS.get(lang, TRANSLATIONS['ca']).get(label, label)

SERVICE_CATALOG = [
    {
        'id': 'cultura',
        'name': 'RURAL-GO Cultura',
        'service_type': 'Cultura',
        'category': 'Cultura',
        'description': 'Transport a teatres, cines, museus, concerts i activitats culturals amb recomanacions de proximitat.',
        'base_fare': 3.50,
        'price_per_km': 0.85,
        'hours': '8:00 - 23:00',
        'response_time': '5-10 minuts',
        'features': ['Recomanacions', 'Itineraris culturals', 'Acompanyament opcional'],
        'use_cases': ['Teatres i concerts', 'Museus i exposicions', 'Cinema i activitats locals'],
    },
    {
        'id': 'familia',
        'name': 'RURAL-GO Família',
        'service_type': 'Familia',
        'category': 'Família',
        'description': 'Viatges per visites familiars, celebracions, dinars de grup i suport intergeneracional.',
        'base_fare': 3.50,
        'price_per_km': 0.85,
        'hours': '7:00 - 22:00',
        'response_time': '10-15 minuts',
        'features': ['Grups familiars', 'Accés fàcil', 'Seguiment per avisos'],
        'use_cases': ['Visites a familiars', 'Celebracions', 'Recollida de persones grans'],
    },
    {
        'id': 'salut',
        'name': 'RURAL-GO Salut',
        'service_type': 'Salut',
        'category': 'Salut',
        'description': 'Transport a CAP, hospitals, farmàcies, òptiques i cites mèdiques amb prioritat de servei.',
        'base_fare': 2.50,
        'price_per_km': 0.75,
        'hours': '6:00 - 20:00',
        'response_time': '5 minuts',
        'features': ['Prioritat', 'Acompanyament', 'Recollida a domicili'],
        'use_cases': ['Cites mèdiques', 'Farmàcia', 'Anàlisis i revisions'],
    },
    {
        'id': 'comunitat',
        'name': 'RURAL-GO Serveis Comunitaris',
        'service_type': 'Comunitat',
        'category': 'Serveis Comunitaris',
        'description': 'Desplaçaments per compres, gestions, voluntariat i activitats comunitàries locals.',
        'base_fare': 2.00,
        'price_per_km': 0.50,
        'hours': '8:00 - 19:00',
        'response_time': '10 minuts',
        'features': ['Ajuda amb bosses', 'Horari flexible', 'Suport en gestions'],
        'use_cases': ['Mercat i supermercat', 'Centre cívic', 'Voluntariat local'],
    },
    {
        'id': 'natura',
        'name': 'RURAL-GO Natura',
        'service_type': 'Natura',
        'category': 'Natura',
        'description': 'Sortides de benestar, passejos naturals, senderisme suau i activitats de connexió amb l’entorn.',
        'base_fare': 3.50,
        'price_per_km': 0.85,
        'hours': '8:00 - 18:00',
        'response_time': '15 minuts',
        'features': ['Rutes tranquil·les', 'Benestar', 'Acompanyament'],
        'use_cases': ['Passejos per parcs', 'Sortides saludables', 'Activitats a la natura'],
    },
    {
        'id': 'urgencia',
        'name': 'RURAL-GO Urgència',
        'service_type': 'Salut',
        'category': 'Urgència',
        'description': 'Mode de prioritat per situacions greus o necessitats socials urgents amb el vehicle disponible més proper.',
        'base_fare': 5.00,
        'price_per_km': 1.20,
        'hours': '24/7',
        'response_time': '3 minuts',
        'features': ['Prioritat màxima', 'Vehicle proper', 'Suport continu'],
        'use_cases': ['Urgències socials', 'Transport prioritari', 'Necessitats sanitàries no crítiques'],
    },
]

DOMUS_ACTIVITIES = [
    {
        'name': 'Concert Jazz a la Plaça',
        'description': 'Música en directe de bandes locals amb ambient comunitari.',
        'location': 'Plaça Reial',
        'duration': '2h',
        'price': 12,
        'difficulty': 'Baixa',
        'rating': 4.7,
        'tags': ['música', 'cultura', 'social'],
    },
    {
        'name': 'Passeig al riu',
        'description': 'Caminada relaxant seguint el riu, pensada per ritme tranquil.',
        'location': 'Passeig del riu',
        'duration': '1h 30m',
        'price': 0,
        'difficulty': 'Baixa',
        'rating': 4.6,
        'tags': ['natura', 'benestar', 'accessible'],
    },
    {
        'name': 'Club de lectura',
        'description': 'Trobada cultural en petit grup per conversar i crear vincle.',
        'location': 'Biblioteca municipal',
        'duration': '1h 30m',
        'price': 0,
        'difficulty': 'Baixa',
        'rating': 4.3,
        'tags': ['literatura', 'comunitat', 'cultura'],
    },
]


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipient_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    recipient_role = db.Column(db.String(32), nullable=True)
    sender_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    sender_role = db.Column(db.String(32), default='system', nullable=False)
    ride_id = db.Column(db.Integer, db.ForeignKey('ride.id'), nullable=True)
    title = db.Column(db.String(160), nullable=False)
    body = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(32), default='info', nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now)
    seen = db.Column(db.Boolean, default=False)


class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ride_id = db.Column(db.Integer, db.ForeignKey('ride.id'), nullable=False)
    sender_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now)


class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ride_id = db.Column(db.Integer, db.ForeignKey('ride.id'), nullable=False)
    rater_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    rated_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=utc_now)


class UserDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    filename = db.Column(db.String(240), nullable=False)
    original_filename = db.Column(db.String(240), nullable=False)
    status = db.Column(db.String(32), default='Pendent', nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now)


def seed_data():
    if Vehicle.query.count() == 0:
        v1 = Vehicle(name='Taxi Carme 1', wheelchair=False)
        v2 = Vehicle(name='Minivan Orpí', wheelchair=True)
        v3 = Vehicle(name='Voluntari SantaMaria', wheelchair=False)
        db.session.add_all([v1, v2, v3])
        db.session.commit()

    if User.query.count() == 0:
        admin_user = User(
            username='admin@ruralgo.local',
            full_name='Administrador Rural-GO',
            phone='600000001',
            password_hash=generate_password_hash('Admin1234!'),
            role='admin'
        )
        family_user = User(
            username='familia@ruralgo.local',
            full_name='Usuari Família Demo',
            phone='600000003',
            password_hash=generate_password_hash('Fam1234!'),
            role='family'
        )
        db.session.add_all([admin_user, family_user])
        db.session.commit()

    if User.query.filter_by(role='driver').count() == 0:
        driver_one = User(
            username='driver1@ruralgo.local',
            full_name='Paco',
            phone='600000004',
            password_hash=generate_password_hash('Driver1234!'),
            role='driver'
        )
        driver_two = User(
            username='driver2@ruralgo.local',
            full_name='Mario',
            phone='600000005',
            password_hash=generate_password_hash('Driver2234!'),
            role='driver'
        )
        db.session.add_all([driver_one, driver_two])
        db.session.commit()


def sync_demo_driver_names():
    demo_names = {
        'driver1@ruralgo.local': 'Paco',
        'driver2@ruralgo.local': 'Mario',
    }
    changed = False
    for username, full_name in demo_names.items():
        user = User.query.filter_by(username=username, role='driver').first()
        if user and user.full_name != full_name:
            user.full_name = full_name
            changed = True
    if changed:
        db.session.commit()


def get_ride_client(ride: Ride):
    booking = Booking.query.filter_by(ride_id=ride.id).first()
    if not booking:
        return None
    return db.session.get(User, booking.user_id)


def create_message(title, body, recipient_user_id=None, recipient_role=None, sender_user_id=None, sender_role='system', ride=None, category='info', rating_suggestion=None):
    existing_message = None
    if ride and recipient_user_id and category == 'rating':
        recent_cutoff = utc_now().timestamp() - 300
        existing_message = (
            Message.query.filter(
                Message.ride_id == ride.id,
                Message.recipient_user_id == recipient_user_id,
                Message.category == 'rating',
                Message.title == title,
            )
            .filter(Message.created_at >= datetime.fromtimestamp(recent_cutoff, UTC))
            .first()
        )
    if existing_message:
        return existing_message

    message = Message(
        recipient_user_id=recipient_user_id,
        recipient_role=recipient_role,
        sender_user_id=sender_user_id,
        sender_role=sender_role,
        ride_id=ride.id if ride else None,
        title=title,
        body=body,
        category=category,
    )
    if rating_suggestion:
        message.extra = json.dumps(rating_suggestion)
    db.session.add(message)
    db.session.commit()
    return message


def get_user_messages(user, limit=None):
    query = Message.query.order_by(Message.created_at.desc())

    if user.role in ('admin',):
        query = query.filter(or_(Message.recipient_role == 'staff', Message.recipient_role == user.role, Message.recipient_user_id == user.id))
    else:
        query = query.filter(Message.recipient_user_id == user.id)

    if limit is not None:
        query = query.limit(limit)
    try:
        return query.all()
    except OperationalError as oe:
        if 'no such column' in str(oe).lower() or 'seen' in str(oe).lower():
            try:
                db.session.rollback()
            except Exception:
                pass
            ensure_message_seen_column()
            query = Message.query.order_by(Message.created_at.desc())
            if user.role in ('admin',):
                query = query.filter(or_(Message.recipient_role == 'staff', Message.recipient_role == user.role, Message.recipient_user_id == user.id))
            else:
                query = query.filter(Message.recipient_user_id == user.id)
            if limit is not None:
                query = query.limit(limit)
            return query.all()
        raise


def get_unread_messages(user, limit=None):
    if not user:
        return []
    query = Message.query.filter(Message.seen == False).order_by(Message.created_at.desc())
    if user.role in ('admin',):
        query = query.filter(or_(Message.recipient_role == 'staff', Message.recipient_role == user.role, Message.recipient_user_id == user.id))
    else:
        query = query.filter(Message.recipient_user_id == user.id)
    if limit is not None:
        query = query.limit(limit)
    try:
        return query.all()
    except OperationalError as oe:
        if 'no such column' in str(oe).lower() or 'seen' in str(oe).lower():
            try:
                db.session.rollback()
            except Exception:
                pass
            ensure_message_seen_column()
            return get_unread_messages(user, limit=limit)
        raise


def get_unread_count(user):
    if not user:
        return 0
    try:
        q = Message.query.filter(Message.seen == False)
    except OperationalError:
        # missing column; try to add and retry
        try:
            db.session.rollback()
        except Exception:
            pass
        ensure_message_seen_column()
        q = Message.query.filter(Message.seen == False)

    if user.role in ('admin',):
        q = q.filter(or_(Message.recipient_role == 'staff', Message.recipient_role == user.role, Message.recipient_user_id == user.id))
    else:
        q = q.filter(Message.recipient_user_id == user.id)
    return q.count()


def is_user_online(user):
    if not user or not user.online_visible:
        return False
    return True


def can_user_access_message(user, message):
    if not user or not message:
        return False
    if message.recipient_user_id == user.id:
        return True
    if user.role in ('admin',) and message.recipient_role in ('staff', user.role):
        return True
    return False


def ensure_message_seen_column():
    """Add the 'seen' column to the message table if it does not exist (safe for SQLite)."""
    try:
        if db.engine.dialect.name == 'sqlite':
            res = db.session.execute(text("PRAGMA table_info('message')")).fetchall()
            cols = [r[1] for r in res]
            if 'seen' not in cols:
                db.session.execute(text("ALTER TABLE message ADD COLUMN seen BOOLEAN DEFAULT 0"))
                db.session.commit()
                print("ensure_message_seen_column: added 'seen' column to message table")
    except Exception as e:
        # If this fails, don't crash the app; surface in console for debugging
        print('ensure_message_seen_column error:', e)


def ensure_ride_extra_columns():
    """Add optional ride columns in SQLite without requiring a migration tool."""
    try:
        if db.engine.dialect.name != 'sqlite':
            return
        res = db.session.execute(text("PRAGMA table_info('ride')")).fetchall()
        cols = [r[1] for r in res]
        added = False
        if 'support_needs' not in cols:
            db.session.execute(text("ALTER TABLE ride ADD COLUMN support_needs TEXT DEFAULT ''"))
            added = True
        if 'distance_km' not in cols:
            db.session.execute(text("ALTER TABLE ride ADD COLUMN distance_km FLOAT DEFAULT 0"))
            added = True
        if added:
            db.session.commit()
            print('ensure_ride_extra_columns: added optional ride columns')
    except Exception as e:
        print('ensure_ride_extra_columns error:', e)


def ensure_rating_table():
    """Create the rating table on older local SQLite databases."""
    try:
        Rating.__table__.create(db.engine, checkfirst=True)
    except Exception as e:
        print('ensure_rating_table error:', e)


def ensure_user_extra_columns():
    """Add optional user profile columns in SQLite without requiring migrations."""
    try:
        if db.engine.dialect.name != 'sqlite':
            return
        res = db.session.execute(text("PRAGMA table_info('user')")).fetchall()
        cols = [r[1] for r in res]
        added = False
        if 'profile_photo' not in cols:
            db.session.execute(text("ALTER TABLE user ADD COLUMN profile_photo VARCHAR(240)"))
            added = True
        if 'last_seen_at' not in cols:
            db.session.execute(text("ALTER TABLE user ADD COLUMN last_seen_at DATETIME"))
            added = True
        if 'online_visible' not in cols:
            db.session.execute(text("ALTER TABLE user ADD COLUMN online_visible BOOLEAN DEFAULT 1"))
            added = True
        db.session.execute(text("UPDATE user SET online_visible = 1 WHERE online_visible IS NULL"))
        if added:
            db.session.commit()
            print('ensure_user_extra_columns: added optional user columns')
        else:
            db.session.commit()
    except Exception as e:
        print('ensure_user_extra_columns error:', e)


def get_user_rides(current_user):
    if current_user.role in ('admin',):
        return Ride.query.order_by(Ride.created_at.desc()).all()
    if current_user.role == 'driver':
        assignments = RideAssignment.query.filter_by(driver_id=current_user.id).all()
        ride_ids = [assignment.ride_id for assignment in assignments]
        return Ride.query.filter(Ride.id.in_(ride_ids)).order_by(Ride.created_at.desc()).all() if ride_ids else []
    bookings = Booking.query.filter_by(user_id=current_user.id).all()
    ride_ids = [booking.ride_id for booking in bookings]
    return Ride.query.filter(Ride.id.in_(ride_ids)).order_by(Ride.created_at.desc()).all() if ride_ids else []


def get_driver_active_rides(driver):
    assignments = RideAssignment.query.filter_by(driver_id=driver.id).all()
    ride_ids = [assignment.ride_id for assignment in assignments]
    if not ride_ids:
        return []
    rides = Ride.query.filter(Ride.id.in_(ride_ids)).order_by(Ride.created_at.desc()).all()
    return [ride for ride in rides if ride.status in ('assigned', 'in_route')]


def has_driver_active_route(driver):
    return len(get_driver_active_rides(driver)) > 0


def get_chat_messages(ride: Ride, limit=None):
    query = ChatMessage.query.filter_by(ride_id=ride.id).order_by(ChatMessage.created_at.asc())
    if limit is not None:
        query = query.limit(limit)
    return query.all()


def send_chat_message(ride: Ride, sender: User, body: str):
    message = ChatMessage(ride_id=ride.id, sender_user_id=sender.id, body=body.strip())
    db.session.add(message)
    db.session.commit()

    assigned_driver = get_assigned_driver(ride)
    client = get_ride_client(ride)

    if sender.role == 'driver' and client:
        create_message(
            title='Nou missatge del conductor',
            body=f'{sender.full_name}: {body.strip()}',
            recipient_user_id=client.id,
            ride=ride,
            category='chat',
        )
    elif sender.role in ('family', 'admin') and assigned_driver:
        create_message(
            title='Nou missatge del client',
            body=f'{sender.full_name}: {body.strip()}',
            recipient_user_id=assigned_driver.id,
            ride=ride,
            category='chat',
        )

    return message


def notify_new_ride_request(ride: Ride, client: User):
    support_text = describe_support_needs(ride)
    create_message(
        title='Nova sol·licitud rebuda',
        body=f'{client.full_name} ha demanat un trajecte {ride.service_type} de {ride.origin} a {ride.destination}. {support_text}',
        recipient_role='staff',
        ride=ride,
        category='request',
    )
    create_message(
        title='Reserva feta',
        body='La teva reserva s’ha fet correctament. Ara queda pendent que el conductor l’accepti.',
        recipient_user_id=client.id,
        ride=ride,
        category='info',
    )


def notify_assignment(ride: Ride, driver: User):
    client = get_ride_client(ride)
    support_text = describe_support_needs(ride)
    create_message(
        title='Nou trajecte assignat',
        body=f'Tens una reserva assignada: {client.full_name if client else ride.requester}, {ride.origin} → {ride.destination}. {support_text}',
        recipient_user_id=driver.id,
        ride=ride,
        category='assignment',
    )
    create_message(
        title='Conductor avisat',
        body=f'El trajecte #{ride.id} s’ha enviat a {driver.full_name}. Rebràs un avís quan l’accepti.',
        recipient_user_id=client.id if client else None,
        ride=ride,
        category='assignment',
    )
    create_message(
        title='Assignació completada',
        body=f'S’ha assignat el conductor {driver.full_name} al trajecte #{ride.id}.',
        recipient_role='staff',
        ride=ride,
        category='assignment',
    )


def notify_status_change(ride: Ride, new_status: str, actor: User):
    client = get_ride_client(ride)
    assigned_driver = get_assigned_driver(ride)
    status_labels = {
        'assigned': 'assignat',
        'in_route': 'en ruta',
        'completed': 'completat',
    }
    label = status_labels.get(new_status, new_status)

    if client:
        create_message(
            title=f'El trajecte està {label}',
            body=f'El trajecte #{ride.id} ha passat a estat {label}.',
            recipient_user_id=client.id,
            ride=ride,
            sender_user_id=actor.id,
            sender_role=actor.role,
            category='status',
        )

    if assigned_driver and assigned_driver.id != actor.id:
        create_message(
            title=f'Actualització de trajecte: {label}',
            body=f'El trajecte #{ride.id} ha passat a estat {label}.',
            recipient_user_id=assigned_driver.id,
            ride=ride,
            sender_user_id=actor.id,
            sender_role=actor.role,
            category='status',
        )

    if new_status == 'completed' and assigned_driver and client:
        rating_context = build_rating_context(ride, assigned_driver)
        if rating_context.get('pending'):
            create_message(
                title='Valora el teu trajecte',
                body='Com va el trajecte? Puntua la teva experiència amb el client i afegix un comentari.',
                recipient_user_id=assigned_driver.id,
                ride=ride,
                category='rating',
                rating_suggestion={
                    'ride_id': ride.id,
                    'target_user_id': client.id,
                    'target_label': 'client',
                    'target_name': client.full_name,
                },
            )
        rating_context = build_rating_context(ride, client)
        if rating_context.get('pending'):
            create_message(
                title='Valora el teu trajecte',
                body='Com va el trajecte? Puntua la teva experiència amb el conductor i afegix un comentari.',
                recipient_user_id=client.id,
                ride=ride,
                category='rating',
                rating_suggestion={
                    'ride_id': ride.id,
                    'target_user_id': assigned_driver.id,
                    'target_label': 'conductor',
                    'target_name': assigned_driver.full_name,
                },
            )

    create_message(
        title=f'Canvi d’estat: {label}',
        body=f'El trajecte #{ride.id} ha passat a estat {label}.',
        recipient_role='staff',
        ride=ride,
        sender_user_id=actor.id,
        sender_role=actor.role,
        category='status',
    )


def parse_coordinate(text, axis):
    normalized_text = (text or '').lower()
    igualada_coords = (41.581, 1.617)
    gps_match = re.search(r'GPS[:\s]*([-+]?\d+(?:\.\d+)?),\s*([-+]?\d+(?:\.\d+)?)', text or '', re.IGNORECASE)
    if gps_match:
        latitude = float(gps_match.group(1))
        longitude = float(gps_match.group(2))
        if haversine_km(latitude, longitude, igualada_coords[0], igualada_coords[1]) > 25:
            latitude, longitude = igualada_coords
        return latitude if axis == 'lat' else longitude

    demo_points = {
        'cap anoia': (41.589, 1.623),
        'cap igualada nord': (41.589, 1.623),
        'cap igualada urba': (41.580, 1.617),
        'cap igualada urbà': (41.580, 1.617),
        'cap igualada sud': (41.574, 1.619),
        'hospital universitari igualada': (41.586, 1.628),
        'hospital igualada': (41.586, 1.628),
        'estacio autobusos': (41.579, 1.617),
        'estació autobusos': (41.579, 1.617),
        'ateneu': (41.579, 1.617),
        'teatre ateneu': (41.579, 1.617),
        'museu de la pell': (41.582, 1.620),
        "museu d'igualada": (41.582, 1.620),
        'museu igualada': (41.582, 1.620),
        'parc central': (41.577, 1.625),
        'parc valldaura': (41.586, 1.618),
        'valldaura': (41.586, 1.618),
        'plaça cal font': (41.580, 1.617),
        'placa cal font': (41.580, 1.617),
        'passeig verdaguer': (41.580, 1.619),
        'biblioteca central': (41.581, 1.621),
        'mercat la masuca': (41.581, 1.615),
        'la masuca': (41.581, 1.615),
        'teatre': (41.579, 1.617),
        'cap': (41.589, 1.623),
        'hospital': (41.586, 1.628),
        'farmacia': (41.580, 1.617),
        'farmàcia': (41.580, 1.617),
        'santa maria': (41.582, 1.615),
        'museu': (41.582, 1.620),
        'cine': igualada_coords,
        'concert': igualada_coords,
        'biblioteca': igualada_coords,
        'centre civic': igualada_coords,
        'centre cívic': igualada_coords,
        'mercat': igualada_coords,
        'parc': igualada_coords,
        'muntanya': igualada_coords,
        'igualada': igualada_coords,
    }
    default_coords = igualada_coords

    for keyword, coords in demo_points.items():
        if keyword in normalized_text:
            return coords[0] if axis == 'lat' else coords[1]

    base_lat = igualada_coords[0] + (sum(ord(char) for char in normalized_text) % 17) * 0.001
    base_lng = igualada_coords[1] + (sum(ord(char) for char in normalized_text[::-1]) % 19) * 0.001
    return base_lat if axis == 'lat' else base_lng


def calculate_route_distance_km(origin, destination):
    road_distance = calculate_real_route_distance_km(origin, destination)
    if road_distance:
        return road_distance
    origin_lat = parse_coordinate(origin, 'lat')
    origin_lng = parse_coordinate(origin, 'lng')
    destination_lat = parse_coordinate(destination, 'lat')
    destination_lng = parse_coordinate(destination, 'lng')
    return round(haversine_km(origin_lat, origin_lng, destination_lat, destination_lng), 2)


def sanitize_igualada_place(value):
    if not value:
        return value
    replacements = {
        "Teatre Kursaal (Igualada)": "Teatre de l'Ateneu Igualadi",
        "Parc de l'Agulla (Igualada)": "Parc Central d'Igualada",
        "Parc de la Seu (Igualada)": "Parc de Valldaura d'Igualada",
        "Passeig del riu (Igualada)": "Passeig Verdaguer d'Igualada",
        "Museu d'Igualada": "Museu de la Pell d'Igualada",
        "Hospital de Sant Joan de Deu (Igualada)": "Hospital Universitari d'Igualada",
        "Hospital de Sant Joan de Déu (Igualada)": "Hospital Universitari d'Igualada",
        "CAP Carme": "CAP Igualada Nord",
        "CAP Orpi": "CAP Igualada Sud",
        "CAP Orpí": "CAP Igualada Sud",
        "La Pobla de Claramunt": "Barri de les Comes d'Igualada",
        "Santa Maria de Miralles": "Barri del Poble Sec d'Igualada",
        "Muntanya / passeig saludable": "Parc Central d'Igualada",
    }
    cleaned = replacements.get(value, value)
    gps_match = re.search(r'GPS[:\s]*([-+]?\d+(?:\.\d+)?),\s*([-+]?\d+(?:\.\d+)?)', cleaned, re.IGNORECASE)
    if gps_match:
        latitude = float(gps_match.group(1))
        longitude = float(gps_match.group(2))
        if haversine_km(latitude, longitude, 41.581, 1.617) > 25:
            return 'Ubicacio actual (Igualada)'
    return cleaned


def sanitize_existing_igualada_routes():
    try:
        changed = False
        for ride in Ride.query.all():
            origin = sanitize_igualada_place(ride.origin)
            destination = sanitize_igualada_place(ride.destination)
            if origin != ride.origin:
                ride.origin = origin
                changed = True
            if destination != ride.destination:
                ride.destination = destination
                changed = True
            recalculated_distance = calculate_route_distance_km(ride.origin, ride.destination)
            if ride.distance_km != recalculated_distance:
                ride.distance_km = recalculated_distance
                changed = True
            location = RideLocation.query.filter_by(ride_id=ride.id).first()
            if location:
                origin_lat = parse_coordinate(ride.origin, 'lat')
                origin_lng = parse_coordinate(ride.origin, 'lng')
                if haversine_km(location.latitude, location.longitude, 41.581, 1.617) > 25:
                    location.latitude = origin_lat
                    location.longitude = origin_lng
                    location.updated_at = utc_now()
                    changed = True
        if changed:
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        print('sanitize_existing_igualada_routes error:', e)


def fetch_json(url):
    request_obj = Request(url, headers={'User-Agent': 'Rural-GO demo app'})
    with urlopen(request_obj, timeout=4) as response:
        return json.loads(response.read().decode('utf-8'))


def geocode_place(text_value):
    if not text_value:
        return None
    normalized_text = text_value.lower()
    if 'ubicació actual' in normalized_text or 'ubicacion actual' in normalized_text:
        return parse_coordinate(text_value, 'lat'), parse_coordinate(text_value, 'lng')
    gps_match = re.search(r'GPS[:\s]*([-+]?\d+(?:\.\d+)?),\s*([-+]?\d+(?:\.\d+)?)', text_value, re.IGNORECASE)
    if gps_match:
        return parse_coordinate(text_value, 'lat'), parse_coordinate(text_value, 'lng')

    query = quote(f'{text_value}, Igualada, Anoia, Catalunya, Spain')
    url = f'https://nominatim.openstreetmap.org/search?q={query}&format=json&limit=1'
    data = fetch_json(url)
    if not data:
        return None
    return float(data[0]['lat']), float(data[0]['lon'])


def calculate_real_route_distance_km(origin, destination):
    try:
        origin_coords = geocode_place(origin)
        destination_coords = geocode_place(destination)
        if not origin_coords or not destination_coords:
            return None
        origin_lat, origin_lng = origin_coords
        destination_lat, destination_lng = destination_coords
        url = (
            'https://router.project-osrm.org/route/v1/driving/'
            f'{origin_lng},{origin_lat};{destination_lng},{destination_lat}?overview=false'
        )
        data = fetch_json(url)
        routes = data.get('routes') or []
        if not routes:
            return None
        return round(routes[0]['distance'] / 1000, 2)
    except Exception:
        return None


def normalize_support_needs(values):
    return [value for value in values if value]


def serialize_support_needs(values):
    return '|'.join(normalize_support_needs(values))


def parse_support_needs(value):
    if not value:
        return []
    return [item for item in value.split('|') if item]


def describe_support_needs(ride: Ride):
    selected_values = set(parse_support_needs(ride.support_needs))
    labels = [option['label'] for option in SUPPORT_NEEDS_OPTIONS if option['value'] in selected_values]
    if ride.wheelchair:
        labels.append('Accés per cadira de rodes')
    if not labels:
        return 'No hi ha necessitats especials indicades.'
    return 'Assistència marcada: ' + ', '.join(labels) + '.'


def haversine_km(lat1, lon1, lat2, lon2):
    radius = 6371.0
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    delta_lat = lat2_rad - lat1_rad
    delta_lon = lon2_rad - lon1_rad
    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius * c


def ensure_location_for_ride(ride: Ride, driver: User):
    location = RideLocation.query.filter_by(ride_id=ride.id).first()
    if location:
        return location

    origin_lat = parse_coordinate(ride.origin, 'lat')
    origin_lng = parse_coordinate(ride.origin, 'lng')
    location = RideLocation(
        ride_id=ride.id,
        driver_id=driver.id,
        latitude=origin_lat,
        longitude=origin_lng,
        speed_kmh=27.0,
        heading='east',
    )
    db.session.add(location)
    db.session.commit()
    return location


def move_location_toward_destination(ride: Ride, move_factor=0.25, speed_kmh=28.0, heading='east'):
    driver = get_assigned_driver(ride)
    if not driver:
        return None
    previous_status = ride.status

    location = RideLocation.query.filter_by(ride_id=ride.id).first()
    if not location:
        location = ensure_location_for_ride(ride, driver)

    destination_lat = parse_coordinate(ride.destination, 'lat')
    destination_lng = parse_coordinate(ride.destination, 'lng')
    move_factor = max(0.05, min(float(move_factor), 1.0))

    location.latitude = location.latitude + (destination_lat - location.latitude) * move_factor
    location.longitude = location.longitude + (destination_lng - location.longitude) * move_factor
    location.speed_kmh = float(speed_kmh)
    location.heading = heading
    location.updated_at = datetime.now(UTC)

    ride.status = 'in_route'
    if haversine_km(location.latitude, location.longitude, destination_lat, destination_lng) < 0.25:
        ride.status = 'completed'

    db.session.commit()
    if previous_status != 'completed' and ride.status == 'completed':
        notify_status_change(ride, 'completed', driver)
    return location


def auto_assign_booking_flow(ride: Ride):
    vehicle = assign_vehicle_for_ride(ride, mark_assigned=False)
    if ride.preferred_driver_id:
        driver = assign_driver_for_ride(ride, driver_id=ride.preferred_driver_id)
    else:
        driver = assign_driver_for_ride(ride)
    ride.status = 'pending'
    db.session.commit()
    if driver:
        notify_assignment(ride, driver)
    return vehicle, driver


def create_booking_for_user(current_user, form_data):
    support_needs = normalize_support_needs(form_data.get('support_needs', []))
    distance_km = calculate_route_distance_km(form_data['origin'], form_data['destination'])
    price = calculate_price(
        form_data['service_type'],
        distance_km=distance_km,
        vulnerable=bool(form_data.get('vulnerable')),
        viva_pass=False,
    )
    preferred_driver_id = form_data.get('preferred_driver_id') or 'any'
    ride = Ride(
        requester=form_data.get('requester') or current_user.full_name,
        phone=form_data.get('phone') or current_user.phone,
        service_type=form_data['service_type'],
        origin=form_data['origin'],
        destination=form_data['destination'],
        wheelchair=bool(form_data.get('wheelchair')),
        vulnerable=bool(form_data.get('vulnerable')),
        viva_pass=False,
        support_needs=serialize_support_needs(support_needs),
        distance_km=distance_km,
        price=price,
        preferred_driver_id=int(preferred_driver_id) if preferred_driver_id != 'any' else None,
    )
    db.session.add(ride)
    db.session.commit()
    booking = Booking(user_id=current_user.id, ride_id=ride.id)
    db.session.add(booking)
    db.session.commit()
    notify_new_ride_request(ride, current_user)
    auto_assign_booking_flow(ride)
    return ride


def calculate_price(service_type, distance_km=5, vulnerable=False, viva_pass=False):
    # simplified pricing rules adapted from spec
    base = 3.0
    if service_type == 'Cultura':
        base = 6.0
    elif service_type == 'Familia':
        base = 5.0
    elif service_type == 'Salut':
        base = 4.0
    elif service_type == 'Comunitat':
        base = 2.0
    elif service_type == 'Natura':
        base = 4.0

    # scale a bit with distance
    price = base + max(0, (distance_km - 3) * 0.5)

    # vulnerability discount
    if vulnerable:
        price *= 0.5

    return round(price, 2)


def service_label_for_text(text):
    normalized_text = (text or '').lower()
    keyword_map = {
        'Cultura': ['teatro', 'cine', 'concert', 'museu', 'fiesta', 'festa', 'cultura'],
        'Familia': ['familia', 'familiares', 'niet', 'nét', 'avis', 'fills', 'germans'],
        'Salut': ['cap', 'hospital', 'farmacia', 'farmàcia', 'metge', 'consulta', 'salut'],
        'Comunitat': ['voluntari', 'associacio', 'associació', 'vecinal', 'veïnal', 'comunitat'],
        'Natura': ['parc', 'muntanya', 'riu', 'sender', 'caminar', 'paseo', 'passeig'],
    }

    for label, keywords in keyword_map.items():
        if any(keyword in normalized_text for keyword in keywords):
            return label
    return 'Comunitat'


def suggest_from_aura_command(command_text):
    normalized_text = (command_text or '').strip().lower()
    if not normalized_text:
        return {
            'service_type': 'Comunitat',
            'title': 'Comença parlant amb AURA',
            'summary': 'Escriu una frase com "vull anar al teatre divendres" o "necessito anar al CAP".',
            'confidence': 'Baja',
            'next_step': 'La IA et proposarà un tipus de trajecte i el pots reservar després.',
        }

    service_type = service_label_for_text(normalized_text)
    emotional_triggers = ['sol', 'sola', 'soledat', 'trista', 'trist', 'angoix', 'ensopit', 'ensopida']
    emotional_hint = any(trigger in normalized_text for trigger in emotional_triggers)
    family_hint = service_type == 'Familia'
    health_hint = service_type == 'Salut'

    if health_hint:
        title = 'AURA ha detectat un desplaçament de salut'
        summary = 'Et recomanem prioritzar un vehicle proper i, si cal, adaptar accés i espera.'
        confidence = 'Alta'
        next_step = 'Reserva el trajecte i marca si necessites ajuda o cadira de rodes.'
    elif family_hint:
        title = 'AURA ha interpretat una visita familiar'
        summary = 'Aquest trajecte encaixa amb suport intergeneracional i connexió familiar.'
        confidence = 'Alta'
        next_step = 'Reserva amb el tipus Família i activa el seguiment per avisos.'
    elif service_type == 'Cultura':
        title = 'AURA et proposa un trajecte cultural'
        summary = 'Pots convertir el trajecte en activitat social i cultural amb valor afegit.'
        confidence = 'Alta'
        next_step = 'Reserva amb el tipus Cultura i activa Viva Pass si fas ús recurrent.'
    elif service_type == 'Natura':
        title = 'AURA ha suggerit una sortida de benestar'
        summary = 'Una ruta a la natura ajuda a la mobilitat activa i al benestar emocional.'
        confidence = 'Mitjana'
        next_step = 'Reserva amb el tipus Natura i activa acompanyament si cal.'
    else:
        title = 'AURA ha detectat una necessitat comunitària'
        summary = 'Pots usar aquest trajecte per voluntariat, gestions o activitat social local.'
        confidence = 'Mitjana'
        next_step = 'Reserva el trajecte i consulta si hi ha subvenció automàtica aplicable.'

    if emotional_hint:
        summary += ' També detectem una possible situació de soledat; convé prioritzar un viatge amb component social.'
        next_step = 'Considera una activitat cultural o comunitària, no només un desplaçament funcional.'

    return {
        'service_type': service_type,
        'title': title,
        'summary': summary,
        'confidence': confidence,
        'next_step': next_step,
    }


def build_aura_prefill(aura_data):
    support_needs = normalize_support_needs(aura_data.get('support_needs', []))
    return {
        'service_type': aura_data.get('service_type', 'Comunitat'),
        'requester': aura_data.get('requester', '').strip(),
        'phone': aura_data.get('phone', '').strip(),
        'origin': aura_data.get('origin', '').strip(),
        'destination': aura_data.get('destination', '').strip(),
        'support_needs': support_needs,
        'wheelchair': bool(aura_data.get('wheelchair')),
        'command_text': aura_data.get('command_text', '').strip(),
        'aura_title': aura_data.get('aura_title', 'AURA ha preparat la ruta'),
        'aura_summary': aura_data.get('aura_summary', 'Revisa les dades abans de continuar.'),
    }


def build_user_insights(user):
    user_links = Booking.query.filter_by(user_id=user.id).all()
    rides = Ride.query.filter(Ride.id.in_([link.ride_id for link in user_links])).all() if user_links else []

    rides_count = len(rides)
    recent_rides = sorted(rides, key=lambda ride: ride.created_at, reverse=True)[:3]
    culture_count = len([ride for ride in rides if ride.service_type == 'Cultura'])
    health_count = len([ride for ride in rides if ride.service_type == 'Salut'])
    family_count = len([ride for ride in rides if ride.service_type == 'Familia'])
    community_count = len([ride for ride in rides if ride.service_type == 'Comunitat'])
    nature_count = len([ride for ride in rides if ride.service_type == 'Natura'])
    vulnerable_count = len([ride for ride in rides if ride.vulnerable])

    alerts = []
    if rides_count == 0:
        alerts.append('Encara no tens activitat. AURA et pot ajudar a convertir un desplaçament en una experiència social útil.')
    elif rides_count < 3:
        alerts.append('Tens poca activitat registrada. Pot ser bon moment per suggerir una sortida cultural o familiar.')

    if vulnerable_count > 0:
        alerts.append('S’ha detectat perfil amb subvenció potencial en trajectes previs.')

    recommendations = []
    if culture_count <= family_count:
        recommendations.append('Prova una sortida cultural per reforçar la connexió amb la comunitat.')
    if health_count > 0:
        recommendations.append('Per trajectes de salut, mantén el perfil d’ajuda i accés adaptat activat.')
    if community_count == 0:
        recommendations.append('Pots afegir una activitat comunitària o voluntariat al teu proper trajecte.')
    if nature_count == 0:
        recommendations.append('Una sortida a la natura pot millorar el benestar emocional.')
    if not recommendations:
        recommendations.append('Mantén Viva Pass actiu si fas servir el servei de forma regular.')

    return {
        'rides_count': rides_count,
        'recent_rides': recent_rides,
        'alerts': alerts,
        'recommendations': recommendations,
        'activity_breakdown': {
            'Cultura': culture_count,
            'Família': family_count,
            'Salut': health_count,
            'Comunitat': community_count,
            'Natura': nature_count,
        },
    }


def assign_vehicle_for_ride(ride: Ride, mark_assigned=True):
    # naive assignment: prefer wheelchair-capable vehicle if needed, else first vehicle
    if ride.wheelchair:
        v = Vehicle.query.filter_by(wheelchair=True).first()
    else:
        v = Vehicle.query.first()

    if v:
        ride.assigned_vehicle = v.id
        if mark_assigned:
            ride.status = 'assigned'
        db.session.commit()
        return v
    return None


def assign_driver_for_ride(ride: Ride, driver_id=None):
    existing_assignment = RideAssignment.query.filter_by(ride_id=ride.id).first()
    if driver_id:
        selected_driver = db.session.get(User, int(driver_id))
        if not selected_driver or selected_driver.role != 'driver':
            return None
        if has_driver_active_route(selected_driver):
            return None
    elif existing_assignment:
        return db.session.get(User, existing_assignment.driver_id)
    else:
        drivers = User.query.filter_by(role='driver').order_by(User.id.asc()).all()
        if not drivers:
            return None
        available_drivers = [driver for driver in drivers if not has_driver_active_route(driver)]
        if not available_drivers:
            return None
        selected_driver = available_drivers[(ride.id - 1) % len(available_drivers)]

    if existing_assignment:
        existing_assignment.driver_id = selected_driver.id
        db.session.commit()
        return selected_driver

    assignment = RideAssignment(ride_id=ride.id, driver_id=selected_driver.id)
    db.session.add(assignment)
    db.session.commit()
    return selected_driver


def get_active_assignment(ride: Ride):
    assignment = RideAssignment.query.filter_by(ride_id=ride.id).first()
    if not assignment:
        return None
    return assignment


def get_assigned_driver(ride: Ride):
    assignment = get_active_assignment(ride)
    if not assignment:
        return None
    return db.session.get(User, assignment.driver_id)


def get_assigned_driver_label(ride: Ride):
    assignment = get_active_assignment(ride)
    if not assignment:
        return translate('Pending')
    driver = db.session.get(User, assignment.driver_id)
    return driver.full_name if driver else translate('Deleted driver')


def delete_uploaded_file(folder, filename):
    if not filename:
        return
    path = os.path.join(folder, filename)
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        app.logger.warning('No s’ha pogut eliminar el fitxer %s', path)


def delete_user_account(user: User):
    is_driver = user.role == 'driver'
    ride_ids_to_delete = []

    if is_driver:
        for assignment in RideAssignment.query.filter_by(driver_id=user.id).all():
            ride = db.session.get(Ride, assignment.ride_id)
            if ride and ride.status != 'completed':
                RideLocation.query.filter_by(ride_id=ride.id).delete()
                db.session.delete(assignment)
                ride.status = 'pending'
                ride.assigned_vehicle = None
                if ride.preferred_driver_id == user.id:
                    ride.preferred_driver_id = None
    else:
        user_bookings = Booking.query.filter_by(user_id=user.id).all()
        ride_ids_to_delete = [booking.ride_id for booking in user_bookings]

    if ride_ids_to_delete:
        ChatMessage.query.filter(ChatMessage.ride_id.in_(ride_ids_to_delete)).delete(synchronize_session=False)
        Message.query.filter(Message.ride_id.in_(ride_ids_to_delete)).delete(synchronize_session=False)
        Rating.query.filter(Rating.ride_id.in_(ride_ids_to_delete)).delete(synchronize_session=False)
        RideLocation.query.filter(RideLocation.ride_id.in_(ride_ids_to_delete)).delete(synchronize_session=False)
        RideAssignment.query.filter(RideAssignment.ride_id.in_(ride_ids_to_delete)).delete(synchronize_session=False)
        Booking.query.filter(Booking.ride_id.in_(ride_ids_to_delete)).delete(synchronize_session=False)
        Ride.query.filter(Ride.id.in_(ride_ids_to_delete)).delete(synchronize_session=False)

    for document in UserDocument.query.filter_by(user_id=user.id).all():
        delete_uploaded_file(app.config['UPLOAD_FOLDER'], document.filename)
        db.session.delete(document)

    delete_uploaded_file(app.config['PROFILE_PHOTO_FOLDER'], user.profile_photo)
    Booking.query.filter_by(user_id=user.id).delete()
    ChatMessage.query.filter_by(sender_user_id=user.id).delete()
    Rating.query.filter(or_(Rating.rater_user_id == user.id, Rating.rated_user_id == user.id)).delete(synchronize_session=False)
    Message.query.filter(or_(Message.sender_user_id == user.id, Message.recipient_user_id == user.id)).delete(synchronize_session=False)
    Ride.query.filter_by(preferred_driver_id=user.id).update({'preferred_driver_id': None})
    db.session.delete(user)


def serialize_ride_location(location: RideLocation):
    if not location:
        return None
    return {
        'latitude': location.latitude,
        'longitude': location.longitude,
        'speed_kmh': location.speed_kmh,
        'heading': location.heading,
        'updated_at': location.updated_at.isoformat() if location.updated_at else None,
    }


def build_ride_tracker(ride: Ride):
    status_order = ['pending', 'assigned', 'in_route', 'completed']
    current_index = status_order.index(ride.status) if ride.status in status_order else 0
    labels = {
        'pending': 'Sol·licitat',
        'assigned': 'Assignat',
        'in_route': 'En ruta',
        'completed': 'Completat',
    }
    steps = []
    for index, key in enumerate(status_order):
        steps.append({
            'key': key,
            'label': labels[key],
            'done': index <= current_index,
            'active': index == current_index,
        })

    progress_percent = int((current_index / (len(status_order) - 1)) * 100) if len(status_order) > 1 else 0
    current_label = labels.get(ride.status, 'Sol·licitat')
    driver = get_assigned_driver(ride)
    vehicle = db.session.get(Vehicle, ride.assigned_vehicle) if ride.assigned_vehicle else None
    location = RideLocation.query.filter_by(ride_id=ride.id).first() if ride else None
    if ride:
        route_distance_km = ride.distance_km or calculate_route_distance_km(ride.origin, ride.destination)
    else:
        route_distance_km = None
    origin_lat = parse_coordinate(ride.origin, 'lat') if ride else None
    origin_lng = parse_coordinate(ride.origin, 'lng') if ride else None
    destination_lat = parse_coordinate(ride.destination, 'lat') if ride else None
    destination_lng = parse_coordinate(ride.destination, 'lng') if ride else None
    eta_minutes = None
    distance_km = None
    progress_to_destination = None
    if location and destination_lat is not None and destination_lng is not None:
        distance_km = round(haversine_km(location.latitude, location.longitude, destination_lat, destination_lng), 2)
        eta_minutes = max(1, int((distance_km / max(location.speed_kmh, 10)) * 60))
        route_total = haversine_km(parse_coordinate(ride.origin, 'lat'), parse_coordinate(ride.origin, 'lng'), destination_lat, destination_lng)
        if route_total > 0:
            progress_to_destination = max(0, min(100, int((1 - (distance_km / route_total)) * 100)))
    return {
        'steps': steps,
        'progress_percent': progress_percent,
        'current_label': current_label,
        'eta_minutes': eta_minutes,
        'distance_km': distance_km,
        'route_distance_km': route_distance_km,
        'progress_to_destination': progress_to_destination,
        'driver_name': get_assigned_driver_label(ride) if get_active_assignment(ride) else None,
        'vehicle_name': vehicle.name if vehicle else None,
        'location': serialize_ride_location(location),
        'origin_lat': origin_lat,
        'origin_lng': origin_lng,
        'destination_lat': destination_lat,
        'destination_lng': destination_lng,
    }


def get_ride_access(current_user, ride):
    if current_user.role in ('admin',):
        return True
    if current_user.role == 'driver':
        driver = get_assigned_driver(ride)
        return driver is not None and driver.id == current_user.id
    booking = Booking.query.filter_by(user_id=current_user.id, ride_id=ride.id).first()
    return booking is not None


def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    return db.session.get(User, user_id)


def login_user(user):
    session['user_id'] = user.id


def logout_user():
    session.pop('user_id', None)


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if get_current_user() is None:
            flash('Necessites iniciar sessió per continuar.', 'warning')
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapped_view


def role_required(*allowed_roles):
    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            current_user = get_current_user()
            if current_user is None:
                flash('Necessites iniciar sessió per continuar.', 'warning')
                return redirect(url_for('login'))
            if current_user.role not in allowed_roles:
                flash('No tens permís per accedir a aquesta secció.', 'danger')
                return redirect(url_for('dashboard'))
            return view(*args, **kwargs)
        return wrapped_view
    return decorator


@app.context_processor
def inject_user():
    user = get_current_user()
    driver_active_rides = get_driver_active_rides(user) if user and user.role == 'driver' else []
    return {
        'current_user': user,
        'unread_count': get_unread_count(user) if user else 0,
        'driver_has_active_route': bool(driver_active_rides),
        'driver_active_ride_id': driver_active_rides[0].id if driver_active_rides else None,
        'service_catalog': SERVICE_CATALOG,
        'current_lang': get_current_lang(),
        '_': translate,
    }


@app.before_request
def _ensure_schema_once():
    # Ensure the optional 'seen' column exists before serving requests.
    # Some Flask versions don't expose before_first_request; use before_request
    # and run once via a module-level flag on the app object.
    if not getattr(app, '_seen_schema_checked', False):
        try:
            ensure_message_seen_column()
            ensure_ride_extra_columns()
            ensure_user_extra_columns()
            ensure_rating_table()
            sanitize_existing_igualada_routes()
        finally:
            setattr(app, '_seen_schema_checked', True)

    current_user = get_current_user()
    if current_user:
        current_user.last_seen_at = datetime.now(UTC)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()


@app.route('/api/ride/<int:ride_id>')
@login_required
def api_ride(ride_id):
    ride = db.session.get(Ride, ride_id)
    if not ride:
        return jsonify({'error': 'not_found'}), 404
    current_user = get_current_user()
    if not get_ride_access(current_user, ride):
        return jsonify({'error': 'forbidden'}), 403
    return jsonify({
        'id': ride.id,
        'requester': ride.requester,
        'phone': ride.phone,
        'service_type': ride.service_type,
        'origin': ride.origin,
        'destination': ride.destination,
        'support_needs': parse_support_needs(ride.support_needs),
        'distance_km': ride.distance_km,
        'status': ride.status
    })


@app.route('/message/<int:message_id>/mark_read', methods=['POST'])
@login_required
def mark_message_read(message_id):
    msg = db.session.get(Message, message_id)
    if not msg:
        return jsonify({'error': 'not_found'}), 404
    current_user = get_current_user()
    if not can_user_access_message(current_user, msg):
        return jsonify({'error': 'forbidden'}), 403
    msg.seen = True
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/language/<lang>')
def set_language(lang):
    session['lang'] = 'es' if lang == 'es' else 'ca'
    return redirect(request.referrer or url_for('dashboard'))


def build_booking_form_data(current_user):
    return {
        'requester': current_user.full_name,
        'phone': current_user.phone,
        'service_type': 'Comunitat',
        'origin': '',
        'destination': '',
        'wheelchair': False,
        'vulnerable': False,
        'support_needs': [],
        'preferred_driver_id': 'any',
    }


def build_profile_form_data(current_user):
    return {
        'username': current_user.username,
        'full_name': current_user.full_name,
        'phone': current_user.phone,
    }


def build_profile_documents(user):
    uploaded_documents = UserDocument.query.filter_by(user_id=user.id).order_by(UserDocument.created_at.desc()).all()
    suggested_documents = [
        {'name': 'DNI / NIE', 'status': 'Verificat', 'detail': 'Identitat confirmada'},
        {'name': 'Targeta sanitària', 'status': 'Pendent', 'detail': 'Recomanada per trajectes Salut'},
        {'name': 'Mobilitat reduïda', 'status': 'Opcional', 'detail': 'Activa adaptació si cal'},
    ]
    if user.role == 'driver':
        suggested_documents = [
            {'name': 'Permís de conduir', 'status': 'Verificat', 'detail': 'Document obligatori'},
            {'name': 'Assegurança', 'status': 'Verificat', 'detail': 'Vehicle cobert'},
            {'name': 'Certificat d’acompanyament', 'status': 'Pendent', 'detail': 'Millora el perfil assistencial'},
            {'name': 'Valoracions', 'status': '4.8/5', 'detail': 'Basat en trajectes demo'},
        ]
    return suggested_documents, uploaded_documents


def get_document_owner(document):
    return db.session.get(User, document.user_id)


def get_user_average_rating(user_id):
    ratings = Rating.query.filter_by(rated_user_id=user_id).all()
    if not ratings:
        return None
    return round(sum(rating.score for rating in ratings) / len(ratings), 1)


def get_existing_rating(ride_id, rater_user_id, rated_user_id):
    return Rating.query.filter_by(
        ride_id=ride_id,
        rater_user_id=rater_user_id,
        rated_user_id=rated_user_id,
    ).first()


def build_rating_context(ride: Ride, user: User):
    assigned_driver = get_assigned_driver(ride)
    client = get_ride_client(ride)
    if not user or ride.status != 'completed' or not assigned_driver or not client:
        return {
            'target': None,
            'target_label': '',
            'existing_rating': None,
            'pending': False,
        }

    if user.id == client.id:
        target = assigned_driver
        target_label = 'conductor'
    elif user.id == assigned_driver.id:
        target = client
        target_label = 'client'
    else:
        target = None
        target_label = ''

    existing_rating = get_existing_rating(ride.id, user.id, target.id) if target else None
    return {
        'target': target,
        'target_label': target_label,
        'existing_rating': existing_rating,
        'pending': bool(target and not existing_rating),
    }


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        full_name = request.form.get('full_name', '').strip()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')
        form_data = {
            'username': username,
            'full_name': full_name,
            'phone': phone,
        }
        field_errors = {}

        if not username or not full_name or not phone or not password or not password_confirm:
            field_errors['form'] = 'Omple tots els camps.'
            return render_template('register.html', form_data=form_data, field_errors=field_errors)

        if password != password_confirm:
            field_errors['password_confirm'] = 'Les contrasenyes no coincideixen.'
            return render_template('register.html', form_data=form_data, field_errors=field_errors)

        existing = User.query.filter_by(username=username).first()
        if existing:
            field_errors['username'] = 'Aquest usuari ja existeix.'
            return render_template('register.html', form_data=form_data, field_errors=field_errors)

        user = User(
            username=username,
            full_name=full_name,
            phone=phone,
            password_hash=generate_password_hash(password),
            role='family'
        )
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash('Compte creat correctament.', 'success')
        return redirect(url_for('dashboard'))

    return render_template('register.html', form_data={})


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')
        form_data = {'username': username}
        user = User.query.filter_by(username=username).first()

        if user is None or not check_password_hash(user.password_hash, password):
            return render_template('login.html', form_data=form_data, field_errors={'form': 'Credencials incorrectes.'})

        login_user(user)
        flash('Sessió iniciada.', 'success')
        return redirect(url_for('dashboard'))

    return render_template('login.html', form_data={})


@app.route('/logout')
def logout():
    logout_user()
    flash('Sessió tancada.', 'info')
    return redirect(url_for('index'))


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    current_user = get_current_user()
    field_errors = {}
    form_data = build_profile_form_data(current_user)
    insights = build_user_insights(current_user)
    suggested_documents, uploaded_documents = build_profile_documents(current_user)

    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        full_name = request.form.get('full_name', '').strip()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')

        form_data = {
            'username': username,
            'full_name': full_name,
            'phone': phone,
        }

        if not username or not full_name or not phone:
            field_errors['form'] = 'Els camps bàsics són obligatoris.'
            return render_template('profile.html', form_data=form_data, field_errors=field_errors, insights=insights, suggested_documents=suggested_documents, uploaded_documents=uploaded_documents, average_rating=get_user_average_rating(current_user.id))

        existing = User.query.filter(User.username == username, User.id != current_user.id).first()
        if existing:
            field_errors['username'] = 'Aquest usuari ja està en ús.'
            return render_template('profile.html', form_data=form_data, field_errors=field_errors, insights=insights, suggested_documents=suggested_documents, uploaded_documents=uploaded_documents, average_rating=get_user_average_rating(current_user.id))

        current_user.username = username
        current_user.full_name = full_name
        current_user.phone = phone
        if password:
            current_user.password_hash = generate_password_hash(password)

        db.session.commit()
        flash('Perfil actualitzat correctament.', 'success')
        return redirect(url_for('profile'))

    return render_template('profile.html', form_data=form_data, field_errors=field_errors, insights=insights, suggested_documents=suggested_documents, uploaded_documents=uploaded_documents, average_rating=get_user_average_rating(current_user.id))


@app.route('/profile/documents', methods=['POST'])
@login_required
def upload_profile_document():
    current_user = get_current_user()
    if current_user.role in ('admin',):
        flash('Els documents no són necessaris per al perfil administrador.', 'info')
        return redirect(url_for('profile'))
    title = request.form.get('title', '').strip() or 'Document'
    uploaded_file = request.files.get('document')
    if not uploaded_file or not uploaded_file.filename:
        flash('Selecciona un document abans de pujar-lo.', 'warning')
        return redirect(url_for('profile'))

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    safe_name = secure_filename(uploaded_file.filename)
    timestamp = utc_now().strftime('%Y%m%d%H%M%S')
    stored_name = f'user_{current_user.id}_{timestamp}_{safe_name}'
    uploaded_file.save(os.path.join(app.config['UPLOAD_FOLDER'], stored_name))
    document = UserDocument(
        user_id=current_user.id,
        title=title,
        filename=stored_name,
        original_filename=uploaded_file.filename,
        status='Pendent',
    )
    db.session.add(document)
    db.session.commit()
    create_message(
        title='Document pendent de validació',
        body=f'{current_user.full_name} ha pujat "{document.title}" i espera validació.',
        recipient_role='staff',
        sender_user_id=current_user.id,
        sender_role=current_user.role,
        category='document',
    )
    flash('Document pujat correctament. Queda pendent de revisió.', 'success')
    return redirect(url_for('profile'))


@app.route('/profile/photo', methods=['POST'])
@login_required
def upload_profile_photo():
    current_user = get_current_user()
    uploaded_file = request.files.get('profile_photo')
    if not uploaded_file or not uploaded_file.filename:
        flash('Selecciona una foto abans de pujar-la.', 'warning')
        return redirect(url_for('profile'))

    safe_name = secure_filename(uploaded_file.filename)
    allowed_extensions = {'jpg', 'jpeg', 'png', 'webp', 'gif'}
    extension = safe_name.rsplit('.', 1)[-1].lower() if '.' in safe_name else ''
    if extension not in allowed_extensions:
        flash('La foto ha de ser JPG, PNG, WEBP o GIF.', 'warning')
        return redirect(url_for('profile'))

    os.makedirs(app.config['PROFILE_PHOTO_FOLDER'], exist_ok=True)
    timestamp = utc_now().strftime('%Y%m%d%H%M%S')
    stored_name = f'user_{current_user.id}_{timestamp}_{safe_name}'
    uploaded_file.save(os.path.join(app.config['PROFILE_PHOTO_FOLDER'], stored_name))
    current_user.profile_photo = stored_name
    db.session.commit()
    flash('Foto de perfil actualitzada.', 'success')
    return redirect(url_for('profile'))


@app.route('/profile/photo/delete', methods=['POST'])
@login_required
def delete_profile_photo():
    current_user = get_current_user()
    if current_user.profile_photo:
        photo_path = os.path.join(app.config['PROFILE_PHOTO_FOLDER'], current_user.profile_photo)
        if os.path.exists(photo_path):
            try:
                os.remove(photo_path)
            except OSError:
                pass
        current_user.profile_photo = None
        db.session.commit()
        flash('Foto de perfil eliminada.', 'success')
    else:
        flash('No hi havia cap foto per eliminar.', 'info')
    return redirect(url_for('profile'))


@app.route('/profile/online', methods=['POST'])
@login_required
def update_online_visibility():
    current_user = get_current_user()
    if current_user.role != 'driver':
        flash('Aquesta opció només és per conductors.', 'warning')
        return redirect(url_for('profile'))
    current_user.online_visible = bool(request.form.get('online_visible'))
    db.session.commit()
    flash('Estat en línia actualitzat.', 'success')
    return redirect(url_for('profile'))


@app.route('/favicon.ico')
def favicon():
    return redirect(url_for('static', filename='logo.png'))


@app.route('/manifest.webmanifest')
def webmanifest():
    return app.send_static_file('manifest.webmanifest')


@app.route('/service-worker.js')
def service_worker():
    response = app.send_static_file('sw.js')
    response.headers['Service-Worker-Allowed'] = '/'
    return response


@app.route('/')
def index():
    if get_current_user():
        return redirect(url_for('dashboard'))
    return render_template('index.html', services=SERVICE_CATALOG[:5], activities=DOMUS_ACTIVITIES)


@app.route('/services')
def services():
    return render_template('services.html', services=SERVICE_CATALOG, activities=DOMUS_ACTIVITIES)


@app.route('/dashboard')
@login_required
def dashboard():
    current_user = get_current_user()
    inbox_messages = get_unread_messages(current_user, limit=5)

    if current_user.role == 'driver':
        primary_rides = [ride for ride in get_user_rides(current_user) if ride.status != 'completed']
        latest_ride = primary_rides[0] if primary_rides else None
        latest_tracker = build_ride_tracker(latest_ride) if latest_ride else None
        dashboard_mode = 'driver'
        total_rides = len(primary_rides)
        pending_rides = len([ride for ride in primary_rides if ride.status == 'pending'])
        assigned_rides = len([ride for ride in primary_rides if ride.status == 'assigned'])
        active_rides = len([ride for ride in primary_rides if ride.status in ('assigned', 'in_route')])
        finished_rides = len([ride for ride in primary_rides if ride.status == 'completed'])
        total_users = User.query.filter_by(role='driver').count()
        culture_rides = len([ride for ride in primary_rides if ride.service_type == 'Cultura'])
        health_rides = len([ride for ride in primary_rides if ride.service_type == 'Salut'])
        family_rides = len([ride for ride in primary_rides if ride.service_type == 'Familia'])
        community_rides = len([ride for ride in primary_rides if ride.service_type == 'Comunitat'])
        nature_rides = len([ride for ride in primary_rides if ride.service_type == 'Natura'])
        alerts = []
        recommendations = []
        activity_breakdown = {'Cultura': culture_rides, 'Família': family_rides, 'Salut': health_rides, 'Comunitat': community_rides, 'Natura': nature_rides}
    elif current_user.role in ('admin',):
        all_rides = Ride.query.order_by(Ride.created_at.desc()).all()
        primary_rides = [ride for ride in all_rides if ride.status != 'completed']
        latest_ride = primary_rides[0] if primary_rides else None
        latest_tracker = build_ride_tracker(latest_ride) if latest_ride else None
        dashboard_mode = 'admin'
        total_rides = len(all_rides)
        pending_rides = len([ride for ride in all_rides if ride.status == 'pending'])
        assigned_rides = len([ride for ride in all_rides if ride.status == 'assigned'])
        active_rides = len([ride for ride in all_rides if ride.status in ('assigned', 'in_route')])
        finished_rides = len([ride for ride in all_rides if ride.status == 'completed'])
        total_users = User.query.count()
        culture_rides = len([ride for ride in all_rides if ride.service_type == 'Cultura'])
        health_rides = len([ride for ride in all_rides if ride.service_type == 'Salut'])
        family_rides = len([ride for ride in all_rides if ride.service_type == 'Familia'])
        community_rides = len([ride for ride in all_rides if ride.service_type == 'Comunitat'])
        nature_rides = len([ride for ride in all_rides if ride.service_type == 'Natura'])
        alerts = []
        recommendations = []
        activity_breakdown = {'Cultura': culture_rides, 'Família': family_rides, 'Salut': health_rides, 'Comunitat': community_rides, 'Natura': nature_rides}
    else:
        insights = build_user_insights(current_user)
        primary_rides = [ride for ride in get_user_rides(current_user) if ride.status != 'completed'][:3]
        latest_ride = primary_rides[0] if primary_rides else None
        latest_tracker = build_ride_tracker(latest_ride) if latest_ride else None
        dashboard_mode = 'family'
        total_rides = insights['rides_count']
        pending_rides = len([ride for ride in primary_rides if ride.status == 'pending'])
        assigned_rides = len([ride for ride in primary_rides if ride.status == 'assigned'])
        active_rides = len([ride for ride in primary_rides if ride.status in ('assigned', 'in_route')])
        finished_rides = len([ride for ride in primary_rides if ride.status == 'completed'])
        total_users = User.query.count()
        culture_rides = insights['activity_breakdown']['Cultura']
        health_rides = insights['activity_breakdown']['Salut']
        family_rides = insights['activity_breakdown']['Família']
        community_rides = insights['activity_breakdown']['Comunitat']
        nature_rides = insights['activity_breakdown']['Natura']
        alerts = insights['alerts']
        recommendations = insights['recommendations']
        activity_breakdown = insights['activity_breakdown']

    pending_rating_prompt = None
    for completed_ride in get_user_rides(current_user):
        rating_context = build_rating_context(completed_ride, current_user)
        if rating_context['pending']:
            pending_rating_prompt = {
                'ride': completed_ride,
                'context': rating_context,
            }
            break

    return render_template(
        'dashboard.html',
        dashboard_mode=dashboard_mode,
        primary_rides=primary_rides,
        alerts=alerts,
        recommendations=recommendations,
        activity_breakdown=activity_breakdown,
        total_rides=total_rides,
        pending_rides=pending_rides,
        assigned_rides=assigned_rides,
        active_rides=active_rides,
        finished_rides=finished_rides,
        total_users=total_users,
        culture_rides=culture_rides,
        health_rides=health_rides,
        family_rides=family_rides,
        community_rides=community_rides,
        nature_rides=nature_rides,
        latest_ride=latest_ride,
        latest_tracker=latest_tracker,
        inbox_messages=inbox_messages,
        pending_rating_prompt=pending_rating_prompt,
    )


@app.route('/track/<int:ride_id>')
@login_required
def track_ride(ride_id):
    current_user = get_current_user()
    ride = Ride.query.get_or_404(ride_id)
    has_access = get_ride_access(current_user, ride)

    if not has_access:
        flash('No tens permís per veure aquest trajecte.', 'danger')
        return redirect(url_for('dashboard'))

    assigned_driver = get_assigned_driver(ride)
    vehicle = db.session.get(Vehicle, ride.assigned_vehicle) if ride.assigned_vehicle else None
    tracker = build_ride_tracker(ride)
    client = get_ride_client(ride)
    rating_context = build_rating_context(ride, current_user)
    return render_template(
        'track.html',
        ride=ride,
        assigned_driver=assigned_driver,
        vehicle=vehicle,
        tracker=tracker,
        rating_context=rating_context,
        client=client,
    )


@app.route('/api/track/<int:ride_id>')
@login_required
def api_track(ride_id):
    current_user = get_current_user()
    ride = Ride.query.get_or_404(ride_id)
    if not get_ride_access(current_user, ride):
        return jsonify({'error': 'forbidden'}), 403

    if ride.status in ('assigned', 'in_route'):
        assigned_driver_for_move = get_assigned_driver(ride)
        if assigned_driver_for_move:
            if not RideLocation.query.filter_by(ride_id=ride.id).first():
                ensure_location_for_ride(ride, assigned_driver_for_move)
            move_location_toward_destination(ride, move_factor=0.08, speed_kmh=30, heading='east')

    tracker = build_ride_tracker(ride)
    location = RideLocation.query.filter_by(ride_id=ride.id).first()
    assigned_driver = get_assigned_driver(ride)
    vehicle = db.session.get(Vehicle, ride.assigned_vehicle) if ride.assigned_vehicle else None
    return jsonify({
        'ride_id': ride.id,
        'status': ride.status,
        'requester': ride.requester,
        'service_type': ride.service_type,
        'origin': ride.origin,
        'destination': ride.destination,
        'tracker': tracker,
        'location': serialize_ride_location(location),
        'driver': {
            'name': assigned_driver.full_name if assigned_driver else None,
            'phone': assigned_driver.phone if assigned_driver else None,
        },
        'vehicle': {
            'name': vehicle.name if vehicle else None,
        },
    })


@app.route('/aura', methods=['GET', 'POST'])
@role_required('family', 'admin')
def aura():
    command_text = ''
    suggestion = suggest_from_aura_command('')
    current_user = get_current_user()
    drivers = User.query.filter_by(role='driver').order_by(User.full_name.asc()).all()
    driver_busy_map = {driver.id: has_driver_active_route(driver) for driver in drivers}
    if request.method == 'POST':
        command_text = request.form.get('command_text', '')
        suggestion = suggest_from_aura_command(command_text or request.form.get('summary_text', ''))
        preferred_driver_id = request.form.get('preferred_driver_id') or 'any'
        if preferred_driver_id != 'any':
            selected_driver = db.session.get(User, int(preferred_driver_id))
            if selected_driver and has_driver_active_route(selected_driver):
                flash('El conductor seleccionat ja té una ruta activa. Hem buscat un conductor disponible per aquesta reserva.', 'warning')
                preferred_driver_id = 'any'
        support_needs = normalize_support_needs(request.form.getlist('support_needs'))
        aura_prefill = build_aura_prefill({
            'service_type': request.form.get('service_type') or suggestion['service_type'],
            'requester': request.form.get('requester') or current_user.full_name,
            'phone': request.form.get('phone') or current_user.phone,
            'origin': request.form.get('origin', ''),
            'destination': request.form.get('destination', ''),
            'support_needs': support_needs,
            'wheelchair': request.form.get('wheelchair'),
            'command_text': command_text,
            'aura_title': suggestion['title'],
            'aura_summary': suggestion['summary'],
        })
        aura_prefill['aura_next_step'] = suggestion['next_step']
        ride = create_booking_for_user(current_user, {
            'requester': aura_prefill['requester'] or current_user.full_name,
            'phone': aura_prefill['phone'] or current_user.phone,
            'service_type': aura_prefill['service_type'],
            'origin': aura_prefill['origin'],
            'destination': aura_prefill['destination'],
            'wheelchair': bool(aura_prefill['wheelchair']),
            'vulnerable': bool(request.form.get('vulnerable')),
            'support_needs': support_needs,
            'preferred_driver_id': preferred_driver_id,
        })
        flash('AURA ha registrat la reserva automàticament.', 'success')
        return redirect(url_for('confirmation', ride_id=ride.id))

    return render_template(
        'aura.html',
        command_text=command_text,
        suggestion=suggestion,
        service_options=['Cultura', 'Familia', 'Salut', 'Comunitat', 'Natura'],
        support_options=SUPPORT_NEEDS_OPTIONS,
        drivers=drivers,
        driver_busy_map=driver_busy_map,
    )


@app.route('/book', methods=['GET', 'POST'])
@role_required('family', 'admin')
def book():
    current_user = get_current_user()
    aura_prefill = session.pop('aura_prefill', None) if request.method == 'GET' else session.get('aura_prefill')
    form_data = build_booking_form_data(current_user)
    service_type_from_query = request.args.get('service_type')
    valid_service_types = {service['service_type'] for service in SERVICE_CATALOG}
    if service_type_from_query in valid_service_types:
        form_data['service_type'] = service_type_from_query
    drivers = User.query.filter_by(role='driver').order_by(User.full_name.asc()).all()
    driver_busy_map = {driver.id: has_driver_active_route(driver) for driver in drivers}
    if aura_prefill:
        form_data['service_type'] = aura_prefill.get('service_type', form_data['service_type'])
        form_data['origin'] = aura_prefill.get('origin', form_data['origin'])
        form_data['destination'] = aura_prefill.get('destination', form_data['destination'])
        form_data['support_needs'] = aura_prefill.get('support_needs', form_data['support_needs'])
        form_data['wheelchair'] = aura_prefill.get('wheelchair', form_data['wheelchair'])

    if request.method == 'POST':
        support_needs = normalize_support_needs(request.form.getlist('support_needs'))
        form_data = {
            'requester': request.form.get('requester') or current_user.full_name,
            'phone': request.form.get('phone') or current_user.phone,
            'service_type': request.form.get('service_type') or (aura_prefill.get('service_type') if aura_prefill else 'Comunitat'),
            'origin': request.form.get('origin', '').strip(),
            'destination': request.form.get('destination', '').strip(),
            'wheelchair': bool(request.form.get('wheelchair')),
            'vulnerable': bool(request.form.get('vulnerable')),
            'support_needs': support_needs,
            'preferred_driver_id': request.form.get('preferred_driver_id') or 'any',
        }

        field_errors = {}
        if not form_data['service_type']:
            field_errors['service_type'] = 'Escull un tipus de servei.'
        if not form_data['origin']:
            field_errors['origin'] = 'Indica l’origen del trajecte.'
        if not form_data['destination']:
            field_errors['destination'] = 'Indica la destinació del trajecte.'
        if form_data['preferred_driver_id'] != 'any' and not any(str(driver.id) == str(form_data['preferred_driver_id']) for driver in drivers):
            field_errors['preferred_driver_id'] = 'Escull un conductor vàlid.'
        elif form_data['preferred_driver_id'] != 'any':
            selected_driver = db.session.get(User, int(form_data['preferred_driver_id']))
            if selected_driver and has_driver_active_route(selected_driver):
                field_errors['preferred_driver_id'] = 'Aquest conductor ja té una ruta activa. Quan la completi, es podrà tornar a seleccionar.'

        if field_errors:
            return render_template(
                'book.html',
                current_user=current_user,
                form_data=form_data,
                field_errors=field_errors,
                aura_prefill=aura_prefill,
                drivers=drivers,
                driver_busy_map=driver_busy_map,
                support_options=SUPPORT_NEEDS_OPTIONS,
            )

        ride = create_booking_for_user(current_user, form_data)
        flash('Petició registrada correctament.', 'success')
        return redirect(url_for('confirmation', ride_id=ride.id))

    return render_template('book.html', current_user=current_user, form_data=form_data, aura_prefill=aura_prefill, drivers=drivers, driver_busy_map=driver_busy_map, support_options=SUPPORT_NEEDS_OPTIONS)


@app.route('/services/<service_id>/book-now', methods=['POST'])
@role_required('family', 'admin')
def book_service_now(service_id):
    current_user = get_current_user()
    service = next((item for item in SERVICE_CATALOG if item['id'] == service_id), None)
    if not service:
        flash('Servei no trobat.', 'warning')
        return redirect(url_for('services'))

    origin = request.form.get('origin', '').strip() or 'Ubicació actual'
    destination = request.form.get('destination', '').strip() or service['use_cases'][0]
    ride = create_booking_for_user(current_user, {
        'requester': current_user.full_name,
        'phone': current_user.phone,
        'service_type': service['service_type'],
        'origin': origin,
        'destination': destination,
        'wheelchair': False,
        'vulnerable': False,
        'support_needs': [],
        'preferred_driver_id': 'any',
    })
    flash(f'Servei {service["category"]} reservat automàticament.', 'success')
    return redirect(url_for('confirmation', ride_id=ride.id))


@app.route('/confirmation/<int:ride_id>')
def confirmation(ride_id):
    ride = Ride.query.get_or_404(ride_id)
    tracker = build_ride_tracker(ride)
    assigned_driver = get_assigned_driver(ride)
    vehicle = db.session.get(Vehicle, ride.assigned_vehicle) if ride.assigned_vehicle else None
    current_user = get_current_user()
    client = get_ride_client(ride)
    rating_context = build_rating_context(ride, current_user)
    return render_template(
        'confirmation.html',
        ride=ride,
        tracker=tracker,
        assigned_driver=assigned_driver,
        vehicle=vehicle,
        rating_context=rating_context,
        client=client,
    )


@app.route('/ride/<int:ride_id>/rate', methods=['POST'])
@login_required
def rate_ride(ride_id):
    current_user = get_current_user()
    ride = Ride.query.get_or_404(ride_id)
    if ride.status != 'completed':
        flash('Només es pot valorar un trajecte completat.', 'warning')
        return redirect(url_for('track_ride', ride_id=ride.id))
    if not get_ride_access(current_user, ride):
        flash('No tens permís per valorar aquest trajecte.', 'danger')
        return redirect(url_for('dashboard'))

    assigned_driver = get_assigned_driver(ride)
    client = get_ride_client(ride)
    if not assigned_driver or not client:
        flash('Falta conductor o usuari per poder valorar.', 'warning')
        return redirect(url_for('track_ride', ride_id=ride.id))

    if current_user.id == client.id:
        rated_user = assigned_driver
        redirect_target = url_for('track_ride', ride_id=ride.id)
    elif current_user.id == assigned_driver.id:
        rated_user = client
        redirect_target = url_for('track_ride', ride_id=ride.id)
    else:
        flash('No pots valorar aquest trajecte.', 'danger')
        return redirect(url_for('dashboard'))

    try:
        score = int(request.form.get('score', 0))
    except ValueError:
        score = 0
    score = max(1, min(score, 5))
    comment = request.form.get('comment', '').strip()

    rating = get_existing_rating(ride.id, current_user.id, rated_user.id)
    if rating:
        rating.score = score
        rating.comment = comment
    else:
        rating = Rating(ride_id=ride.id, rater_user_id=current_user.id, rated_user_id=rated_user.id, score=score, comment=comment)
        db.session.add(rating)
    db.session.commit()
    flash('Valoració guardada correctament.', 'success')
    return redirect(redirect_target)


@app.route('/ruralgo-viva')
def ruralgo_viva():
    return redirect(url_for('dashboard'))


@app.route('/admin')
@role_required('admin',)
def admin():
    rides = Ride.query.order_by(Ride.created_at.desc()).all()
    vehicles = Vehicle.query.all()
    drivers = User.query.filter_by(role='driver').order_by(User.full_name.asc()).all()
    users = User.query.order_by(User.role.asc(), User.full_name.asc()).all()
    vehicle_names = {vehicle.id: vehicle.name for vehicle in vehicles}
    driver_names = {}
    tracker_data = {}
    for assignment in RideAssignment.query.all():
        driver = db.session.get(User, assignment.driver_id)
        driver_names[assignment.ride_id] = driver.full_name if driver else 'Conductor eliminado'
    for ride in rides:
        tracker_data[ride.id] = build_ride_tracker(ride)
    total_rides = len(rides)
    pending_rides = len([ride for ride in rides if ride.status == 'pending'])
    assigned_rides = len([ride for ride in rides if ride.status == 'assigned'])
    pending_documents = UserDocument.query.filter_by(status='Pendent').order_by(UserDocument.created_at.desc()).all()
    document_owners = {document.id: get_document_owner(document) for document in pending_documents}
    user_details = {}
    for user in users:
        user_rides = get_user_rides(user)
        user_documents = UserDocument.query.filter_by(user_id=user.id).order_by(UserDocument.created_at.desc()).all()
        user_details[user.id] = {
            'rides_count': len(user_rides),
            'active_count': len([ride for ride in user_rides if ride.status in ('assigned', 'in_route')]),
            'completed_count': len([ride for ride in user_rides if ride.status == 'completed']),
            'documents_count': len(user_documents),
            'pending_documents_count': len([document for document in user_documents if document.status == 'Pendent']),
            'last_seen': user.last_seen_at.strftime('%d/%m/%Y %H:%M') if user.last_seen_at else 'Sense activitat',
            'online': is_user_online(user),
        }
    return render_template(
        'admin.html',
        rides=rides,
        vehicles=vehicles,
        drivers=drivers,
        vehicle_names=vehicle_names,
        driver_names=driver_names,
        tracker_data=tracker_data,
        total_rides=total_rides,
        pending_rides=pending_rides,
        assigned_rides=assigned_rides,
        inbox_messages=get_user_messages(get_current_user(), limit=8),
        users=users,
        user_details=user_details,
        user_average_ratings={user.id: get_user_average_rating(user.id) for user in users},
        pending_documents=pending_documents,
        document_owners=document_owners,
    )


@app.route('/admin/user/<int:user_id>')
@role_required('admin',)
def admin_user_detail(user_id):
    user = User.query.get_or_404(user_id)
    user_rides = get_user_rides(user)
    documents = UserDocument.query.filter_by(user_id=user.id).order_by(UserDocument.created_at.desc()).all()
    return render_template(
        'admin_user.html',
        user=user,
        user_rides=user_rides,
        documents=documents,
        average_rating=get_user_average_rating(user.id),
        online=is_user_online(user),
    )


@app.route('/admin/user/<int:user_id>/role', methods=['POST'])
@role_required('admin',)
def admin_update_user_role(user_id):
    user = User.query.get_or_404(user_id)
    new_role = request.form.get('role', '')
    if new_role not in ('family', 'driver', 'admin'):
        flash('Rol no vàlid.', 'danger')
        return redirect(url_for('admin'))
    user.role = new_role
    db.session.commit()
    flash(f'Rol actualitzat: {user.full_name} ara és {new_role}.', 'success')
    return redirect(request.referrer or url_for('admin'))


@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@role_required('admin')
def admin_delete_user(user_id):
    current_user = get_current_user()
    user = User.query.get_or_404(user_id)

    if current_user and current_user.id == user.id:
        flash('No pots eliminar el teu propi compte des del panell.', 'warning')
        return redirect(url_for('admin_user_detail', user_id=user.id))

    if user.role == 'admin' and User.query.filter_by(role='admin').count() <= 1:
        flash('No pots eliminar l’últim administrador.', 'warning')
        return redirect(url_for('admin_user_detail', user_id=user.id))

    deleted_name = user.full_name
    was_driver = user.role == 'driver'
    delete_user_account(user)
    db.session.commit()

    if was_driver:
        flash(f'{deleted_name} eliminat. Les rutes completades queden al historial i les actives tornen a pendents.', 'success')
    else:
        flash(f'{deleted_name} eliminat amb les seves dades i reserves.', 'success')
    return redirect(url_for('admin'))


@app.route('/admin/document/<int:document_id>/review', methods=['POST'])
@role_required('admin',)
def admin_review_document(document_id):
    current_user = get_current_user()
    document = UserDocument.query.get_or_404(document_id)
    decision = request.form.get('decision', '')
    if decision not in ('approve', 'reject'):
        flash('Decisió de document no vàlida.', 'danger')
        return redirect(request.referrer or url_for('admin'))

    document.status = 'Verificat' if decision == 'approve' else 'Rebutjat'
    owner = get_document_owner(document)
    db.session.commit()

    if owner:
        create_message(
            title='Document validat' if decision == 'approve' else 'Document rebutjat',
            body=f'El document "{document.title}" ha quedat en estat: {document.status}.',
            recipient_user_id=owner.id,
            sender_user_id=current_user.id,
            sender_role=current_user.role,
            category='document',
        )
    flash(f'Document {document.status.lower()} correctament.', 'success')
    return redirect(request.referrer or url_for('admin'))


@app.route('/assign/<int:ride_id>', methods=['POST'])
@role_required('admin',)
def assign(ride_id):
    ride = Ride.query.get_or_404(ride_id)
    driver_id = request.form.get('driver_id')
    if not driver_id:
        return 'Driver required', 400

    v = assign_vehicle_for_ride(ride, mark_assigned=False)
    driver = assign_driver_for_ride(ride, driver_id=driver_id)
    if driver:
        ride.status = 'pending'
        db.session.commit()
        notify_assignment(ride, driver)
        flash(f'Trajecte #{ride.id} assignat a {driver.full_name}.', 'success')
    if v and driver:
        return redirect(url_for('admin'))
    return 'No vehicle available', 400


@app.route('/api/assign/<int:ride_id>', methods=['POST'])
@role_required('admin',)
def api_assign(ride_id):
    ride = Ride.query.get_or_404(ride_id)
    v = assign_vehicle_for_ride(ride)
    driver = assign_driver_for_ride(ride)
    if v:
        return jsonify({'ride_id': ride.id, 'vehicle': v.name, 'driver': driver.full_name if driver else None}), 200
    return jsonify({'error': 'no vehicle'}), 400


@app.route('/admin/run-migrations', methods=['POST'])
@role_required('admin',)
def admin_run_migrations():
    ensure_message_seen_column()
    ensure_user_extra_columns()
    ensure_ride_extra_columns()
    ensure_rating_table()
    flash('Migració comprovada.', 'success')
    return redirect(url_for('admin'))


@app.route('/rides')
@login_required
def rides():
    current_user = get_current_user()
    rides = get_user_rides(current_user)
    return render_template('rides.html', rides=rides)


@app.route('/messages')
@login_required
def messages():
    current_user = get_current_user()
    inbox_messages = get_user_messages(current_user)
    inbox_unread_messages = [message for message in inbox_messages if not message.seen]
    inbox_read_messages = [message for message in inbox_messages if message.seen]
    accessible_rides = get_user_rides(current_user)
    selected_ride_id = request.args.get('ride_id', type=int)
    selected_ride = None
    if selected_ride_id:
        selected_ride = next((ride for ride in accessible_rides if ride.id == selected_ride_id), None)
    if not selected_ride and accessible_rides:
        selected_ride = accessible_rides[0]
    chat_messages = get_chat_messages(selected_ride) if selected_ride else []
    selected_client = get_ride_client(selected_ride) if selected_ride else None
    selected_driver = get_assigned_driver(selected_ride) if selected_ride else None
    return render_template(
        'messages.html',
        inbox_messages=inbox_messages,
        inbox_unread_messages=inbox_unread_messages,
        inbox_read_messages=inbox_read_messages,
        message_count=len(inbox_messages),
        accessible_rides=accessible_rides,
        selected_ride=selected_ride,
        selected_client=selected_client,
        selected_driver=selected_driver,
        selected_client_online=is_user_online(selected_client),
        selected_driver_online=is_user_online(selected_driver),
        chat_messages=chat_messages,
    )


@app.route('/driver')
@role_required('driver', 'admin')
def driver_dashboard():
    current_user = get_current_user()
    if current_user.role in ('admin',):
        current_user = User.query.filter_by(role='driver').order_by(User.full_name.asc()).first() or current_user
    status_filter = request.args.get('status', 'active')
    assignments = RideAssignment.query.filter_by(driver_id=current_user.id).order_by(RideAssignment.created_at.desc()).all()
    ride_ids = [assignment.ride_id for assignment in assignments]
    rides = Ride.query.filter(Ride.id.in_(ride_ids)).order_by(Ride.created_at.desc()).all() if ride_ids else []
    if status_filter == 'active':
        rides = [ride for ride in rides if ride.status in ('pending', 'assigned', 'in_route')]
    elif status_filter != 'all':
        rides = [ride for ride in rides if ride.status == status_filter]
    assigned_clients = len(rides)
    active_routes = len([ride for ride in rides if ride.status in ('assigned', 'in_route')])
    finished_routes = len([ride for ride in rides if ride.status == 'completed'])
    vehicles_count = Vehicle.query.count()
    latest_ride = rides[0] if rides else None
    latest_tracker = build_ride_tracker(latest_ride) if latest_ride else None
    active_route_rides = [ride for ride in rides if ride.status in ('assigned', 'in_route')]
    has_active_route = bool(active_route_rides)
    active_ride_id = active_route_rides[0].id if active_route_rides else None
    ride_trackers = {ride.id: build_ride_tracker(ride) for ride in rides}
    ride_drivers = {ride.id: get_assigned_driver(ride) for ride in rides}
    ride_clients = {ride.id: get_ride_client(ride) for ride in rides}
    ride_client_insights = {}
    for ride in rides:
        client = ride_clients.get(ride.id)
        ride_client_insights[ride.id] = build_user_insights(client) if client else None
    ride_vehicles = {ride.id: (db.session.get(Vehicle, ride.assigned_vehicle) if ride.assigned_vehicle else None) for ride in rides}
    ride_locations = {ride.id: RideLocation.query.filter_by(ride_id=ride.id).first() for ride in rides}
    ride_support_summary = {ride.id: describe_support_needs(ride) for ride in rides}
    ride_client_online = {ride.id: is_user_online(ride_clients.get(ride.id)) for ride in rides}
    ride_rating_contexts = {ride.id: build_rating_context(ride, current_user) for ride in rides}

    return render_template(
        'driver.html',
        rides=rides,
        assigned_clients=assigned_clients,
        active_routes=active_routes,
        finished_routes=finished_routes,
        vehicles_count=vehicles_count,
        latest_ride=latest_ride,
        latest_tracker=latest_tracker,
        ride_trackers=ride_trackers,
        ride_drivers=ride_drivers,
        ride_clients=ride_clients,
        ride_client_insights=ride_client_insights,
        ride_vehicles=ride_vehicles,
        ride_locations=ride_locations,
        ride_support_summary=ride_support_summary,
        ride_client_online=ride_client_online,
        ride_rating_contexts=ride_rating_contexts,
        status_filter=status_filter,
        has_active_route=has_active_route,
        active_ride_id=active_ride_id,
    )


@app.route('/driver/ride/<int:ride_id>/status', methods=['POST'])
@role_required('driver')
def driver_update_ride_status(ride_id):
    current_user = get_current_user()
    ride = Ride.query.get_or_404(ride_id)
    assigned_driver = get_assigned_driver(ride)
    if not assigned_driver or assigned_driver.id != current_user.id:
        flash('Aquest trajecte no està assignat al teu compte.', 'danger')
        return redirect(url_for('driver_dashboard'))

    next_status = request.form.get('status', '')
    allowed_statuses = ['in_route', 'completed']
    if next_status not in allowed_statuses:
        flash('Estat no vàlid.', 'danger')
        return redirect(url_for('driver_dashboard'))

    ride.status = next_status
    if next_status == 'in_route' and not RideLocation.query.filter_by(ride_id=ride.id).first():
        ensure_location_for_ride(ride, current_user)
    db.session.commit()
    notify_status_change(ride, next_status, current_user)
    flash('Estat actualitzat correctament.', 'success')
    if next_status == 'completed':
        return redirect(url_for('track_ride', ride_id=ride.id))
    return redirect(url_for('driver_dashboard'))


@app.route('/driver/ride/<int:ride_id>/decision', methods=['POST'])
@role_required('driver')
def driver_decide_ride(ride_id):
    current_user = get_current_user()
    ride = Ride.query.get_or_404(ride_id)
    assigned_driver = get_assigned_driver(ride)
    if not assigned_driver or assigned_driver.id != current_user.id:
        flash('Aquest trajecte no està assignat al teu compte.', 'danger')
        return redirect(url_for('driver_dashboard'))

    decision = request.form.get('decision', '')
    if decision == 'accept':
        if has_driver_active_route(current_user):
            flash('Ja tens una ruta activa. Has de completar-la abans d’acceptar una altra.', 'warning')
            return redirect(url_for('driver_dashboard'))
        ride.status = 'assigned'
        if not RideLocation.query.filter_by(ride_id=ride.id).first():
            ensure_location_for_ride(ride, current_user)
        db.session.commit()
        notify_status_change(ride, 'assigned', current_user)
        flash('Has acceptat la ruta.', 'success')
    elif decision == 'reject':
        RideAssignment.query.filter_by(ride_id=ride.id).delete()
        ride.status = 'pending'
        ride.assigned_vehicle = None
        db.session.commit()
        create_message(
            title='Ruta rebutjada pel conductor',
            body=f'El trajecte #{ride.id} ha estat rebutjat per {current_user.full_name}.',
            recipient_role='staff',
            ride=ride,
            sender_user_id=current_user.id,
            sender_role='driver',
            category='status',
        )
        client = get_ride_client(ride)
        if client:
            create_message(
                title='El conductor no ha pogut assumir la ruta',
                body=f'El trajecte #{ride.id} encara espera un altre conductor.',
                recipient_user_id=client.id,
                ride=ride,
                sender_user_id=current_user.id,
                sender_role='driver',
                category='status',
            )
        flash('Has rebutjat la ruta.', 'info')
    else:
        flash('Decisió no vàlida.', 'danger')
    return redirect(url_for('driver_dashboard'))


@app.route('/chat/<int:ride_id>', methods=['POST'])
@login_required
def chat_send(ride_id):
    current_user = get_current_user()
    ride = Ride.query.get_or_404(ride_id)
    if not get_ride_access(current_user, ride):
        flash('No tens permís per enviar missatges en aquest trajecte.', 'danger')
        return redirect(url_for('messages'))

    body = request.form.get('body', '').strip()
    if not body:
        flash('Escriu un missatge abans d’enviar-lo.', 'warning')
        return redirect(url_for('messages', ride_id=ride.id))

    send_chat_message(ride, current_user, body)
    flash('Missatge enviat.', 'success')
    return redirect(url_for('messages', ride_id=ride.id))


@app.route('/driver/ride/<int:ride_id>/location', methods=['POST'])
@role_required('driver')
def driver_update_location(ride_id):
    current_user = get_current_user()
    ride = Ride.query.get_or_404(ride_id)
    assigned_driver = get_assigned_driver(ride)
    if not assigned_driver or assigned_driver.id != current_user.id:
        flash('Aquest trajecte no està assignat al teu compte.', 'danger')
        return redirect(url_for('driver_dashboard'))

    move_location_toward_destination(
        ride,
        move_factor=request.form.get('move_factor', 0.25),
        speed_kmh=request.form.get('speed_kmh', 28),
        heading=request.form.get('heading', 'east'),
    )

    flash('Ubicació actualitzada.', 'success')
    if ride.status == 'completed':
        return redirect(url_for('track_ride', ride_id=ride.id))
    return redirect(url_for('driver_dashboard', status=request.args.get('status', 'all')))


@app.route('/driver/ride/<int:ride_id>/tick', methods=['POST'])
@role_required('driver')
def driver_tick_location(ride_id):
    current_user = get_current_user()
    ride = Ride.query.get_or_404(ride_id)
    assigned_driver = get_assigned_driver(ride)
    if not assigned_driver or assigned_driver.id != current_user.id:
        return jsonify({'error': 'forbidden'}), 403

    location = move_location_toward_destination(ride, move_factor=0.18, speed_kmh=30, heading='east')
    tracker = build_ride_tracker(ride)
    return jsonify({
        'ride_id': ride.id,
        'status': ride.status,
        'tracker': tracker,
        'location': serialize_ride_location(location),
    })


@app.route('/reports')
@role_required('admin',)
def reports():
    return redirect(url_for('history'))


@app.route('/history')
@role_required('admin',)
def history():
    rides = Ride.query.order_by(Ride.created_at.desc()).all()
    service_counts = {}
    for ride in rides:
        service_counts[ride.service_type] = service_counts.get(ride.service_type, 0) + 1

    total_price = sum(ride.price for ride in rides)
    average_price = round(total_price / len(rides), 2) if rides else 0
    vulnerable_rides = len([ride for ride in rides if ride.vulnerable])
    viva_pass_rides = len([ride for ride in rides if ride.viva_pass])
    unique_users = User.query.count()
    family_rides = len([ride for ride in rides if ride.service_type == 'Familia'])
    culture_rides = len([ride for ride in rides if ride.service_type == 'Cultura'])
    health_rides = len([ride for ride in rides if ride.service_type == 'Salut'])
    community_rides = len([ride for ride in rides if ride.service_type == 'Comunitat'])
    nature_rides = len([ride for ride in rides if ride.service_type == 'Natura'])
    social_impact_score = (family_rides * 2) + (culture_rides * 2) + health_rides + community_rides + nature_rides
    ride_history = rides[:10]
    ride_history_clients = {
        ride.id: (get_ride_client(ride).full_name if get_ride_client(ride) else ride.requester or translate('Deleted user'))
        for ride in ride_history
    }
    ride_history_drivers = {ride.id: get_assigned_driver_label(ride) for ride in ride_history}

    return render_template(
        'reports.html',
        service_counts=service_counts,
        average_price=average_price,
        vulnerable_rides=vulnerable_rides,
        viva_pass_rides=viva_pass_rides,
        total_rides=len(rides),
        unique_users=unique_users,
        family_rides=family_rides,
        culture_rides=culture_rides,
        health_rides=health_rides,
        community_rides=community_rides,
        nature_rides=nature_rides,
        social_impact_score=social_impact_score,
        ride_history=ride_history,
        ride_history_clients=ride_history_clients,
        ride_history_drivers=ride_history_drivers,
    )


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        ensure_user_extra_columns()
        ensure_message_seen_column()
        ensure_ride_extra_columns()
        ensure_rating_table()
        seed_data()
        sync_demo_driver_names()
    debug_enabled = os.environ.get('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes', 'on')
    app.run(debug=debug_enabled, host='0.0.0.0', port=5000)
