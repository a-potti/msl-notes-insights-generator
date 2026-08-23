import os, anthropic
from insighthub.corpus import get_note

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
note = get_note("NOTE-0009")          # a long advisory-board debrief

resp = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=1024,
    messages=[{"role": "user",
               "content": f"Extract the insights from this call note:\n\n{note.text}"}],
)
print(resp.content[0].text)
print("---")
print(resp.usage)
