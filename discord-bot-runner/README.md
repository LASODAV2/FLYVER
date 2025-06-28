# Discord Bot Runner (Railway 24/7)

Un bot Discord simple permettant d'exécuter des commandes système via `!run`.

## ✅ Fonctionnalités

- Commande `!run` pour exécuter du code (bash, python, etc.)
- Commande `!ping` de test
- Exécution sécurisée avec timeout 10s

## 🚀 Déploiement sur Railway

1. Fork ce repo
2. Va sur [https://railway.app](https://railway.app)
3. "New Project" > "Deploy from GitHub repo"
4. Ajoute une variable :
   - `DISCORD_TOKEN` = ton token secret Discord
5. Railway détecte `main.py` et `requirements.txt`, puis lance automatiquement

## 🔐 Sécurité

Tu peux remplacer :
```python
if ctx.author.id != ctx.bot.owner_id
```
par ton propre ID Discord si tu veux restreindre l'accès.

## 🧠 À savoir

- Compatible Railway (hébergement 24/24)
- Code Python simple et léger
