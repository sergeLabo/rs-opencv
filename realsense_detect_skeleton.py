
import math
from time import time, sleep
from json import dumps
from datetime import datetime

import numpy as np
import cv2

from oscpy.client import OSCClient

import pyrealsense2 as rs

client = OSCClient(b'localhost', 8003)

kernel_size = 5
threshold = 0.1
in_width  = 160
in_height = 160
MEAN = 0.3
SCALE = 1/255
MODE = "COCO"
CALC = "cpu"

if MODE == "COCO":
    protoFile = "pose/coco/pose_deploy_linevec.prototxt"
    weightsFile = "pose/coco/pose_iter_440000.caffemodel"
    num_points = 18
    POSE_PAIRS = [ [1,0],[1,2],[1,5],[2,3],[3,4],[5,6],[6,7],[1,8],[8,9],[9,10],
                        [1,11],[11,12],[12,13],[0,14],[0,15],[14,16],[15,17]]

elif MODE == "MPI" :
    protoFile = "pose/mpi/pose_deploy_linevec_faster_4_stages.prototxt"
    weightsFile = "pose/mpi/pose_iter_160000.caffemodel"
    num_points = 15
    POSE_PAIRS = [[0,1], [1,2], [2,3], [3,4], [1,5], [5,6], [6,7], [1,14],
                    [14,8], [8,9], [9,10], [14,11], [11,12], [12,13] ]

net = cv2.dnn.readNetFromCaffe(protoFile, weightsFile)

if CALC == "cpu":
    net.setPreferableBackend(cv2.dnn.DNN_TARGET_CPU)
    print("Using CPU device")

elif CALC == "gpu":
    net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
    net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)
    print("Using GPU device")

def save_json(fichier, data):
    with open(fichier, "w") as fd:
        fd.write(dumps(data))
    fd.close()

def get_blobFromImage(frame):
    """
    blobFromImage   (   InputArray      image,
        double      scalefactor = 1.0,
        const Size &    size = Size(),
        const Scalar &      mean = Scalar(),
        bool    swapRB = false,
        bool    crop = false,
        int     ddepth = CV_32F )
        inpBlob = cv2.dnn.blobFromImage(frame, 1.0/255, (in_width, in_height),
                    (0, 0, 0), swapRB=False, crop=False, ddepth=cv2.CV_32F)
    """
    inpBlob = cv2.dnn.blobFromImage(frame,
                                    scalefactor=SCALE,
                                    size=(in_width, in_height),
                                    mean=MEAN,  # in (mean-R, mean-G, mean-B) order
                                    swapRB=True,
                                    crop = False,
                                    ddepth = cv2.CV_32F)
    return inpBlob


pipeline = rs.pipeline()
config = rs.config()

pipeline_wrapper = rs.pipeline_wrapper(pipeline)
pipeline_profile = config.resolve(pipeline_wrapper)
device = pipeline_profile.get_device()
device_product_line = str(device.get_info(rs.camera_info.product_line))

if device_product_line == 'L500':
    config.enable_stream(rs.stream.color, 960, 540, rs.format.bgr8, 30)
else:
    config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
    config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)

pipeline.start(config)

align = rs.align(rs.stream.color)

unaligned_frames = pipeline.wait_for_frames()
frames = align.process(unaligned_frames)
depth = frames.get_depth_frame()
depth_intrinsic = depth.profile.as_video_stream_profile().intrinsics

t0 = time()
n = 0
data = []  # Pour enregistrement d'un json
cv2.namedWindow('RealSense', cv2.WINDOW_AUTOSIZE)

try:
    while True:
        unaligned_frames = pipeline.wait_for_frames()
        frames = align.process(unaligned_frames)
        color_frame = frames.get_color_frame()
        depth_frame = frames.get_depth_frame()
        if not color_frame or not depth_frame:
            continue

        depth = np.asanyarray(depth_frame.get_data())
        frame = np.asanyarray(color_frame.get_data())
        frameWidth = frame.shape[1]
        frameHeight = frame.shape[0]
        inpBlob = get_blobFromImage(frame)

        net.setInput(inpBlob)

        output = net.forward()

        H = output.shape[2]
        W = output.shape[3]

        # Pour ajouter tous les points en 2D et 3D, y compris None
        points2D = []
        points3D = []

        for num_point in range(num_points):
            # confidence map of corresponding body's part.
            probMap = output[0, num_point, :, :]

            # Find global maxima of the probMap.
            minVal, prob, minLoc, point = cv2.minMaxLoc(probMap)

            # Scale the point to fit on the original image
            x = int(((frameWidth * point[0]) / W) + 0.5)
            y = int(((frameHeight * point[1]) / H) + 0.5)

            if prob > threshold :  # 0.1
                points2D.append([x, y])
                kernel = []
                x_min = max(x - kernel_size, 0)  # mini à 0
                x_max = max(x + kernel_size, 0)
                y_min = max(y - kernel_size, 0)
                y_max = max(y + kernel_size, 0)
                for u in range(x_min, x_max):
                    for v in range(y_min, y_max):
                        kernel.append(depth_frame.get_distance(u, v))
                # Equivaut à median si 50
                median = np.percentile(np.array(kernel), 50)

                pt = None
                point_with_deph = None
                if median >= 0.05:
                    # DepthIntrinsics, InputPixelAsFloat, DistanceToTargetInDepthScale)
                    # Coordonnées du point dans un repère centré sur la caméra
                    # 3D coordinate space with origin = Camera
                    point_with_deph = rs.rs2_deproject_pixel_to_point(
                                                            depth_intrinsic,
                                                            [x, y],
                                                            median)
                if point_with_deph:
                    points3D.append(point_with_deph)
                else:
                    points3D.append(None)
            else:
                points2D.append(None)
                points3D.append(None)

        # #print("3", points3D)
        # Envoi du point en OSC en 3D
        # Liste de n°body puis toutes les coordonnées sans liste de 3
        # oscpy n'envoie pas de liste de listes
        bodyId = 110  # TODO récupérer le vrai nums de body
        msg = []
        for point in points3D:
            if point:
                for i in range(3):
                    # Envoi en int
                    msg.append(int(point[i]*1000))
            # Si pas de point ajout arbitraire de 3 fois -1 pour avoir toujours
            # 3*18 valeurs dans la liste
            else:
                msg.extend((-1000000, -1000000, -1000000))  # tuple ou list

        # N° body à la fin
        msg.append(bodyId)
        data.append(msg)
        client.send_message(b'/points', msg)

        # Draw articulation 2D
        for point in points2D:
            if point:
                cv2.circle(frame, (point[0], point[1]), 4, (0, 255, 255),
                            thickness=2)


        # Draw Skeleton
        for pair in POSE_PAIRS:
            if points2D[pair[0]] and points2D[pair[1]]:
                p1 = tuple(points2D[pair[0]])
                p2 = tuple(points2D[pair[1]])
                cv2.line(frame, p1, p2, (0, 255, 0), 2)

        cv2.imshow('RealSense', frame)

        n += 1
        t = time()
        if t - t0 > 10:
            print("FPS =", round(n/10, 1))
            t0 = t
            n = 0
        if cv2.waitKey(1) == 27:
            break

    cv2.destroyAllWindows()

finally:
    pipeline.stop()

sleep(1)

dt_now = datetime.now()
dt = dt_now.strftime("%Y_%m_%d_%H_%M")
fichier = f"./blender_osc/scripts/cap_{dt}.json"
save_json(fichier, data)
