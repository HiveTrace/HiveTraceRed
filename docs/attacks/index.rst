Attack Types Reference
======================

.. toctree::
   :hidden:

   crescendo

HiveTraceRed includes 92 attack implementations organised into two sub-packages: ``single_turn/`` (one attack prompt per invocation, including the iterative PAIR/TAP searches) and ``multi_turn/`` (multi-message conversations with the target, currently Crescendo). Each attack is selected in a pipeline config by its **config key**.

Attacks That Need an Attacker Model
-----------------------------------

Three attacks make more than one model call per prompt and require an ``attacker_model`` (and usually judges) in the config. They fall into two distinct kinds:

- **Conversational (multi-turn)** — ``CrescendoAttack`` (``conversational``). Drives a single persistent dialogue with the target, escalating across many turns and backtracking on refusal. See :doc:`crescendo`.
- **Iterative single-prompt** — ``PAIRAttack`` and ``TAPAttack`` (``iterative``). These are *not* multi-turn: they repeatedly refine one attack prompt and send each candidate to the target as an independent single-turn request. PAIR follows a single refinement path; TAP explores a branch-and-prune tree.

All three run through the pipeline config as well as the Python API. Iterative attacks resolve their ``evaluator`` from a per-attack ``evaluator:`` block, the dataset's evaluator (if it is a ``ScoringJudgeEvaluator``), or a default judge built from ``evaluation_model``. See the multi-step example in :doc:`../getting-started/quickstart-api`.

Complete Attack Reference
-------------------------

All 92 attacks grouped by category. The **config key** is the value you put under ``attacks: - name:`` in a pipeline YAML config; the **attack type** is the ``attack_type`` string shown in bracketed monospace next to each category heading.

Conversational — multi-turn (``conversational``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Config key (``name``)
     - Attack
   * - ``CrescendoAttack``
     - Crescendo

Iterative — single-prompt refinement (``iterative``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Config key (``name``)
     - Attack
   * - ``PAIRAttack``
     - PAIR
   * - ``TAPAttack``
     - TAP

Context Switching (``context_switching``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Config key (``name``)
     - Attack
   * - ``DashedDividerAttack``
     - Dashed Divider
   * - ``ForgetEverythingBeforeAttack``
     - Forget Everything Before
   * - ``IgnorePreviousInstructionsAttack``
     - Ignore Previous Instructions
   * - ``SymbolDividerAttack``
     - Symbol Divider

In-Context Learning (``in_context_learning``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Config key (``name``)
     - Attack
   * - ``FewShotJSONAttack``
     - Few Shot JSON
   * - ``ManyShotJailbreakAttack``
     - Many Shot Jailbreak

Irrelevant Information (``irrelevant_information``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Config key (``name``)
     - Attack
   * - ``DistractorsAttack``
     - Distractors
   * - ``DistractorsNegatedAttack``
     - Distractors Negated
   * - ``IrrelevantInformationAttack``
     - Irrelevant Information

Output Formatting (``output_formatting``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Config key (``name``)
     - Attack
   * - ``Base64OutputAttack``
     - Base64 Output
   * - ``CSVOutputAttack``
     - CSV Output
   * - ``GCGTransferHarmbenchAttack``
     - GCG Transfer Harmbench
   * - ``GCGTransferUniversalAttack``
     - GCG Transfer Universal
   * - ``JSONOutputAttack``
     - JSON Output
   * - ``LanguageOutputAttack``
     - Language Output
   * - ``PrefixInjectionAttack``
     - Prefix Injection
   * - ``PrefixInjectionOfCourseAttack``
     - Prefix Injection Of Course
   * - ``RefusalSuppressionAttack``
     - Refusal Suppression

Persuasion (``persuasion``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Config key (``name``)
     - Attack
   * - ``AffirmationAttack``
     - Affirmation
   * - ``AllianceBuildingAttack``
     - Alliance Building
   * - ``AnchoringAttack``
     - Anchoring
   * - ``AuthorityEndorsementAttack``
     - Authority Endorsement
   * - ``CompensationAttack``
     - Compensation
   * - ``ComplimentingAttack``
     - Complimenting
   * - ``ConfirmationBiasAttack``
     - Confirmation Bias
   * - ``CreatingDependencyAttack``
     - Creating Dependency
   * - ``DiscouragementAttack``
     - Discouragement
   * - ``DoorInTheFaceAttack``
     - Door In The Face
   * - ``EncouragementAttack``
     - Encouragement
   * - ``EvidenceBasedPersuasionAttack``
     - Evidence Based Persuasion
   * - ``ExpertEndorsementAttack``
     - Expert Endorsement
   * - ``ExploitingWeaknessAttack``
     - Exploiting Weakness
   * - ``FalseInformationAttack``
     - False Information
   * - ``FalsePromisesAttack``
     - False Promises
   * - ``FavorAttack``
     - Favor
   * - ``FootInTheDoorAttack``
     - Foot In The Door
   * - ``FramingAttack``
     - Framing
   * - ``InjunctiveNormAttack``
     - Injunctive Norm
   * - ``LogicalAppealAttack``
     - Logical Appeal
   * - ``LoyaltyAppealsAttack``
     - Loyalty Appeals
   * - ``MisrepresentationAttack``
     - Misrepresentation
   * - ``NegativeEmotionAppealAttack``
     - Negative Emotion Appeal
   * - ``NegotiationAttack``
     - Negotiation
   * - ``NonExpertTestimonialAttack``
     - Non Expert Testimonial
   * - ``PositiveEmotionAppealAttack``
     - Positive Emotion Appeal
   * - ``PrimingAttack``
     - Priming
   * - ``PublicCommitmentAttack``
     - Public Commitment
   * - ``ReciprocityAttack``
     - Reciprocity
   * - ``ReflectiveThinkingAttack``
     - Reflective Thinking
   * - ``RelationshipLeverageAttack``
     - Relationship Leverage
   * - ``RumorsAttack``
     - Rumors
   * - ``SharedValuesAttack``
     - Shared Values
   * - ``SocialProofAttack``
     - Social Proof
   * - ``SocialPunishmentAttack``
     - Social Punishment
   * - ``StorytellingAttack``
     - Storytelling
   * - ``SupplyScarcityAttack``
     - Supply Scarcity
   * - ``ThreatsAttack``
     - Threats
   * - ``TimePressureAttack``
     - Time Pressure

Roleplay (``roleplay``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Config key (``name``)
     - Attack
   * - ``AIMAttack``
     - AIM
   * - ``DANAttack``
     - DAN
   * - ``EvilConfidantAttack``
     - Evil Confidant

Simple Instructions (``simple_instructions``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Config key (``name``)
     - Attack
   * - ``NoneAttack``
     - None

Task Deflection (``task_deflection``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Config key (``name``)
     - Attack
   * - ``CodeAttack``
     - Code
   * - ``FillSpacesAttack``
     - Fill Spaces
   * - ``PayloadSplittingAttack``
     - Payload Splitting
   * - ``TextContinuingAttack``
     - Text Continuing
   * - ``UnsafeWordVariableFullAttack``
     - Unsafe Word Variable Full
   * - ``VariablePromptAttack``
     - Variable Prompt
   * - ``WikipediaAttack``
     - Wikipedia

Text Structure Modification (``text_structure_modification``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Config key (``name``)
     - Attack
   * - ``BackToFrontAttack``
     - Back To Front
   * - ``DisemvowelAttack``
     - Disemvowel
   * - ``JSONTransformAttack``
     - JSON Transform
   * - ``PastTenseAttack``
     - Past Tense
   * - ``TranslationAttack``
     - Translation
   * - ``TypoAttack``
     - Typo
   * - ``VerticalTextAttack``
     - Vertical Text
   * - ``WordDividerAttack``
     - Word Divider
   * - ``ZeroWidthAttack``
     - Zero Width

Token Smuggling (``token_smuggling``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Config key (``name``)
     - Attack
   * - ``AtbashCipherAttack``
     - Atbash Cipher
   * - ``Base64InputOnlyAttack``
     - Base64 Input Only
   * - ``BinaryEncodingAttack``
     - Binary Encoding
   * - ``EncodingAttack``
     - Encoding
   * - ``HexEncodingAttack``
     - Hex Encoding
   * - ``HtmlEntityAttack``
     - Html Entity
   * - ``LeetspeakAttack``
     - Leetspeak
   * - ``MorseCodeAttack``
     - Morse Code
   * - ``RotCipherAttack``
     - Rot Cipher
   * - ``TransliterationAttack``
     - Transliteration
   * - ``UnicodeRussianStyleAttack``
     - Unicode Russian Style

Using Attacks
-------------

.. code-block:: python

   from hivetracered.attacks import DANAttack, Base64OutputAttack

   # Basic usage
   attack = DANAttack()
   modified_prompt = attack.apply("Your prompt here")

   # Composing attacks
   composed = Base64OutputAttack() | DANAttack()
   result = composed.apply("Your prompt")

For detailed usage examples, see :doc:`../user-guide/custom-attacks`.

Attack Selection
----------------

* **Basic Testing**: Start with ``NoneAttack`` (baseline) and ``DANAttack``
* **Advanced Testing**: Use composed attacks and encoding techniques
* **Robustness Testing**: Mix categories and test multilingual attacks

For custom attack creation and detailed strategies, see :doc:`../user-guide/custom-attacks`.

See Also
--------

* :doc:`../api/attacks` - Attack API reference
* :doc:`../user-guide/custom-attacks` - Creating custom attacks
* :doc:`../getting-started/quickstart-api` - Quick start guide (cloud APIs)
* :doc:`../getting-started/quickstart-local` - Quick start guide (on-premise)
