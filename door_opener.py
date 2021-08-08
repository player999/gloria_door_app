#!/usr/bin/python
from flask import Flask
import json
import subprocess
from subprocess import Popen
import time
from requests.auth import HTTPDigestAuth
import flask_httpauth
import requests
import sys

app = Flask(__name__)
app.config["SECRET_KEY"] = "Get#VcP25gPN"
digest_auth = flask_httpauth.HTTPDigestAuth()

global settings
global cached_images

@digest_auth.get_password
def get_password(username: str):
    global settings
    if username in settings["users"]:
        return settings["users"].get(username)
    return None

def abort_if_invalid_camera_number(camera_no: int):
    if camera_no >= len(settings["intercom"]):
        abort(404, message="There is no intercom {}".format(camera_no))

def make_rtsp_url(intercom_no: int, is_big: bool) -> str:
    abort_if_invalid_camera_number(intercom_no)
    url = "rtsp://%s:%s@%s:554/Streaming/Channels/"%(settings["intercom"][intercom_no]["rtsp_login"],
                                                     settings["intercom"][intercom_no]["rtsp_password"],
                                                     settings["intercom"][intercom_no]["rtsp_host"])
    if is_big:
        url += "101"
    else:
        url += "102"
    return url

def get_picture(intercom_no: int, is_big: bool):
    url = make_rtsp_url(intercom_no, is_big)
    command = ["ffmpeg", "-y", "-i", url, "-vframes", "1", "-pix_fmt", "yuv420p", "-f", "mjpeg", "-"]
    p = Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    cached_images[intercom_no] = {"timestamp": time.time(), "picture": stdout}
    return stdout

def picture(camera_no: int, is_big: bool) -> str:
    abort_if_invalid_camera_number(camera_no)
    if (camera_no in cached_images.keys()) and ((time.time() - cached_images[camera_no]["timestamp"]) < 5):
        picture = cached_images[camera_no]["picture"]
    else:
        picture = get_picture(camera_no, is_big)
    return picture, 200, {'Content-Type': 'image/jpeg'}

#URLs
def description(camera_no: int):
    abort_if_invalid_camera_number(camera_no)
    return settings["intercom"][camera_no]["description"], 200, {'Content-Type': 'text/plain; charset=utf-8'}

def big_picture(camera_no: int):
    return picture(camera_no, True)

def small_picture(camera_no: int):
    return picture(camera_no, False)

def list_intercoms():
	def desc(a: dict) -> dict:
		out = {"description": a["description"]}
		if "section" in a.keys():
			out["section"] = a["section"]
		return out
	return json.dumps(list(map(desc, settings["intercom"]))), 200, {'Content-Type': 'application/json; charset=utf-8'}

def open_door(intercom_no):
    url = "http://%s/ISAPI/AccessControl/RemoteControl/door/1"%(settings["intercom"][intercom_no]["rtsp_host"])
    r = requests.put(url, data="<RemoteControlDoor><cmd>open</cmd></RemoteControlDoor>",
                      auth=HTTPDigestAuth(settings["intercom"][intercom_no]["rtsp_login"],
                                          settings["intercom"][intercom_no]["rtsp_password"]),
                      headers={'Content-Type': 'application/xml'})
    return "OK", 200, {'Content-Type': 'text/plain; charset=utf-8'}

@app.route('/auth_digest/intercoms/<int:camera_no>/description')
@digest_auth.login_required
def digest_description(camera_no: int):
    return description(camera_no)

@app.route('/auth_digest/intercoms/<int:camera_no>/big_picture')
@digest_auth.login_required
def digest_big_picture(camera_no: int):
    return big_picture(camera_no)

@app.route('/auth_digest/intercoms/<int:camera_no>/small_picture')
@digest_auth.login_required
def digest_small_picture(camera_no: int):
    return small_picture(camera_no)

@app.route('/auth_digest/intercoms/<int:intercom_no>/open_door')
@digest_auth.login_required
def digest_open_door(intercom_no: int):
    return open_door(intercom_no)

@app.route('/auth_digest/intercoms')
@digest_auth.login_required
def digest_list_intercoms():
    return list_intercoms()

if __name__ == '__main__':
    # Load configuration
    global settings
    global cached_images
    cached_images = {}
    if len(sys.argv) != 2:
        conf = "configuration.json"
    else:
        conf = sys.argv[1]
    with open(conf, "rb") as f:
        conf = f.read()
        settings = json.loads(conf.decode("utf-8", "ignore"))
        app.config["SECRET_KEY"] = settings["secret_key"]
    app.run(host="0.0.0.0", port=8050, debug=settings["debug"])
