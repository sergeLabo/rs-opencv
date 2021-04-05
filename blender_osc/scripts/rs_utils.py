from time import time, sleep
import json
from collections import deque

import numpy as np
try:
    from scipy.signal import savgol_filter
    SCIPY = True
except:
    print("Vous devez installer scipy !")
    SCIPY = False

class Filtre:
    """Filtre les points reçus du RealSense
    piles[17][2] = deque([1.937, -0.495, 0.144, 3.24], maxlen=4)
    """

    def __init__(self, nb_points=18, pile_size=20):
        self.pile_size = pile_size
        self.nb_points = nb_points
        self.points = None

        self.piles = [0]*nb_points
        # Pour créer les queues: si créées en les définissant à la place du 0,
        # ça crée des queues qui pointent toutes vers la même queue
        for i in range(self.nb_points):  # 18
            self.piles[i] = []
            for j in range(3):
                self.piles[i].append(deque(maxlen=pile_size))

        # Filtre
        self.window_length = self.get_window_length()
        self.order = 2

    def add(self, points):
        """points = liste de 18 items, soit [1,2,3] soit None"""
        # Si pas de points, on passe
        self.points = points
        if points:
            for i in range(self.nb_points):  # 18
                if points[i]:
                    for j in range(3):  # 3
                        self.piles[i][j].append(points[i][j])

    def get_smooth_points(self):

        new_points = [0]*18
        for i in range(self.nb_points):  # 18
            if self.points:
                if self.points[i]:
                    new_points[i] = []
                    valid = True
                    for j in range(3):
                        lst = []
                        for item in self.piles[i][j]:
                            lst.append(item)
                        if len(lst) < self.window_length:
                            valid = False
                        else:
                            if SCIPY:
                                sav = savgol_filter(lst, self.window_length, self.order)
                                new_points[i].append(round(sav[-1], 3))
                            else:
                                new_points[i].append(round(self.piles[i][j][-1], 3))

                            # #if i == 4 and j == 0:
                                # #print("\n\n")
                                # #print("sav ", sav)
                                # #print("lst ", lst)
                                # #print("last sav ", round(sav[-1], 3))

                    if not valid:
                        new_points[i] = None
                else:
                    new_points[i] = None
            else:
                new_points = None

        # #try:
            # #print("pile last =", round(self.piles[4][0][-1], 3))
            # #print("new       =", round(new_points[4][0], 3))
        # #except:
            # #pass

        return new_points

    def get_window_length(self):
        """window_length=impair le plus grand dans la pile"""

        if self.pile_size % 2 == 0:
            window_length = self.pile_size - 1
        else:
            window_length = self.pile_size
        return window_length


def read_json(fichier):
    try:
        with open(fichier) as f:
            data = json.load(f)
        f.close()
    except:
        data = Nonefiltre
        print("Fichier inexistant ou impossible à lire:")
    return data


def get_points(data):
    """frame_data = list(coordonnées des points empilés d'une frame
        soit 3*18 items avec:
            mutipliées par 1000
            les None sont remplacés par (-1000000, -1000000, -1000000)
            le numéro du body (dernier de la liste) doit être enlevé
    """
    nb = 18
    if len(data) % 3 == 0 and len(data)/3 == nb:
        points = []
        for i in range(nb):
            # data[de 0 à 54] n'est jamais None car vient de l'OSC
            val = [ data[(3*i)],
                    data[(3*i)+1],
                    data[(3*i)+2]]
            if val == [-1000000, -1000000, -1000000]:
                points.append(None)
            else:
                # Less coords sont multipliées par 1000 avant envoi en OSC
                # Permutation de y et z, z est la profondeur pour RS et OpenCV
                # et inversion de l'axe des y en z
                points.append([val[0]/1000, val[2]/1000, -val[1]/1000])
    else:
        points = None
    return points


if __name__ == '__main__':

    filtre = Filtre(18, 20)
    fichier = "7.json"
    data = read_json(fichier)

    for i in range(len(data)):
        # [:-1] pour oter le numéro du body en fin de liste
        points = get_points(data[i][:-1])
        # #print("\npoints:", points)
        filtre.add(points)
        # #print("piles:", filtre.piles)
        last_points = filtre.get_smooth_points()  # impair
        print("last_points:", last_points)
