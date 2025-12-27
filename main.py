import discord
from discord.ext import commands
import json
import os
from discord import app_commands
import datetime
from types import FunctionType
import google.generativeai as genai

# --------- CONFIG ---------
TOKEN = "MTQzNjQyMDI1Njk4OTA1MzExMw.Ghan8_.v-fREaSEJyTW_Yxw00c2YA3XcQ506Fgbh3McoI"
INVITES_CHANNEL_ID = 1440405854452187207  # salon où le bot envoie les messages
CHAT_CHANNEL_ID = 0
SAB_CHANNEL_ID = 0

INVITES_JSON_FILE = "invites.json"
GIVEAWAYS_JSON_FILE = "giveaways.json"

intents = discord.Intents.default()
intents.members = True

# client = genai.Client()

bot = commands.Bot(command_prefix="!", intents=intents)

def save_giveaways(data):
    with open(GIVEAWAYS_JSON_FILE, "w") as f:
        json.dump(data, f)

def get_invites_count(user):
    if user:
        user_id = str(user.id)
        count = invites_count.get(user_id, 0)
        return f"{user.mention} a fait {count} invitations."
    else:
        user_id = str(user.id)
        count = invites_count.get(user_id, 0)
        return f"Tu as fait {count} invitations."
button=None
button_fonctions = []
class Button(discord.ui.View):
    label, color = None, None
    def __init__ (self, label, color, json_file:str=None, timeout=None, interaction_msg=None, onclick_code:str=None):
        super().__init__(timeout=timeout)
        self.label=label
        self.color=color
        self.onclick_code=onclick_code
        self.interaction_msg=interaction_msg
        self.json_file=json_file

        button = discord.ui.Button(label=label, style=color, custom_id="button")
        button.callback = self.on_click
        self.add_item(button)

    async def on_click(self, interaction: discord.Interaction):
        await interaction.response.send_message(self.interaction_msg, ephemeral=True)
        namespace={}
        namespace["json_file"]=self.json_file
        namespace["user"]=interaction.user
        exec(self.onclick_code, namespace)
        return True

# --------- DICTIONNAIRES ---------
invites_cache = {}  # guild_id : list(invites)
invites_count = {}  # inviter_id : nombre total d'invites

# --------- CHARGER LES INVITES DU FICHIER ---------
if os.path.exists(INVITES_JSON_FILE):
    with open(INVITES_JSON_FILE, "r") as f:
        invites_count = json.load(f)

# --------- FONCTION POUR SAUVEGARDER ---------
def save_invites():
    with open(INVITES_JSON_FILE, "w") as f:
        json.dump(invites_count, f)

# --------- AU LANCEMENT DU BOT ---------
@bot.event
async def on_ready():
    print(f"{bot.user} est connecté !")
    for guild in bot.guilds:
        try:
            invites_cache[guild.id] = await guild.invites()
        except discord.Forbidden:
            invites_cache[guild.id] = []
            print(f"⚠️ Le bot n'a pas la permission de voir les invites sur {guild.name}")
    await bot.tree.sync()
    print("Cache des invites initialisé et commandes slash synchronisées !")

# --------- QUAND UNE INVITE EST CRÉÉE ---------
@bot.event
async def on_invite_create(invite):
    guild = invite.guild
    if guild.id not in invites_cache:
        invites_cache[guild.id] = []
    print("Nouvelle invite créée :", invite.code)
    invites_cache[guild.id].append(invite)

# --------- QUAND UN MEMBRE REJOINT ---------
@bot.event
async def on_member_join(member):
    guild = member.guild
    before = invites_cache.get(guild.id, [])
    try:
        after = await guild.invites()
    except discord.Forbidden:
        after = before

    used_invite = None
    for new in after:
        for old in before:
            if new.code == old.code and new.uses > old.uses:
                used_invite = new
                break

    # mise à jour du cache
    invites_cache[guild.id] = after

    channel = bot.get_channel(INVITES_CHANNEL_ID)
    if not channel:
        print("⚠️ Salon introuvable ou ID incorrect")
        return

    if used_invite:
        inviter = used_invite.inviter
        inviter_id = str(inviter.id)

        # mettre à jour le nombre d'invites
        if inviter_id not in invites_count:
            invites_count[inviter_id] = 0
        invites_count[inviter_id] += 1
        save_invites()  # sauvegarder dans le fichier JSON

        personal_invites_button = Button(color=discord.ButtonStyle.green, label="Voir mes invitations", onclick_code="interaction.response.send_message(get_invites_count(user), ephemeral=True)", json_file=None, interaction_msg=None)
        await channel.send(
            content=f"# <a:tada:1453048315779481752> Bienvenue {member.mention} <a:tada:1453048315779481752>",
            embed=discord.Embed(title=f"{member} vient de rejoindre le serveur!", description=f"Il a été invité par <@{inviter.id}> qui a désormais {invites_count[inviter_id]} invitations! <a:pepeclap:1453682464181588065>", color=0x00ff00),
            view=personal_invites_button
        )
    else:
        await channel.send(f"👀 {member.mention} a rejoint, mais je suis incapable de déterminer qui l'a invité.")

# --------- COMMANDE SLASH /invites ---------
@bot.tree.command(name="invites", description="Voir le nombre d'invitations que vous avez faites.")
async def invites(interaction: discord.Interaction, user: discord.Member = None):
    await interaction.response.send_message(get_invites_count(user or interaction.user))

@bot.tree.command(name="topinvites", description="Voir le classement des invitations.")
async def top_invites(interaction: discord.Interaction):
    if not invites_count:
        await interaction.response.send_message("Aucune invitation enregistrée.")
        return

    sorted_invites = sorted(invites_count.items(), key=lambda x: x[1], reverse=True)
    top_message = "🏆 **Classement des invitations :**\n"
    for i, (user_id, count) in enumerate(sorted_invites[:10], start=1):
        user = interaction.guild.get_member(int(user_id))
        if user:
            top_message += f"**{i}. {user.mention}** - {count} invitations\n"
        else:
            top_message += f"**{i}. Utilisateur inconnu ({user_id})** - {count} invitations\n"

    await interaction.response.send_message(top_message)


@bot.event
async def on_message(message):
    if message.author != bot.user :
        if message.channel.id == CHAT_CHANNEL_ID:
            if "trade" in message.content.lower().content:
                message.delete()

@bot.tree.command(name="giveaway", description="Lancer un giveaway.")
@app_commands.checks.has_permissions(administrator=True)
async def giveaway(interaction : discord.Interaction, titre:str, récompense : str, durée : int, gagnants : int, salon : discord.TextChannel = None, mention : discord.Member = None, text : str = None):
    end = datetime.datetime.now() + datetime.timedelta(minutes=durée)
    embed = discord.Embed(title=titre,
                          description=f"Récompense : {récompense}\nNombre de gagnants : {gagnants}\nFin <t:{int(end.timestamp())}:R> (<t:{int(end.timestamp())}:F>)\nParticipants : {0}",
                          color=0x00ff00,)
    target_channel = salon or interaction.channel
    giveaway_button_onclick = """
import json
with open(json_file, "w") as f:
    json.dump(user, f) 
    """
    save_giveaways({"recompense": récompense, "fin": end.timestamp(), "gagnants": gagnants, "participants": []})
    giveaway_button = Button(label="Participer 🎁", color=discord.ButtonStyle.green, interaction_msg="Vous participez désormais au giveaway! 🎁", onclick_code=giveaway_button_onclick, json_file=GIVEAWAYS_JSON_FILE)
    await target_channel.send(content=f"Giveaway 🎉\n{text}\nMention(s) : {mention.mention}", embed=embed, view=giveaway_button)
    await interaction.response.send_message(f"Giveaway lancé dans {target_channel.mention}! 🎉", ephemeral=True)
''

# @bot.event
# async def on_message(message):
#     content = message.content[1:]
#     parts = content.split()
#     command = parts[0].lower()
#     args = parts[1:]

#     print(command, args)
#
# --------- LANCEMENT DU BOT ---------
bot.run(TOKEN)
