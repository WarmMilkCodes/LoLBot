import config, dbInfo, discord, os, logging
from discord.ext import commands
from discord.commands import Option

logger = logging.getLogger('lol_log')

class ReplaysCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        logger.info("ReplaysCog loaded.")

    @commands.slash_command(description="Upload replay file")
    @commands.has_any_role("Bot Guy", "Owner", "League Ops")
    async def replay_submission(self, ctx, file: discord.Attachment):
        await ctx.defer()

        temp_dir = './temp'
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)

        file_path = f"./temp/{file.filename}"
        await file.save(file_path)

        json_object = extract_json_from_rofl(file_path)
        if json_object:
            with open('temp_json_output.json', 'w') as json_file:
                json.dump(json_object, json_file, indent=4)

            with open('temp_json_output.json', 'rb') as json_file:
                await ctx.send(file=discord.File(json_file, 'output.json'))

        else:
            await ctx.respond("Error submitting replay!", ephemeral=True)

        # Clean up after processing
        os.remove(file_path)

import json

def extract_json_from_rofl(file_name):
    with open(file_name, 'rb') as file:
        content = file.read()
        brace_stack = []
        start_idx = None
        end_idx = None

        for idx, byte in enumerate(content):
            if byte == ord('{'):  # If it's an opening brace
                brace_stack.append(idx)
                if start_idx is None:
                    start_idx = idx  # Potential start of JSON
            elif byte == ord('}'):  # If it's a closing brace
                if brace_stack:
                    start_idx_candidate = brace_stack.pop()
                    if not brace_stack:  # All braces closed
                        end_idx = idx  # Potential end of JSON
                        break  # We found the matching closing brace

        if start_idx is not None and end_idx is not None:
            json_bytes = content[start_idx:end_idx + 1]
            try:
                json_str = json_bytes.decode('utf-8', 'ignore')
                json_object = json.loads(json_str)
                return json_object
            except json.JSONDecodeError as e:
                logger.warning(f"Error decoding JSON: {e}")
        return None  # If no JSON structure was found

def setup(bot):
    bot.add_cog(ReplaysCog(bot))