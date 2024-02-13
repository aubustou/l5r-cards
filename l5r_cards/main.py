from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path
from typing import Required, TypedDict

import lxml.etree as ET

logger = logging.getLogger(__name__)

UNIQUE_TYPES = {"event", "stronghold", "wind", "sensei"}
UNIQUE_KEYWORD = "Unique</b>"

DYNASTY_TYPES = {
    "event",
    "holding",
    "personality",
    "celestial",
    "region",
    "wind",
}
FATE_TYPES = {"spell", "strategy", "ancestor", "ring", "sensei", "follower", "item"}
STRONGHOLD_TYPES = {"stronghold"}


class Card(TypedDict, total=False):
    id: Required[str]
    name: Required[str]
    type: Required[str]
    rarity: str
    edition: str
    image: str
    legal: str
    text: str
    cost: str
    focus: str
    images: dict[str, Path]


def load_xml_database(path: Path) -> dict[str, Card]:
    """Load the L5R Oracle XML database into a dictionary of dictionaries.

    <cards version="2023/12/26 Onyx Oracle Edition">	<!--"Oct 4, 2015 Kamisasori no Kaisho (Complete), Nov 28, 2017 Kolat 1.3.4">-->
        <card id="AD092" type="strategy">
                <name>A Chance Meeting</name>
                <rarity>u</rarity>
                <edition>AD</edition><image edition="AD">images/cards/AD/AD092.jpg</image>
                <legal>open</legal>
                <text><![CDATA[<b>Battle:</b> One of your Personalities in this battle challenges an opposing Personality. If the challenged Personality refuses the challenge, that personality becomes dishonored, and all of his or her Followers bow. If the challenged Personality accepts the challenge, the duel's winner gains Honor equal to the number of cards focused by both players, and the loser is destroyed.]]></text>
                <cost>0</cost>
                <focus>3</focus>
        </card>
        <card id="AD081" type="region">
                <name>Akodo Fields</name>
                <rarity>u</rarity>
                <edition>AD</edition><image edition="AD">images/cards/AD/AD081.jpg</image>
                <legal>open</legal>
                <legal>jade</legal>
                <text><![CDATA[<B>Limited:</B> Target one of your Followers in play and pay Gold equal to the Follower's Force. For the rest of the game, the Follower is Elite, contributes its Force to its army's total during the Resolution Segment of battle even if its Personality is bowed, and is immune to Fear.]]></text>
        </card>
    """

    with path.open() as f:
        tree = ET.parse(f)

    root = tree.getroot()
    cards = root.findall("card")

    card_dict: dict[str, Card] = {}
    for card in cards:
        name = card.find("name").text
        card_id = card.attrib["id"]
        card_dict[name] = {
            "id": card_id,
            "name": name,
            "type": card.attrib["type"],
            "images": {
                x.attrib["edition"]: Path(x.text) for x in card.findall("image")
            },
            "text": card.find("text").text,
        }

    return card_dict


def load_deck(path: Path, cards: dict[str, Card]) -> list[Card]:
    """Load a L5R Oracle deck file into a list of cards

        Example:
    Legality: Onyx
    The Dark Capital of the Spider

    1 Mishime Sensei

    1 Imperial Gift
    1 Repairing the Ruins
    1 Siege of the Great Wall
    1 The Realms Merge"""
    with path.open() as f:
        lines = f.readlines()

    deck: list[Card] = []
    for line in lines:
        if not line.strip():
            continue

        if line.startswith("Legality:"):
            continue

        if not line[0].isdigit():
            number = 1
            name = line
        else:
            try:
                number, name = line.split(" ", 1)
            except ValueError:
                logger.warning("Invalid line: %s", line)
                continue

        name = name.strip()

        if card := cards.get(name):
            deck.extend([card] * int(number))
        elif card := cards.get(name + " (1)"):
            deck.extend([card, cards[name + " (2)"]])
        else:
            logger.warning("Card not found: %s", name)
            raise ValueError(f"Card not found: {name}")

    return deck


def sanitize_name(name: str) -> str:
    for char in ':/"?*<>|\\':
        name = name.replace(char, "-")

    return name


# The Hidden School of the Scorpion (1)
STRONGHOLD_NAME_PATTERN = re.compile(r"(.+) \((\d)\)")


def rename_images(
    cards: dict[str, Card], input_path: Path, back_dynasty: Path, back_fate: Path
):
    card_images = {
        x.stem: card for card in cards.values() for x in card["images"].values()
    }

    output_path = input_path.with_stem(input_path.stem + "_output")
    output_path.mkdir(exist_ok=True)

    number_of_cards = {"dynasty": 0, "fate": 0, "stronghold": 0}

    for image in input_path.rglob("*.jpg"):
        image_name = image.with_stem(image.stem.removesuffix("_upscaled")).stem
        if (card := card_images.get(image_name)) is None:
            logger.warning("Card not found for %s", image_name)
            continue

        if card["type"] in UNIQUE_TYPES:
            card_number = 1
        else:
            if UNIQUE_KEYWORD in card["text"]:
                card_number = 1
            elif "Unique" in card["text"]:
                logger.info("Is this card unique? %s", card["name"])
                card_number = int(input(f"{card['text']}"))
            else:
                card_number = 3

        card_id = card["id"]
        card_name = card["name"]

        orientation = "face"
        if card["type"] in DYNASTY_TYPES:
            back = back_dynasty
            number_of_cards["dynasty"] += card_number
        elif card["type"] in FATE_TYPES:
            back = back_fate
            number_of_cards["fate"] += card_number
        elif card["type"] in STRONGHOLD_TYPES:
            back = None
            if (group := STRONGHOLD_NAME_PATTERN.match(card_name).group(1)) is None:
                raise ValueError(f"Invalid stronghold name: {card_name}")
            card_name = group

            if card["id"].endswith("b"):
                orientation = "back"
                card_id = card_id.removesuffix("b")
            else:
                number_of_cards["stronghold"] += card_number
        else:
            raise ValueError(f"Unknown card type: {card['type']}")

        new_name = sanitize_name(
            f"{card_id} - {card_name}[{orientation},{card_number}].jpg"
        )

        logger.info("Renaming %s to %s", image, new_name)
        # new_file.write_bytes(image.read_bytes())

        if back is None:
            continue

        new_back_name = sanitize_name(
            f"{card_id} - {card_name}[back,{card_number}].jpg"
        )
        logger.info("Copying %s to %s", back, new_back_name)
        # (output_path / new_back_name).write_bytes(back.read_bytes())

    logger.info("Number of cards: %s", number_of_cards)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=Path)
    parser.add_argument("--database", "-d", type=Path, default=Path("database.xml"))
    parser.add_argument("--rename", "-r", action="store_true")
    parser.add_argument("--back-dynasty", type=Path)
    parser.add_argument("--back-fate", type=Path)
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)

    cards = load_xml_database(args.database)

    input_path = args.path

    if args.rename:
        if not (back_dynasty := args.back_dynasty):
            raise ValueError("Back dynasty not set")
        if not (back_fate := args.back_fate):
            raise ValueError("Back fate not set")

        rename_images(cards, input_path, back_dynasty, back_fate)
    else:
        deck = load_deck(input_path, cards)

        output = input_path.with_stem(input_path.stem + "_output")
        output.write_text("\n".join(sorted([card["id"] for card in deck])))
        for card in deck:
            logger.info("%s - %s", card["id"], card["name"])


if __name__ == "__main__":
    main()
