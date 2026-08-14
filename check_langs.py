import asyncio
import edge_tts

async def main():
    voices = await edge_tts.list_voices()
    print("Punjabi:", [v['ShortName'] for v in voices if v['Locale'].startswith('pa')])
    print("Urdu:", [v['ShortName'] for v in voices if v['Locale'].startswith('ur')])
    print("Hindi:", [v['ShortName'] for v in voices if v['Locale'].startswith('hi')])
    print("English (all):", [v['ShortName'] for v in voices if v['Locale'].startswith('en')])

asyncio.run(main())
