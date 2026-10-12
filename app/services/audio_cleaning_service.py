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
        "ffmpeg",
        "-y",

        # Fichier audio original à traiter.
        "-i",
        str(input_path),

        # Réduction du bruit et suppression prudente
        # des silences en début et fin d'enregistrement.
        "-af",
        (
            "afftdn,"
            "silenceremove="
            "start_periods=1:"
            "start_duration=0.1:"
            "start_threshold=-55dB:"
            "start_silence=0.2:"
            "stop_periods=1:"
            "stop_duration=1.5:"
            "stop_threshold=-55dB:"
            "stop_silence=0.2"
        ),

        # Format adapté à la transcription vocale.
        "-ac",
        "1",
        "-ar",
        "16000",

        # Fichier WAV nettoyé produit par FFmpeg.
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

        raise AudioCleaningError(
            "Le nettoyage de l'audio a échoué."
        ) from exc