# CoRide

CoRide est une plateforme de covoiturage qui met en relation conducteurs et passagers pour des trajets plus simples, sûrs et économiques.

## Utilisateurs

- **Passagers** : recherchent un trajet et réservent une place.
- **Conducteurs** : publient leurs trajets et gèrent les réservations.
- **Administrateurs** : vérifient les comptes et modèrent la plateforme.

## Modules

| Module | Fonction | Responsable |
|---|---|---|
| Utilisateurs | Comptes, profils et vérification | Alaaeddine Guouider |
| Véhicules | Véhicules et documents | Abdallah Salhi |
| Trajets | Publication et recherche de trajets | Wasim Snoussi |
| Réservations | Places, paiements et suivi | Selim Aschi |
| Communication | Messagerie et avis | Ahmed Ridha Lazhari |

## État du projet

La plupart des modules sont encore des squelettes. Le module Communication comprend maintenant le chat invité et les fonctionnalités de retour. Consultez le journal, la spécification et l’aperçu de chaque application :

| Application | Journal | Spécification | Capture |
|---|---|---|---|
| CoRide | [AI.log](CORIDE/AI.log) | — | [Capture](CORIDE/screenshots/home.png) |
| Utilisateurs | [AI.log](utilisateurs/AI.log) | [Spécification](utilisateurs/01_user-management.md) | [Capture](utilisateurs/screenshots/users.png) |
| Véhicules | [AI.log](vehicules/AI.log) | [Spécification](vehicules/02_vehicle-management.md) | [Capture](vehicules/screenshots/vehicles.png) |
| Trajets | [AI.log](trajets/AI.log) | [Spécification](trajets/03_trip-management.md) | [Capture](trajets/screenshots/trips.png) |
| Réservations | [AI.log](reservations/AI.log) | [Spécification](reservations/04_reservation-management.md) | [Capture](reservations/screenshots/reservations.png) |
| Communication | [AI.log](communication/AI.log) | [Spécification](communication/05_communication-feedback.md) | [Capture](communication/screenshots/coms.png) |

## Fonctionnalités prévues

- Recherche de trajets et gestion des réservations.
- Vérification des comptes et des documents.
- Messagerie, évaluations et modération.
- Assistance par IA pour la vérification, les prix et les recommandations.

## Développement

Consultez [DEV.md](DEV.md) pour installer et lancer le projet.
Le client Android natif se trouve dans `mobile/`; ses instructions de test sont également documentées dans [DEV.md](DEV.md).
