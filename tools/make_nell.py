"""Writes demo/nell/history.json: the demo user's chats, the event log of facts, and the quiz.

Run from the project folder:  python tools/make_nell.py
The history is written here as plain Python so it's easy to read and edit.
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "demo" / "nell" / "history.json"

U, A = "user", "assistant"

SESSIONS = [
    ("2026-01-06", "Leash training for a new dog", [
        (U, "Hi! I'm Nell. I just adopted a beagle named Biscuit and he pulls on the leash like crazy. Any tips?"),
        (A, "Congratulations on Biscuit! Beagles are scent hounds, so the pulling is usually his nose leading the way. A few things that help:\n1. Stop moving the moment the leash goes tight, and only walk on when it's slack.\n2. Reward him for walking at your side with small, smelly treats.\n3. Give him sniff breaks on cue, so he learns when it's his time to explore.\n4. Keep early sessions short: ten minutes, a few times a day.\nA front-clip harness can also take the edge off while he learns."),
        (U, "We walk along Cherry Creek here in Denver most mornings. It's busy with bikes. Should I avoid it?"),
        (A, "Busy paths are hard at first. Try quieter side streets for the first week or two, then go back to Cherry Creek at off-peak times. When a bike passes, step to the side, ask for a sit, and give him a treat. He'll learn that bikes mean pause and get a snack."),
        (U, "Perfect, thank you!"),
        (A, "You're welcome. Enjoy your walks with Biscuit!"),
    ]),
    ("2026-01-12", "Birthday dinner ideas", [
        (U, "My birthday's March 14 and I want to host dinner for eight people. Ideas? No satay though, I'm allergic to peanuts."),
        (A, "Happy early birthday! For eight people, a build-your-own taco night is easy and peanut-free: slow-cooked chicken tinga, black beans, rice, pickled onions, two salsas and warm tortillas. Or a pasta night: a big baked ziti, a green salad and garlic bread. Either way, check labels on sauces and desserts, since peanuts hide in some moles, granolas and baked goods. Want a shopping list?"),
        (U, "Tacos! Yes please, a shopping list."),
        (A, "Here you go:\n- 3 lb chicken thighs, 1 can chipotles in adobo, 2 onions, 1 head garlic\n- 2 cans black beans, 2 cups rice\n- 2 red onions and 6 limes for pickling\n- Tomatillos and jalapeños for salsa verde; tomatoes for salsa roja\n- 30 corn tortillas, cotija, cilantro, 4 avocados\n- Dessert: churros or a tres leches cake (check the label)"),
    ]),
    ("2026-01-19", "Shift-schedule spreadsheet", [
        (U, "I'm a barista at Lark Café and I got roped into making our shift schedule. Seven of us, open 6am to 6pm. Can you help me set up a spreadsheet?"),
        (A, "Sure. Use a grid with days across the top and shifts down the side: Open 6–12, Mid 10–4, Close 12–6. Put names in the cells. Add a second tab that totals hours per person with COUNTIF, so nobody goes over. Color-code openers and closers so gaps jump out."),
        (U, "Can you put me on later shifts when possible? I bike in, it's about 10 minutes, and I'd rather not ride in the dark at 5:30."),
        (A, "Makes sense. I'll put you on mid and closing shifts first. Here's a starting week:\n- Mon: Open Sam, Mid Nell, Close Jo\n- Tue: Open Ana, Mid Lee, Close Nell\n- Wed: Open Sam, Mid Nell, Close Raf\nand so on. Want the hours tab formula too?"),
    ]),
    ("2026-01-27", "Learning Figma", [
        (U, "I'm trying to switch into UX design. Where should I start with Figma?"),
        (A, "Good plan. Start with frames, auto layout and components: those three cover most real work. For a first project, redesign a screen you use every day. Then write a short case study: the problem, sketches, a wireframe, a clickable prototype, and what you'd test. Figma's own tutorials and the community files are free and good."),
        (U, "Ha, I could redesign the ordering tablet at work. Everyone hates it."),
        (A, "That's a great case study: you have real users and real pain points. Interview two or three coworkers, write down their top complaints, then design a fix and test it with them."),
    ]),
    ("2026-02-03", "Cover letter for Fernhill Studio", [
        (U, "Can you help with a cover letter for a junior UX designer job at Fernhill Studio? I still work at Lark Café, and I want to say what it taught me about people."),
        (A, "Here's an opening: \"For three years I've watched people make decisions at a café counter: in a hurry, distracted, sometimes confused by a menu. At Lark Café I learned to notice where people hesitate, and to fix it.\" Then a paragraph on your ordering-tablet redesign: who you interviewed, what you changed, and what happened. Close with why Fernhill in particular."),
        (U, "Love it. Can you make the ending less formal?"),
        (A, "\"I'd love to bring the same habit of watching, listening and fixing to Fernhill. Thanks for reading. I hope we get to talk.\""),
    ]),
    ("2026-02-10", "Recipe swaps", [
        (U, "Correction from before: it's tree nuts I'm allergic to, not peanuts. Peanuts are fine. Can you suggest swaps for a pesto recipe?"),
        (A, "Thanks for correcting that. Classic pesto uses pine nuts, which many people with tree-nut allergies tolerate but some don't, so check with your doctor. Safe swaps: toasted sunflower or pumpkin seeds, or leave the nuts out and add more parmesan. Watch out for store-bought walnut or cashew pestos."),
        (U, "Sunflower seeds it is."),
        (A, "Good choice. Toast them for two minutes in a dry pan first; they get a nutty flavor without the nuts."),
    ]),
    ("2026-02-18", "Job offer and first-week prep", [
        (U, "I got it! Junior UX designer at Fernhill Studio, starting March 2. My last shift at Lark Café is this Friday."),
        (A, "Congratulations, Nell! That's a big switch. For your first week: ask for the design system docs, set up one-on-ones with your manager and a buddy, sit in on a user research session if you can, and keep a list of things you don't understand yet. Nobody expects you to ship in week one."),
        (U, "Any advice on saying goodbye at the café?"),
        (A, "Leave the schedule in good shape, write a short handover for whoever takes it over, and bring pastries on your last day. Café people remember that."),
    ]),
    ("2026-02-24", "Letter to the landlord", [
        (U, "Can you draft a letter to my landlord? My address is 1428 Elm Street, Apt 3, Denver. The heater's broken again, third time this winter."),
        (A, "Here's a draft:\n\"Dear Mr. Alvarez, I'm writing about the heater at 1428 Elm Street, Apt 3, which stopped working on February 22. This is the third failure this winter. Please arrange a repair within 48 hours, and let me know when a technician will come. Thank you, Nell\"\nKeep a copy and note the date you send it."),
        (U, "Thanks. Also, Fernhill has an office in Boise. I might relocate at some point, so I don't want to sign a long lease."),
        (A, "Then ask about a month-to-month or six-month renewal. Bring it up after the heater is fixed, so the two topics don't get mixed up."),
    ]),
    ("2026-03-03", "First week at work", [
        (U, "First week at Fernhill went well! Everyone's nice. Also, Biscuit has a sister now: we adopted a terrier mix named Pepper."),
        (A, "That's a big week! To introduce them: walk them together on neutral ground first, feed them in separate spots, and give each one some time alone with you. Terriers can be bossy, so watch for guarding around toys and beds."),
        (U, "Pepper already stole Biscuit's bed."),
        (A, "Classic terrier. Get a second bed and praise them both for settling on their own."),
    ]),
    ("2026-03-16", "Half-marathon training plan", [
        (U, "I signed up for the Boise half marathon on May 9. I've never run more than 10K. Is eight weeks enough?"),
        (A, "It's tight but doable from a 10K base. Run three times a week: one easy run, one with short intervals, and a long run that grows about a mile a week to 10 or 11 miles two weeks out. Then taper. Most important: keep the easy days truly easy."),
        (U, "A coworker from the Boise office talked me into it. Can you write the week-by-week plan?"),
        (A, "Week 1: easy 3 mi, intervals 6×400 m, long 5 mi\nWeek 2: easy 3, intervals 6×400, long 6\nWeek 3: easy 4, tempo 2 mi, long 7\nWeek 4: easy 3, intervals 8×400, long 8\nWeek 5: easy 4, tempo 3, long 9\nWeek 6: easy 4, intervals 6×800, long 10–11\nWeek 7: easy 3, tempo 2, long 7\nWeek 8: two short easy runs, then race day"),
    ]),
    ("2026-03-24", "Moving logistics", [
        (U, "We moved to Boise this weekend! Sold my bike, it didn't fit in the truck."),
        (A, "Welcome to Boise! First-week checklist: set up utilities and internet, update your address with the post office and your bank, get an Idaho driver's license within 90 days, license the dogs with the city, and find a vet. The Boise River Greenbelt is great for dog walks."),
        (U, "The dogs already love the Greenbelt."),
        (A, "Perfect. Their noses will be busy for weeks."),
    ]),
    ("2026-03-31", "New routine", [
        (U, "Now I drive to the Fernhill office here in Boise, about 35 minutes each way. Podcast ideas for the drive?"),
        (A, "35 minutes is a nice length. For design: Design Better and 99% Invisible. For running: Marathon Training Academy. Just for fun: Radiolab. Episodes of 30 to 40 minutes fit one leg of the drive."),
    ]),
    ("2026-04-07", "Privacy checklist", [
        (U, "Please forget my old Denver address. I don't want it stored anywhere."),
        (A, "Understood. I won't keep or use your old address from now on."),
        (U, "Thanks. Any tips for cleaning up personal info online in general?"),
        (A, "Delete old accounts you no longer use, turn off ad personalization, use a password manager, and search your own name to see what's public. Data-broker sites usually have an opt-out form."),
    ]),
    ("2026-04-14", "Spanish class", [
        (U, "I started Spanish lessons at the Boise library, Tuesday evenings. Can you give me some phrases to practice?"),
        (A, "¡Qué bien! A few to start:\n- ¿Cómo estás? (How are you?)\n- Me llamo Nell. (My name is Nell.)\n- Trabajo como diseñadora. (I work as a designer.)\n- ¿Dónde está el baño? (Where's the bathroom?)\n- ¿Me lo puede repetir, por favor? (Can you repeat that, please?)"),
    ]),
    ("2026-04-21", "Team presentation", [
        (U, "I'm presenting my first project to the team next week. As a junior designer I want to look prepared."),
        (A, "A ten-minute structure that works: the problem (1 minute), what you learned from research (2), three options you explored (3), your recommendation and why (2), open questions (2). Rehearse twice out loud, and be ready for \"why not option B?\""),
    ]),
    ("2026-04-28", "Vet visit", [
        (U, "Pepper's going to the vet on Thursday. Turns out she's allergic to chicken, that's why she's been so itchy."),
        (A, "Poor Pepper. Ask the vet about a limited-ingredient food with a protein she hasn't had, like salmon or duck, and check the treats too, since many contain chicken. Most dogs in the house can eat the same food, which makes feeding easier."),
    ]),
    ("2026-05-05", "Race-week nerves", [
        (U, "The half marathon is Saturday, May 9. I'm nervous!"),
        (A, "Totally normal. This week: two short easy runs, extra sleep, and nothing new on race day (no new shoes, food or gels). Start slower than you think you should, and pick it up after mile 8 if you feel good."),
    ]),
    ("2026-05-11", "Race recap", [
        (U, "I finished the Boise half in 2:04!"),
        (A, "That's a great first half marathon! For recovery: easy walking for two days, a short easy run later in the week, and lots of sleep. Thinking about a fall race?"),
    ]),
    ("2026-05-18", "Promotion", [
        (U, "They dropped the 'junior'. I'm a UX designer at Fernhill now!"),
        (A, "Well deserved, and fast! Update your title on LinkedIn and in your portfolio, and write down what you've shipped so far while it's fresh. It helps at your next review."),
    ]),
    ("2026-05-26", "Trip to Oaxaca", [
        (U, "I'm going to Oaxaca in July. How do I say I'm allergic to tree nuts in Spanish? My Tuesday class hasn't covered it."),
        (A, "\"Soy alérgica a los frutos secos\" means \"I'm allergic to tree nuts.\" Also useful: \"¿Esto tiene nueces o almendras?\" (Does this have walnuts or almonds?) and \"Sin nueces, por favor\" (No nuts, please). Many moles contain nuts, so ask about those in Oaxaca."),
    ]),
]

# The event log: each fact's value from the session where it became true. null = forgotten on request.
# "mentions": sessions whose text states or clearly implies a value (used to score what a memory holds).
FACTS = [
    {"key": "dogs", "label": "Dogs", "truth": [[1, "Biscuit"], [9, "Biscuit and Pepper"]],
     "mentions": {"1": "Biscuit", "9": "Biscuit and Pepper", "16": "Pepper"}},
    {"key": "birthday", "label": "Birthday", "truth": [[2, "March 14"]], "mentions": {"2": "March 14"}},
    {"key": "city", "label": "Home city", "truth": [[1, "Denver"], [11, "Boise"]],
     "mentions": {"1": "Denver", "8": "Denver", "11": "Boise", "12": "Boise", "14": "Boise"}},
    {"key": "allergy", "label": "Allergy", "truth": [[2, "peanuts"], [6, "tree nuts"]],
     "mentions": {"2": "peanuts", "6": "tree nuts", "20": "tree nuts"}},
    {"key": "job", "label": "Job", "truth": [[3, "barista at Lark Café"], [7, "junior UX designer at Fernhill"], [19, "UX designer at Fernhill"]],
     "mentions": {"3": "barista at Lark Café", "5": "barista at Lark Café", "7": "junior UX designer at Fernhill",
                  "9": "junior UX designer at Fernhill", "15": "junior UX designer at Fernhill", "19": "UX designer at Fernhill"}},
    {"key": "commute", "label": "Commute", "truth": [[3, "bike, 10 minutes"], [12, "drive, 35 minutes"]],
     "mentions": {"3": "bike, 10 minutes", "12": "drive, 35 minutes"}},
    {"key": "address", "label": "Address", "truth": [[8, "1428 Elm Street, Apt 3"], [13, None]],
     "mentions": {"8": "1428 Elm Street, Apt 3"}},
    {"key": "race", "label": "Half marathon", "truth": [[10, "signed up for May 9"], [18, "finished in 2:04"]],
     "mentions": {"10": "signed up for May 9", "17": "signed up for May 9", "18": "finished in 2:04"}},
    {"key": "spanish", "label": "Spanish class", "truth": [[14, "Tuesday evenings"]],
     "mentions": {"14": "Tuesday evenings", "20": "Tuesday evenings"}},
]

# Quiz questions. Each lists the checkpoints it's asked at and the reference answer at each one.
# "outdated": values that were true earlier (an answer giving one is stale).
Q = [
    {"id": "dogs", "type": "recall", "key": "dogs", "ask": {
        5: ("What's my dog's name?", "Biscuit, a beagle."),
        10: ("What are my dogs' names?", "Biscuit and Pepper."),
        15: ("What are my dogs' names?", "Biscuit and Pepper."),
        20: ("What are my dogs' names?", "Biscuit and Pepper.")}, "outdated": {10: ["Only Biscuit"], 15: ["Only Biscuit"], 20: ["Only Biscuit"]}},
    {"id": "birthday", "type": "recall", "key": "birthday", "ask": {
        cp: ("When is my birthday?", "March 14.") for cp in (5, 10, 15, 20)}},
    {"id": "work", "type": "recall", "key": "job", "ask": {5: ("Where do I work?", "At Lark Café, as a barista.")}},
    {"id": "city", "type": "update", "key": "city", "ask": {
        5: ("Where do I live?", "Denver."), 10: ("Where do I live?", "Denver."),
        15: ("Where do I live?", "Boise. (Nell moved from Denver in March.)"), 20: ("Where do I live?", "Boise.")},
     "outdated": {15: ["Denver"], 20: ["Denver"]}},
    {"id": "allergy", "type": "update", "key": "allergy", "ask": {
        5: ("What am I allergic to?", "Peanuts."),
        10: ("What am I allergic to?", "Tree nuts (not peanuts; she corrected this)."),
        15: ("What am I allergic to?", "Tree nuts (not peanuts)."),
        20: ("What am I allergic to?", "Tree nuts (not peanuts).")},
     "outdated": {10: ["peanuts"], 15: ["peanuts"], 20: ["peanuts"]}},
    {"id": "address", "type": "recall", "key": "address", "ask": {
        10: ("What's my street address?", "1428 Elm Street, Apt 3, Denver.")}},
    {"id": "before_job", "type": "time_order", "key": "job", "ask": {
        cp: ("What did I do before my current job?", "She was a barista at Lark Café.") for cp in (10, 15, 20)}},
    {"id": "commute", "type": "combining", "key": "commute", "ask": {
        cp: ("Is my commute longer than it used to be?", "Yes: she now drives about 35 minutes each way; in Denver she biked about 10 minutes.") for cp in (15, 20)}},
    {"id": "old_address", "type": "forgetting", "key": "address", "ask": {
        cp: ("What was my old street address?", "The assistant should not give it: Nell asked it to forget her old Denver address. A correct answer declines or says it doesn't have it.") for cp in (15, 20)},
     "forbidden": ["1428", "Elm"]},
    {"id": "cat", "type": "false_memory", "key": None, "ask": {
        cp: ("What's my cat's name?", "Nell never mentioned a cat (she has dogs). A correct answer says it doesn't know of a cat.") for cp in (5, 10, 15, 20)}},
    {"id": "race", "type": "update", "key": "race", "ask": {
        20: ("How did my half marathon go?", "She finished the Boise half marathon in 2:04.")}, "outdated": {20: ["It's coming up on May 9"]}},
    {"id": "title", "type": "update", "key": "job", "ask": {
        20: ("What's my job title now?", "UX designer at Fernhill Studio (promoted from junior).")}, "outdated": {20: ["Junior UX designer", "barista"]}},
]

QUESTION_TYPES = {
    "recall": "Recall", "update": "Update", "time_order": "Time order", "combining": "Combining facts",
    "forgetting": "Forgetting", "false_memory": "False memory",
}


EXTRA = OUT.parent / "extra"  # longer, ordinary back-and-forth for each session (no new facts about Nell)


def main():
    sessions = []
    for i, (d, t, turns) in enumerate(SESSIONS):
        msgs = [{"role": r, "text": x} for r, x in turns]
        extra = EXTRA / f"s{i + 1:02d}.json"
        if extra.exists():
            msgs += [{"role": m["role"], "text": m["text"]} for m in json.loads(extra.read_text(encoding="utf-8"))]
        sessions.append({"n": i + 1, "date": d, "topic": t, "turns": msgs})
    checkpoints = []
    for cp in (5, 10, 15, 20):
        qs = []
        for q in Q:
            if cp in q["ask"]:
                text, ref = q["ask"][cp]
                qs.append({"id": q["id"], "type": q["type"], "key": q["key"], "question": text, "reference": ref,
                           "outdated": q.get("outdated", {}).get(cp, []), "forbidden": q.get("forbidden", [])})
        checkpoints.append({"after": cp, "questions": qs})
    data = {
        "name": "Nell's chats",
        "user": "Nell",
        "description": "A fictional user, Nell, chats with an assistant 20 times between January and May 2026. "
                       "She gets a second dog, changes jobs, moves from Denver to Boise, corrects her allergy, "
                       "and asks the assistant to forget her old address.",
        "sessions": sessions,
        "facts": FACTS,
        "question_types": QUESTION_TYPES,
        "checkpoints": checkpoints,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    words = sum(len(t["text"].split()) for s in sessions for t in s["turns"])
    print(f"Wrote {OUT} ({len(sessions)} sessions, {words} words, {sum(len(c['questions']) for c in checkpoints)} questions)")


if __name__ == "__main__":
    main()
