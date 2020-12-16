from flask_mongoengine import MongoEngine
from datetime import datetime, timedelta

db = MongoEngine()

class Stat(db.Document):
    time = db.DateTimeField(required=True)
    user = db.StringField(required=True)
    workflow = db.StringField(required=True)

def daily_stat_count(user, workflow):
    return Stat.objects(user=user, workflow=workflow, time__gte=datetime.now().date(), time__lte=datetime.now().date() + timedelta(days=1)).count()