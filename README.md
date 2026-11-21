# Smart Interactive Whiteboard (Python + NumPy + OpenCV)

## Installation
    pip install -r requirements.txt

## Lancer
    python main.py --sim          # test sans camera (souris = pointeur, clic gauche/droit = Next/Previous)
    python main.py --fullscreen   # mode reel (fenetre UI plein ecran sur le projecteur)

## Ordre de mise en place (mode reel)
1. `python identify_keys.py` -> releve les codes des 2 boutons de la telecommande (keymap.json).
2. `python main.py` -> la 1re fois, calibration : cliquer les 4 croix projetees (HG, HD, BD, BG) dans la vue camera.
   Cliquer ensuite sur d'autres points de la grille : l'erreur de validation s'affiche. ENTREE = sauver.
3. Touche `m` (ou Settings > Pick marker color) : cliquer sur le marqueur pour regler sa couleur.
4. Raccourcis : c = recalibrer, m = couleur, d = vue camera, q = quitter.

## Architecture (chaque fichier = une tache)
| Fichier | Role |
|---|---|
| config.py | constantes et reglages |
| camera.py | acquisition video |
| detection.py | HSV, seuillage, morphologie, centroide, lissage (NumPy) |
| mapping.py | homographie DLT/SVD, BoardMapper image<->tableau |
| calibration.py | calibration interactive coins + couleur du marqueur |
| remote_input.py / identify_keys.py | boutons telecommande -> "left"/"right" |
| ui.py | primitives de dessin + Button |
| screens.py | menus, dessin, images/zoom, cours, reglages |
| app.py | etat global, pile d'ecrans, clics |
| main.py | boucle : camera -> detection -> mapping -> UI -> telecommande -> clic |

## Interaction
Next = clic gauche (selection ; en dessin : stylo pose/leve). Previous = clic droit (retour ; en dessin : leve le stylo ; en cours : diapo precedente).
Mettre des images dans `images/` (sinon 2 images de demo sont generees).

## Limites a mentionner dans le rapport
Marqueur confondu avec un objet de meme couleur ; sensibilite a l'eclairage ; pas de correction de distorsion de l'objectif (homographie plane seulement) ; la fenetre OpenCV doit avoir le focus pour recevoir la telecommande (sinon REMOTE_BACKEND = "pynput").
