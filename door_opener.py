#!/usr/bin/python
from flask import Flask
import json
import subprocess
from subprocess import Popen
import time
from requests.auth import HTTPDigestAuth
import requests

app = Flask(__name__)
global settings
global cached_images

def abort_if_invalid_camera_number(camera_no):
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

@app.route('/intercoms/<int:camera_no>/description')
def description(camera_no):
    abort_if_invalid_camera_number(camera_no)
    return settings["intercom"][camera_no]["description"], 200, {'Content-Type': 'text/plain; charset=utf-8'}

def picture(camera_no: int, is_big: bool) -> str:
    abort_if_invalid_camera_number(camera_no)
    if (camera_no in cached_images.keys()) and ((time.time() - cached_images[camera_no]["timestamp"]) < 5):
        picture = cached_images[camera_no]["picture"]
    else:
        picture = get_picture(camera_no, is_big)
    return picture, 200, {'Content-Type': 'image/jpeg'}

@app.route('/intercoms/<int:camera_no>/big_picture')
def big_picture(camera_no):
    return picture(camera_no, True)

@app.route('/intercoms/<int:camera_no>/small_picture')
def small_picture(camera_no):
    return picture(camera_no, False)

@app.route('/intercoms/<int:intercom_no>/open_door')
def open_door(intercom_no):
    url = "http://%s/ISAPI/AccessControl/RemoteControl/door/1"%(settings["intercom"][intercom_no]["rtsp_host"])
    r = requests.put(url, data="<RemoteControlDoor><cmd>open</cmd></RemoteControlDoor>",
                      auth=HTTPDigestAuth(settings["intercom"][intercom_no]["rtsp_login"],
                                          settings["intercom"][intercom_no]["rtsp_password"]),
                      headers={'Content-Type': 'application/xml'})
    print(r)
    return "OK", 200, {'Content-Type': 'text/plain; charset=utf-8'}

if __name__ == '__main__':
    # Load configuration
    global settings
    global cached_images
    cached_images = {}
    with open("configuration.json", "rb") as f:
        conf = f.read()
        settings = json.loads(conf.decode("utf-8", "ignore"))
    app.run(debug=True)
