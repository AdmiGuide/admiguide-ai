from pathlib import Path
import shutil
import subprocess


class AudioCleaningError(Exception):
    """
    Erreur personnalisée utilisée lorsqu'un problème survient
    pendant le nettoyage d'un fichier audio.

    Cela permet de distinguer une erreur liée au traitement audio
    d'une autre erreur Python plus générale.
    """


def clean_audio(
    input_path: Path,
    output_path: Path,
) -> None:
    """
    Nettoie un enregistrement vocal avant sa transcription.

    Cette fonction reçoit :
    - input_path : chemin du fichier audio original enregistré
      depuis le navigateur, par exemple un fichier WebM ;
    - output_path : chemin où sera créé le fichier audio nettoyé.

    Le traitement est effectué avec FFmpeg.

    L'objectif est de préparer un audio plus propre pour Whisper :
    1. réduire une partie du bruit de fond ;
    2. supprimer les silences trop longs ;
    3. convertir l'audio en mono ;
    4. convertir la fréquence audio en 16 kHz ;
    5. produire un fichier WAV propre pour la transcription.

    Cette fonction ne fait PAS encore la transcription.
    Elle prépare uniquement l'audio.
    """

    # VÉRIFICATION DE FFMPEG

    # shutil.which("ffmpeg") cherche l'exécutable FFmpeg
    # installé sur la machine.
    #
    # S'il retourne None, cela signifie que Python
    # ne trouve pas FFmpeg dans le PATH du système.
    if shutil.which("ffmpeg") is None:
        raise AudioCleaningError(
            "FFmpeg n'est pas installé ou n'est pas accessible."
        )

    # VÉRIFICATION DU FICHIER AUDIO ORIGINAL

    # Avant de lancer FFmpeg, on vérifie que le fichier
    # reçu existe réellement sur le disque.
    #
    # Cela évite de lancer une commande FFmpeg
    # avec un chemin invalide.
    if not input_path.exists():
        raise AudioCleaningError(
            "Le fichier audio à nettoyer est introuvable."
        )

    # CONSTRUCTION DE LA COMMANDE FFMPEG

    # La variable "command" contient exactement la commande
    # que Python va demander à FFmpeg d'exécuter.
    command = [

        # Programme à utiliser.
        "ffmpeg",

        # Autorise FFmpeg à remplacer le fichier de sortie
        # s'il existe déjà.
        "-y",


        # ------------------------------------------------------
        # FICHIER AUDIO D'ENTRÉE
        # ------------------------------------------------------

        # -i signifie "input".
        #
        # FFmpeg va lire le fichier audio original,
        # généralement le fichier WebM envoyé par Angular.
        "-i",
        str(input_path),


        # ------------------------------------------------------
        # FILTRES DE NETTOYAGE AUDIO
        # ------------------------------------------------------

        # -af signifie "audio filters".
        #
        # On applique ici plusieurs traitements
        # les uns après les autres.
        "-af",

        (
            # afftdn est un filtre FFmpeg de réduction
            # du bruit audio.
            #
            # Il permet d'atténuer certains bruits de fond
            # comme un ventilateur, un souffle ou un bruit
            # relativement constant.
            "afftdn,"

            # silenceremove permet de supprimer certaines
            # périodes pendant lesquelles aucune parole
            # significative n'est détectée.
            "silenceremove="

            # Supprime le silence situé au début de l'audio.
            "start_periods=1:"

            # Il faut au moins 0,3 seconde de silence
            # pour que cette zone soit considérée
            # comme un silence à supprimer.
            "start_duration=0.3:"

            # Tout son inférieur à environ -45 dB
            # est considéré ici comme suffisamment faible
            # pour être traité comme du silence.
            "start_threshold=-45dB:"

            # -1 indique à FFmpeg de rechercher également
            # des silences au milieu et à la fin de l'audio.
            "stop_periods=-1:"

            # Un silence doit durer au moins 1,2 seconde
            # avant d'être supprimé.
            #
            # Pour conserver les petites pauses
            "stop_duration=1.2:"

            # Même seuil sonore pour les silences
            # situés pendant ou après la parole.
            "stop_threshold=-45dB"
        ),


        # ------------------------------------------------------
        # CONVERSION EN MONO
        # ------------------------------------------------------

        # -ac signifie "audio channels".
        #
        # 1 signifie qu'on conserve un seul canal audio.
        #
        # Pour une voix humaine, la stéréo n'est pas
        # nécessaire pour la transcription.
        "-ac",
        "1",


        # ------------------------------------------------------
        # FRÉQUENCE AUDIO
        # ------------------------------------------------------

        # -ar signifie "audio sample rate".
        #
        # On convertit l'enregistrement en 16 000 Hz.
        #
        # 16 kHz est une fréquence couramment utilisée
        # pour le traitement de la parole.
        "-ar",
        "16000",


        # ------------------------------------------------------
        # FICHIER DE SORTIE
        # ------------------------------------------------------

        # FFmpeg écrit ici le nouvel audio nettoyé.
        #
        # Dans notre cas, output_path sera généralement
        # un fichier avec l'extension .wav.
        str(output_path),
    ]


    # ==========================================================
    # 4. EXÉCUTION DE FFMPEG
    # ==========================================================

    try:

        # subprocess.run permet à Python d'exécuter
        # une commande système externe.
        #
        # Ici Python lance donc FFmpeg.
        subprocess.run(

            command,

            # Si FFmpeg termine avec une erreur,
            # Python déclenche automatiquement
            # une CalledProcessError.
            check=True,

            # Récupère les messages produits par FFmpeg
            # au lieu de les afficher directement
            # dans le terminal.
            capture_output=True,

            # Demande à Python de traiter ces messages
            # comme du texte et non comme des bytes.
            text=True,
        )

    except subprocess.CalledProcessError as exc:

        # Affiche dans le terminal le véritable message
        # retourné par FFmpeg afin de faciliter le diagnostic.
        print("\n========== ERREUR FFMPEG ==========")
        print(exc.stderr)
        print("===================================\n")

        raise AudioCleaningError(
            "Le nettoyage de l'audio a échoué."
        ) from exc