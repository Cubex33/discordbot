import discord
from discord.ext import commands
from discord.ui import View, Modal, TextInput

# -------------------------- НАСТРОЙКИ --------------------------
TOKEN = "MTIzNTYyMzIyMzY5NDE5NjgxNg.G4I4HC.XhJOl0kpgJSh5jhTCJXuyceB4m8Ssy44JVSkLQ"

VOICE_CONTROL_CHANNEL_ID = 1232858178341830697  # Канал для панели управления
VOICE_TRIGGER_CHANNEL_ID = 1232858410253553829  # Канал для создания приваток
PRIVATE_CATEGORY_ID = None  # Категория для приватных каналов (можно None)

# Словарь: владелец → ID его приватного канала
user_private_channels = {}

# -------------------------- ИНИЦИАЛИЗАЦИЯ БОТА --------------------------
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# -------------------------- СОБЫТИЯ --------------------------
@bot.event
async def on_ready():
    print(f"Бот запущен как {bot.user}")
    # Добавляем persistent view для кнопок панели
    bot.add_view(ChannelControlPersistent())

@bot.event
async def on_message(message):
    if not message.author.bot and message.content.lower() == "привет":
        await message.channel.send("Привет!")
    await bot.process_commands(message)

# -------------------------- ПРИВАТНЫЕ КАНАЛЫ --------------------------
async def try_delete_empty_private_channels(guild):
    for owner_id, ch_id in list(user_private_channels.items()):
        ch = guild.get_channel(ch_id)
        if not ch or len(ch.members) == 0:
            if ch:
                await ch.delete(reason="Пустой приватный канал")
            user_private_channels.pop(owner_id, None)

@bot.event
async def on_voice_state_update(member, before, after):
    guild = member.guild
    # Создание приватного канала при входе
    if after.channel and after.channel.id == VOICE_TRIGGER_CHANNEL_ID:
        old = user_private_channels.get(member.id)
        if old:
            ch = guild.get_channel(old)
            if ch and len(ch.members) == 0:
                await ch.delete()
            user_private_channels.pop(member.id, None)

        category = guild.get_channel(PRIVATE_CATEGORY_ID) if PRIVATE_CATEGORY_ID else after.channel.category
        new_channel = await guild.create_voice_channel(
            name=f"Канал {member.display_name}",
            category=category,
            user_limit=5,
            bitrate=64000
        )
        user_private_channels[member.id] = new_channel.id
        await new_channel.set_permissions(member, connect=True, speak=True, manage_channels=True)
        await member.move_to(new_channel)

    await try_delete_empty_private_channels(guild)

# -------------------------- МОДАЛЬНЫЕ ОКНА --------------------------
class RenameModal(Modal):
    def __init__(self, owner):
        super().__init__(title="Переименовать канал")
        self.owner = owner
        self.name = TextInput(label="Новое название")
        self.add_item(self.name)

    async def on_submit(self, interaction):
        ch = interaction.guild.get_channel(user_private_channels.get(self.owner))
        if ch:
            await ch.edit(name=self.name.value)
            await interaction.response.send_message("Название изменено!", ephemeral=True)
        else:
            await interaction.response.send_message("Канал не найден.", ephemeral=True)

class LimitModal(Modal):
    def __init__(self, owner):
        super().__init__(title="Установить лимит")
        self.owner = owner
        self.limit = TextInput(label="Число (0–99)")
        self.add_item(self.limit)

    async def on_submit(self, interaction):
        ch = interaction.guild.get_channel(user_private_channels.get(self.owner))
        try:
            num = int(self.limit.value)
            num = max(0, min(99, num))
            await ch.edit(user_limit=num)
            await interaction.response.send_message(f"Лимит установлен: {num}", ephemeral=True)
        except:
            await interaction.response.send_message("Ошибка.", ephemeral=True)

class BitrateModal(Modal):
    def __init__(self, owner):
        super().__init__(title="Изменить битрейт")
        self.owner = owner
        self.bitrate = TextInput(label="8000–96000")
        self.add_item(self.bitrate)

    async def on_submit(self, interaction):
        ch = interaction.guild.get_channel(user_private_channels.get(self.owner))
        try:
            num = int(self.bitrate.value)
            num = max(8000, min(96000, num))
            await ch.edit(bitrate=num)
            await interaction.response.send_message(f"Битрейт установлен: {num}", ephemeral=True)
        except:
            await interaction.response.send_message("Ошибка.", ephemeral=True)

class RestrictModal(Modal):
    def __init__(self, owner):
        super().__init__(title="Заблокировать пользователя")
        self.owner = owner
        self.uid = TextInput(label="ID пользователя")
        self.add_item(self.uid)

    async def on_submit(self, interaction):
        ch = interaction.guild.get_channel(user_private_channels.get(self.owner))
        try:
            user = interaction.guild.get_member(int(self.uid.value))
            if not user:
                return await interaction.response.send_message("Пользователь не найден.", ephemeral=True)
            await ch.set_permissions(user, connect=False)
            await interaction.response.send_message(f"{user.mention} заблокирован.", ephemeral=True)
        except:
            await interaction.response.send_message("Неверный ID.", ephemeral=True)

# -------------------------- КНОПКИ --------------------------
class ChannelControlPersistent(View):
    def __init__(self):
        super().__init__(timeout=None)  # Persistent view

    async def get_user_channel(self, interaction):
        ch_id = user_private_channels.get(interaction.user.id)
        if not ch_id:
            await interaction.response.send_message("❌ У тебя нет приватного канала.", ephemeral=True)
            return None
        ch = interaction.guild.get_channel(ch_id)
        if not ch:
            await interaction.response.send_message("❌ Канал не найден.", ephemeral=True)
            return None
        return ch

    @discord.ui.button(label="✏️", style=discord.ButtonStyle.primary, custom_id="rename_button")
    async def rename(self, interaction, button):
        ch = await self.get_user_channel(interaction)
        if ch:
            await interaction.response.send_modal(RenameModal(interaction.user.id))

    @discord.ui.button(label="👥", style=discord.ButtonStyle.success, custom_id="limit_button")
    async def limit(self, interaction, button):
        ch = await self.get_user_channel(interaction)
        if ch:
            await interaction.response.send_modal(LimitModal(interaction.user.id))

    @discord.ui.button(label="🎚️", style=discord.ButtonStyle.secondary, custom_id="bitrate_button")
    async def bitrate(self, interaction, button):
        ch = await self.get_user_channel(interaction)
        if ch:
            await interaction.response.send_modal(BitrateModal(interaction.user.id))

    @discord.ui.button(label="🚫", style=discord.ButtonStyle.danger, custom_id="restrict_button")
    async def restrict(self, interaction, button):
        ch = await self.get_user_channel(interaction)
        if ch:
            await interaction.response.send_modal(RestrictModal(interaction.user.id))

    @discord.ui.button(label="🔒", style=discord.ButtonStyle.secondary, custom_id="lock_button")
    async def lock(self, interaction, button):
        ch = await self.get_user_channel(interaction)
        if not ch:
            return
        everyone = interaction.guild.default_role
        perms = ch.overwrites_for(everyone)
        if perms.connect is False:
            await ch.set_permissions(everyone, connect=True)
            await interaction.response.send_message("🔓 Канал открыт.", ephemeral=True)
        else:
            await ch.set_permissions(everyone, connect=False)
            await interaction.response.send_message("🔒 Канал закрыт.", ephemeral=True)

    @discord.ui.button(label="⚙️", style=discord.ButtonStyle.secondary, custom_id="settings_button")
    async def settings(self, interaction, button):
        ch = await self.get_user_channel(interaction)
        if not ch:
            return
        emb = discord.Embed(
            title="⚙️ Настройки",
            description=(
                f"**Имя:** {ch.name}\n"
                f"**Лимит:** {ch.user_limit}\n"
                f"**Битрейт:** {ch.bitrate}\n"
                f"**ID:** `{ch.id}`"
            ),
            color=0x00A2FF
        )
        await interaction.response.send_message(embed=emb, ephemeral=True)

# -------------------------- КОМАНДА !voice --------------------------
@bot.command()
async def voice(ctx):
    ch = ctx.guild.get_channel(VOICE_CONTROL_CHANNEL_ID)
    if not ch:
        return await ctx.send("❌ Канал панели не найден.")

    # Отправка картинки
    try:
        image_path = "20251119_2002_Замена Текста Manager_remix_01kaea2a3be0yvrbj69d838xg5 (1).png"
        file = discord.File(image_path, filename="voice_control.png")
        img_embed = discord.Embed(color=0x00AAFF)
        img_embed.set_image(url="attachment://voice_control.png")
        await ctx.send(file=file, embed=img_embed)
    except Exception as e:
        await ctx.send("❌ Не удалось отправить картинку панели.")
        print(e)

    # Настройки в embed + view
    settings_embed = discord.Embed(
        title="🎛 Управление приватным голосовым каналом",
        description=(
            "✏️ — Переименовать\n"
            "👥 — Установить лимит пользователей\n"
            "🎚️ — Изменить битрейт\n"
            "🚫 — Ограничить доступ пользователям\n"
            "🔒 — Закрыть / открыть канал\n"
            "⚙️ — Проверить настройки\n"
        ),
        color=0x00AAFF
    )
    await ch.send(embed=settings_embed, view=ChannelControlPersistent())

# -------------------------- КОМАНДЫ rules / welcome --------------------------
@bot.command()
async def rules(ctx):
    try:
        file = discord.File("rules.png", filename="rules.png")
        img = discord.Embed(color=0x00AAFF)
        img.set_image(url="attachment://rules.png")
        await ctx.send(file=file, embed=img)

        embed = discord.Embed(
            title="📜 Глобальные правила сервера",
            description="Добро пожаловать! Соблюдай правила.",
            color=0x00AAFF
        )
        embed.add_field(name="🔥 Уважение", value="Не оскорблять.", inline=False)
        embed.add_field(name="💬 Чат", value="Не спамить.", inline=False)
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send("Ошибка отправки правил.")
        print(e)

@bot.command()
async def welcome(ctx):
    try:
        file = discord.File("welcome.png", filename="welcome.png")
        img = discord.Embed(color=0xFFAA00)
        img.set_image(url="attachment://welcome.png")
        await ctx.send(file=file, embed=img)

        embed = discord.Embed(
            title="🎉 Добро пожаловать!",
            description="Мы рады видеть тебя на сервере Cubex33Games!",
            color=0xFFAA00
        )
        await ctx.send(embed=embed)
    except:
        await ctx.send("Ошибка приветствия.")

# -------------------------- ДРУГИЕ КОМАНДЫ --------------------------
@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

@bot.command()
async def echo(ctx, *, text):
    await ctx.send(text)

# -------------------------- ЗАПУСК БОТА --------------------------
bot.run(TOKEN)