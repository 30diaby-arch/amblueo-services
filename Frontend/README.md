# Frontend

- [Templates Django](templates/)
- [Mise en page commune](templates/pilot/base.html)
- [Feuille de style](static/pilot/app.css)
- [Guide utilisateur](../Documentation/guide-utilisateur.md)


## Graphiques du tableau de bord

Apache ECharts est compilé pendant la construction de l’image Docker. Pour
utiliser les graphiques avec Django lancé hors de Docker, depuis la racine :

```bash
npm --prefix Frontend ci
npm --prefix Frontend run build
```

Le fichier compilé est collecté avec les autres fichiers statiques de Django.
