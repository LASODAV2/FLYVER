import os
import datetime
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("token")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Dictionnaire des réservations : {user_id: {'creneau': ..., 'timestamp': ..., 'channel_id': ..., 'category_id': ...}}
reservations = {}

jours_semaine = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
heures = list(range(9, 21))  # 9h à 20h inclus

def creneau_pris(creneau):
    return any(data['creneau'] == creneau for data in reservations.values())

def normalize_name(name: str) -> str:
    return name.lower().replace(" ", "-")

class CancelButton(discord.ui.Button):
    def __init__(self, user_id):
        super().__init__(label="Annuler la réservation", style=discord.ButtonStyle.danger)
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Vous ne pouvez pas annuler la réservation d'un autre utilisateur.", ephemeral=True)
            return

        user_id = self.user_id
        guild = interaction.guild
        channel = interaction.channel

        if user_id not in reservations:
            await interaction.response.send_message("ℹ️ Vous n'avez aucune réservation enregistrée.", ephemeral=True)
            return

        data = reservations[user_id]

        if channel.id != data['channel_id']:
            await interaction.response.send_message("❌ Ce bouton doit être utilisé dans votre salon privé de réservation.", ephemeral=True)
            return

        archive_cat = discord.utils.get(guild.categories, name="archives")
        if not archive_cat:
            archive_cat = await guild.create_category("archives")

        try:
            await channel.edit(category=archive_cat, sync_permissions=True)
            await channel.send(f"❌ Cette réservation a été annulée par {interaction.user.mention} et archivée.")
        except Exception as e:
            print(f"Erreur lors de l'archivage du channel: {e}")

        category = guild.get_channel(data['category_id'])
        if category:
            if len(category.channels) <= 1:
                try:
                    await category.delete()
                except Exception as e:
                    print(f"Erreur lors de la suppression de la catégorie: {e}")

        del reservations[user_id]

        await interaction.response.send_message(f"❌ Votre réservation pour **{data['creneau']}** a été annulée et archivée.", ephemeral=True)

        staff_channel = discord.utils.get(guild.text_channels, name="vols-confirmés")
        if staff_channel:
            await staff_channel.send(f"❌ **Annulation** : {interaction.user.mention} a annulé sa réservation ({data['creneau']})")

class JourSelect(discord.ui.Select):
    def __init__(self, parent_view):
        self.parent_view = parent_view
        options = [discord.SelectOption(label=jour, value=jour) for jour in jours_semaine]
        super().__init__(placeholder="Choisissez un jour", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        self.parent_view.jour_choisi = self.values[0]
        self.parent_view.heure_choisi = None

        options_heure = []
        for h in heures:
            creneau_test = f"{self.parent_view.jour_choisi} {h}h - {h+1}h"
            if creneau_pris(creneau_test):
                label = f"{h}h - {h+1}h (Pris)"
            else:
                label = f"{h}h - {h+1}h"
            options_heure.append(discord.SelectOption(label=label, value=str(h)))

        self.parent_view.heure_select.options = options_heure
        await interaction.response.edit_message(view=self.parent_view)

class HeureSelect(discord.ui.Select):
    def __init__(self, parent_view):
        self.parent_view = parent_view
        options = [discord.SelectOption(label=f"{h}h - {h+1}h", value=str(h)) for h in heures]
        super().__init__(placeholder="Choisissez une heure", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if not self.parent_view.jour_choisi:
            await interaction.response.send_message("⚠️ Veuillez d'abord choisir un jour.", ephemeral=True)
            return

        heure = int(self.values[0])
        creneau_choisi = f"{self.parent_view.jour_choisi} {heure}h - {heure+1}h"

        if creneau_pris(creneau_choisi):
            await interaction.response.send_message("❌ Ce créneau est déjà réservé, veuillez en choisir un autre.", ephemeral=True)
            return

        user_id = interaction.user.id
        guild = interaction.guild

        if user_id in reservations:
            await interaction.response.send_message("❌ Vous avez déjà une réservation. Annulez-la avant d'en prendre une autre.", ephemeral=True)
            return

        now = datetime.datetime.utcnow()

        # Nom catégorie et channel : <pseudo>-<jour>-<heure>h
        pseudo = normalize_name(interaction.user.name)
        jour_norm = normalize_name(self.parent_view.jour_choisi)
        cat_name = f"{pseudo}-{jour_norm}-{heure}h"

        overwrites_cat = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True),
        }
        category = await guild.create_category(cat_name, overwrites=overwrites_cat)

        overwrites_chan = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        channel = await guild.create_text_channel(cat_name, category=category, overwrites=overwrites_chan)

        reservations[user_id] = {
            'creneau': creneau_choisi,
            'timestamp': now,
            'channel_id': channel.id,
            'category_id': category.id
        }

        cancel_button = CancelButton(user_id=user_id)
        view = discord.ui.View()
        view.add_item(cancel_button)

        await channel.send(
            f"✅ Bonjour {interaction.user.mention}, votre réservation pour le créneau **{creneau_choisi}** est confirmée.",
            view=view
        )

        await interaction.response.send_message(
            f"✅ Réservation confirmée pour **{creneau_choisi}**. Salon privé créé : {channel.mention}",
            ephemeral=True
        )

        staff_channel = discord.utils.get(guild.text_channels, name="vols-confirmés")
        if staff_channel:
            await staff_channel.send(f"📅 **Nouvelle réservation** : {interaction.user.mention} a réservé **{creneau_choisi}**. Salon privé : {channel.mention}")

        # Reset de la vue
        self.parent_view.jour_choisi = None
        self.parent_view.heure_choisi = None
        self.parent_view.jour_select.placeholder = "Choisissez un jour"
        options_heure = [discord.SelectOption(label=f"{h}h - {h+1}h", value=str(h)) for h in heures]
        self.parent_view.heure_select.options = options_heure
        try:
            await interaction.message.edit(view=self.parent_view)
        except:
            pass

class ReservationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.jour_choisi = None
        self.heure_choisi = None

        self.jour_select = JourSelect(self)
        self.heure_select = HeureSelect(self)

        self.add_item(self.jour_select)
        self.add_item(self.heure_select)

@bot.command()
async def flyver(ctx):
    view = ReservationView()
    await ctx.send("🛫 Bienvenue chez **Flyver** ! Choisissez un jour puis une heure :", view=view)

@tasks.loop(minutes=10)
async def verifier_archives():
    now = datetime.datetime.utcnow()
    if not bot.guilds:
        return
    guild = bot.guilds[0]
    archive_cat = discord.utils.get(guild.categories, name="archives")
    if not archive_cat:
        archive_cat = await guild.create_category("archives")

    to_archive = [uid for uid, data in reservations.items() if (now - data['timestamp']).total_seconds() > 86400]

    for user_id in to_archive:
        data = reservations.pop(user_id)
        user = guild.get_member(user_id)
        if not user:
            continue

        channel = guild.get_channel(data['channel_id'])
        if channel:
            await channel.edit(category=archive_cat, sync_permissions=True)
            await channel.send(
                f"📦 **Votre réservation a été archivée automatiquement après 24h**.\n\n"
                f"**Créneau réservé** : {data['creneau']}\nMerci d’avoir volé avec Flyver ✈️ !"
            )

        category = guild.get_channel(data['category_id'])
        if category:
            try:
                await category.delete()
            except Exception as e:
                print(f"Erreur lors de la suppression de la catégorie: {e}")

@bot.event
async def on_ready():
    print(f"Connecté en tant que {bot.user}")
    verifier_archives.start()

bot.run(TOKEN)
