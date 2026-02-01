import discord
from discord.ext import commands
import json
import os
from discord import app_commands
import datetime
from types import FunctionType
from discord.utils import utcnow
import psycopg2
from discord.ui import Button, View, Modal, Select
import re
import aiohttp
import asyncio

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.presences = True

bot = commands.Bot(command_prefix="+", intents=intents)
guild = bot.get_guild(1438222268185706599)

GROQ_API_KEY = os.getenv("AI_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


DATABASE_URL = os.getenv("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()


cursor.execute("""CREATE TABLE IF NOT EXISTS vouchs (
    vouch_id SERIAL PRIMARY KEY,
    user_id TEXT,
    voucher_id TEXT,
    reason TEXT,
    datetime TEXT
);""")

cursor.execute("""CREATE TABLE IF NOT EXISTS invites (
    invite_id SERIAL PRIMARY KEY,
    inviter_id TEXT,
    invited_id TEXT,
    invite_code TEXT,
    datetime TEXT
);""")

cursor.execute("""CREATE TABLE IF NOT EXISTS tickets (
    ticket_id SERIAL PRIMARY KEY,
    member_id TEXT,
    reason TEXT,
    timestamp TEXT,
    status TEXT,
    channel_id TEXT
);""")

cursor.execute("""CREATE TABLE IF NOT EXISTS newyear (
    newyear_id SERIAL PRIMARY KEY,
    sending TEXT,
    receiving TEXT,
    datetime TEXT
);""")

cursor.execute("""CREATE TABLE IF NOT EXISTS ticket_msg_id (
    id TEXT
);""")

conn.commit()

# --------- CONFIG ---------
TOKEN = os.getenv("TOKEN")
print(TOKEN)
INVITES_CHANNEL_ID = 1440405854452187207  # salon où le bot envoie les messages
CHAT_CHANNEL_ID = 0
SAB_CHANNEL_ID = 0
VOTE2PROFIL_CHANNEL_ID = 1453103598090191011
VOTE2FAME_CHANNEL_ID = 1453103163468026190
EATORPASS_CHANNEL_ID = 1453105475200618497
SMASHORPASS_CHANNEL_ID = 1453104548809015467
VOUCH_CHANNEL_ID = 1452648909716586719
BOTS_CHANNEL_ID = 1445785148011446323
OWNER_ID = 1071516026484822096
TEST_ACCOUNT_ID = 1444323038953738382
TICKET_CHANNEL_ID = 1467463103636705321
TICKET_CATEGORY_ID = 1467462870387392512
MOD_ROLE_ID = 1456391253783740530
MM_ROLE_ID = 1443685365545177270
MEMBER_COUNT_CHANNEL_ID = 1460268450038546432
BOT_COUNT_CHANNEL_ID = 1460268646667517994
ONLINE_COUNT_CHANNEL_ID = 1460268512747589876
BOOST_COUNT_CHANNEL_ID = 1460268694251769893
MAX_MEMORY = 100

conversation_memory = []

# client = genai.Client()

# --------- CHARGER LES INVITES DU FICHIER ---------

cursor.execute("SELECT * FROM invites;")
invites_count = cursor.fetchall()
cursor.execute("SELECT * FROM vouchs;")
vouchs = cursor.fetchall()

# --------- FONCTION POUR SAUVEGARDER ---------

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
    embed.set_thumbnail(url=user.avatar.url if user.avatar.url else user.default_avatar.url)
    return embed
def get_vouchs_count(user:discord.Member):
    cursor.execute("SELECT * FROM vouchs WHERE user_id = %s;", (str(user.id),))
    return len(cursor.fetchall())

# --------- DICTIONNAIRES ---------
invites_cache = {}  # guild_id : list(invites)
invites_count = {}  # inviter_id : nombre total d'invites

# --------- AU LANCEMENT DU BOT ---------
@bot.event
async def on_ready():
    print(f"{bot.user} est connecté !")
    guild = bot.get_guild(1438222268185706599)
    for member in guild.members:
        custom = next((a for a in member.activities if isinstance(a, discord.CustomActivity)), None)
        if custom and custom.name and "/himura".lower() in custom.name.lower():
            if guild.get_role(1455978240777650439) not in member.roles:
                await member.add_roles(discord.utils.get(member.guild.roles, id=1455978240777650439))
        else:
            if guild.get_role(1455978240777650439) in member.roles:
                await member.remove_roles(discord.utils.get(member.guild.roles, id=1455978240777650439))

    cursor.execute("SELECT id FROM ticket_msg_id")
    ticket_creation_msg_id = cursor.fetchall()[0][0]
    try:
        ticket_channel = bot.get_channel(TICKET_CHANNEL_ID)
    except:
        print("Cannot find ticket message.")
    ticket_creation_msg = await ticket_channel.fetch_message(int(ticket_creation_msg_id))
    await ticket_creation_msg.delete()

    guild = bot.get_guild(1438222268185706599)
    
    embed = discord.Embed(title="Création de tickets", description="Pour ouvrir un ticket, sélectionnez une raison à l'aide du sélecteur ci-dessous!", color=discord.Color.green())
    embed.set_thumbnail(url=guild.icon.url)
    embed.set_footer(text="Merci de ne pas créer des tickets sans raison!", icon_url=guild.icon.url)
    embed.set_author(name=guild.name, url="https://discord.gg/himura")
    ticket_creation_msg = await ticket_channel.send(embed=embed, view=TicketReasonView())
    cursor.execute("UPDATE ticket_msg_id SET id=%s WHERE id=%s", (ticket_creation_msg.id, ticket_creation_msg_id))
    conn.commit()

    member_count_channel = bot.get_channel(MEMBER_COUNT_CHANNEL_ID)
    await member_count_channel.edit(name=f"「👥」𝑴𝑬𝑴𝑩𝑹𝑬𝑺 : {guild.member_count}")

    bot_count_channel = bot.get_channel(BOT_COUNT_CHANNEL_ID)
    await bot_count_channel.edit(name=f"「🤖」𝑩𝑶𝑻𝑺 : {len([m for m in guild.members if m.bot])}")

    online_count_channel = bot.get_channel(ONLINE_COUNT_CHANNEL_ID)
    actifs = sum(1 for m in guild.members if m.status in (discord.Status.online, discord.Status.idle, discord.Status.dnd))
    await online_count_channel.edit(name=f"「🟢」𝑬𝑵-𝑳𝑰𝑮𝑵𝑬 : {actifs}")

    boost_count_channel = bot.get_channel(BOOST_COUNT_CHANNEL_ID)
    await boost_count_channel.edit(name=f"「⚡」𝑩𝑶𝑶𝑺𝑻𝑺 : {guild.premium_subscription_count}")

    views = [TicketReasonView(), TicketOptionsView(), TicketCloseConfirmation(), TicketReasonModal(), TicketReasonSelect(), PersonnalInvitesButton()]

    for view in views:
        bot.add_view(view=view)

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
class PersonnalInvitesButton(View):
    def __init__ (self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Voir mes invitations", style=discord.ButtonStyle.green, custom_id="personal_invites_button")
    async def personal_invites_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        message = get_invites_count(interaction.user, True)
        await interaction.response.send_message(embed=message, ephemeral=True)

@bot.event
async def on_member_join(member:discord.Member):
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
        if used_invite:
            break

    # mise à jour du cache
    invites_cache[guild.id] = after

    channel = bot.get_channel(INVITES_CHANNEL_ID)
    if not channel:
        print("⚠️ Salon introuvable ou ID incorrect")
        return
    
    member_count_channel = bot.get_channel(MEMBER_COUNT_CHANNEL_ID)
    await member_count_channel.edit(name=f"「👥」𝑴𝑬𝑴𝑩𝑹𝑬𝑺 : {member.guild.member_count}")

    bot_count_channel = bot.get_channel(BOT_COUNT_CHANNEL_ID)
    await bot_count_channel.edit(name=f"「🤖」𝑩𝑶𝑻𝑺 : {len([m for m in member.guild.members if m.bot])}")

    if used_invite:
        inviter = used_invite.inviter
        inviter_id = str(inviter.id)

        datetime_now = datetime.datetime.now()
        try:
            cursor.execute("INSERT INTO invites (inviter_id, invited_id, invite_code, datetime) VALUES (%s, %s, %s, %s)", (inviter_id, member.id, used_invite.code, datetime_now))
            conn.commit()
        except:
            conn.rollback()

        cursor.execute("SELECT * FROM invites WHERE inviter_id = %s", (str(inviter.id),))
        invites_count = cursor.fetchall()

        welcome_embed = discord.Embed(title=f"{member} vient de rejoindre le serveur!",
                                      description=f"Il a été invité par <@{inviter.id}> qui a désormais {len(invites_count)} invitations! <a:pepeclap:1453682464181588065>\n Nous sommes désormais {guild.member_count} membres sur le serveur! <a:birb:1452995535882555524>", 
                                      color=discord.Color.green())
        welcome_embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        await channel.send(
            content=f"# <a:tada:1453048315779481752> Bienvenue {member.mention} <a:tada:1453048315779481752>",
            embed=welcome_embed,
            view=PersonnalInvitesButton()
        )
    elif used_invite.code == "himura":
        welcome_embed = discord.Embed(title=f"{member} vient de rejoindre le serveur!",
                                      description=f"Il a rejoint grâce à l'invitation personnalisée **himura** qui a désormais {used_invite.uses} utilisations! <a:pepeclap:1453682464181588065>\n Nous sommes désormais {guild.member_count} membres sur le serveur! <a:birb:1452995535882555524>", 
                                      color=discord.Color.green())
        await channel.send(
            content=f"# <a:tada:1453048315779481752> Bienvenue {member.mention} <a:tada:1453048315779481752>",
            embed=welcome_embed,
            view=PersonnalInvitesButton()
        )
    else:
        await channel.send(f"👀 {member.mention} a rejoint, mais je suis incapable de déterminer qui l'a invité.")

@bot.event
async def on_member_remove(member:discord.Member):
    member_count_channel = bot.get_channel(MEMBER_COUNT_CHANNEL_ID)
    await member_count_channel.edit(name=f"「👥」𝑴𝑬𝑴𝑩𝑹𝑬𝑺 : {member.guild.member_count}")

    bot_count_channel = bot.get_channel(BOT_COUNT_CHANNEL_ID)
    await bot_count_channel.edit(name=f"「🤖」𝑩𝑶𝑻𝑺 : {len([m for m in member.guild.members if m.bot])}")

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
async def on_message(message:discord.Message):
    if message.author == bot.user:
        return

    if message.author.id == OWNER_ID and (message.content.startswith("# Vote2Profil") or message.content.startswith("# Vote2Fame")):
        if message.channel.id == VOTE2PROFIL_CHANNEL_ID or message.channel.id == VOTE2FAME_CHANNEL_ID:
            await message.add_reaction("<:un:1453699994090733602>")
            await message.add_reaction("<:deux:1453700018904105044>")
    if message.author.id == OWNER_ID and (message.content.startswith("# Eat or Pass")):
        if message.channel.id == EATORPASS_CHANNEL_ID:
            await message.add_reaction("<:manger:1453435371315662897>")
            await message.add_reaction("<:pass:1453435746412138537>")
    if message.author.id == OWNER_ID and (message.content.startswith("# Smash or Pass")):
        if message.channel.id == SMASHORPASS_CHANNEL_ID:
            await message.add_reaction("<:oui:1453011623349456906>")
            await message.add_reaction("<:non:1453011584569053197>")

    await bot.process_commands(message)

@bot.command()
async def detruire(ctx):
    if ctx.author.id != OWNER_ID:
        await ctx.channel.send("Vous n'avez pas la permission d'utiliser cette commande.")
        return
    for channel in ctx.guild.channels:
        try:
            await channel.delete()
        except:
            pass

@bot.command()
async def vouch(ctx, member:discord.Member, *, args):
    if ctx.channel.id == VOUCH_CHANNEL_ID and ctx.author.id != member.id:
        await ctx.message.add_reaction("❤️")
        vouch_user(member, args, ctx.author)
    elif ctx.author.id == member.id:
        await ctx.send("Vous ne pouvez pas vous vouch vous-même 😓", delete_after=3000)
        await ctx.message.delete()

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
        
        class PublicVouchsButton(View):
            def __init__ (self):
                super().__init__(timeout=180)
            @discord.ui.button(label="Rendre Publique", style=discord.ButtonStyle.green)
            async def public_vouchs_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                message = f"{interaction.user.mention} a {get_vouchs_count(interaction.user)} {'vouch' if get_vouchs_count(interaction.user) == 1 else 'vouchs'}." if get_vouchs_count(interaction.user) > 0 else f"{interaction.user.mention} n'a aucun vouch <a:triste:1453390284762124450>"
                await interaction.response.send_message(content=message, ephemeral=False)

        class PersonalVouchsButton(View):
            def __init__ (self):
                super().__init__(timeout=180)
            @discord.ui.button(label="Voir mon nombre de vouchs", style=discord.ButtonStyle.green)
            async def personal_vouchs_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                message = f"Vous avez {get_vouchs_count(interaction.user)} {'vouch' if get_vouchs_count(interaction.user) == 1 else 'vouchs'}." if get_vouchs_count(interaction.user) > 0 else "Vous n'avez aucun vouch <a:triste:1453390284762124450>"
                await interaction.response.send_message(content=message, view=PublicVouchsButton(), ephemeral=True)

        if len(user_vouchs) > 0:
            embed = discord.Embed(title=f"Nombre de vouchs :", description=f"{member.mention} a {len(user_vouchs)} {"vouch" if len(user_vouchs) == 1 else "vouchs"}. <a:pepeclap:1453682464181588065>\nPour voir sa liste de vouchs, utilisez la commande `+vouchs_list`", color=discord.Color.green(), view=PersonalVouchsButton())
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            await ctx.channel.send(embed=embed, view=PersonalVouchsButton())
            return embed, PersonalVouchsButton()
        else:
            embed = discord.Embed(title=f"Nombre de vouchs :", description=f"{member.mention} n'a aucun vouch <a:triste:1453390284762124450>", color=discord.Color.red())
            return embed, PersonalVouchsButton()
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
async def mute(ctx, member:discord.Member, duration:int=40320, reason:str="Aucun raison fournie"):
    try:
        guild = bot.get_guild(1438222268185706599)
        mod_role = guild.get_role(1456391253783740530)
        if member.id == ctx.author.id:
            await ctx.channel.send("Vous ne pouvez pas vous mute vous-même <:lol:1453660116816760885><a:kekw:1438550949504225311>")
        elif member.id == OWNER_ID:
            await ctx.channel.send(f"Vous n'avez pas la permission de mute mon créateur, développeur, et propriétaire : <@{OWNER_ID}><a:coeurbleu:1453664603744505896>")
        elif ((mod_role in ctx.author.roles or ctx.author.guild_permissions.administrator) and ctx.author.top_role > member.top_role) or ctx.author.id == OWNER_ID:
            date=None
            if duration:
                date = (utcnow() + datetime.timedelta(minutes=duration))
                timestamp = int(date.timestamp())
            
            class CancelMuteButton(View):
                def __init__ (self):
                    super().__init__(timeout=180)
                @discord.ui.button(label="Annuler l'action", style=discord.ButtonStyle.red, emoji="<a:non:1453011584569053197>", custom_id="cancel_mute_button")
                async def cancel_mute_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    guild = bot.get_guild(1438222268185706599)
                    user = guild.get_member(interaction.user.id)
                    mod_role = guild.get_role(1456391253783740530)
                    if (mod_role in user.roles or user.guild_permissions.administrator) and user.top_role > member.top_role and member.id != OWNER_ID and member.id != user.id:
                        await member.edit(timed_out_until=None)
                        await member.send(f"Le mute qui vous avait été appliqué sur le serveur {ctx.guild.name} a été annulé par {interaction.user.mention}.")
                        await interaction.response.send_message(content=f"{user.mention} vient tout juste d'annuler le mute de {member.mention}.", ephemeral=False, delete_after=20)
                        button.disabled=True
                        interaction.edit_original_response(view=self)
                    else:
                        await interaction.response.send_message("Vous n'avez pas la permission d'utiliser cette commande.", ephemeral=True)
            await member.edit(timed_out_until=date, reason=reason)
            await ctx.channel.send(content=f"{member.mention} a été mute pendant {duration} minutes pour la raison `{reason}`.", view=CancelMuteButton(), )
            await member.send(f"Vous avez été mute sur le serveur {ctx.guild.name} jusqu'au <t:{int(timestamp)}:F>(<t:{int(timestamp)}:R>) pour la raison `{reason}`.")
            await ctx.author.send(content=f"Vous avez mute {member.mention} sur le serveur {ctx.guild.name} jusqu'au <t:{int(timestamp)}:F>(<t:{int(timestamp)}:R>) pour la raison `{reason}`.", view=CancelMuteButton())
        elif guild.get_role(1456391253783740530) not in ctx.author.roles and not ctx.author.guild_permissions.administrator:
            await ctx.channel.send("Vous n'avez pas la permission d'utiliser cette commande.")
        elif member.top_role >= ctx.author.top_role:
            await ctx.channel.send("Vous n'avez pas la permission de mute ce membre car il a un rôle égal ou supérieur au votre.")
        elif guild.get_member(bot.user.id).top_role <= member.top_role:
            await ctx.channel.send("Je n'ai pas la permission de mute ce membre car il a un rôle égal ou supérieur au mien.")
    except discord.Forbidden:
        await ctx.channel.send("Je n'ai pas la permission de mute ce membre car il a un rôle égal ou plus haut que le mien.")
    except Exception as e:
        await ctx.channel.send(f"Une erreur est survenue lors de l'exécution de l'action. Erreur : `{e}`")

@bot.command()
async def unmute(ctx, member:discord.Member, *, args=None):
    guild = bot.get_guild(1438222268185706599)
    mod_role = guild.get_role(1456391253783740530)
    if (ctx.author.id == OWNER_ID or (mod_role in ctx.author.roles or ctx.author.guild_permissions.administrator) and ctx.author.top_role > member.top_role) and member.is_timed_out():
        await member.edit(timed_out_until=None)
        await ctx.channel.send(content=f"{member.mention} a été unmute.")
        await member.send(f"Vous avez été unmute sur le serveur {ctx.guild.name} par {ctx.author.mention}{f" pour la raison `{args}`" if args else ""}.")
    elif mod_role not in ctx.author.roles and ctx.author.guild_permissions.administrator:
        await ctx.channel.send("Vous n'avez pas la permission d'utiliser cette commande car vous n'êtes pas modérateur sur le serveur.")
    elif ctx.author.top_role <= member.top_role:
        await ctx.channel.send("Vous n'avez pas la permission d'utiliser cette commande car ce membre a un rôle égal ou plus haut que le vôtre.")
    elif not member.is_timed_out():
        await ctx.channel.send("Ce membre n'a pas été mute.")
    elif bot.user.top_role <= member.top_role:
        await ctx.channel.send("Je n'ai pas la permission de unmute de membre car il a un rôle égal ou plus haut que le mien.")

@bot.command()
async def kick(ctx, member:discord.Member, *, args=None):
    guild = bot.get_guild(1438222268185706599)
    mod_role = guild.get_role(1456391253783740530)
    try:
        if member.id == ctx.author.id:
            await ctx.channel.send("Vous ne pouvez pas vous expulser vous-même <:lol:1453660116816760885><a:kekw:1438550949504225311>")
        elif member.id == OWNER_ID:
            await ctx.channel.send(f"Vous n'avez pas la permission d'expulser mon créateur, développeur, et propriétaire : <@{OWNER_ID}><a:coeurbleu:1453664603744505896>")
        elif (ctx.author.id == OWNER_ID or (mod_role in ctx.author.roles or ctx.author.guild_permissions.administrator) and ctx.author.top_role > member.top_role):
            await member.kick(reason=args)
            await ctx.channel.send(content=f"{member.mention} a été explulsé du serveur{f" pour la raison `{args}`" if args else " mais aucune raison n'a été spécifiée"}.")
            await member.send(f"Vous avez été expulsé du serveur {ctx.guild.name} par {ctx.author.mention}{f" pour la raison `{args}`" if args else " mais aucune raison n'a été spécifiée"}.")
        elif mod_role not in ctx.author.roles and ctx.author.guild_permissions.administrator:
            await ctx.channel.send("Vous n'avez pas la permission d'utiliser cette commande car vous n'êtes pas modérateur sur le serveur.")
        elif ctx.author.top_role <= member.top_role:
            await ctx.channel.send("Vous n'avez pas la permission d'utiliser cette commande car ce membre a un rôle égal ou plus haut que le vôtre.")
        elif guild.get_member(bot.user.id).top_role <= member.top_role:
            await ctx.channel.send("Je n'ai pas la permission d'expulser ce membre car il a un rôle égal ou plus haut que le mien.")
    except discord.Forbidden:
        await ctx.channel.send("Je n'ai pas la permission d'expulser ce membre car il a un rôle égal ou plus haut que le mien.")
    except Exception as e:
        await ctx.channel.send(f"Une erreur est survenue lors de l'exécution de l'action. Erreur : `{e}`")

@bot.command()
async def ban(ctx, member:discord.Member, *, args=None):
    guild = bot.get_guild(1438222268185706599)
    mod_role = guild.get_role(1456391253783740530)
    try:
        if member.id == ctx.author.id:
            await ctx.channel.send("Vous ne pouvez pas vous bannir vous-même <:lol:1453660116816760885><a:kekw:1438550949504225311>")
        elif member.id == OWNER_ID:
            await ctx.channel.send(f"Vous n'avez pas la permission de bannir mon créateur, développeur, et propriétaire : <@{OWNER_ID}><a:coeurbleu:1453664603744505896>")
        elif (ctx.author.id == OWNER_ID or (mod_role in ctx.author.roles or ctx.author.guild_permissions.administrator) and ctx.author.top_role > member.top_role):
            class CancelBanButton(View):
                def __init__(self, member):
                    super().__init__()
                @discord.ui.button(label="Annuler l'action", emoji="<a:non:1453011584569053197>", style=discord.ButtonStyle.red, custom_id="cancel_ban_button")
                async def cancel_ban_button(self, interaction: discord.Interaction, button:discord.Button):
                    user = guild.get_member(interaction.user.id)
                    if (mod_role in user.roles or user.guild_permissions.administrator) and user.top_role > member.top_role and member.id != OWNER_ID:
                        member.unban()
                        interaction.response.send_message(f"{member.mention} a été unban avec succès!")
                        member.send(f"Vous avez été unban du serveur **{guild.name}** par {user.mention}!")
                        user.send(f"Vous avez unban {member.mention} sur le serveur **{guild.name}**")
            await member.ban(reason=args)
            await ctx.channel.send(content=f"{member.mention} a été banni du serveur{f" pour la raison `{args}`" if args else " mais aucune raison n'a été spécifiée"}.", view=CancelBanButton(member))
            await member.send(f"Vous avez été banni du serveur {ctx.guild.name} par {ctx.author.mention}{f" pour la raison `{args}`" if args else " mais aucune raison n'a été spécifiée"}.")
        elif mod_role not in ctx.author.roles and ctx.author.guild_permissions.administrator:
            await ctx.channel.send("Vous n'avez pas la permission d'utiliser cette commande car vous n'êtes pas modérateur sur le serveur.")
        elif ctx.author.top_role <= member.top_role:
            await ctx.channel.send("Vous n'avez pas la permission de bannir ce membre car il a un rôle égal ou plus haut que le vôtre.")
        elif guild.get_member(bot.user.id).top_role <= member.top_role:
            await ctx.channel.send("Je n'ai pas la permission de bannir ce membre car il a un rôle égal ou plus haut que le mien.")
    except discord.Forbidden:
        await ctx.channel.send("Je n'ai pas la permission de bannir ce membre car il a un rôle égal ou plus haut que le mien.")
    except Exception as e:
        await ctx.channel.send(f"Une erreur est survenue lors de l'exécution de l'action. Erreur : `{e}`")

@bot.command()
async def unban(ctx, member:discord.Member, reason:str=None):
    guild = bot.get_guild(1438222268185706599)
    mod_role = guild.get_role(1456391253783740530)
    if (ctx.author.id == OWNER_ID or (mod_role in ctx.author.roles or ctx.author.guild_permissions.administrator) and ctx.author.top_role > member.top_role) and member.is_timed_out():
        await member.edit(timed_out_until=None)
        await ctx.channel.send(content=f"{member.mention} a été unban.")
        await member.send(f"Vous avez été unban sur le serveur {ctx.guild.name} par {ctx.author.mention}{f" pour la raison `{reason}`" if reason else ""}.")
    elif mod_role not in ctx.author.roles and ctx.author.guild_permissions.administrator:
        await ctx.channel.send("Vous n'avez pas la permission d'utiliser cette commande car vous n'êtes pas modérateur sur le serveur.")
    elif ctx.author.top_role <= member.top_role:
        await ctx.channel.send("Vous n'avez pas la permission d'utiliser cette commande car ce membre a un rôle égal ou plus haut que le vôtre.")
    elif not member.is_timed_out():
        await ctx.channel.send("Ce membre n'a pas été banni!")
    elif bot.user.top_role <= member.top_role:
        await ctx.channel.send("Je n'ai pas la permission de unban de membre car il a un rôle égal ou plus haut que le mien.")


@bot.command()
async def invites(ctx, member:discord.Member=None):
    if member:
        class PersonnalInvitesButton(View):
            def __init__ (self):
                super().__init__(timeout=None)
            @discord.ui.button(label="Voir mes invitations", style=discord.ButtonStyle.green, custom_id="personal_invites_button")
            async def personal_invites_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                message = get_invites_count(interaction.user, True)
                await interaction.response.send_message(embed=message, ephemeral=True)
        embed, button = get_invites_count(member, personal=True)
    else:
        embed = get_invites_count(ctx.author, personal=False)
    ctx.channel.send(embed=embed, button=PersonnalInvitesButton() if member else None)

@bot.event
async def on_presence_update(before:discord.Member, after:discord.Member):
    guild = bot.get_guild(1438222268185706599)
    role = guild.get_role(1455978240777650439)
    before_custom = next((a for a in before.activities if isinstance(a, discord.CustomActivity)), None)
    after_custom = next((a for a in after.activities if isinstance(a, discord.CustomActivity)), None)
    if before_custom != after_custom:
        if after_custom and after_custom.name:
            if after_custom and after_custom.name and "/himura".lower() in after_custom.name.lower():
                if role not in after.roles:
                    await after.add_roles(role)
            else:
                if role in after.roles:
                    await after.remove_roles(role)

    online_count_channel = bot.get_channel(ONLINE_COUNT_CHANNEL_ID)
    actifs = sum(1 for m in guild.members if m.status in (discord.Status.online, discord.Status.idle, discord.Status.dnd))
    await online_count_channel.edit(name=f"「🟢」𝑬𝑵-𝑳𝑰𝑮𝑵𝑬 : {actifs}")

@bot.command()
async def newyear(ctx):
    if ctx.author.id == OWNER_ID:
        await ctx.message.delete()
        embed = discord.Embed(title="Message de bonne année <a:tada:1453048315779481752>", description="Souhaitez une bonne année à quelqu'un et obtenez le rôle spécial <@&1456236148224561232>!", color=discord.Color.green())
        embed.set_thumbnail(url=guild.icon.url)
        await ctx.channel.send(embed=embed, view=NewYearButton())

class NewYearModal(Modal):
    def __init__(self, member:discord.Member):
        super().__init__(title="Message de bonne année")
        self.add_item(discord.ui.TextInput(label="Votre message de bonne année", style=discord.TextStyle.paragraph, placeholder="Écrivez votre message ici...", max_length=2000, required=True))
        self.member = member

    async def on_submit(self, interaction: discord.Interaction):
        dm_embed = discord.Embed(title="Message de bonne année reçu! <a:tada:1453048315779481752>", description=f"Vous avez reçu un message de bonne année de la part de {interaction.user.mention} qui vous dit :\n{self.children[0].value}", color=discord.Color.green())
        dm_embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)
        await self.member.send(embed=dm_embed)
        await interaction.user.add_roles(discord.utils.get(interaction.guild.roles, id=1456236148224561232))
        success_embed = discord.Embed(title="Message envoyé avec succès! <a:tada:1453048315779481752>", description=f"Votre message de bonne année a été envoyé à {self.member.mention} avec succès! Vous avez également reçu le rôle spécial <@&1456236148224561232>.", color=discord.Color.green())
        success_embed.set_thumbnail(url=self.member.avatar.url if self.member.avatar else self.member.default_avatar.url)
        await interaction.response.send_message(embed=success_embed, ephemeral=True)
        cursor.execute("INSERT INTO newyear (sending, receiving, datetime) VALUES (%s, %s, %s)", (interaction.user.name, self.member.name, datetime.datetime.now().isoformat()))
        conn.commit()

class NewYearMemberSelectView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(NewYearMemberSelect())

class NewYearMemberSelect(discord.ui.UserSelect):
    def __init__(self):
        super().__init__(placeholder="Sélectionnez un membre...", min_values=1, max_values=1)
        
    async def callback(self, interaction: discord.Interaction):
        cursor.execute("SELECT * FROM newyear WHERE sending = %s", (interaction.user.name,))
        sent_messages = cursor.fetchall()
        member = self.values[0]
        if member.id == interaction.user.id:
            embed = discord.Embed(title="Erreur", description="Vous ne pouvez pas vous envoyer un message de bonne année à vous-même! 😅<a:tropdrole:1453334029037338656>", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        elif len(sent_messages) >= 3:
            embed = discord.Embed(title="Limite atteinte", description="Vous avez déjà envoyé 3 messages de bonne année cette année! 🎉", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        else:
            for sent_message in sent_messages:
                if sent_message[2] == interaction.user.name:
                    embed = discord.Embed(title="Erreur", description="Vous avez déjà envoyé un message de bonne année à cette personne! 😅<a:tropdrole:1453334029037338656>", color=discord.Color.red())
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
                else:
                    pass
            await interaction.response.send_modal(NewYearModal(member))

class NewYearButton(View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Souhaiter une bonne année", style=discord.ButtonStyle.green, emoji="<a:tada:1453048315779481752>")
    async def new_year_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="Sélection du membre", description="Veuillez sélectionner le membre auquel vous souhaitez envoyer un message de bonne année.", color=discord.Color.green())
        await interaction.response.send_message(embed=embed, view=NewYearMemberSelectView(), ephemeral=True)

@bot.command()
async def newyearstats(ctx, member:discord.Member=None):
    if ctx.author.id == OWNER_ID:
        target_member = member or ctx.author
        cursor.execute("SELECT COUNT(*) FROM newyear WHERE receiving = %s;", (str(target_member.name),))
        count = cursor.fetchone()[0]
        await ctx.channel.send(content=f"{target_member.mention} a reçu {count} message{'s' if count > 1 else ''} de bonne année.")

class ReopenDeleteTicket(View):
    def __init__(self, member:discord.Member, moderator_roles):
        super().__init__(timeout=None)
        self.member = member
        self.moderator_roles = moderator_roles
    
    @discord.ui.button(label="Rouvrir le ticket", style=discord.ButtonStyle.green, custom_id="reopen_ticket_button")
    async def reopen_ticket_button(self, interaction:discord.Interaction, button:discord.Button):
        user = interaction.guild.get_member(interaction.user.id)
        reopened_embed = discord.Embed(title=f"Ticket réouvert", description=f"{"Votre" if user.id != self.member.id else "Ce"} ticket a été ouvert par {user.mention}", color=discord.Color.green())
        if user.id != self.member.id:
            await self.member.send(f"Votre ticket sur {interaction.guild.name} a été réouvert par {user.mention}")
        cursor.execute("UPDATE tickets SET status = %s, user_id = %s WHERE channel_id = %s", ("reopened", user.id, str(interaction.channel.id)))
        conn.commit()
        await interaction.response.send_message(content=self.member.mention if user.id != self.member.id else None, embed=reopened_embed)

    @discord.ui.button(label="Supprimer le ticket", style=discord.ButtonStyle.danger, custom_id="delete_ticket_button")
    async def delete_ticket_button(self, interaction:discord.Interaction, button:discord.Button):
        user = interaction.guild.get_member(interaction.user.id)
        for moderator_role in self.moderator_roles:
            if moderator_role in user.roles:
                moderator = True
                break
            else:
                moderator = False
                break
        if moderator or user.guild_permissions.administrator:
            delete_confirmation_embed = discord.Embed(title="Confirmation", description="Êtes-vous sûr de vouloir supprimer ce ticket?", color=discord.Color.red())
            await interaction.response.send_message(embed=delete_confirmation_embed, view=TicketCloseConfirmation(self.moderator_roles, self.member, interaction.message.id), ephemeral=True)
        else:
            delete_confirmation_embed = discord.Embed(title="Manque de permissions", description="Vous n'avez pas la permission de supprimer ce ticket.", color=discord.Color.red())
            await interaction.response.send_message(embed=delete_confirmation_embed, ephemeral=True)

ticket_msg_id = None

class TicketCloseConfirmation(View):
    def __init__(self, moderator_roles, member:discord.Member, ticket_msg_id):
        super().__init__(timeout=None)
        self.moderator_roles = moderator_roles
        self.member = member
        self.ticket_msg_id = ticket_msg_id
    
    @discord.ui.button(label="Oui", style=discord.ButtonStyle.green, custom_id="yes_close_ticket_confirmation")
    async def yes_button(self, interaction:discord.Interaction, button:discord.ui.Button):
        user = interaction.guild.get_member(interaction.user.id)
        moderator = any(role in user.roles for role in self.moderator_roles)
        if moderator or user.guild_permissions.administrator:
            cursor.execute("UPDATE tickets SET status = %s WHERE channel_id = %s", ("deleted", str(interaction.channel.id)))
            conn.commit()
            await self.member.send(f"Votre ticket sur {interaction.guild.name} a été supprimé par {user.mention}")
            await interaction.channel.delete(reason="Ticket fermé")
        else:
            embed=discord.Embed(title="Ticket fermé", description=f"{user.mention} vient de fermer son ticket.", color=discord.Color.blue())
            await interaction.response.send_message(embed=embed, view=ReopenDeleteTicket(self.member, self.moderator_roles))
            cursor.execute("UPDATE tickets SET status = %s WHERE channel_id = %s", ("closed", str(interaction.channel.id)))
            conn.commit()

    @discord.ui.button(label="Non", style=discord.ButtonStyle.danger, custom_id="no_close_ticket_confirmation")
    async def no_button(self, interaction:discord.Interaction, button:discord.ui.Button):
        user = interaction.guild.get_member(interaction.user.id)
        canceled_embed = discord.Embed(title="Action annulée", description="La fermeture du ticket a été annulée avec succès!", color=discord.Color.blue())
        await interaction.response.edit_message(embed=canceled_embed, view=None, delete_after=60)

class TicketOptionsView(View):
    def __init__(self, moderator_roles, member:discord.Member):
        super().__init__(timeout=None)
        self.moderator_roles = moderator_roles
        self.member = member
    @discord.ui.button(label="Prendre en charge", style=discord.ButtonStyle.blurple, emoji="🛠️", custom_id="handle_ticket")
    async def handle_button(self, interaction:discord.Interaction, button:discord.ui.Button):
        user = interaction.guild.get_member(interaction.user.id)
        for moderator_role in self.moderator_roles:
            if moderator_role in user.roles:
                moderator = True
                break
            else:
                moderator = False
                break
        if moderator or user.guild_permissions.administrator:
            handle_embed = discord.Embed(title="Ticket pris en charge!", description=f"Votre ticket a été pris en charge par {user.mention}!", color=discord.Color.green())
            await interaction.response.send_message(content=self.member.mention, embed=handle_embed)
            cursor.execute("UPDATE tickets SET status = %s WHERE channel_id=%s", ("handled", str(interaction.channel.id)))
            conn.commit()
            button.disabled = True
            button.label = "Ticket pris en charge"
            button.emoji = "✅"
            await interaction.message.edit(view=self)
        else:
            handle_embed = discord.Embed(title="Manque de permissions", description="Vous n'avez pas la permission de prendre en charge ce ticket!", color=discord.Color.red())
            await interaction.response.send_message(embed=handle_embed, ephemeral=True)
    
    @discord.ui.button(label="Fermer le ticket", emoji="🔒", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction:discord.Interaction, button:discord.Button):
        user = interaction.guild.get_member(interaction.user.id)
        for moderator_role in self.moderator_roles:
            if moderator_role in user.roles:
                moderator = True
                break
            else:
                moderator = False
                break
        
        if moderator or self.member.guild_permissions.administrator:
            confirmation_embed = discord.Embed(title="Confirmation", description="Êtes-vous sûr de vouloir fermer et supprimer le ticket?", color=discord.Color.red())
        else:
            confirmation_embed = discord.Embed(title="Confirmation", description="Êtes-vous sûr de vouloir fermer le ticket?", color=discord.Color.red())
        await interaction.response.send_message(embed=confirmation_embed, view=TicketCloseConfirmation(self.moderator_roles, self.member, interaction.message.id), ephemeral=True)

class TicketReasonModal(Modal):
    def __init__(self):
        super().__init__(title="Raison d'ouverture de ticket")
        self.reason_input = discord.ui.TextInput(label="Raison", style=discord.TextStyle.paragraph, placeholder="Décrivez votre demande...")
        self.add_item(self.reason_input)

    async def on_submit(self, interaction:discord.Interaction):
        mods = [interaction.guild.get_role(MOD_ROLE_ID),]
        member = interaction.guild.get_member(interaction.user.id)
        ticket_category = discord.utils.get(interaction.guild.categories, id=TICKET_CATEGORY_ID)
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        for mod in mods:
            if mod:
                overwrites[mod] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        ticket_channel = await interaction.guild.create_text_channel(name=f"ticket-{member.display_name}", category=ticket_category, overwrites=overwrites)
        await interaction.response.send_message(content="Votre ticket est en cours de création", ephemeral=True)
        try:
            owner = interaction.guild.get_member(OWNER_ID)
            if owner:
                await owner.send(f"{member.mention} vient de créer un ticket pour la raison `{self.reason_input.value}`. {ticket_channel.jump_url}")
        except:
            pass
        ticket_debut_embed = discord.Embed(title=f"Ticket ouvert par {member}", description=f"{member.mention} vient d'ouvrir un ticket!\nRaison : **{self.reason_input.value}**", color=discord.Color.green())
        ticket_debut_embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        ticket_debut_embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon.url)
        datetime_now = datetime.datetime.now().timestamp()
        cursor.execute("INSERT INTO tickets (member_id, reason, timestamp, status, channel_id) VALUES (%s, %s, %s, %s, %s)", (str(member.id), self.reason_input.value, str(datetime_now), "open", str(ticket_channel.id)))
        conn.commit()
        ticket_msg = await ticket_channel.send(content=f"Bienvenue {member.mention} dans votre ticket, un membre du staff vous prendra le plus vite possible en charge. Restez là!", embed=ticket_debut_embed, view=TicketOptionsView(mods, member))
        ticket_created_success_embed = discord.Embed(title="Succès", description=f"Votre ticket a été créé avec succès dans {ticket_channel.jump_url}", color=discord.Color.green())
        await interaction.followup.send(content=member.mention, embed=ticket_created_success_embed, ephemeral=True)

class TicketReasonSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Récompense Giveaway/Event", description="Réclamez votre récompense pour un giveaway ou un event!", emoji="<a:gift:1453461527154921666>"),
            discord.SelectOption(label="Signaler un membre", description="Signalez un membre (ou même un staff) du serveur pour non respect des règles", emoji="<a:danger:1453146172876259432>"),
            discord.SelectOption(label="Proposition", description="Proposer un concept pour améliorer le serveur!", emoji="💡"),
            discord.SelectOption(label="Partenariat", description="Demande de partenariat avec un serveur Discord ou autre", emoji="🤝"),
            discord.SelectOption(label="Demande de Middle Man", description="Demander un Middle Man Steal a Brainrot pour sécuriser un trade ou un index.", emoji="<:staff:1452235667856687204>"),
            discord.SelectOption(label="Animations", description="Demander de participer à une animation ou en proposer une.", emoji="<a:birb:1452995535882555524>"),
            discord.SelectOption(label="Autre", emoji="<:jsp:1453042316347572274>"),
        ]

        super().__init__(placeholder="Veuillez choisir une raison pour ouvrir un ticket...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction:discord.Interaction):
        if self.values[0] == "Autre":
            await interaction.response.send_modal(TicketReasonModal())
            return
        
        mods = [interaction.guild.get_role(MOD_ROLE_ID),]
        member = interaction.guild.get_member(interaction.user.id)
        ticket_category = discord.utils.get(interaction.guild.categories, id=TICKET_CATEGORY_ID)
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        for mod in mods:
            if mod:
                overwrites[mod] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        ticket_channel = await interaction.guild.create_text_channel(name=f"{self.values[0]}-{member.display_name}", category=ticket_category, overwrites=overwrites)
        await interaction.response.send_message(content="Votre ticket est en cours de création", ephemeral=True)
        try:
            owner = interaction.guild.get_member(OWNER_ID)
            if owner:
                await owner.send(f"{member.mention} vient de créer un ticket pour la raison `{self.values[0]}`. {ticket_channel.jump_url}")
        except:
            pass
        ticket_debut_embed = discord.Embed(title=f"Ticket ouvert par {member}", description=f"{member.mention} vient d'ouvrir un ticket!\nRaison : **{self.values[0]}**", color=discord.Color.green())
        ticket_debut_embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        ticket_debut_embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon.url)
        datetime_now = datetime.datetime.now().timestamp()
        ticket_msg = await ticket_channel.send(content=f"Bienvenue {member.mention} dans votre ticket, un membre du staff vous prendra le plus vite possible en charge. Restez là! {[mod_role.mention for mod_role in mods]}", embed=ticket_debut_embed, view=TicketOptionsView(mods, member))
        cursor.execute("INSERT INTO tickets (member_id, reason, timestamp, status, channel_id) VALUES (%s, %s, %s, %s, %s)", (str(member.id), self.values[0], str(datetime_now), "open", str(ticket_channel.id)))
        conn.commit()
        ticket_created_success_embed = discord.Embed(title="Succès", description=f"Votre ticket a été créé avec succès dans {ticket_channel.jump_url}", color=discord.Color.green())
        await interaction.followup.send(content=member.mention, embed=ticket_created_success_embed, ephemeral=True)

class TicketReasonView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketReasonSelect())

@bot.command()
async def ticketsystem(ctx):
    if ctx.author.id == OWNER_ID or ctx.author.id == TEST_ACCOUNT_ID:
        cursor.execute("SELECT id FROM ticket_msg_id")
        ticket_creation_msg_id = cursor.fetchall()[0][0]
        ticket_channel = bot.get_channel(TICKET_CHANNEL_ID)
        ticket_creation_msg = await ticket_channel.fetch_message(int(ticket_creation_msg_id))
        try:
            await ticket_creation_msg.delete()
        except:
            print("Cannot find ticket message")

        embed = discord.Embed(title="Création de tickets", description="Pour ouvrir un ticket, sélectionnez une raison à l'aide du sélecteur ci-dessous!", color=discord.Color.green())
        embed.set_thumbnail(url=ctx.guild.icon.url)
        embed.set_footer(text="Merci de ne pas créer des tickets sans raison!", icon_url=ctx.guild.icon.url)
        embed.set_author(name=ctx.guild.name, url="https://discord.gg/H4JNyVMkjH")
        await ticket_channel.send(embed=embed, view=TicketReasonView())
        await ctx.message.delete()
        cursor.execute("UPDATE ticket_msg_id SET id=%s WHERE id=%s", (ticket_creation_msg.id, ticket_creation_msg_id))
        conn.commit()
        
async def ticketclose(ctx, channel:discord.TextChannel=None):
    user = ctx.author
    moderator_role = ctx.guild.get_role(1456391253783740530)
    is_mod = moderator_role in ctx.author.roles
    target_channel = channel if channel else ctx.channel
    cursor.execute("SELECT channel_id FROM tickets WHERE channel_id=%s", (target_channel.id,))
    channel_exists = 1 if len(cursor.fetchall()) > 0 else None
    if channel_exists:
        cursor.execute("SELECT * FROM tickets WHERE channel_id=%s", (target_channel.id,))
        ticket = cursor.fetchall()
        
        member = ctx.guild.get_member(int(ticket[0][5]))
        ticket_channel = bot.get_channel(int(ticket[0][6]))
        if is_mod or user.guild_permissions.administrator:
            ticket_channel = channel if channel else ctx.channel
            cursor.execute("UPDATE tickets SET status = %s, status=%s WHERE channel_id = %s", ("deleted", str(ticket_channel.id), "deleted", str(ticket_channel.id)))
            conn.commit()
            await member.send(f"Votre ticket sur {ctx.guild.name} a été supprimé par {user.mention}")
            await ticket_channel.delete(reason="Ticket fermé")
        else:
            embed=discord.Embed(title="Ticket fermé", description=f"{user.mention} vient de fermer son ticket.", color=discord.Color.blue())
            await ticket_channel.send_message(embed=embed, view=ReopenDeleteTicket(member, [moderator_role]))
            cursor.execute("UPDATE tickets SET status = %s WHERE channel_id = %s", ("closed", str(ctx.channel.id)))
            conn.commit()
    else:
        await ctx.send("Ce salon n'est pas un de mes tickets.")

@bot.command()
async def renew(ctx, channel:discord.TextChannel=None):
    if ctx.author.guild_permissions.administrator or ctx.author.id == OWNER_ID:
        channel = channel if type(channel) == discord.TextChannel else ctx.channel
        channel_position = channel.position
        channel_name = channel.name
        channel_topic = channel.topic
        channel_perms = channel.overwrites
        nsfw = channel.is_nsfw()
        channel_category = channel.category
        slowmode = channel.slowmode_delay
        await channel.delete()
        new_channel = await ctx.guild.create_text_channel(name=channel_name, category=channel_category, overwrites=channel_perms)
        await new_channel.edit( topic=channel_topic, slowmode_delay=slowmode, nsfw=nsfw, position=channel_position)
        msg = await new_channel.send(ctx.author.mention)
        await msg.delete()
    else:
        await ctx.send("Vous n'avez pas les permissions nécessaires pour utiliser cette commande.")

@bot.event
async def on_guild_update(before:discord.Guild, after:discord.Guild):
    if before.premium_subscription_count != after.premium_subscription_count:
        boost_count_channel = bot.get_channel(BOOST_COUNT_CHANNEL_ID)
        await boost_count_channel.edit(name=f"「⚡」𝑩𝑶𝑶𝑺𝑻𝑺 : {after.premium_subscription_count}")

@bot.command()
async def rainbowrole(ctx, member:discord.Member):
    if ctx.author.guild_permissions.administrator or ctx.author.id == 1373746108601471077:
        if not ctx.guild.get_role(1461089163334910013) in member.roles:
            await member.add_roles(ctx.guild.get_role(1461089163334910013))
            await ctx.send(f"Le rôle a été donné à {member.mention} avec succès")
            return
        else:
            await member.remove_roles(ctx.guild.get_role(1461089163334910013))
            await ctx.send(f"Le rôle a été retiré à {member.mention} avec succès")
            return

@bot.command()
async def replacechannel(ctx, channel:discord.abc.GuildChannel, position:int):
    await channel.edit(position=position)
    await ctx.send("Le salon ou le rôle spécifié a été déplacé avec succès")

@bot.command()
async def newrole(ctx, position:int, *name:str):
    if ctx.author.guild_permissions.manage_roles or ctx.author.id == OWNER_ID:
        if ctx.author.top_role.position > position:
            if ctx.guild.me.top_role.position > position:
                role_name = " ".join(name)
                new_role = await ctx.guild.create_role(name=role_name)
                roles_sorted = sorted(ctx.guild.roles, key=lambda r: r.position, reverse=True)
                index = position - 1
                await new_role.edit(position=roles_sorted[index].position)
                await ctx.send("Succès")
            else:
                await ctx.send("Je n'ai pas la permission d'ajouter ce rôle car il est égal ou plus haut que le mien.")
        else:
            await ctx.send("Le role que vous voulez ajouter est égal ou plus haut que le vôtre.")
    else:
        await ctx.send("Vous n'avez pas les permissions nécessaires pour utiliser cette commande.")
    

@bot.command()
async def addrole(ctx, members:commands.Greedy[discord.Member], roles:commands.Greedy[discord.Role]):

    if ctx.author.guild_permissions.manage_roles or ctx.author.id == OWNER_ID:
        for member in members:
            for i, role in enumerate(roles):
                if ctx.author.top_role > role and ctx.author.id != OWNER_ID:
                    roles.pop(i-1)
                    await ctx.send("Vous n'avez pas les permissions")

                if ctx.guild.me.top_role > role:
                    roles.pop(i-1)
                    await ctx.send("Je n'ai pas les permissions")

            if len(roles) > 0:
                await member.add_roles(*roles)
                await ctx.send("Succès")
            else:
                await ctx.send("Erreur")
    else:
        await ctx.send("Vous n'avez pas les permissions nécessaires pour utiliser cette commande.")

async def clearemojis(ctx):
    if ctx.author.id == OWNER_ID:
        for emoji in ctx.guild.emojis:
            ctx.guild.delete_emoji(emoji)
        await ctx.send("Tous les emojis du serveur ont été supprimés avec succès.")

async def createemoji(ctx, *emojis):
    if ctx.author.guild_permissions.administator or ctx.author.guild_permissions.manage_emojis_and_stickers or ctx.author.id == OWNER_ID:
        for emoji in emojis:
            if isinstance(emoji, discord.Emoji):
                async with aiohttp.ClientSession() as session:
                    async with session.get(str(emoji.url)) as resp:
                        if resp.status != 200:
                            await ctx.send("Impossible de récupérer l'emoji 😢")
                            return
                        data = await resp.read()

                discord.Guild.create_custom_emoji(ctx.guild, name=emoji.name, image=data)
        await ctx.send("Emojis ajoutés avec succès!")
    else:
        await ctx.send("Vous n'avez pas la permissione d'utiliser cette commande")

# @bot.command()
# async def roleicon(ctx, *, args):
#     role_mentions=ctx.message.role_mentions
#     if "add" or "ajouter" or "edit" or "modifier" in args and ctx.message.attachments and role_mentions:
#         icons = {}
#         for attachment, role_mention in ctx.message.attachments, role_mentions:
#             icons.pop(key=role_mention)
#             icons[role_mention]=attachment
#         for role, icon in icons.items():
#             with open(icon.)

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
