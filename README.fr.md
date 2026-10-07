[English](README.md) · **Français**

# Plugin Video Frame Expedition pour Claude Code

Un plugin qui relie Claude Code à
[Video Frame Expedition for DaVinci Resolve](https://github.com/VideoFrameExpedition/video-frame-expedition-resolve/blob/main/README.fr.md),
une application locale qui analyse vos rushs avec un modèle de vision local, pour qu'un assistant
IA monte dans DaVinci Resolve en sachant ce que contient chaque plan.

Il apporte deux choses :
- **la connexion au serveur MCP de l'application** (`vfe-vision`, 25 outils) : analyses,
  recherche sémantique dans toute la bibliothèque, points de coupe sûrs, recadrages, et les outils
  DaVinci Resolve de l'application (lire la timeline ouverte, préparer un recadrage, construire une
  nouvelle timeline, poser des marqueurs) ;
- **un skill, `resolve-editing`**, qui donne la méthode à Claude : relier la timeline ouverte aux
  analyses, choisir les plans, écrire une liste de montage, obtenir des coupes sûres, construire ou
  modifier le montage dans une nouvelle timeline, recadrer pour un autre format, poser des
  marqueurs. Il contient les règles et les pièges mesurés de l'API de scripts de DaVinci Resolve
  Studio 21.1, et des modèles de scripts testés.

## Prérequis

- **Video Frame Expedition for DaVinci Resolve 1.1.1 ou plus récente**, installée et lancée,
  sous Windows 11 ou sur un Mac à puce Apple Silicon : voir
  [son README](https://github.com/VideoFrameExpedition/video-frame-expedition-resolve/blob/main/README.fr.md). LM Studio peut tourner sur le même ordinateur ou
  sur un autre, sous Windows, macOS ou Linux.
- **Claude Code**, sur l'ordinateur de l'application ou sur un autre (réglages ci-dessous).
- Pour monter : **DaVinci Resolve Studio 21.1 ou plus récent**, sous Windows, macOS ou Linux.
  Avec la case « Outils Resolve pour l'assistant » (page Connexions), l'application pilote
  Resolve même sur un autre ordinateur : l'assistant IA, l'application et Resolve peuvent être
  sur trois ordinateurs différents. Pour le reste (fondus enchaînés, effets), le serveur MCP de
  DaVinci Resolve Studio ne pilote que le Resolve de son propre ordinateur : ajoutez-le à Claude
  Code sur cet ordinateur-là (Resolve le propose dans son menu Fichier, « Setup AI Assistants »
  dans l'interface anglaise).
- Pour les petits scripts du skill : Python 3, avec Windows PowerShell sous Windows ou
  `osascript` (fourni avec macOS) sur un Mac.

## Installation

Dans Claude Code :

```text
/plugin marketplace add VideoFrameExpedition/video-frame-expedition-claude-plugin
/plugin install video-frame-expedition@video-frame-expedition
```

Puis confirmez les réglages avec `/plugin configure video-frame-expedition@video-frame-expedition` :

| Réglage | Valeur |
|---|---|
| Adresse de l'application | `http://127.0.0.1:8765/mcp` (par défaut) quand l'application tourne sur cet ordinateur ; sinon son adresse sur votre réseau local ou Tailscale, par exemple `http://100.64.12.34:8765/mcp` |
| Jeton d'accès | Laissez-le vide sur l'ordinateur de l'application. Depuis un autre ordinateur : le jeton affiché dans la page Connexions de l'application (rangé dans le coffre de mots de passe du système) |

Si vous aviez déjà ajouté le serveur vous-même (`claude mcp add … vfe-vision`), retirez cette
entrée pour que Claude Code garde une seule connexion.

## Utilisation

Demandez avec vos mots, par exemple :
- « Regarde la timeline ouverte dans Resolve et dis-moi ce que contient chaque plan. »
- « Monte 45 secondes avec les vidéos du lac, avec des coupes sûres. »
- « Fais une version 9:16 de cette timeline, cadrée sur les personnes. »

Claude prend le skill de lui-même quand une demande porte sur un montage dans Resolve ; vous
pouvez aussi l'appeler avec `/video-frame-expedition:resolve-editing`.

Claude ne modifie jamais votre timeline en place : les outils de l'application construisent une
nouvelle timeline, et le skill duplique une timeline avant de la changer. Le projet n'est pas
enregistré à votre place : enregistrez-le dans Resolve si vous gardez le montage.

## Ce que le plugin contacte

Seulement l'application, à l'adresse que vous avez réglée. Les petits scripts du skill appellent
la même adresse (outils en lecture seule). Le serveur MCP de DaVinci Resolve, si vous l'ajoutez,
est indépendant de ce plugin. Rien d'autre n'est téléchargé ni envoyé.

Le plugin n'a aucun hook : rien ne se lance tout seul. Les scripts du skill (Python, plus
PowerShell sous Windows ou JavaScript for Automation sur macOS) ne s'exécutent que lorsque Claude
les appelle pour une tâche que vous avez demandée, et ne téléchargent
rien. Pour signaler une faille : [SECURITY.fr.md](SECURITY.fr.md).

## Licence

[Licence Apache 2.0](LICENSE) (texte officiel en anglais). Voir aussi [NOTICE](NOTICE).

Projet indépendant, ni affilié à Blackmagic Design ou à Anthropic, ni approuvé par eux ; DaVinci
Resolve et Claude sont des marques de leurs propriétaires respectifs.
