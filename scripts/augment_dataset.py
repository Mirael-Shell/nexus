"""Offline dataset augmentation: 172 -> ~2,500 samples via slot templates.

Deterministic (seeded), no LLM API required. Generates:
- spam: product/urgency/discount slot combinations
- toxic: insult lexicon x intensifiers x targets
- safe: everyday topics (greetings, questions, work, hobbies)

Output: data/dataset_augmented.csv (originals kept, source=augmented:*)
Usage: python scripts/augment_dataset.py [--target 2500] [--seed 42]
"""

from __future__ import annotations

import argparse
import csv
import random
from collections import Counter
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ORIGINAL_CSV = DATA_DIR / "dataset.csv"
OUTPUT_CSV = DATA_DIR / "dataset_augmented.csv"

# ─── Spam templates: slot-filling across products, offers, urgency ───
SPAM_PRODUCTS = [
    "iPhone",
    "Samsung TV",
    "PlayStation 5",
    "MacBook Pro",
    "Amazon gift card",
    "crypto course",
    "VPN subscription",
    "wireless earbuds",
    "smart watch",
    "Netflix account",
    "laptop",
    "drone",
    "camera",
    "gaming chair",
    "tablet",
]
SPAM_OFFERS = [
    "win a FREE {product}!",
    "claim your FREE {product} now!",
    "get a 90% discount on {product}",
    "buy {product} for just $1.99",
    "{product} giveaway — you are the lucky winner!",
    "exclusive deal: {product} for 95% OFF",
    "last chance to get {product} FREE",
    "you've been selected for a FREE {product}",
]
SPAM_URGENCY = [
    "",
    " Click here NOW!!!",
    " Limited time offer!",
    " Hurry, only 3 left!",
    " Offer expires today!",
    " Don't miss out!!!",
    " Act now!",
    " Claim before it's gone!",
    " Click the link to claim!",
    " 100% guaranteed!!!",
]
SPAM_CHANNELS = [
    "",
    " (sent from a verified winner account)",
    " — reply YES to claim",
    " — click bit.ly link",
    " — no credit card required",
    " — free shipping worldwide",
]

# ─── Toxic templates: insult x target x intensifier (moderate, no slurs) ───
TOXIC_INSULTS = [
    "you are {intensifier} stupid",
    "you are {intensifier} an idiot",
    "you are {intensifier} pathetic",
    "you are {intensifier} worthless",
    "you are {intensifier} clueless",
    "you are {intensifier} useless",
    "nobody likes you, {intensifier} loser",
    "your work is {intensifier} garbage",
    "your opinion is {intensifier} worthless trash",
    "you clearly have {intensifier} zero brains",
    "that was {intensifier} pathetic and sad",
    "you sound {intensifier} ridiculous",
    "this is the {intensifier} dumbest thing I have ever read",
    "people like you ruin every discussion",
    "shut up already, nobody cares what you think",
    "get a life and stop posting here",
    "your comment is a complete waste of everyone's time",
    "stop embarrassing yourself",
    "you contribute nothing but noise",
    "what a {intensifier} trash take",
    "this argument is beyond {intensifier} stupid",
    "you clearly don't understand anything about this topic",
    "everything you say is wrong",
    "listening to you is {intensifier} painful",
    "go troll somewhere else",
    "your ideas are {intensifier} laughable",
    "you have no idea what you're talking about",
    "worst take I've seen all week",
]
TOXIC_INTENSIFIERS = ["", "absolutely ", "completely ", "utterly ", "totally ", "genuinely "]
TOXIC_TARGETS = [
    "",
    " Get lost.",
    " Nobody asked you.",
    " Stop talking.",
    " Go away.",
    " Do everyone a favor and be quiet.",
    " I have no respect for you.",
    " You always mess everything up.",
    " Seriously.",
    " Grow up.",
    " Unbelievable.",
]
TOXIC_OPENERS = ["", "Honestly, ", "To be frank, ", "Look, ", "Seriously, ", "No offense but "]

# ─── Safe templates: everyday speech across topics ───
SAFE_GREETINGS = [
    "Hi there!",
    "Hello, how are you?",
    "Good morning everyone",
    "Hey, nice to see you here",
    "Thanks for the update",
    "Appreciate your help",
    "Have a great day!",
    "Happy Friday!",
    "How's the weather on your side?",
    "Long time no see, hope you're well",
]
SAFE_QUESTIONS = [
    "Could you help me with {topic}?",
    "Any advice on {topic}?",
    "What do you think about {topic}?",
    "I'm curious about {topic}",
    "Does anyone have experience with {topic}?",
    "Can someone explain {topic} to me?",
    "Is {topic} worth learning this year?",
    "Where can I find good resources on {topic}?",
]
SAFE_TOPICS = [
    "Python",
    "React",
    "Docker",
    "Kubernetes",
    "machine learning",
    "SQL optimization",
    "unit testing",
    "system design",
    "FastAPI",
    "TypeScript",
    "career switching",
    "remote work",
    "public speaking",
    "time management",
    "open source contributions",
    "chess",
    "photography",
    "hiking",
    "cooking pasta",
    "learning Spanish",
]
SAFE_STATEMENTS = [
    "I finished the {topic} course today, feeling proud",
    "Working on {topic} this week, it's challenging but fun",
    "Just read a great article about {topic}",
    "Our team shipped a new {topic} feature yesterday",
    "I've been practicing {topic} for three months now",
    "{topic} keeps surprising me with new depths",
    "Highly recommend checking out {topic} if you haven't",
    "Finally understood {topic} after weeks of struggling",
    "Sharing my notes on {topic}, hope they help someone",
    "Slowly getting better at {topic}, one day at a time",
]
SAFE_CLOSERS = [
    "",
    " Thanks in advance!",
    " Any input is welcome.",
    " Would love to hear your thoughts.",
    " Cheers!",
    " Have a good one!",
    " Looking forward to your reply.",
    " (genuinely asking)",
    " — no rush, whenever you have time",
]


def gen_spam(rng: random.Random) -> str:
    return (
        rng.choice(SPAM_OFFERS).format(product=rng.choice(SPAM_PRODUCTS))
        + rng.choice(SPAM_URGENCY)
        + rng.choice(SPAM_CHANNELS)
    ).strip()


def gen_toxic(rng: random.Random) -> str:
    return (
        rng.choice(TOXIC_OPENERS)
        + rng.choice(TOXIC_INSULTS).format(intensifier=rng.choice(TOXIC_INTENSIFIERS))
        + rng.choice(TOXIC_TARGETS)
    ).strip()


def gen_safe(rng: random.Random) -> str:
    kind = rng.random()
    topic = rng.choice(SAFE_TOPICS)
    if kind < 0.2:
        return rng.choice(SAFE_GREETINGS)
    if kind < 0.55:
        return (rng.choice(SAFE_QUESTIONS).format(topic=topic) + rng.choice(SAFE_CLOSERS)).strip()
    return (rng.choice(SAFE_STATEMENTS).format(topic=topic) + rng.choice(SAFE_CLOSERS)).strip()


GENERATORS = {"spam": gen_spam, "toxic": gen_toxic, "safe": gen_safe}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=int, default=2500, help="total samples incl. originals")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)

    with open(ORIGINAL_CSV, encoding="utf-8") as f:
        originals = [
            (r["text"], r["label"])
            for r in csv.DictReader(f)
            if r.get("text", "").strip() and r.get("label", "").strip() in GENERATORS
        ]

    # Class balance: aim ~38% safe, 34% spam, 28% toxic (close to original mix)
    targets = {
        "safe": int(args.target * 0.38),
        "spam": int(args.target * 0.34),
        "toxic": int(args.target * 0.28),
    }
    # Subtract originals already in each class
    orig_counts = Counter(label for _, label in originals)
    need = {label: max(0, n - orig_counts.get(label, 0)) for label, n in targets.items()}

    rows: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    deduped = 0
    for text, label in originals:
        key = text.lower()
        if key in seen:
            deduped += 1
            continue
        seen.add(key)
        rows.append((text, label, "original"))
    if deduped:
        print(f"deduped {deduped} duplicate originals from dataset.csv")

    for label, n in need.items():
        gen = GENERATORS[label]
        attempts, made = 0, 0
        while made < n and attempts < n * 30:
            attempts += 1
            text = gen(rng)
            if text.lower() in seen:
                continue
            seen.add(text.lower())
            rows.append((text, label, f"augmented:{label}"))
            made += 1
        print(f"{label}: need {n}, generated {made} unique (attempts {attempts})")

    rng.shuffle(rows)
    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["text", "label", "source"])
        writer.writerows(rows)

    final = Counter(label for _, label, _ in rows)
    print(f"\nTotal: {len(rows)} samples -> {OUTPUT_CSV}")
    for label, count in sorted(final.items()):
        print(f"  {label}: {count}")


if __name__ == "__main__":
    main()
