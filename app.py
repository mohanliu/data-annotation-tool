from libs.utils import to_base64
from libs.stats import db
from flask import Flask, render_template, request, redirect, url_for, send_from_directory

from workflows.tod_survey import local_bp as tod_survey_bp
from workflows.tod_report import local_bp as tod_report_bp
from workflows.size_location_survey import local_bp as size_location_survey_bp
from workflows.tsl_survey import local_bp as tsl_survey_bp
from workflows.damage_type_annotation import local_bp as damage_type_annotation_bp
from workflows.damage_type_annotation_viewresults import local_bp as tod_viewresults_bp
from workflows.tod_annotation_progress import local_bp as tod_annotation_progress

from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
from flask_mongoengine import MongoEngine

import os
import json

login_manager = LoginManager()

with open(os.path.join(
	os.path.dirname(os.path.realpath(__file__)), "user_info.json"
		), "r") as f:
	users = json.load(f)

class User(UserMixin):
	pass

@login_manager.user_loader
def user_loader(email):
	if email not in users:
		return

	user = User()
	user.id = email
	return user

@login_manager.request_loader
def request_loader(request):
	email = request.form.get("email")
	if email not in users:
		return

	if request.form["pw"] != users[email]["pw"]:
		return

	user = User()
	user.id = email
	user.is_authenticated = request.form["pw"] == users[email]["pw"]

	return user

app = Flask(__name__)
app.debug = True

app.register_blueprint(tod_survey_bp, url_prefix="/tod_survey")
app.register_blueprint(tod_report_bp, url_prefix="/tod_report")
app.register_blueprint(size_location_survey_bp, url_prefix="/size_location_survey")
app.register_blueprint(tsl_survey_bp, url_prefix="/tsl_survey")
app.register_blueprint(damage_type_annotation_bp, url_prefix="/damage_type_annotation")
app.register_blueprint(tod_viewresults_bp, url_prefix="/damage_type_annotation_results")
app.register_blueprint(tod_annotation_progress, url_prefix="/tod_annotation_progress")


app.jinja_env.globals.update(to_base64=to_base64)
app.secret_key = 'dsadrdfgdfsaee4'
login_manager.init_app(app)
app.config["MONGODB_DB"] = "photos"
app.config["DEBUG"] = True
db.init_app(app)

@app.route("/")
@login_required
def index():
	return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
	if request.method == "GET":
		return render_template(
			"login.html"
			)

	email = request.form["email"]
	if email in users and request.form["pw"] == users[email]["pw"]:
		user = User()
		user.id = email
		login_user(user)
		return redirect(url_for("index"))

	return render_template(
			"login.html",
			badlogin=True,
			)

@app.route("/logout")
def logout():
	logout_user()
	return redirect(url_for("login"))

@app.route("/test_error")
def test_error():
	x = 0
	1 / x
	return 'Error page'

@app.route("/temp_images/<path:filename>")
def base_static(filename):
    return send_from_directory(app.root_path + '/temp_images/', filename)

@login_manager.unauthorized_handler
def unauthorized_handler():
	return redirect(url_for("login"))

if __name__ == "__main__":
	app.debug = True
	app.run(host='0.0.0.0')
	# app.run(port=9000)
