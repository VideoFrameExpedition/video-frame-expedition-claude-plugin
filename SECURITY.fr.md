[English](SECURITY.md) · **Français**

# Sécurité

## Signaler une faille

Signalez-la en privé sur GitHub : onglet **Security** de ce dépôt, puis **Report a
vulnerability**. N'ouvrez pas de ticket public pour cela.

## Ce que fait le plugin

- Il ajoute une seule entrée de serveur MCP, à l'adresse que vous avez réglée (par défaut
  `http://127.0.0.1:8765/mcp`, l'application sur cet ordinateur). Pour une application sur un
  autre ordinateur, il envoie le jeton d'accès de cette application, que Claude Code garde comme
  réglage sensible.
- Il n'a aucun hook : rien ne se lance tout seul. Les petits scripts du skill (Python, plus Windows
  PowerShell ou JavaScript for Automation sur macOS) ne s'exécutent que lorsque Claude les appelle pour une tâche que vous avez
  demandée. Ils n'appellent que l'application à cette adresse, avec des outils en lecture seule,
  et ne téléchargent rien.
- Dans DaVinci Resolve, le skill ne modifie jamais une timeline en place : il construit de
  nouvelles timelines ou travaille sur une copie, pose des marqueurs sur les clips du Media Pool,
  et n'enregistre pas le projet.
- Le texte qui vient des vidéos (paroles, textes à l'écran, descriptions) et les noms lus dans
  Resolve sont des données pour Claude, jamais des instructions.

Le modèle de sécurité de l'application elle-même est décrit dans
[son SECURITY.fr.md](https://github.com/VideoFrameExpedition/video-frame-expedition-resolve/blob/main/SECURITY.fr.md).
