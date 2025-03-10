import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import asyncio
import random
import io
import os
import logging

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(message)s')

# ============ CONFIGURAÇÕES GLOBAIS ============
TOKEN = os.environ["Token"]  # Seu token do bot
GUILD_ID = 1346523864699506829  # ID do servidor

# IDs dos cargos
CARGO_RESTRITO_ID = 1346529577865969695       # Cargo de "Visitante" (restrição)
CARGO_TEC_TUNAGEM_ID = 1346549148773519362     # Cargo "Técnico de Tunagem" (habilitação)

# Canais fixos
CANAL_AUTORIZACAO_ID = 1346529407375769742  # Canal de habilitação
CANAL_PROVA_ID = 1346529440389402624        # Canal onde o botão de prova fica
CANAL_LOG_ID = 1346539009395916891          # Canal para transcript

# Categoria para criação do canal de prova
CATEGORIA_PROVA_ID = 1346565192200355963

# Lista global de IDs autorizados para iniciar a prova
autorizados = set()

# Perguntas da prova (texto, peso)
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

# Embeds padrão
embed_iniciar_prova = discord.Embed(
    title="Bem Vindo ao Sistema de Provas da RedLine",
    description=(
          "**Atenção:**\n"
            "Ao iniciar a prova, todos os seus cargos serão retirados e você perderá acesso a vários canais do servidor. "
            "Os seus cargos serão devolvidos ao final da prova.\n\n"
            "- Ao iniciar a prova você terá 1 minuto para responder cada questão.\n"
            "- Você precisa tirar 20 ou mais pontos para passar na prova.\n"
            "- Atingir entre 15 e 18 pontos resulta em advertência e precisará farmar 100 kits.\n"
            "- Atingir menos de 10 pontos fica sujeito a PD e precisará farmar 300 kits.\n"
            "- A prova tem um total de 15 questões e vale um total de 30 pontos.\n\n"
            "**Observação:** Após terminar a prova, aguarde que um superior faça a correção, lembrando que a prova será salva.\n\n"
            "Quando estiver pronto, clique no botão abaixo para iniciar a prova:"
    ),
    color=discord.Color.red()
)

embed_habilitar_prova = discord.Embed(
    title="📝 HABILITAR PROVA 📝",
    description=(
        "Clique no botão abaixo para habilitar o menor aprendiz para a prova.\n"
        "Apenas **Técnico de Tunagem** ou superior pode realizar essa ação!"
    ),
    color=discord.Color.blue()
)

# ============ INTENTS E BOT ============
intents = discord.Intents.default()
intents.guilds = True
intents.members = True        # Necessário para acessar os membros do servidor
intents.messages = True
intents.message_content = True  # Necessário para ler o conteúdo das mensagens

bot = commands.Bot(command_prefix="/", intents=intents)

# ============ FUNÇÕES DE LIMPEZA ============
async def cleanup_authorization_channel(bot_instance: commands.Bot):
    """Limpa o canal de autorização e reenvia a mensagem padrão."""
    await asyncio.sleep(5)
    guild = bot_instance.get_guild(GUILD_ID)
    canal_autorizacao = guild.get_channel(CANAL_AUTORIZACAO_ID)
    try:
        await canal_autorizacao.purge(limit=None, check=lambda m: not m.pinned)
        # Obtém a view do cog de autorização
        cog = bot_instance.get_cog("AuthorizationCog")
        if cog is not None:
            view_instance = cog.get_view_instance()
            await canal_autorizacao.send(embed=embed_habilitar_prova, view=view_instance)
        else:
            logging.error("AuthorizationCog não encontrado!")
    except Exception as e:
        logging.error("Erro na limpeza do canal de autorização: %s", e)

async def cleanup_main_prova_channel(bot_instance: commands.Bot):
    """Limpa o canal de prova e reenvia a mensagem padrão."""
    await asyncio.sleep(5)
    guild = bot_instance.get_guild(GUILD_ID)
    canal_prova = guild.get_channel(CANAL_PROVA_ID)
    try:
        await canal_prova.purge(limit=None, check=lambda m: not m.pinned)
        cog = bot_instance.get_cog("TestCog")
        if cog is not None:
            view_instance = cog.get_view_instance()
            await canal_prova.send(embed=embed_iniciar_prova, view=view_instance)
        else:
            logging.error("TestCog não encontrado!")
    except Exception as e:
        logging.error("Erro na limpeza do canal de prova: %s", e)

# ============ COG DE AUTORIZAÇÃO ============
class AuthorizationCog(commands.Cog, name="AuthorizationCog"):
    def __init__(self, bot_instance: commands.Bot):
        self.bot = bot_instance

    def get_view_instance(self):
        return self.AutorizarView()

    class HabilitarModal(Modal):
        def __init__(self):
            super().__init__(title="RedLine Performance", timeout=180, custom_id="habilitar_modal")
            self.user_id_input = TextInput(
                label="Insira o ID",
                style=discord.TextStyle.short,
                placeholder="Digite o ID do usuário aqui",
                required=True,
                max_length=30
            )
            self.add_item(self.user_id_input)

        async def on_submit(self, interaction: discord.Interaction):
            guild = interaction.client.get_guild(GUILD_ID)
            cargo_tec = guild.get_role(CARGO_TEC_TUNAGEM_ID)
            if cargo_tec not in interaction.user.roles:
                await interaction.response.send_message("Você não tem permissão para habilitar a prova!", ephemeral=True)
                return

            user_id_str = self.user_id_input.value.strip()
            try:
                possible_id = int(user_id_str)
                target_member = guild.get_member(possible_id)
                if target_member is None:
                    target_member = await guild.fetch_member(possible_id)
            except (ValueError, discord.NotFound):
                target_member = discord.utils.find(
                    lambda m: m.nick and user_id_str.lower() in m.nick.lower(),
                    guild.members
                )
            if target_member is None:
                await interaction.response.send_message("Usuário não encontrado. Verifique o ID ou apelido.", ephemeral=True)
                await cleanup_authorization_channel(interaction.client)
                return

            autorizados.add(target_member.id)
            await interaction.response.send_message(
                f"Usuário {target_member.mention} foi habilitado para iniciar a prova!",
                ephemeral=False
            )
            await cleanup_authorization_channel(interaction.client)

    class AutorizarView(View):
        def __init__(self):
            super().__init__(timeout=None)

        @discord.ui.button(label="Habilitar Prova", style=discord.ButtonStyle.green, custom_id="habilitar_prova")
        async def habilitar_prova(self, interaction: discord.Interaction, button: Button):
            guild = interaction.client.get_guild(GUILD_ID)
            cargo_tec = guild.get_role(CARGO_TEC_TUNAGEM_ID)
            if cargo_tec not in interaction.user.roles:
                await interaction.response.send_message(
                    "Você não tem cargo de Técnico de Tunagem para habilitar!",
                    ephemeral=True
                )
                return
            await interaction.response.send_modal(AuthorizationCog.HabilitarModal())

    @commands.Cog.listener()
    async def on_error(self, event_method, *args, **kwargs):
        logging.error("Erro no Cog de Autorização: %s", event_method, exc_info=True)

# ============ COG DE PROVA ============
class TestCog(commands.Cog, name="TestCog"):
    def __init__(self, bot_instance: commands.Bot):
        self.bot = bot_instance

    def get_view_instance(self):
        return self.ProvaView()

    class ProvaView(View):
        def __init__(self):
            super().__init__(timeout=None)

        @discord.ui.button(label="Iniciar Prova", style=discord.ButtonStyle.red, custom_id="iniciar_prova")
        async def iniciar_prova(self, interaction: discord.Interaction, button: Button):
            member = interaction.user
            if member.id not in autorizados:
                await interaction.response.send_message("Você não está autorizado!", ephemeral=True)
                return
            autorizados.remove(member.id)

            guild = interaction.client.get_guild(GUILD_ID)
            old_roles = [r for r in member.roles if r != guild.default_role]
            try:
                for r in old_roles:
                    await member.remove_roles(r)
                cargo_visitante = guild.get_role(CARGO_RESTRITO_ID)
                await member.add_roles(cargo_visitante)
            except Exception as e:
                logging.error("Erro ao modificar cargos do usuário: %s", e)
                await interaction.response.send_message("Erro ao ajustar seus cargos. Tente novamente.", ephemeral=True)
                return

            categoria_prova = guild.get_channel(CATEGORIA_PROVA_ID)
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                member: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
            }
            try:
                canal_temp = await guild.create_text_channel(
                    name=f"prova-{member.display_name}",
                    category=categoria_prova,
                    overwrites=overwrites
                )
            except Exception as e:
                logging.error("Erro ao criar canal de prova: %s", e)
                await interaction.response.send_message("Erro ao criar canal de prova. Tente novamente.", ephemeral=True)
                return

            await interaction.response.send_message(
                f"{member.mention}, seu canal de prova foi criado: {canal_temp.mention}!"
            )
            await canal_temp.send(
                f"{member.mention}, **sua prova começou!** Você tem 1 minuto para responder cada questão.\nResponda abaixo de cada pergunta."
            )

            perguntas_sorteadas = random.sample(PERGUNTAS, 15)
            respostas = []
            for i, (pergunta, peso) in enumerate(perguntas_sorteadas, start=1):
                await canal_temp.send(f"**{i}) {pergunta}** (Peso: {peso} pontos)")
                def resposta_check(m):
                    return m.author == member and m.channel == canal_temp
                try:
                    msg = await interaction.client.wait_for("message", check=resposta_check, timeout=60)
                    respostas.append((pergunta, msg.content))
                except asyncio.TimeoutError:
                    respostas.append((pergunta, "Não respondeu"))
                    await canal_temp.send("Tempo esgotado para essa questão!")

            await canal_temp.send(f"{member.mention}, sua prova acabou! Estou restaurando seus cargos...")
            try:
                await member.remove_roles(cargo_visitante)
                for r in old_roles:
                    await member.add_roles(r)
            except Exception as e:
                logging.error("Erro ao restaurar cargos: %s", e)

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
            try:
                await canal_log.send(
                    content=f"Transcript da prova de {member.display_name} (ID {member.id}):",
                    file=discord.File(file_buffer, filename=f"prova_{member.id}.txt")
                )
            except Exception as e:
                logging.error("Erro ao enviar transcript: %s", e)

            await canal_temp.send("Este canal será deletado em instantes...")
            await asyncio.sleep(2)
            try:
                await canal_temp.delete()
            except Exception as e:
                logging.error("Erro ao deletar canal de prova: %s", e)
            await cleanup_main_prova_channel(interaction.client)

    @commands.Cog.listener()
    async def on_error(self, event_method, *args, **kwargs):
        logging.error("Erro no Cog de Prova: %s", event_method, exc_info=True)

# ============ EVENTOS ============
@bot.event
async def on_ready():
    logging.info(f"Bot conectado como {bot.user}")
    # Adiciona os cogs aguardando-os corretamente
    await bot.add_cog(AuthorizationCog(bot))
    await bot.add_cog(TestCog(bot))
    # Após os cogs serem adicionados, executa a limpeza dos canais
    await cleanup_authorization_channel(bot)
    await cleanup_main_prova_channel(bot)

bot.run(TOKEN)
