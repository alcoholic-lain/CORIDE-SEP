# CoRide

**Application web de covoiturage** qui met en relation les personnes qui ont une voiture et celles qui font le même trajet, pour voyager ensemble en partageant les frais, de façon simple et sûre.

> Projet Software Engineering – 3e année Intelligence Artificielle · ESPRIT · 2026-2027
>
> Équipe **Blackberry**

---

## Le problème

Chaque jour, beaucoup de personnes font le même trajet pour aller au travail, étudier ou voyager entre les villes, souvent dans des transports en commun bondés, pendant que des voitures circulent avec des places vides.

Aujourd'hui, le covoiturage s'organise surtout dans des groupes sur les réseaux sociaux :
- aucune vérification de l'identité des conducteurs ni des papiers des voitures ;
- aucune gestion des places disponibles ;
- des prix fixés sans repère ;
- aucun moyen de savoir si un conducteur ou un passager est fiable.

## Notre solution

CoRide est une plateforme unique et sécurisée où :
- chaque utilisateur est **vérifié** à l'inscription ;
- seules les **voitures en règle** peuvent proposer des trajets ;
- les **places et les réservations** sont gérées automatiquement ;
- un **prix juste** est suggéré pour chaque trajet ;
- conducteurs et passagers peuvent **discuter** et **s'évaluer** après le trajet.

---

## Utilisateurs

| Utilisateur | Rôle |
|---|---|
| **Passager** | Cherche un trajet, réserve une place, discute avec le conducteur, donne son avis |
| **Conducteur** | Enregistre sa voiture, publie des trajets, accepte les passagers |
| **Administrateur** | Gère les comptes, vérifie les voitures, surveille les contenus |

---

## Modules et équipe

| Module | Ce qu'il permet | Responsable | Branche |
|---|---|---|---|
| **1. Gestion des utilisateurs** | Inscription, vérification de l'identité, profils, administration des comptes | | `utilisateurs` |
| **2. Gestion des véhicules** | Enregistrement des voitures et vérification de leurs papiers | | `vehicules` |
| **3. Gestion des trajets** | Publication des trajets et recherche par les passagers | | `trajets` |
| **4. Gestion des réservations** | Demande, acceptation et annulation des réservations, billet QR code | | `reservations` |
| **5. Communication et avis** | Discussion entre conducteur et passager, notes et commentaires | | `communication` |

---

Pour les guides développeur, l'état des applications et leurs spécifications, consultez [DEV.md](DEV.md).

## Intelligence artificielle

| Module | Fonctionnalité |
|---|---|
| Utilisateurs | Vérification de l'identité par selfie, contrôle des photos de profil, détection des faux comptes, assistant virtuel |
| Véhicules | Lecture automatique des papiers de la voiture |
| Trajets | Suggestion d'un prix juste pour chaque place |
| Réservations | Recommandation de trajets selon les habitudes du passager |
| Communication et avis | Blocage des messages et commentaires insultants |

---

## Planning

Le projet est réalisé avec la méthode **Scrum**, en 3 sprints de 2 semaines.

| Sprint | Objectif |
|---|---|
| **Sprint 1** | Structure du projet et fonctionnalités de base de chaque module |
| **Sprint 2** | Fonctionnalités métier : filtres, recherche avancée, pagination, rapports PDF, export Excel |
| **Sprint 3** | Intégration de l'intelligence artificielle |

---

## Impact

En remplissant les places vides des voitures, CoRide contribue à :
- **réduire le coût** des déplacements ;
- **diminuer le nombre de voitures** sur les routes et la pollution ;
- **rendre le covoiturage plus sûr** grâce à la vérification des utilisateurs.