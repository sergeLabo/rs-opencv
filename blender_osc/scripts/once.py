
from time import time
import json

from bge import logic as gl
from scripts.utils import get_all_objects, add_object, read_json
from scripts.rs_utils import Filtre, get_points

from oscpy.server import OSCThreadServer


def default_handler(*args):
    print("default_handler", args)


def on_points(*args):
    body = args[-1]
    args = args[:-1]

    gl.points = get_points(args)
    gl.new = 1
    # Durée en frame depuis la dernière réception
    gl.tempo = gl.frame_number - gl.receive_at
    gl.receive_at = gl.frame_number


def parts(args, n):
    points = []
    nb = 18
    # #print(args)
    for i in range(nb):
        points.append([args[n*i], args[n*i+1]])
    # #print(points)
    return points


def osc_server_init():
    gl.server = OSCThreadServer()
    gl.server.listen('0.0.0.0', port=8003, default=True)
    # Les callbacks du serveur
    gl.server.default_handler = default_handler
    gl.server.bind(b'/points', on_points)


def main():
    print("Lancement de once.py ...")

    gl.all_obj = get_all_objects()
    gl.cube = gl.all_obj["Cube"]
    gl.metarig = gl.all_obj["metarig"]
    gl.person = gl.all_obj["person"]

    gl.spheres = []
    # 18 est le  body au centre de 11 et 12
    # 19 est le centre des yeux pour la tête
    for i in ["00", "01", "02", "03", "04", "05", "06", "07", "08", "09",
                "10", "11", "12", "13", "14", "15", "16", "17", "18", "19"]:
        gl.spheres.append(gl.all_obj[i])

    # AA sur Text
    for obj_name, obj in gl.all_obj.items():
        if "Text" in obj_name:
            obj.resolution = 64

    gl.t = time()
    gl.fps = 0
    gl.server = None
    gl.points = None
    gl.frame_number = 0
    gl.nums = 20
    gl.new = 0
    gl.receive_at = 0
    gl.tempo = 0
    gl.body_visible = 1
    gl.person.visible = 0

    gl.debug = 1  # 1=avec fichier enregistré
    if gl.debug:
        gl.data_4 = read_json("./scripts/4.json")
        print("Nombre de frame 4 =", len(gl.data_4))
        gl.data_7 = read_json("./scripts/7.json")
        print("Nombre de frame 7 =", len(gl.data_7))
        gl.data_14 = read_json("./scripts/14.json")
        print("Nombre de frame 14 =", len(gl.data_14))
        gl.data_big = read_json("./scripts/cap_2021_04_03_14_44_fps_14.json")
        print("Nombre de frame big =", len(gl.data_big))
        gl.data = gl.data_4
    else:
        osc_server_init()

    # Le filtre Savonarol Brigowski de scipy
    gl.filtre = Filtre(18, 20)

    # Placement et échelle dans la scène
    gl.scale = 1
    gl.up_down = 1.5
    gl.left_right = 0.2
    gl.av_ar = -2.5
