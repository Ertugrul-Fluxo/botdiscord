import discord
from discord.ext import commands
from discord.ui import Button, View
import asyncio
import random
import io
import os


# ============ CONFIGURAÇÕES DO BOT ============
TOKEN = os.environ["Token"]  # Substitua pelo seu token de bot válido
GUILD_ID = 1346523864699506829  # ID do servidor

# Cargo que restringe (Visitante)
CARGO_RESTRITO_ID = 1346529577865969695

# Cargo "Técnico de Tunagem" (quem pode habilitar a prova)
CARGO_TEC_TUNAGEM_ID = 1346549148773519362

# Canais fixos
CANAL_AUTORIZACAO_ID = 1346529407375769742  # Canal onde IDs são autorizados
CANAL_PROVA_ID = 1346529440389402624        # Canal onde o usuário clica para iniciar a prova
CANAL_LOG_ID = 1346539009395916891          # Canal onde serão enviados os transcripts

# Categoria onde o canal de prova será criado
CATEGORIA_PROVA_ID = 1346565192200355963

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True  # Necessário para ler o conteúdo das mensagens

bot = commands.Bot(command_prefix="/", intents=intents)

# ============ DADOS DA PROVA ============
autorizados = set()  # IDs de usuários que podem iniciar a prova

# Perguntas (com pesos)
PERGUNTAS = [
    ("CITE 3 MOTIVOS QUE GERAM ADVERTÊNCIA", 2),
    ("QUAL VALOR DO MÓDULO NEON E KIT REPARO COM E SEM PARCERIA?", 2),
    ("QUANTO CUSTA O FULL TUNING COM E SEM PARCERIA?", 2),
    ("O QUE É OPCIONAL DAR DE BRINDE PARA OS CLIENTES?", 1),
    ("QUANTO CUSTA A PINTURA RGB COM E SEM PARCERIA?", 2),
    ("QUANTO CUSTA OS ITENS QUE NÃO ESTÃO NA TABELA?", 1),
    ("CITE 2 ACESSÓRIOS QUE NÃO ESTÃO NA TABELA", 3),
    ("QUANTO CUSTA A SUSPENSÃO?", 2),
    ("QUANTAS E QUAIS SÃO AS PEÇAS DO FULL TUNING?", 4),
    ("CITE 3 TIPOS DE PINTURAS", 1),
    ("QUANTO CUSTA O PNEU BLINDADO COM E SEM PARCERIA?", 2),
    ("QUANTO CUSTA A RODA COM E SEM PARCERIA?", 2),
    ("QUANTO CUSTA O REPARO NO NORTE E SUL?", 2),
    ("QUANTO CUSTA A FULL BLINDAGEM COM E SEM PARCERIA?", 2),
    ("CITE NO MÍNIMO 5 PARCERIAS DO ILEGAL ATIVAS", 2)
]

# ===================== EMBEDS =====================
embed_iniciar_prova = discord.Embed(
    title="Bem Vindo ao Sistema de Provas da RedLine",
    description=(
        "**Atenção:**\n"
        "Ao iniciar a prova, todos os seus cargos serão retirados e você perderá acesso a vários canais do servidor. "
        "O tempo da prova será reiniciado e seus cargos serão devolvidos ao final da prova.\n\n"
        "- Ao iniciar a prova você terá 1 minuto para responder cada questão.\n"
        "- Para cada pergunta errada ou não respondida você perderá 20 pontos.\n"
        "- Atingir menos de 18 pontos resulta em advertência.\n"
        "- Atingir menos de 10 pontos fica sujeito a PD.\n"
        "- A prova tem um total de 15 questões e um total de 30 pontos.\n\n"
        "**Observação:** Após terminar a prova, aguarde que um superior faça a correção, lembrando que a prova será salva.\n\n"
        "Quando estiver pronto, clique no botão abaixo para iniciar a prova:"
    ),
    color=discord.Color.red()
)

embed_habilitar_prova = discord.Embed(
    title="📝 HABILITAR PROVA 📝",
    description=(
        "Para habilitar alguém a fazer a prova, clique no botão abaixo.\n\n"
        "Apenas **Técnico de Tunagem** pode habilitar!"
    ),
    color=discord.Color.blue()
)

# ============ FUNÇÕES DE LIMPEZA ============

async def cleanup_authorization_channel():
    """Aguarda 5s, limpa o canal de autorização e reenvia a mensagem inicial."""
    await asyncio.sleep(5)
    guild = bot.get_guild(GUILD_ID)
    canal_autorizacao = guild.get_channel(CANAL_AUTORIZACAO_ID)
    await canal_autorizacao.purge(limit=None, check=lambda m: not m.pinned)
    await canal_autorizacao.send(embed=embed_habilitar_prova, view=AutorizarView())

async def cleanup_main_prova_channel():
    """Aguarda 5s, limpa o canal principal de provas e reenvia a mensagem inicial."""
    await asyncio.sleep(5)
    guild = bot.get_guild(GUILD_ID)
    canal_prova = guild.get_channel(CANAL_PROVA_ID)
    await canal_prova.purge(limit=None, check=lambda m: not m.pinned)
    await canal_prova.send(embed=embed_iniciar_prova, view=ProvaView())

# ===================== VIEW DA PROVA (INICIAR) =====================
class ProvaView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Iniciar Prova", style=discord.ButtonStyle.red, custom_id="iniciar_prova")
    async def iniciar_prova(self, interaction: discord.Interaction, button: Button):
        """Cria um canal de prova e inicia o processo, se o usuário estiver autorizado."""
        member = interaction.user

        if member.id not in autorizados:
            await interaction.response.send_message("Você não está autorizado!", ephemeral=True)
            return

        autorizados.remove(member.id)
        guild = bot.get_guild(GUILD_ID)
        old_roles = [r for r in member.roles if r != guild.default_role]
        for r in old_roles:
            await member.remove_roles(r)
        cargo_visitante = guild.get_role(CARGO_RESTRITO_ID)
        await member.add_roles(cargo_visitante)
        categoria_prova = guild.get_channel(CATEGORIA_PROVA_ID)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        canal_temp = await guild.create_text_channel(
            name=f"prova-{member.display_name}",
            category=categoria_prova,
            overwrites=overwrites
        )
        await interaction.response.send_message(
            f"{member.mention}, seu canal de prova foi criado: {canal_temp.mention}",
            ephemeral=True
        )
        await canal_temp.send(
            f"{member.mention}, sua prova começou! Você tem 1 minuto para responder cada questão."
        )

        # Coleta as respostas do usuário para as 15 perguntas sorteadas
        perguntas_sorteadas = random.sample(PERGUNTAS, 15)
        respostas = []
        for i, (pergunta, peso) in enumerate(perguntas_sorteadas, start=1):
            await canal_temp.send(f"**{i}) {pergunta}** (Peso: {peso} pontos)")
            def resposta_check(m):
                return m.author == member and m.channel == canal_temp
            try:
                msg = await bot.wait_for("message", check=resposta_check, timeout=60)
                respostas.append((pergunta, msg.content))
            except asyncio.TimeoutError:
                respostas.append((pergunta, "Não respondeu"))
                await canal_temp.send("Tempo esgotado para essa questão!")

        await canal_temp.send(f"{member.mention}, sua prova acabou! Estou restaurando seus cargos...")
        await member.remove_roles(cargo_visitante)
        for r in old_roles:
            await member.add_roles(r)

        # Gera um transcript formatado de maneira agradável
        transcript_str = (
            "========================================\n"
            "           TRANSCRIPT DA PROVA          \n"
            "========================================\n\n"
            f"Nome: {member.display_name}\n"
            f"ID: {member.id}\n\n"
        )
        for idx, (pergunta, resposta) in enumerate(respostas, start=1):
            transcript_str += (
                f"Questão {idx}:\n"
                f"Pergunta: {pergunta}\n"
                f"Resposta: {resposta}\n"
                "----------------------------------------\n\n"
            )

        canal_log = guild.get_channel(CANAL_LOG_ID)
        file_buffer = io.BytesIO(transcript_str.encode('utf-8'))
        await canal_log.send(
            content=f"Transcript da prova de {member.display_name} (ID {member.id}):",
            file=discord.File(file_buffer, filename=f"prova_{member.id}.txt")
        )

        await canal_temp.send("Este canal será deletado em instantes...")
        await asyncio.sleep(2)
        await canal_temp.delete()

        await interaction.followup.send(
            f"{member.mention}, prova finalizada e transcript salvo no log!",
            ephemeral=True
        )
        await cleanup_main_prova_channel()

# ===================== VIEW PARA HABILITAR PROVA =====================
class AutorizarView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Habilitar Prova", style=discord.ButtonStyle.green, custom_id="habilitar_prova")
    async def habilitar_prova(self, interaction: discord.Interaction, button: Button):
        """Só quem for 'Técnico de Tunagem' pode habilitar a prova."""
        member = interaction.user
        guild = bot.get_guild(GUILD_ID)
        cargo_tec = guild.get_role(CARGO_TEC_TUNAGEM_ID)
        if cargo_tec not in member.roles:
            await interaction.response.send_message(
                "Você não tem cargo de Técnico de Tunagem para habilitar!",
                ephemeral=True
            )
            return
        await interaction.response.send_message(
            "Envie o **ID do usuário** ou um trecho presente no apelido para habilitar:",
            ephemeral=True
        )
        def check(m):
            return m.author == member and m.channel == interaction.channel
        try:
            msg = await bot.wait_for("message", check=check, timeout=90)
            user_id_str = msg.content.strip()
            target_member = discord.utils.find(
                lambda m: m.nick and user_id_str.lower() in m.nick.lower(),
                guild.members
            )
            if target_member is None:
                try:
                    possible_id = int(user_id_str)
                    target_member = guild.get_member(possible_id)
                except ValueError:
                    await interaction.channel.send(
                        "Não encontrei esse apelido nem consegui converter para ID numérico."
                    )
                    await cleanup_authorization_channel()
                    return
            if target_member is None:
                await interaction.channel.send(
                    "Usuário não encontrado. Verifique o apelido/ID e tente novamente."
                )
                await cleanup_authorization_channel()
                return
            autorizados.add(target_member.id)
            await interaction.channel.send(
                f"Usuário {target_member.mention} está habilitado para iniciar a prova!"
            )
        except asyncio.TimeoutError:
            await interaction.channel.send("Tempo expirado. Tente novamente.")
        finally:
            await cleanup_authorization_channel()

# ============ EVENTOS ============
@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")
    bot.add_view(ProvaView())
    bot.add_view(AutorizarView())
    await cleanup_authorization_channel()
    await cleanup_main_prova_channel()

bot.run(TOKEN)
