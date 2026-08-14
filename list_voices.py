import asyncio
import edge_tts
import os

async def list_en_voices():
    voices = await edge_tts.list_voices()
    en_voices = [v['ShortName'] for v in voices if v['ShortName'].startswith('en-') and 'Neural' in v['ShortName']]
    print(en_voices)

asyncio.run(list_en_voices())
