# Receipt-Photobooth

This is a much richer frame, and it changes the project meaningfully. You're not really making a toy with backstory — you're making a _device that performs the seduction_ so the viewer feels it in their body, and the artist statement is where the critique lands. The piece is the bait; the statement is the hook. That's a strong structure. Let me reflect the whole thing back and sharpen it.

**The core move.** The sculpture does to the viewer exactly what you're critiquing: it's cute, it flatters you, it wants to be your friend, it offers to know you and tell you your future — and you _like_ it. You walk away charmed. Then the statement reframes that charm as the exact mechanism that 90s "friendly tech" trained us to accept, and that today's AI and surveillance economy exploit at scale. The discomfort isn't in the experience; it's retroactive. You realize you just enjoyed being read. That's far better than a creepy object, because complicity is the point.

**The three threads and how they brace each other.** You're juggling three critiques, and they're actually one argument:

The first is the _AI-sycophancy_ thread — technology that compliments you, tells you you're smart, wants to help, wants to be your friend. The toy embodies the friendly-companion lineage (Teddy Ruxpin, Furby, Tamagotchi) and the statement connects it to the present, where that same warmth is engineered to maximize engagement and trust.

The second is the _innocent-then-sinister_ thread — the same impulse "to know you" felt playful in the 90s and is predatory now, and your sharp insight is that _the technology didn't turn sinister, we did_ — it's a choice about use, not an inherent property. That keeps the piece from being naive anti-tech doom.

The third — and this is the one that elevates it from "AI bad" to something with real teeth — is the _nostalgia-as-distortion_ thread. The blur of "simpler times" is itself the trap. The piece makes you feel that "things were better then," and the statement turns and says: were they? That same yearning to "go back" is the engine of reactionary politics — _make it great again_, arm yourself with a past that didn't exist. So the nostalgia the toy generates is implicated in the same way the flattery is. Both are comforting lies that ask nothing of you and steer you somewhere.

That third thread is what makes the other two land harder, because it indicts the _viewer's own feeling_ rather than just the technology. The piece manufactures a feeling and then questions whether you should trust feelings manufactured for you — which is the whole point about AI and about political nostalgia at once.

**On the nostalgia etymology** — you're remembering it right, and it's a perfect spine for the statement. Let me confirm the history.Your memory of the article is dead-on, and the history is even better than you remembered for your purposes.

The word was coined in 1688 by a nineteen-year-old Swiss medical student, Johannes Hofer, who built it from the Greek _nostos_ (homecoming) and _algos_ (pain/grief). It described a diagnosable and sometimes fatal disease, treated with opium and bloodletting and in one case the threat of being buried alive. Sufferers took on a lifeless, haggard countenance, became indifferent to their surroundings, confused past and present, and even hallucinated voices and ghosts. Notably, it wasn't disproved out of existence — it was retired from medical classification not because it was disproved, but because medicine outgrew the framework that made it legible as a disease. And there's a detail that's pure gold for your statement: Hofer didn't invent it during a moment of progress — he coined it amid the conflicts and instability of the General Crisis of the Seventeenth Century. Nostalgia was born in an age of upheaval, as a _symptom_ of it.

So the arc is exactly the inversion you want: nostalgia began as a _war disease_ — a potentially lethal longing to return to a home that displaced soldiers couldn't reach — and over three centuries it softened into a warm, bittersweet emotion, a longing for a bygone era, a childhood melody, a sepia photograph. The teeth got pulled. We forgot it was ever a sickness.

That's your whole thesis in one etymology, and it braces all three threads:

The piece _gives you_ the soft sepia version — the cute toy, the receipt, the feeling of being known. The statement reminds you the word started as a deadly disorder of displaced soldiers in wartime, then asks the uncomfortable question: which version is the truth? When a culture under strain starts aching to "go back," is that the warm feeling or the war disease? _Make it great again_ is nostalgia in its original clinical sense — a longing for a home that doesn't exist, severe enough to make people do dangerous things. The toy flatters you with the sweet version; the history reveals the sweet version was always a sedated form of the sick one.

It also rhymes with the AI thread perfectly: the 90s friendly-toy tech felt like the soft version (cute, harmless, your pal), and the same impulse "to know you" is now the war-disease version (tracking, extraction, manipulation) — but we still talk to it like it's the Furby. Same softening, same forgetting, same teeth quietly pulled.

This gives you a clean two-layer structure for the whole project:

The **front** (sculpture + flyer + receipt) stays fully earnest-uncanny and warm. Tomorrow Friends Inc. sincerely wants to know you and help you and tell you your future. The viewer has a sweet time. No irony visible.

The **back** (artist statement) is where you pull the teeth back out — the etymology, the AI critique, the _we-did-this-not-the-tech_ point, and the political-nostalgia turn. The statement doesn't explain the toy; it diagnoses the _feeling the toy just gave you_.

A couple of decisions this surfaces:

The phrase "Tomorrow Friends" now does double work — it's a company that sold you the future as a friend, which is precisely the seduction you're critiquing. You might lean into that the friend is always _tomorrow_, never actually present. Worth keeping.

And it suggests a possible hidden spine for the receipt or flyer: the _nostos / algos_ split. A warm fortune on the front of the receipt, and somewhere — a footer, a fine-print line, a "diagnosis code" styled like a real receipt's barcode area — the original meaning leaks through. _home-woe._ A receipt always has that clinical garbage at the bottom (transaction codes, store numbers). You could bury the disease there.

Want to work on the artist statement next, now that we have its backbone — or develop the front-facing flyer/receipt language first and let the statement stay in your pocket?


python3 -c "
from gpiozero import Button
b = Button(23, pull_up=True)
print('Resting is_pressed =', b.is_pressed, '(should be False when untouched)')
b.when_pressed  = lambda: print('PRESSED')
b.when_released = lambda: print('released')
print('Now press the button...')
from signal import pause; pause()
"
