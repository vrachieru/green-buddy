from os import environ, path

from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy

from flowercare import FlowerCare

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

project_dir = path.dirname(path.abspath(__file__))
database_file = "sqlite:///{}".format(path.join(project_dir, "database.db"))

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = database_file

db = SQLAlchemy(app)

scheduler = BackgroundScheduler(daemon=True)
scheduler.start()


class Plant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True, nullable=False, primary_key=False)

class Sensor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String, unique=True)
    plant_id = db.Column(db.Integer, db.ForeignKey('plant.id'))

class Measurement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plant_id = db.Column(db.Integer, db.ForeignKey('plant.id'))
    timestamp = db.Column(db.DateTime(), unique=False, nullable=False, primary_key=False)
    temperature = db.Column(db.Float(), unique=False, nullable=False, primary_key=False)
    moisture = db.Column(db.Float, unique=False, nullable=False, primary_key=False)
    light = db.Column(db.Float, unique=False, nullable=False, primary_key=False)
    conductivity = db.Column(db.Float, unique=False, nullable=False, primary_key=False)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/<period>')
def periodd(period):
    return render_template('index.html', period=period)

@app.route('/json')
def json():
    periods = {
        'day':   24,
        'week':  24 * 7,
        'month': 24 * 7 * 30,
        'year':  24 * 7 * 365
    }

    period = request.args.get('period')
    size = periods.get(period, 24)

    entries = list(reversed(Measurement.query.order_by(Measurement.timestamp.desc()).limit(size).all()))
    timestamps = [entry.timestamp.strftime('%H:%M') for entry in entries]
    temperature = [entry.temperature for entry in entries]
    moisture = [entry.moisture for entry in entries]
    light = [entry.light for entry in entries]
    conductivity = [entry.conductivity for entry in entries]
    
    return render_template('json.html', timestamps=timestamps, temperature=temperature, moisture=moisture, light=light, conductivity=conductivity)

@app.route('/poll')
@scheduler.scheduled_job(id='poll_sensors', trigger=CronTrigger.from_crontab(environ.get('POLL_SENSORS_CRON', '0 */12 * * *')))
def poll_sensors():
    sensor = FlowerCare(mac=environ['FLOWERCARE_MAC'])
    latest = db.session.query(Measurement).order_by(Measurement.timestamp.desc()).first()
    
    if latest:
        print ('Last measurement in db %s:%s' % (latest.id, latest.timestamp))

    for entry in sensor.historical_data:
        if latest == None or latest.timestamp < entry.timestamp:
            try:
                print ('Inserting entry from %s' % entry.timestamp)
                db.session.add(Measurement(**entry.__dict__))
                db.session.commit()
            except Exception as e:
                print(e)
    return 'ok'

@app.route('/db/initialize')
def initialize_db():
  db.create_all()
  return 'OK'


if __name__ == '__main__':
    app.jinja_env.auto_reload = True
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.run(host='0.0.0.0', port=5000)
