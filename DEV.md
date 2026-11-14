# Guide de développement

## Préparation

Créez un environnement virtuel, installez les dépendances, puis lancez Django :

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Le serveur local est disponible à `http://127.0.0.1:8000/`. Exécutez les commandes depuis le dossier contenant `manage.py`.

## Structure

| Chemin | Contenu |
|---|---|
| `utilisateurs/` | Comptes et profils |
| `vehicules/` | Véhicules et documents |
| `trajets/` | Publication et recherche de trajets |
| `reservations/` | Réservations |
| `communication/` | Messagerie et avis |
| `mobile/` | Application Android |

Chaque module possède une spécification Markdown dans son dossier.

## Tester l’application Android sur le réseau local

1. Installez Android Studio, le SDK Android et un JDK compatible.
2. Connectez le téléphone et l’ordinateur au même réseau.
3. Depuis la racine du dépôt, lancez `.\run-coride.ps1` et suivez les instructions pour choisir l’adresse réseau.
4. Ouvrez `mobile/` dans Android Studio, puis lancez l’application.

L’application utilise le serveur Django configuré pour le test et conserve un accès de secours à la version hébergée. Le mode HTTP non chiffré est réservé au développement local.

## Mises à jour Android

Les changements poussés sur la branche `mobile` déclenchent le workflow Android et une nouvelle version stable. Le numéro de correctif est augmenté automatiquement.

L’application vérifie les versions stables pendant son utilisation. Lorsqu’une nouvelle version est trouvée, elle propose une fois par version d’ouvrir la page GitHub. **Open GitHub** ouvre la page de publication; **Not now** ferme le rappel. Le bouton **View update** reste disponible. L’application ne télécharge ni n’installe l’APK automatiquement.

Le workflow utilise le secret GitHub `ANDROID_DEBUG_KEYSTORE_BASE64` pour signer les APK de façon cohérente. Sans ce secret, il peut produire un artefact non destiné à une mise à jour sur un appareil déjà installé.

## Commandes utiles

```powershell
python manage.py runserver
python manage.py test
python manage.py makemigrations
python manage.py migrate
```

Avant de pousser, vérifiez les changements et exécutez les tests concernés. Les fichiers générés, secrets et bases de données locales ne doivent pas être ajoutés au dépôt.
