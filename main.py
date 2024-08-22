import discord
from discord.ext import commands
from discord import app_commands
from collections import defaultdict
import re
import time
import os
from dotenv import load_dotenv

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# 特定のチャンネルID
TARGET_CHANNEL_ID = 1274621348773101611

# スパムメッセージを記録するための辞書
user_messages = defaultdict(list)
warnings = defaultdict(int)

# グローバルBANされたユーザーを記録するリスト
global_ban_list = []

# 機能の有効・無効フラグ
invite_check_enabled = True
prohibited_words_check_enabled = True

# 暴言や卑猥な言葉のパターン（例）
prohibited_words = re.compile(r'\b(?:無能|死ね|消えろ|殺すぞ|カス|くたばれ|レイプ|セックス|ちんこ|マンコ|まんこ|sex|オナニー)\b', re.IGNORECASE)

# 時間の定数
TIME_FRAME = 4  # 4秒
SPAM_THRESHOLD = 4  # 4メッセージ
TIMEOUT_1 = 60  # 60秒
TIMEOUT_2 = 3600  # 1時間

# 処罰内容の辞書
punishments = {
    1: f"警告1: 注意",
    2: f"警告2: 警告",
    3: "警告3: キック",
    4: "警告4: ソフトBAN",
    5: "警告5: 永久BAN"
}

async def ban_user_globally(user_id):
    user = await bot.fetch_user(user_id)
    if user is None:
        return

    for guild in bot.guilds:
        member = guild.get_member(user.id)
        if member:
            await guild.ban(member, reason="自動グローバルBAN")

    # グローバルBANリストに追加
    if user_id not in global_ban_list:
        global_ban_list.append(user_id)

async def apply_punishment(message_channel, user, warning_count):
    try:
        if warning_count == 1:
            await message_channel.send(f"{user.mention}, {punishments[1]}")
            await user.timeout(duration=TIMEOUT_1)
        elif warning_count == 2:
            await message_channel.send(f"{user.mention}, {punishments[2]}")
            await user.timeout(duration=TIMEOUT_2)
        elif warning_count == 3:
            await message_channel.send(f"{user.mention}, {punishments[3]}")
            await message_channel.guild.kick(user)
        elif warning_count == 4:
            await message_channel.send(f"{user.mention}, {punishments[4]}")
            await message_channel.guild.ban(user, reason="ソフトBAN")
            await message_channel.guild.unban(user)
        elif warning_count >= 5:
            await message_channel.send(f"{user.mention}, {punishments[5]}")
            await message_channel.guild.ban(user, reason="永久BAN")
    except discord.Forbidden:
        await message_channel.send(f"{user.mention}, タイムアウトの設定に失敗しました。権限を確認してください。")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

    # BOT起動時に特定のチャンネルのメッセージをすべてチェック
    for guild in bot.guilds:
        channel = guild.get_channel(TARGET_CHANNEL_ID)
        if channel:
            async for message in channel.history(limit=None):
                user_ids = re.findall(r'\d{17,19}', message.content)
                for user_id in user_ids:
                    await ban_user_globally(int(user_id))

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # グローバルBANのチェック（メッセージ内容からユーザーIDを抽出）
    if message.channel.id == TARGET_CHANNEL_ID:
        user_ids = re.findall(r'\d{17,19}', message.content)
        for user_id in user_ids:
            await ban_user_globally(int(user_id))

    # 招待リンクの検出と警告
    if invite_check_enabled:
        invite_pattern = re.compile(
            r'(discord\.(gg|com|me|io)/[a-zA-Z0-9]{6,}|discordapp\.com/invite/[a-zA-Z0-9]{6,})', 
            re.IGNORECASE
        )
        if invite_pattern.search(message.content):
            await message.channel.send(f"{message.author.mention}, 招待リンクは禁止されています。")

    # 暴言や卑猥な言葉の検出
    if prohibited_words_check_enabled and prohibited_words.search(message.content):
        await message.channel.send(f"{message.author.mention}, 不適切な言葉が含まれています。")

    # スパム警告システムのチェック
    current_time = time.time()
    user_id = message.author.id

    # 古いメッセージをリストから削除
    user_messages[user_id] = [msg_time for msg_time in user_messages[user_id] if current_time - msg_time < TIME_FRAME]
    user_messages[user_id].append(current_time)

    # スパムを検出
    if len(user_messages[user_id]) >= SPAM_THRESHOLD:
        warnings[user_id] += 1
        warning_count = warnings[user_id]
        
        # 警告数に応じた処罰を適用
        await apply_punishment(message.channel, message.author, warning_count)

    await bot.process_commands(message)

# グローバルBANを手動で追加するスラッシュコマンド
@bot.tree.command(name="add_gban", description="グローバルBANするユーザーを指定します")
@commands.has_permissions(administrator=True)
async def add_gban(interaction: discord.Interaction, user: discord.User):
    user_id = user.id
    if user_id not in global_ban_list:
        await ban_user_globally(user_id)
        await interaction.response.send_message(f"{user.mention}がグローバルBANリストに追加されました。", ephemeral=True)
    else:
        await interaction.response.send_message(f"{user.mention}は既にグローバルBANリストに存在します。", ephemeral=True)

# グローバルBANされたユーザーリストを表示するスラッシュコマンド
@bot.tree.command(name="gbanlist", description="グローバルBANされたユーザーのリストを表示します")
async def gbanlist(interaction: discord.Interaction):
    if not global_ban_list:
        await interaction.response.send_message("グローバルBANされたユーザーはいません。", ephemeral=True)
    else:
        banned_users = "\n".join([f"<@{user_id}>" for user_id in global_ban_list])
        await interaction.response.send_message(f"グローバルBANされたユーザーリスト:\n{banned_users}", ephemeral=True)

# 機能の有効・無効を設定するスラッシュコマンド
@bot.tree.command(name="setblock", description="招待リンク、暴言、卑猥な言葉の検出機能を有効または無効にします")
@commands.has_permissions(manage_guild=True)
async def setblock(interaction: discord.Interaction, invite_check: bool, prohibited_words_check: bool):
    global invite_check_enabled, prohibited_words_check_enabled
    invite_check_enabled = invite_check
    prohibited_words_check_enabled = prohibited_words_check

    invite_status = "有効" if invite_check_enabled else "無効"
    prohibited_words_status = "有効" if prohibited_words_check_enabled else "無効"

    await interaction.response.send_message(
        f"招待リンクの検出機能は{invite_status}になりました。\n"
        f"暴言や卑猥な言葉の検出機能は{prohibited_words_status}になりました。", 
        ephemeral=True
    )

# サポートサーバーの招待リンクをDMで送信するスラッシュコマンド
@bot.tree.command(name="support", description="サポートサーバーの招待リンクをDMで送信します")
async def support(interaction: discord.Interaction):
    try:
        await interaction.user.send("https://discord.gg/yCS4VuzZ がサポートサーバーです。")
        await interaction.response.send_message("サポートサーバーの招待リンクをDMで送信しました。", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("DMの送信に失敗しました。設定を確認してください。", ephemeral=True)

# ヘルプコマンドを追加するスラッシュコマンド
@bot.tree.command(name="help", description="使用可能なコマンドとその説明を表示します")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Bot コマンドリスト",
        description="以下はこのBotで使用可能なコマンドのリストです。",
        color=discord.Color.blue()
    )
    
    commands_info = [
        ("`/add_gban [ユーザー]`", "指定したユーザーをグローバルBANします。"),
        ("`/gbanlist`", "グローバルBANされたユーザーのリストを表示します。"),
        ("`/setblock [招待リンクの検出] [暴言/卑猥な言葉の検出]`", "検出機能を有効または無効にします。"),
        ("`/support`", "サポートサーバーの招待リンクをDMで送信します。"),
        ("`/add_warning [ユーザー]`", "指定したユーザーの警告を1増やします。"),
        ("`/remove_warning [ユーザー]`", "指定したユーザーの警告を1減らします。"),
    ]
    
    for name, value in commands_info:
        embed.add_field(name=name, value=value, inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# 警告を手動で増やすスラッシュコマンド
@bot.tree.command(name="add_warning", description="指定したユーザーの警告を1増やします")
@commands.has_permissions(manage_messages=True)
async def add_warning(interaction: discord.Interaction, user: discord.User):
    user_id = user.id
    warnings[user_id] += 1
    warning_count = warnings[user_id]
    await interaction.response.send_message(f"{user.mention}の警告が増えました。現在の警告数: {warning_count}", ephemeral=True)
    
    # 警告数に応じた処罰を適用
    await apply_punishment(interaction.channel, user, warning_count)

# 警告を手動で減らすスラッシュコマンド
@bot.tree.command(name="remove_warning", description="指定したユーザーの警告を1減らします")
@commands.has_permissions(manage_messages=True)
async def remove_warning(interaction: discord.Interaction, user: discord.User):
    user_id = user.id
    if warnings[user_id] > 0:
        warnings[user_id] -= 1
        await interaction.response.send_message(f"{user.mention}の警告が減りました。現在の警告数: {warnings[user_id]}", ephemeral=True)
    else:
        await interaction.response.send_message(f"{user.mention}には減らす警告がありません。", ephemeral=True)
        await interaction.response.send_message(f"{user.mention}には減らす警告がありません。", ephemeral=True)
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    
    # スラッシュコマンドの同期
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s) to the guild(s).")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
TOKEN = os.getenv('DISCORD_TOKEN')
bot.run(TOKEN)