from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Required, TypedDict

import lxml.etree as ET

logger = logging.getLogger(__name__)


class Card(TypedDict, total=False):
    id: Required[str]
    name: Required[str]
    rarity: str
    edition: str
    image: str
    legal: str
    text: str
    cost: str
    focus: str


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--database", "-d", type=Path, default=Path("database.xml"))
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)

    cards = load_xml_database(args.database)

    input_path = args.path

    deck = load_deck(input_path, cards)

    output = input_path.with_stem(input_path.stem + "_output")
    output.write_text("\n".join(sorted([card["id"] for card in deck])))
    for card in deck:
        logger.info("%s - %s", card["id"], card["name"])


if __name__ == "__main__":
    main()
