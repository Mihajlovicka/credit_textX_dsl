"""
Procesni motor - izvrsava WorkflowDef iz DSL-a kao PIPELINE, potpuno
GENERICKI u odnosu na konkretne uloge/permisije/imena koraka koje neko
napise u .credit fajlu.

Kljucna ideja: motor NE zna niti hardkoduje imena akcija (npr. "approve",
"submit_application") - to su proizvoljne reci koje autor DSL-a smisli.
Umesto toga, motor reaguje na STRUKTURU koja je univerzalna za SVAKI
workflow definisan gramatikom:

  - korak koji ima 'on_reject' i/ili 'on_success' JE tacka odluke
    (bez obzira kako se zove njegova akcija ili uloga)
  - proizvod uvek ima tacno JEDAN 'eligibility' blok, sto je vec
    generalna "funkcija odluke" za taj proizvod (definisana u DSL-u,
    ne u Python kodu)

Zato: prvi put kad motor naidje na tacku odluke, izracuna evaluate()
JEDNOM (uzimajuci u obzir i opseg iznosa/roka i eligibility pravila -
oboje je vec deo evaluate()) i taj rezultat je IZLAZ tog koraka. Ako
ima jos koraka posle (npr. drugi korak odlucivanja dalje niz workflow),
isti rezultat mu je ULAZ - ne racuna se ponovo. Ovo radi za bilo koji
broj koraka odlucivanja, bilo koje uloge, bilo koje nazive akcija -
dakle radi za svaki workflow koji neko napise u DSL-u, ne samo za dati
primer.

Non-decision korake (npr. cist "prijem" korak bez on_reject/on_success)
motor tretira kao "prolazne" (audit trag) - njihov izlaz je opisni
snapshot (ko/kada/koja uloga), a ulaz sledeceg koraka ostaje isti
kontekst.

Napomena o gramatici (nakon profesorove izmene):
  - step.role       -> RoleDef  (iz 'handled_by')
  - step.action     -> ID       (naziv permisije, npr. 'approve')
  - step.next       -> ProcessStep | WorkflowState (sledeci cvor procesa)
  - step.on_reject  -> WorkflowState
  - step.on_success -> WorkflowState
"""
from bankdsl.interpreter.evaluator import evaluate


def entry_step(workflow):
    """Korak na koji se nijedan drugi korak ne oslanja kroz 'next' je pocetni."""
    return _entry_step(workflow)


def is_decision_point(step):
    return _is_decision_point(step)


def find_step(workflow, name):
    for step in workflow.steps:
        if step.name == name:
            return step
    raise ValueError(f"Korak '{name}' ne postoji u workflow-u '{workflow.name}'.")


def _entry_step(workflow):
    """Korak na koji se nijedan drugi korak ne oslanja kroz 'next' je pocetni."""
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
    """Generickicka provera - ne zavisi od imena akcije ili uloge, samo
    od strukture koju SVAKI workflow vec ima u gramatici."""
    return getattr(step, "on_reject", None) is not None or \
        getattr(step, "on_success", None) is not None


def run_process(workflow, product, application, actor_role=None):
    """
    Izvrsava dati workflow (WorkflowDef) kao pipeline: rezultat evaluacije
    se racuna JEDNOM na prvoj tacki odluke i prosledjuje kao ulaz svakoj
    sledecoj tacki odluke niz tok. Radi generickicki za bilo koji workflow,
    ulogu ili naziv akcije definisan u DSL-u.

    Vraca:
        {
          "trail": [imena koraka/stanja kroz koje je proces prosao],
          "final": ime krajnjeg stanja (npr. "Odobreno"/"Odbijeno"),
          "steps": {ime_koraka: izlaz_tog_koraka, ...},   # istorija svih koraka
          "evaluation": rezultat evaluate() (None ako nijedan korak nije
                        tacka odluke - npr. workflow bez eligibility provere),
        }
    """
    current = _entry_step(workflow)
    trail = []
    steps_output = {}
    evaluation = None

    while True:
        trail.append(current.name)

        if actor_role is not None and actor_role.name != current.role.name:
            raise PermissionError(
                f"Korak '{current.name}' zahteva ulogu '{current.role.name}', "
                f"a izvrsava ga '{actor_role.name}'."
            )

        on_reject = getattr(current, "on_reject", None)
        on_success = getattr(current, "on_success", None)
        next_node = getattr(current, "next", None)

        if _is_decision_point(current):
            if evaluation is None:
                # Racuna se JEDNOM za ceo workflow (uzima u obzir i opseg
                # iznosa/roka i eligibility pravila - oboje je vec deo
                # evaluate()) i deli se izmedju svih narednih tacaka odluke.
                evaluation = evaluate(product, application)
            output = evaluation
            passed = evaluation["decision"] == "ODOBREN"
        else:
            # Neutralan, prolazan korak (npr. cist "prijem") - nema
            # sopstvenu poslovnu logiku u DSL-u, samo audit trag.
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
