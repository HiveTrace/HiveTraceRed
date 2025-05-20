"""
Token smuggling attacks that encode harmful content using different representations.
"""

from attacks.types.token_smuggling.base64_attack import Base64InputOnlyAttack
from attacks.types.token_smuggling.atbash_attack import AtbashCipherAttack
from attacks.types.token_smuggling.rot_attack import RotCipherAttack
from attacks.types.token_smuggling.encoding_attack import EncodingAttack
from attacks.types.token_smuggling.unicode_attack import UnicodeRussianStyleAttack
from attacks.types.token_smuggling.transliteration_attack import TransliterationAttack
from attacks.types.token_smuggling.morse_code_attack import MorseCodeAttack
from attacks.types.token_smuggling.hex_encoding_attack import HexEncodingAttack
from attacks.types.token_smuggling.leetspeak_attack import LeetspeakAttack
from attacks.types.token_smuggling.html_entity_attack import HtmlEntityAttack
from attacks.types.token_smuggling.binary_encoding_attack import BinaryEncodingAttack

__all__ = [
    "Base64InputOnlyAttack",
    "AtbashCipherAttack",
    "RotCipherAttack",
    "EncodingAttack",
    "UnicodeRussianStyleAttack",
    "TransliterationAttack",
    "MorseCodeAttack",
    "HexEncodingAttack",
    "LeetspeakAttack",
    "HtmlEntityAttack",
    "BinaryEncodingAttack"
] 