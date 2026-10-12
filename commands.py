"""Things said to Lorekeeper itself, handled at once with no AI. parse(text) -> (action, arg) or None."""
import re

RULES = [
    ('stop', r'(?:stop|shush|quiet|be quiet|shut up|never ?mind|cancel)'),
    ('repeat', r'(?:repeat(?: that)?|say (?:that|it) again|what did you say|come again)'),
    ('clip', r'(?:clip (?:it|that|this)|save (?:a |that |the )?clip|(?:make|take) a clip|clip the last .+)'),
    ('spoil', r'(?:(?:ok(?:ay)?,? )?spoil (?:it|that|away)(?: for me)?|spoilers? on|go ahead and spoil(?: it)?)'),
    ('playing', r"(?:i'?m|i am|we'?re) (?:now )?playing (.+)"),
    ('auto', r'(?:detect (?:the )?game|auto(?:matic)?(?: detect)?|forget (?:the|which) game)'),
    ('note', r'(?:note|remember|note that|make a note|take a note)[:,]? (.+)'),
    ('note', r"((?:i'?m|i am) (?:at|in|on|up to|past) .+|i (?:just )?(?:beat|killed|finished|defeated|reached|unlocked|chose|picked|sided with|got to) .+)"),
]
NOT_PROGRESS = re.compile(r'\b(what|where|how|who|why|which|should|does|is it|can i)\b', re.I)


def clean(text):
    return re.sub(r'\s+', ' ', re.sub(r'^(?:hey |ok(?:ay)? )?(?:lorekeeper|keeper)[,:]? ', '', text.strip(), flags=re.I)).strip(' .!?')


def parse(text):
    t = clean(text)
    for action, rx in RULES:
        m = re.fullmatch(rx, t, re.I)
        if m:
            arg = m.group(1).strip(' .') if m.groups() else ''
            if action == 'note' and NOT_PROGRESS.search(arg) and not t.lower().startswith(('note', 'remember', 'make a note', 'take a note')):
                return None   # "I'm at Stormveil, where do I go?" is a question
            if action == 'playing' and NOT_PROGRESS.search(arg):
                return None
            return action, arg
    return None
