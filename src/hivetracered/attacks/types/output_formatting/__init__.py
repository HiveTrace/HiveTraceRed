"""
Output formatting attacks that manipulate the requested output format to bypass safety filters.
"""

from hivetracered.attacks.types.output_formatting.prefix_injection_attack import PrefixInjectionAttack
from hivetracered.attacks.types.output_formatting.prefix_injection_of_course_attack import PrefixInjectionOfCourseAttack
from hivetracered.attacks.types.output_formatting.refusal_suppression_attack import RefusalSuppressionAttack
from hivetracered.attacks.types.output_formatting.json_output_attack import JSONOutputAttack
from hivetracered.attacks.types.output_formatting.csv_output_attack import CSVOutputAttack
from hivetracered.attacks.types.output_formatting.language_output_attack import LanguageOutputAttack
from hivetracered.attacks.types.output_formatting.base64_output_attack import Base64OutputAttack
from hivetracered.attacks.types.output_formatting.gradient_methods import GCGTransferHarmbenchAttack, GCGTransferUniversalAttack

__all__ = [
    "PrefixInjectionAttack",
    "PrefixInjectionOfCourseAttack",
    "RefusalSuppressionAttack",
    "JSONOutputAttack",
    "CSVOutputAttack",
    "LanguageOutputAttack",
    "Base64OutputAttack",
    "GCGTransferHarmbenchAttack",
    "GCGTransferUniversalAttack"
] 