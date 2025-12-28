import discord
from discord.ext import commands
import json
import os
from discord import app_commands
import datetime
from types import FunctionType
from discord.utils import utcnow

# --------- CONFIG ---------
TOKEN = "MTQzNjQyMDI1Njk4OTA1MzExMw.Ghan8_.v-fREaSEJyTW_Yxw00c2YA3XcQ506Fgbh3McoI"
INVITES_CHANNEL_ID = 1440405854452187207  # salon où le bot envoie les messages
CHAT_CHANNEL_ID = 0
SAB_CHANNEL_ID = 0
LEAVS_CHANNEL_ID = 1445785148011446323

INVITES_JSON_FILE = "invites.json"
GIVEAWAYS_JSON_FILE = "giveaways.json"
MEMBER_INVITER_FILE = "member_inviter.json"

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

# client = genai.Client()

bot = commands.Bot(command_prefix="-", intents=intents)

# --------- CHARGER LES INVITES DU FICHIER ---------
if os.path.exists(INVITES_JSON_FILE):
    with open(INVITES_JSON_FILE, "r") as f:
        try:
            invites_count = json.load(f)
        except json.JSONDecodeError:
            invites_count = {}
else:
    invites_count = {}

# charger mapping member -> inviter
if os.path.exists(MEMBER_INVITER_FILE):
    with open(MEMBER_INVITER_FILE, "r") as f:
        try:
            member_inviter = json.load(f)
        except json.JSONDecodeError:
            member_inviter = {}
else:
    member_inviter = {}

# --------- FONCTION POUR SAUVEGARDER ---------
def save_invites():
    with open(INVITES_JSON_FILE, "w") as f:
        json.dump(invites_count, f)

def save_giveaways(data):
    with open(GIVEAWAYS_JSON_FILE, "w") as f:
        json.dump(data, f)

def save_member_inviter():
    with open(MEMBER_INVITER_FILE, "w") as f:
        json.dump(member_inviter, f)

def get_invites_count(user, personal:bool=False):
    if not personal:
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
    def __init__ (self, label, color, json_file:str=None, timeout=None, interaction_msg=None, onclick_code=None, callback=None):
        super().__init__(timeout=timeout)
        self.label=label
        self.color=color
        self.onclick_code=onclick_code
        self.interaction_msg=interaction_msg
        self.json_file=json_file
        self.callback=callback

        button = discord.ui.Button(label=label, style=color, custom_id="button")
        button.callback = self.on_click
        self.add_item(button)

    async def on_click(self, interaction: discord.Interaction):
        if self.callback:
            await self.callback(interaction)
        elif self.interaction_msg:
            await interaction.response.send_message(self.interaction_msg, ephemeral=True)
        elif self.onclick_code:
            await interaction.response.send_message(self.interaction_msg, ephemeral=True)
            
        return True

# --------- DICTIONNAIRES ---------
invites_cache = {}  # guild_id : list(invites)
invites_count = {}  # inviter_id : nombre total d'invites

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
        
        async def invite_callback(interaction: discord.Interaction):
            message = get_invites_count(interaction.user, True)
            await interaction.response.send_message(message, ephemeral=True)
        
        personal_invites_button = Button(color=discord.ButtonStyle.green, label="Voir mes invitations", callback=invite_callback, json_file=None)
        welcome_embed = discord.Embed(title=f"{member} vient de rejoindre le serveur!",
                                      description=f"Il a été invité par <@{inviter.id}> qui a désormais {invites_count[inviter_id]} invitations! <a:pepeclap:1453682464181588065>", 
                                      color=discord.Color.green())
        welcome_embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        await channel.send(
            content=f"# <a:tada:1453048315779481752> Bienvenue {member.mention} <a:tada:1453048315779481752>",
            embed=welcome_embed,
            view=personal_invites_button
        )
    else:
        await channel.send(f"👀 {member.mention} a rejoint, mais je suis incapable de déterminer qui l'a invité.")

@bot.event
async def on_member_remove(member:discord.Member):
    channel = bot.get_channel(LEAVS_CHANNEL_ID)
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
    if not channel:
        print("⚠️ Salon introuvable ou ID incorrect")
        return
    if used_invite:
        inviter = used_invite.inviter
        invites_count[inviter.id] -= 1
        save_invites()
        await channel.send(
            content="Un membre vient de quitter le serveur.",
            embed=discord.Embed(
                title=f"{member} vient de quitter le serveur.",
                description=f"Il a été invité par <@{inviter.id}> qui a désormais {invites_count[inviter.id]} invitations.",
                color=discord.Color.red()
            )
        )

@bot.command()
async def leave(ctx, member: discord.Member):
    await ctx.channel.send("leave")

@bot.command()
async def join(ctx, member: discord.Member):
    if ctx.author.id != 1071516026484822096:
        print("not join")
        await ctx.channel.send("Vous n'avez pas la permission d'utiliser cette commande.")
        return
    print("join")
        # mettre à jour le nombre d'invites
    channel = bot.get_channel(ctx.channel.id)
    
    async def invite_callback(interaction: discord.Interaction):
        message = get_invites_count(interaction.user, True)
        await interaction.response.send_message(message, ephemeral=True)
    
    personal_invites_button = Button(color=discord.ButtonStyle.green, label="Voir mes invitations", callback=invite_callback, json_file=None)
    await channel.send(
        content=f"# <a:tada:1453048315779481752> Bienvenue {member.mention} <a:tada:1453048315779481752>",
        view=personal_invites_button
    )

# --------- COMMANDE SLASH /invites ---------
@bot.tree.command(name="invites", description="Voir le nombre d'invitations que vous avez faites.")
async def invites(interaction: discord.Interaction, user: discord.Member = None):
    await interaction.response.send_message(get_invites_count(user, False if user else True))

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
    if message.author == bot.user:
        return
    if message.channel.id == CHAT_CHANNEL_ID:
        if "trade" in message.content.lower():
            await message.delete()

    await bot.process_commands(message)

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

@bot.command()
async def mute(ctx, member:discord.Member, duration:int, reason:str="Aucun raison fournie"):
    if ctx.author.guild_permissions.administrator:
        date = utcnow() + datetime.timedelta(minutes=duration)
        timestamp = date.timestamp()
        cancel_button = Button(label="Annuler l'action", color=discord.ButtonStyle.green, interaction_msg=f"Vous avez annulé le mute de {member.mention}.", onclick_code=member.edit(timed_out_until=None))
        await member.edit(timed_out_until=date, reason=reason)
        await ctx.channel.send(content=f"{member.mention} a été mute pendant {duration} minutes pour la raison `{reason}`.", view=cancel_button)
        await member.send(f"Vous avez été mute sur le serveur {ctx.guild.name} jusqu'au <t:{int(timestamp)}:F> pour la raison `{reason}`.")
        await ctx.author.send(content=f"Vous avez mute {member.mention} sur le serveur {ctx.guild.name} jusqu'au <t:{int(timestamp)}:F> pour la raison `{reason}`.", view=cancel_button)
    else:
        await ctx.channel.send("Vous n'avez pas la permission d'utiliser cette commande.")
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
