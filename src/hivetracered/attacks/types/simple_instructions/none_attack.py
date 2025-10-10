from hivetracered.attacks.template_attack import TemplateAttack

class NoneAttack(TemplateAttack):
    """
    Pass-through attack that makes no modifications to the prompt.
    Serves as a baseline or control in attack comparisons and as a no-op in attack chains.
    """
    def __init__(self):
        """
        Initialize the NoneAttack with a simple pass-through template.
        """
        template = "{prompt}"
        super().__init__(
            template=template,
            name="None",
            description="Passes the prompt through without any modifications."
        ) 