# app.py
# -*- coding: utf-8 -*-
print("=== Flask app 啟動於此路徑 ===")
import os
print(os.path.abspath(__file__))

from flask import Flask, render_template, jsonify, request
from game_logic import (
    start_game,
    stop_game,
    get_status,
    set_sound_mode,
    set_mute,
    set_game_time,
    set_game_modes,
)

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True

@app.after_request
def add_no_cache_headers(resp):
    # 避免瀏覽器快取導致 UI/設定看起來「跳回預設值」
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/start")
def start():
    start_game()
    return jsonify({"msg": "round started"})

@app.route("/stop")
def stop():
    stop_game()
    return jsonify({"msg": "round stopped"})

@app.route("/status")
def status():
    return jsonify(get_status())

@app.route("/sound/<mode>")
def sound(mode):
    set_sound_mode(mode)
    return jsonify({"msg": f"sound mode set to {mode}"})

@app.route("/mute")
def mute():
    set_mute(True)
    return jsonify({"msg": "muted"})

@app.route("/unmute")
def unmute():
    set_mute(False)
    return jsonify({"msg": "unmuted"})

@app.route("/set_time", methods=["GET"])
def set_time():
    seconds = request.args.get("seconds", type=int)
    if seconds is None:
        return jsonify({"msg": "invalid seconds"}), 400
    set_game_time(seconds)
    return jsonify({"msg": f"game time set to {seconds} seconds"})

@app.route("/set_modes", methods=["GET"])
def set_modes():
    g1 = request.args.get("game1", type=int)
    g2 = request.args.get("game2", type=int)
    if g1 is None or g2 is None:
        return jsonify({"msg": "missing game1/game2"}), 400
    set_game_modes(g1, g2)
    return jsonify({"msg": f"next round modes set: game1={g1}, game2={g2}"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
