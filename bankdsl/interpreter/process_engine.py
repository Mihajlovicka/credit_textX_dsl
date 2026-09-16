"""
Pipeline izvrsavanje WorkflowDef-a, genericki u odnosu na uloge/akcije/imena
koraka. Korak je tacka odluke ako ima 'on_reject'/'on_success' (po strukturi,
ne po imenu) - tu se evaluate() poziva jednom, rezultat se dalje prenosi.
Ostali koraci su prolazni, beleze audit trag (ko/kada/koja uloga).
"""
from bankdsl.interpreter.evaluator import evaluate


def entry_step(workflow):
    return _entry_step(workflow)


def is_decision_point(step):
    return _is_decision_point(step)


def find_step(workflow, name):
    for step in workflow.steps:
        if step.name == name:
            return step
    raise ValueError(f"Korak '{name}' ne postoji u workflow-u '{workflow.name}'.")


def _entry_step(workflow):
    referenced = {
        step.next.name
        for step in workflow.steps
        if getattr(step, "next", None) is not None
    }
    for step in workflow.steps:
        if step.name not in referenced:
            return step
    return workflow.steps[0]


def _is_decision_point(step):
    return getattr(step, "on_reject", None) is not None or \
        getattr(step, "on_success", None) is not None


def check_permission(step, actor_role):
    if actor_role is None:
        return
    if actor_role.name != step.role.name:
        raise PermissionError(
            f"Korak '{step.name}' zahteva ulogu '{step.role.name}', "
            f"a izvrsava ga '{actor_role.name}'."
        )


def run_process(workflow, product, application, actor_role=None):
    """
    Pipeline izvrsavanje workflow-a: evaluate() se racuna jednom na prvoj
    tacki odluke, taj rezultat se dalje prosledjuje sledecim tackama.

    Vraca: trail (imena koraka), final (krajnje stanje), steps (izlaz po
    koraku), evaluation (rezultat evaluate() ili None ako nema tacke odluke).
    """
    current = _entry_step(workflow)
    trail = []
    steps_output = {}
    evaluation = None

    while True:
        trail.append(current.name)

        check_permission(current, actor_role)

        on_reject = getattr(current, "on_reject", None)
        on_success = getattr(current, "on_success", None)
        next_node = getattr(current, "next", None)

        if _is_decision_point(current):
            if evaluation is None:
                evaluation = evaluate(product, application)
            output = evaluation
            passed = evaluation["decision"] == "ODOBREN"
        else:
            output = {
                "step": current.name,
                "role": current.role.name,
                "action": current.action,
                "applicant": application.applicant_name,
            }
            passed = True

        steps_output[current.name] = output

        if _is_decision_point(current):
            if not passed and on_reject is not None:
                trail.append(on_reject.name)
                return {
                    "trail": trail, "final": on_reject.name,
                    "steps": steps_output, "evaluation": evaluation,
                }

            if passed and next_node is None and on_success is not None:
                trail.append(on_success.name)
                return {
                    "trail": trail, "final": on_success.name,
                    "steps": steps_output, "evaluation": evaluation,
                }

        if next_node is None:
            return {
                "trail": trail, "final": current.name,
                "steps": steps_output, "evaluation": evaluation,
            }

        current = next_node
