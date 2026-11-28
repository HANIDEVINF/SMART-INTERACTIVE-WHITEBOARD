# ============================================================
# remote.py : telecommande (2 boutons : Next / Previous)
# Une telecommande de presentation envoie des TOUCHES CLAVIER
# (en general Page Down et Page Up). On associe :
#     Next      -> clic gauche
#     Previous  -> clic droit
# ============================================================
import config


class Telecommande:
    def __init__(self, reglages):
        self.reglages = reglages

    def action(self, touche):
        """Retourne 'gauche', 'droit' ou None selon la touche recue."""
        if touche == self.reglages["touche_clic_gauche"]:
            return "gauche"
        if touche == self.reglages["touche_clic_droit"]:
            return "droit"
        return None

    def apprendre(self, cote, touche):
        """Associe une nouvelle touche au clic 'gauche' ou 'droit'."""
        self.reglages["touche_clic_" + cote] = touche
        config.sauver_reglages(self.reglages)

    def touche(self, cote):
        return self.reglages["touche_clic_" + cote]

    def par_defaut(self):
        for cote in ("gauche", "droit"):
            self.reglages["touche_clic_" + cote] = config.REGLAGES_DEFAUT["touche_clic_" + cote]
        config.sauver_reglages(self.reglages)
